
import streamlit as st
import pandas as pd
import random
import math
import folium
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation

st.set_page_config(page_title="一餐的碳足跡大冒險", layout="centered")

st.title("🍽️ 一餐的碳足跡大冒險（穩定版）")

# ========================
# 基本常數與係數
# ========================
DEFAULT_LAT = 24.1477   # 台中
DEFAULT_LON = 120.6736

EF_MOTOR = 9.51e-2     # kgCO2e / pkm
EF_CAR   = 1.15e-1     # kgCO2e / pkm
EF_TRUCK = 2.71        # kgCO2e / tkm

# ========================
# 工具函式
# ========================
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

# ========================
# 使用者資訊
# ========================
name = st.text_input("請輸入姓名")
if not name:
    st.stop()

st.success(f"你好 {name}，請繼續選擇餐點")

# ========================
# 假資料（示範用，不會是空）
# ========================
data = [
    {"group": "1", "name": "雞腿便當", "cf": 2.0, "weight": 0.6},
    {"group": "1", "name": "豬排便當", "cf": 3.0, "weight": 0.7},
    {"group": "1", "name": "蔬食便當", "cf": 1.2, "weight": 0.5},
    {"group": "1", "name": "牛肉便當", "cf": 4.5, "weight": 0.8},
    {"group": "1", "name": "魚排便當", "cf": 2.8, "weight": 0.6},
]
df = pd.DataFrame(data)

# ========================
# 主食（5 選 2）
# ========================
st.header("🍚 主食（隨機 5 選 2）")

options = [f"{r['name']} ({r['cf']} kgCO₂e)" for _, r in df.iterrows()]
choice = st.multiselect("請選 2 種主食", options, max_selections=2)

if len(choice) < 2:
    st.stop()

selected = df[df["name"].isin([c.split(" (")[0] for c in choice])]

st.write("### 你選擇的食材")
st.dataframe(selected[["name", "cf", "weight"]])

total_weight = selected["weight"].sum()
st.info(f"食材總重量：{total_weight:.2f} kg")

# ========================
# 料理方式
# ========================
st.header("🍳 料理方式")
cook_cf = 0.0
for _, r in selected.iterrows():
    method = st.radio(
        f"{r['name']} 的料理方式",
        ["水煮", "油炸"],
        key=r['name']
    )
    if method == "水煮":
        cook_cf += 0.02
    else:
        cook_cf += 0.05

# ========================
# 定位與地圖
# ========================
st.header("🗺️ 採買交通（全聯 PX Mart）")

geo = streamlit_geolocation()
lat = geo.get("latitude") if geo else None
lon = geo.get("longitude") if geo else None

if lat is None or lon is None:
    lat, lon = DEFAULT_LAT, DEFAULT_LON
    st.warning("未取得定位，已使用預設位置（台中）")

stores = [
    {"name": "全聯A", "lat": lat+0.01, "lon": lon+0.01},
    {"name": "全聯B", "lat": lat+0.02, "lon": lon-0.01},
    {"name": "全聯C", "lat": lat-0.01, "lon": lon+0.02},
    {"name": "全聯D", "lat": lat-0.015, "lon": lon-0.015},
    {"name": "全聯E", "lat": lat+0.005, "lon": lon-0.02},
]

for s in stores:
    s["dist"] = haversine(lat, lon, s["lat"], s["lon"])

stores = sorted(stores, key=lambda x: x["dist"])[:5]

store_names = [f"{s['name']}（{s['dist']*2:.2f} km 來回）" for s in stores]
store_choice = st.selectbox("選擇分店", store_names)

idx = store_names.index(store_choice)
distance_km = stores[idx]["dist"] * 2

m = folium.Map(location=[lat, lon], zoom_start=14)
for s in stores:
    folium.Marker([s["lat"], s["lon"]], popup=s["name"]).add_to(m)
st_folium(m, height=300)

# ========================
# 交通方式
# ========================
st.header("🚶🚗 交通方式")
mode = st.radio("選擇交通方式", ["走路", "機車", "汽車", "貨車"])

if mode == "走路":
    transport_cf = 0.0
elif mode == "機車":
    transport_cf = distance_km * EF_MOTOR
elif mode == "汽車":
    transport_cf = distance_km * EF_CAR
else:
    transport_cf = distance_km * total_weight * EF_TRUCK

# ========================
# 結果
# ========================
total_cf = selected["cf"].sum() + cook_cf + transport_cf

st.success(f"本餐總碳足跡：{total_cf:.2f} kgCO₂e")
