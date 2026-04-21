import streamlit as st
import sqlite3
import requests
from groq import Groq
import json


# CONFIGURATION
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

def get_client():
    return Groq(api_key=os.getenv("GROQ_API_KEY"))


# DATABASE SETUP
conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password TEXT,
    age INTEGER,
    condition TEXT,
    allergy TEXT
)
""")
conn.commit()



# AUTHORIZATION FUNCTIONS
def register_user(username, password, age, condition, allergy):
    try:
        c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                  (username, password, age, condition, allergy))
        conn.commit()
        return True
    except:
        return False

def login_user(username, password):
    c.execute("SELECT * FROM users WHERE username=? AND password=?",
              (username, password))
    return c.fetchone()


# PRODUCTS DATABASE
conn_products = sqlite3.connect("products.db", check_same_thread=False)
cp = conn_products.cursor()

cp.execute("""
    CREATE TABLE IF NOT EXISTS products (
    barcode TEXT PRIMARY KEY,
    product_json TEXT
    )
    """)
conn_products.commit()


# FETCH PRODUCT FROM PRODUCTS DATABASE
def get_product_from_db(barcode):
    cp.execute("SELECT product_json FROM products WHERE barcode=?", (barcode,))
    row = cp.fetchone()

    if row:
        return json.loads(row[0])
    
    return None


# SAVE PRODUCT TO PRODUCTS DATABASE
def save_product_to_db(barcode, product):
    cp.execute(
        "INSERT OR REPLACE INTO products VALUES (?, ?)",
        (barcode, json.dumps(product))
    )
    conn_products.commit()


# BARCODE FORMAT
def format_barcode(barcode):
    barcode = ''.join(filter(str.isdigit, str(barcode)))
    if len(barcode) not in [8, 12, 13]:
        raise ValueError("Invalid barcode")
    return barcode


# FETCH PRODUCT FROM API
def fetch_product(barcode):
    try:
        formatted_barcode = format_barcode(barcode)

        url = f"https://world.openfoodfacts.org/api/v0/product/{formatted_barcode}.json"

        headers = {
            "User-Agent": "Nutriscanapp/1.0 (shailvisdlsingh@gmail.com)"

        }

        response = requests.get(url, headers=headers, timeout=10)

        # DEBUG
        print("Status Code:", response.status_code)

        if response.status_code != 200:
            return {"error": f" API request failed (Status {response.status_code})"}

        data = response.json()

        if data.get("status") != 1:
            return {"error": " Product not found in Open Food Facts"}

        return data["product"]

    except requests.exceptions.Timeout:
        return {"error": " Request timed out. Check internet."}

    except requests.exceptions.ConnectionError:
        return {"error": "No internet connection."}

    except Exception as e:
        return {"error": str(e)}


# EXTRACT INFORMATION ABOUT PRODUCT
def extract(product):
    nutriments = product.get("nutriments", {})

    return {
        "Product Name": product.get("product_name", "N/A"),
        "Brand": product.get("brands", "N/A"),
        "Ingredients": product.get("ingredients_text", "N/A"),
        "Serving size": product.get("serving_size", "N/A"),
        
        "Nutrient Levels": "\n".join(
            [f"{k}: {v}" for k, v in product.get("nutrient_levels", {}).items()]
        ) if product.get("nutrient_levels") else "N/A",

        "Allergens": product.get("allergens", "N/A"),
        "Additives": product.get("additives", "N/A"),

        "Energy (kcal)": nutriments.get("energy-kcal_100g", "N/A"),
        "Protein (g)": nutriments.get("proteins_100g", "N/A"),
        "Fat (g)": nutriments.get("fat_100g", "N/A"),
        "Sugar (g)": nutriments.get("sugars_100g", "N/A"),
        "Salt (g)": nutriments.get("salt_100g", "N/A"),
    }
# FSSAI
LIMITS_FOR_DIFFERENT_AGE_GROUP = {
    "Children": {
        "energy_kcal": 1600,
        "salt_g": 5
    },
    "Adolescents": {
        "energy_kcal": 2000,
        "salt_g": 6
    },
    "Adults": {
        "energy_kcal": 2000,
        "salt_g": 5
    }
    }
# Nutri Score Based on FASSI
def get_risk_level(value, rda):
    percent = (value / rda) * 100

    if percent <= 10:
        return 0, "Safe "
    elif percent <= 25:
        return 1, "Low "
    elif percent <= 50:
        return 2, "Moderate "
    elif percent <= 75:
        return 3, "High "
    else:
        return 4, "Very High "


def calculate_risk(data):
    total_score = 0
    warnings = []

    # Energy
    score, level = get_risk_level(data["energy"], 2000)
    total_score += score

    # Fat
    score, level = get_risk_level(data["fat"], 67)
    total_score += score
    warnings.append(f"Fat: {level}")

    # Saturated Fat
    score, level = get_risk_level(data["sat_fat"], 22)
    total_score += score
    warnings.append(f"Saturated Fat: {level}")

    # Sugar
    score, level = get_risk_level(data["sugar"], 50)
    total_score += score
    warnings.append(f"Sugar: {level}")

    # Sodium
    score, level = get_risk_level(data["sodium"], 2000)
    total_score += score
    warnings.append(f"Sodium: {level}")

    return total_score, warnings


def get_final_status(score):
    if score <= 3:
        return "Healthy "
    elif score <= 7:
        return "Moderate "
    elif score <= 12:
        return "Low Nutrition Value "
    else:
        return "Very Low Nutrition Value "
    


# AI ANALYSIS
def analyze(product, user):
    client = get_client()

    prompt = f"""
    You are a nutrition expert.

    Product Data:
    {product}

    User Profile:
    {user}

    FSSAI Limits:
    {LIMITS_FOR_DIFFERENT_AGE_GROUP}

    Tasks:
    
    1. Check if sugar, fat, salt exceed FSSAI limits
    2. Explain health risks
    3. Personalize based on user condition
    4. Suggest healthier alternatives
    5. Give answer in simple readable text

    """

    res = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )

    return res.choices[0].message.content


# CHATBOT
def ask_bot(q, product, user):
    client = get_client()

    prompt = f"""
    You are a smart food assistant.

    Product Info:
    {product}

    User:
    {user}

    Question:
    {q}

    Answer clearly.Be factual. If unsure, say "Not available in product data".
    """

    res = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )

    return res.choices[0].message.content


# STREAMLIT UI

# SESSION STATE
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "page" not in st.session_state:
    st.session_state.page = "scanner"


#DAILY RECORD INITIALIZATION
if "daily" not in st.session_state:
    st.session_state.daily = {
        "energy": 0,
        "fat": 0,
        "sat_fat": 0,
        "trans_fat": 0,
        "sugar": 0,
        "sodium": 0
    }


# DAILY LIMIT CHECK FUNCTION
def check_limits(d):
    warnings = []

    if d["energy"] > 2000:
        warnings.append(" Energy exceeded (2000 kcal)")
    if d["fat"] > 67:
        warnings.append(" Fat exceeded (67 g)")
    if d["sat_fat"] > 22:
        warnings.append(" Saturated Fat exceeded (22 g)")
    if d["trans_fat"] > 2:
        warnings.append(" Trans Fat exceeded (2 g)")
    if d["sugar"] > 50:
        warnings.append(" Sugar exceeded (50 g)")
    if d["sodium"] > 2000:
        warnings.append(" Sodium exceeded (2000 mg / 5g salt)")

    return warnings


# REGISTER / LOGIN
if not st.session_state.logged_in:

    menu = ["Login", "Register"]
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "Register":
        st.subheader("Create Account")

        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        age = st.number_input("Age", 1, 100)

        condition_options = ["None", "Diabetes", "Blood Pressure", "Heart Condition", "Others"]
        selected_condition = st.selectbox("Select Health Condition", condition_options)

        custom_condition = ""
        if selected_condition == "Others":
            custom_condition = st.text_input("Enter your condition")

        condition = custom_condition if selected_condition == "Others" else selected_condition
        allergy = st.text_input("Allergy")

        if st.button("Register"):
            if register_user(user, pwd, age, condition, allergy):
                st.success("Account created!")
            else:
                st.error("User exists")

    elif choice == "Login":
        st.subheader("Login")

        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")

        if st.button("Login"):
            data = login_user(user, pwd)

            if data:
                st.session_state.logged_in = True
                st.session_state.user = {
                    "age": data[2],
                    "condition": data[3],
                    "allergy": data[4]
                }
                st.success("Logged in")
                st.rerun()
            else:
                st.error("Invalid credentials")


# MAIN PAGE
else:
    # SIDEBAR DAILY RECORD
    st.sidebar.subheader(" Daily Consumption")
    st.sidebar.json(st.session_state.daily)

    warnings = check_limits(st.session_state.daily)
    if warnings:
        st.sidebar.error(" Limits exceeded")

    # SCANNER PAGE
    if st.session_state.page == "scanner":

        st.title(" Packaged Food Label Analyzer")

        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()

        barcode = st.text_input("Enter Barcode")

        if st.button("Scan"):
            if not barcode:
                st.warning("Enter barcode first")
            else:
                with st.spinner("Fetching product..."):
                    # 1. Check database first
                    product = get_product_from_db(barcode)

                    if product:
                        st.success("Loaded from database (fast)")
                    else:
                    # 2. Fetch from API
                        product = fetch_product(barcode)

                        if "error" in product:
                            st.error(product["error"])
                            st.stop()
    
                        # 3. Save to database
                        save_product_to_db(barcode, product)
                        st.success("Fetched from API & saved")

                    #if "error" in product:
                    #    st.error(product["error"])
                    #else:
                    info = extract(product)

                    # STORE PRODUCT + NUTRIENTS
                    st.session_state.product = info

                    st.session_state.last_n = {
                            "energy": float(product.get("nutriments", {}).get("energy-kcal_100g", 0)),
                            "fat": float(product.get("nutriments", {}).get("fat_100g", 0)),
                            "sat_fat": float(product.get("nutriments", {}).get("saturated-fat_100g", 0)),
                            "trans_fat": float(product.get("nutriments", {}).get("trans-fat_100g", 0)),
                            "sugar": float(product.get("nutriments", {}).get("sugars_100g", 0)),
                            "sodium": float(product.get("nutriments", {}).get("sodium_100g", 0)) * 1000
                        }

                    st.success("Product Found")
                    st.json(info)

                    try:
                        risk_data = {
                                "energy": float(info.get("Energy (kcal)", 0)),
                                "fat": float(info.get("Fat (g)", 0)),
                                "sat_fat": float(product.get("nutriments", {}).get("saturated-fat_100g", 0)),
                                "sugar": float(info.get("Sugar (g)", 0)),
                                "sodium": float(product.get("nutriments", {}).get("sodium_100g", 0)) * 1000
                            }

                        score, warnings = calculate_risk(risk_data)
                        status = get_final_status(score)

                        st.subheader(" FSSAI Nutrition Analysis")
                        st.error(f"Nutri Score: {score}")
                        st.warning(f"Status: {status}")

                        st.subheader("Warnings:")
                        for w in warnings:
                            st.write(f"- {w}")

                        # AI ANALYSIS
                        st.subheader(" AI Health Analysis")

                        with st.spinner("Analyzing with AI..."):
                            try:
                                ai_result = analyze(
                                    st.session_state.product,
                                    st.session_state.user
                                )
                                st.write(ai_result)
                            except Exception as e:
                                st.error(f"AI analysis failed: {e}")

                    except Exception as e:
                        st.warning(f"Risk analysis not available: {e}")

        
        # ADD TO DAILY BUTTON
        if "last_n" in st.session_state:

            if st.button("Add to Daily Record"):

                n = st.session_state.last_n

                for k in st.session_state.daily:
                    st.session_state.daily[k] += n[k]

                st.success("Added to daily record")

                warnings = check_limits(st.session_state.daily)

                if warnings:
                    st.error(" You have exceeded daily limits!")
                    for w in warnings:
                        st.write(w)
                else:
                    st.success(" Within daily limits")

        # CHATBOT BUTTON
        if "product" in st.session_state:
            if st.button("For more queries, Ask Chatbot"):
                st.session_state.page = "chatbot"
                st.rerun()

    # CHATBOT PAGE
    elif st.session_state.page == "chatbot":

        st.title(" Chat with AI")

        if st.button(" Back to Scanner"):
            st.session_state.page = "scanner"
            st.rerun()

        if "product" in st.session_state:
            question = st.text_input("Ask something")

            if st.button("Ask"):
                answer = ask_bot(
                    question,
                    st.session_state.product,
                    st.session_state.user
                )
                st.write(answer)
        else:
            st.warning("Scan a product first")