import streamlit as st
import pandas as pd
import requests, base64, io, os
from pyzbar.pyzbar import decode
from PIL import Image
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient

st.set_page_config(page_title="FoodGenie", page_icon="🥑", layout="wide")
# Use a container to hold the title box styling
with st.container(border=True): # The border=True adds a native Streamlit border
    st.markdown(
        """
        <h1 style='text-align: center; color: #4CAF50; font-weight: 800; padding: 10px;'>
            🥗 FoodGenie: A Smart Nutrition Assistant
        </h1>
        """,
        unsafe_allow_html=True
    )
    # Optional: Add a tagline below the main title
    st.markdown(
        """
        <p style='text-align: center; font-size: 1.1em; color: #555555; padding-bottom: 5px;'>
        Upload a food label or barcode image to get detailed nutrition insights!
        </p>
        """,
        unsafe_allow_html=True
    )

# Use a divider to separate the header from the main content
st.divider()

load_dotenv(override=True)
url = os.getenv("API_URL")
client = MongoClient(os.getenv("MONGO_URI"))
collection = client[os.getenv("MONGO_DB")][os.getenv("MONGO_COLLECTION")]

# --- Persistent Variables ---
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0
if "user_input_key" not in st.session_state:
    st.session_state.user_input_key = "demo_user"

tab1, tab2 = st.tabs(["Upload & Analyze", "Past Results"])

# Helper to extract barcode
def extract_barcode(file_bytes):
    img = Image.open(io.BytesIO(file_bytes))
    results = decode(img)
    for res in results:
        if res.type in ["EAN13", "EAN8", "UPCA", "UPCE"]:
            return res.data.decode("utf-8")
    return ""

def get_nutrient_status(value, low, high):
    """Calculates status, color, and a delta value based on thresholds."""
    if value > high:
        status = "High"
        color = "off"
        delta_val = f"+{value - high}"
    elif value > low:
        status = "Moderate"
        color = "off"
        delta_val = f"+{value - low}"
    else:
        status = "Low"
        color = "normal"
        delta_val = "✅ Good"

    return status, color, delta_val

# Helper to display a product summary
def display_summary(result):
    # --- Product Info ---
    st.subheader(f"📦 Product: {result.get('product_name', 'Unknown')}")

    if "image_url" in result:
        with st.expander("Product Image"):
            st.image(result["image_url"], width=200)

    st.divider()

    with st.expander("⚡ Quick Health Summary", expanded=True):
        # Extract key nutrient values safely
        facts = result.get("facts", {})
        fat = facts.get("fat_value", 0)
        sodium = facts.get("sodium_value", 0)
        cholesterol = facts.get("cholesterol_value", 0)

        # Define healthy ranges (example thresholds)
        thresholds = {
            "fat": {"low": 5, "high": 15},
            "sodium": {"low": 150, "high": 400},
            "cholesterol": {"low": 20, "high": 60}
        }

        # --- Display indicators using st.metric in columns ---
        col1, col2, col3 = st.columns(3)

        # FAT Metric
        fat_status, fat_color, fat_delta = get_nutrient_status(fat, **thresholds["fat"])
        with col1:
            st.metric(
                label=f"Fat ({fat_status} Risk)",
                value=f"{int(fat)}g",
                delta=fat_delta,
                delta_color=fat_color,
                help="Total Fat per serving. High fat foods are > 15g/serving."
            )

        # SODIUM Metric
        sodium_status, sodium_color, sodium_delta = get_nutrient_status(sodium, **thresholds["sodium"])
        with col2:
            st.metric(
                label=f"Sodium ({sodium_status} Risk)",
                value=f"{int(sodium)}mg",
                delta=sodium_delta,
                delta_color=sodium_color,
                help="Sodium per serving. High sodium foods are > 400mg/serving."
            )

        # CHOLESTEROL Metric
        cholesterol_status, cholesterol_color, cholesterol_delta = get_nutrient_status(cholesterol, **thresholds["cholesterol"])
        with col3:
            st.metric(
                label=f"Cholesterol ({cholesterol_status} Risk)",
                value=f"{int(cholesterol)}mg",
                delta=cholesterol_delta,
                delta_color=cholesterol_color,
                help="Cholesterol per serving. High cholesterol foods are > 60mg/serving."
            )

    st.divider()

    # --- AI Insights ---
    with st.expander("💬 Insights from FoodGenie", expanded=True):
        ai_response = result.get("response", "No insights available.")
        st.markdown(ai_response)

    st.divider()

    # --- Nutrition Facts ---
    with st.expander("🧾 Nutrition Facts"):
        facts = result.get("facts", {})
        if facts:
            # Get nutrition facts
            display_keys = {
                "energy-kcal_value": "Calories",
                "fat_value": "Total Fat (g)",
                "saturated-fat_value": "Saturated Fat (g)",
                "trans-fat_value": "Trans Fat (g)",
                "cholesterol_value": "Cholesterol (mg)",
                "sodium_value": "Sodium (mg)",
                "carbohydrates_value": "Total Carbs (g)",
                "sugars_value": "Sugars (g)",
                "fiber_value": "Fiber (g)",
                "proteins_value": "Protein (g)",
            }

            # Convert numeric values to int to remove decimals
            trimmed = {}
            for key, label in display_keys.items():
                val = facts.get(key, "N/A")
                if isinstance(val, (float, int)):
                    val = int(val)
                trimmed[label] = val

            # Filter and reformat into a DataFrame
            df = pd.DataFrame(list(trimmed.items()), columns=["Nutrient", "Per Serving"])
            df['Per Serving'] = df['Per Serving'].astype(str)
            st.dataframe(
                df,
                hide_index=True,
                width='stretch'
            )
        else:
            st.info("No nutrition facts found.")

