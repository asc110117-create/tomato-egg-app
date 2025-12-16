import pandas as pd
import streamlit as st
import random
import folium
from streamlit_folium import st_folium
from io import BytesIO
import math
import csv
import io

# =========================
# Functions
# =========================

def load_data_from_excel(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_excel(BytesIO(file_bytes), engine="openpyxl")
    df.columns = ["code", "product_name", "carbon_footprint"]
    df["carbon_footprint"] = pd.to_numeric(df["carbon_footprint"], errors='coerce').fillna(0.0)
    return df

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))

# =========================
# Streamlit Setup
# =========================

st.set_page_config(page_title="碳足跡計算", page_icon="🌍")

st.title("一餐的碳足跡大冒險：從農場到你的胃")
st.write("計算您的碳足跡！")

# File uploader for the Excel file with the data
uploaded_file = st.file_uploader("請上傳碳足跡的 Excel 檔案", type="xlsx")
if uploaded_file:
    df = load_data_from_excel(uploaded_file)
    st.write("數據已成功加載：")
    st.dataframe(df)

# Select dishes
selected_dishes = st.multiselect("選擇食材", options=df["product_name"].tolist())
if selected_dishes:
    st.write(f"您選擇了 {len(selected_dishes)} 種食材。")
else:
    st.warning("請選擇至少一種食材。")

# Cooking method selection
cooking_method = st.radio("選擇烹飪方式", ("水煮", "油炸"))

# =========================
# Carbon Footprint Calculation
# =========================

def calculate_carbon_footprint(dish, cooking_method):
    selected_dish = df[df["product_name"] == dish].iloc[0]
    footprint = selected_dish["carbon_footprint"]
    
    # Adjust for cooking method
    if cooking_method == "油炸":
        footprint *= 1.2  # Assuming oil increases the carbon footprint by 20%
    
    return footprint


# Calculate total carbon footprint for selected dishes
total_carbon_footprint = 0.0
for dish in selected_dishes:
    total_carbon_footprint += calculate_carbon_footprint(dish, cooking_method)

st.write(f"總碳足跡：{total_carbon_footprint:.2f} kg CO₂e")

# =========================
# Transport Selection
# =========================

transport_mode = st.selectbox("選擇交通方式", ("走路", "機車", "汽車", "貨車"))

# Default distance between store and user (example: 5 km)
distance = 5.0
if transport_mode == "走路":
    carbon_footprint = 0
elif transport_mode == "機車":
    carbon_footprint = distance * 0.0951  # Example value for motorcycle
elif transport_mode == "汽車":
    carbon_footprint = distance * 0.115  # Example value for car
else:
    carbon_footprint = distance * 2.71  # Example value for truck (per ton-km)

st.write(f"交通碳足跡：{carbon_footprint:.2f} kg CO₂e")

# =========================
# Map Display (for selecting store)
# =========================

# Location input for user (e.g., from geolocation)
user_lat, user_lon = 24.1477, 120.6736  # Example: Taichung, Taiwan

# Show the map with nearby stores
m = folium.Map(location=[user_lat, user_lon], zoom_start=12)
folium.Marker([user_lat, user_lon], popup="您現在的位置", icon=folium.Icon(color="blue")).add_to(m)

# Example: nearby store (nearby stores logic can be improved with real data)
stores = [{"name": "全聯中華路店", "lat": 24.1467, "lon": 120.6730}, {"name": "全聯大雅店", "lat": 24.1580, "lon": 120.6535}]
for store in stores:
    folium.Marker([store["lat"], store["lon"]], popup=store["name"], icon=folium.Icon(color="orange")).add_to(m)

st_folium(m, width=700, height=500)

# =========================
# Download Results
# =========================

results = {
    "selected_dishes": selected_dishes,
    "cooking_method": cooking_method,
    "total_carbon_footprint": total_carbon_footprint,
    "transport_mode": transport_mode,
    "transport_carbon_footprint": carbon_footprint
}

# Prepare the data to download
import io
import csv

def convert_df_to_csv(results):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=results.keys())
    writer.writeheader()
    writer.writerow(results)
    return output.getvalue()

csv_data = convert_df_to_csv(results)
st.download_button(
    label="下載碳足跡結果 (CSV)",
    data=csv_data,
    file_name="carbon_footprint_results.csv",
    mime="text/csv"
)

