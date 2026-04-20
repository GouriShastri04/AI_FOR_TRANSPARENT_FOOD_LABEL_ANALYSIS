### **AI POWERED PACKAGED FOOD LABEL ANALYZER**
This is an intelligent web application that analyzes food labels using **Llama-3.1-8b-instant** (via **Groq**) to provide personalized health insights. By scanning a product barcode number, users receive a detailed breakdown of nutritional risks based on **FSSAI** standards and their own medical profile.

#### **Features**
* **Barcode Integration:** Fetches real-time data from the **Open Food Facts API**.
* **FSSAI Nutrition Engine:** Mathematically calculates nutritional safety scores for sugar, salt, and fats.
* **Personalized GenAI Analysis:** Cross-references product ingredients with user conditions (e.g., Diabetes, Hypertension) to provide tailored advice.
* **Daily Tracking:** Monitors cumulative intake to warn users when they exceed daily healthy limits.
* **Smart Chatbot:** An interactive assistant for follow-up questions about food products.

#### **Tech Stack**
* **Frontend:** Streamlit
* **LLM:** Llama-3.1-8b-instant (Groq Cloud)
* **Database:** SQLite3
* **Data Source:** Open Food Facts API