def submit_photo(img, status_container):
    with st.spinner("Analyzing your image...please wait ⏳"):
        file_bytes = img.read()
        barcode = extract_barcode(file_bytes)
        status_container.info(f"🔍 Barcode found: {barcode}" if barcode else "No barcode found (using OCR only).")
        binary_file = base64.b64encode(file_bytes).decode('utf-8')
        payload = {
            "user": st.session_state.user_input_key,
            "filename": img.name,
            "image": binary_file,
            "barcode": barcode,
            "user_context": {
                # Health Profile
                "weight_lbs": st.session_state.pref_weight,
                "height_in": st.session_state.pref_height,
                "activity_level": st.session_state.pref_activity,
                # Constraints
                "allergies": st.session_state.pref_allergies,
                "chronic_conditions": st.session_state.pref_conditions,
                "dietary_preference": st.session_state.pref_diet,
                # Goals
                "calorie_goal": st.session_state.pref_calorie_goal,
                "macro_targets": {
                    "protein_pct": st.session_state.pref_protein_pct,
                    "carbs_pct": st.session_state.pref_carbs_pct,
                    "fats_pct": st.session_state.pref_fats_pct,
                }
            }
        }

        response = requests.post(url, json=payload)

    if response.status_code == 200:
        st.session_state.result = response.json()
        st.session_state.uploader_key += 1
        # --- Save to MongoDB ---
        if st.session_state.result.get('product_name') or st.session_state.result.get('facts'):
            record = {
                "user": st.session_state.user_input_key,
                "filename": img.name,
                "timestamp": datetime.now(),
                "result": st.session_state.result,
            }
            collection.insert_one(record)
            status_container.success("✅ Analysis complete! Result saved to history.")
        else:
            status_container.warning("⚠️ Analysis complete, but no valid nutrition data was found for this image.")
    else:
        status_container.error(f"❌ Upload failed: {response.text}")

# --- User Identity Section ---
st.sidebar.header("👤 User Identity")
user_input = st.sidebar.text_input("Username", key="user_input_key")

st.sidebar.markdown(f"Currently logged in as: **{st.session_state.user_input_key}**")

# --- Health Profile ---
st.sidebar.header("User Preferences")
with st.sidebar.expander("️❤️ Health Profile", expanded=True):
    st.number_input("Weight (lbs)", min_value=1, value=100, key="pref_weight")
    st.number_input("Height (in)", min_value=1, value=60, key="pref_height")
    st.radio("Activity Level",
                     ('Sedentary', 'Lightly Active', 'Moderately Active', 'Very Active'),
                     key="pref_activity")

# --- Preferences & Constraints ---
with st.sidebar.expander("⚠️ Preferences & Constraints", expanded=True):
    st.multiselect("Allergies",
                           ("Gluten", "Dairy", "Nuts", "Soy", "Shellfish", "Corn"),
                           key="pref_allergies")
    st.multiselect("Chronic Conditions",
                           ("Diabetes", "High Blood Pressure", "High Blood Sugar", "Obesity"),
                           key="pref_conditions")
    st.selectbox("Dietary Preferences",
                         ("Keto", "Vegan", "Low Sodium", "High Protein", "Low Carb", "Low Calorie"),
                         index=2,
                         key="pref_diet")

# --- Goals ---
with st.sidebar.expander("🎯 Daily Goals", expanded=True):
    st.slider("Daily Calorie Goal", 1600, 2600, value=2000, key="pref_calorie_goal")
    st.slider("Protein (%)", 10, 50, value=30, key="pref_protein_pct")
    st.slider("Carbs (%)", 20, 70, value=40, key="pref_carbs_pct")
    st.slider("Fats (%)", 10, 60, value=30, key="pref_fats_pct")

with tab1:
    # Show uploader
    status = st.empty()
    st.subheader("📸 Step 1: Upload a Product Label")
    file = st.file_uploader(
        "Upload a clear image of a barcode or nutrition facts label",
        key=st.session_state.uploader_key
    )
    if file is not None:
        st.subheader("✨ Step 2: Review & Analyze")
        st.image(file, caption=f"Previewing {file.name}", width=250)
        submit_photo(file, status)
        st.header(f"✨ Analysis Complete:")
        display_summary(st.session_state.result)

with tab2:
    st.header("📜 Search History")
    user = st.session_state.user_input_key
    results = list(collection.find({"user": user}).sort("timestamp", -1).limit(10))
    if results:
        for entry in results:
            with st.expander(f"📦 {entry['result'].get('product_name', 'Unknown Product')} — {entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}"):
                display_summary(entry["result"])
    else:
        st.info("Nothing in your history! Upload an item to get started 🙂.")
