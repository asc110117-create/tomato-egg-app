
# tomato_egg_app_FINAL_RESTORE_COOK_TRANSPORT.py
import math
import random
from io import BytesIO

import pandas as pd
import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation

st.set_page_config(page_title="碳足跡餐點計算", layout="centered")

# -----------------
# Constants
# -----------------
EF_WALK = 0.0
EF_MOTOR = 9.51E-2      # kgCO2e / pkm
EF_CAR = 1.15E-1        # kgCO2e / pkm
EF_TRUCK = 2.71         # kgCO2e / tkm

# -----------------
# Helpers
# -----------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def nominatim_nearby(query, lat, lon, limit=5):
    params = {
        "q": query,
        "format": "json",
        "limit": 20
    }
    r = requests.get("https://nominatim.openstreetmap.org/search", params=params, headers={"User-Agent": "edu-app"})
    data = r.json()
    stores = []
    for x in data:
        slat, slon = float(x["lat"]), float(x["lon"])
        d = haversine(lat, lon, slat, slon)
        stores.append({
            "name": x["display_name"].split(",")[0],
            "lat": slat,
            "lon": slon,
            "dist": d
        })
    stores = sorted(stores, key=lambda x: x["dist"])[:limit]
    return stores

# -----------------
# Load Excel
# -----------------
st.title("🍽 碳足跡餐點模擬")

uploaded = st.file_uploader("上傳《碳足跡4.xlsx》", type=["xlsx"])
if not uploaded:
    st.stop()

df = pd.read_excel(uploaded)
df.columns = ["group", "name", "cf_kg", "weight_g"]
df["weight_kg"] = df["weight_g"] / 1000

# Group split
food = df[df["group"] == 1]
oil = df[df["group"] == "1-1"]
water = df[df["group"] == "1-2"]
drink = df[df["group"] == 2]

# -----------------
# Main dish logic (UNCHANGED)
# -----------------
st.subheader("🥗 主食（從 5 選 2）")
sample5 = food.sample(min(5, len(food)))
choices = st.multiselect(
    "選擇兩樣主食",
    options=sample5["name"].tolist(),
    max_selections=2
)

cook_cf = 0
total_weight = 0

for name in choices:
    row = sample5[sample5["name"] == name].iloc[0]
    total_weight += row["weight_kg"]
    method = st.radio(f"{name} 的料理方式", ["水煮", "油炸"], key=name)
    if method == "水煮":
        pick = water.sample(1).iloc[0]
    else:
        pick = oil.sample(1).iloc[0]
    cook_cf += pick["cf_kg"]
    total_weight += pick["weight_kg"]
    st.caption(f"→ 使用 {pick['name']}（{pick['cf_kg']} kgCO₂e）")

# Drink
st.subheader("🥤 飲料")
if not drink.empty:
    drow = drink.sample(1).iloc[0]
    st.write(f"{drow['name']}（{drow['cf_kg']} kgCO₂e）")
    cook_cf += drow["cf_kg"]
    total_weight += drow["weight_kg"]

# -----------------
# Transport
# -----------------
st.subheader("🚶‍♂️ 交通方式（自動抓定位）")
geo = streamlit_geolocation()
if not geo or not geo.get("latitude"):
    st.warning("尚未取得定位")
    st.stop()

lat, lon = geo["latitude"], geo["longitude"]
stores = nominatim_nearby("全聯", lat, lon)

store_names = [f"{s['name']}（{s['dist']:.2f} km）" for s in stores]
idx = st.radio("選擇最近的全聯分店", range(len(store_names)), format_func=lambda i: store_names[i])
chosen = stores[idx]

round_km = chosen["dist"] * 2
st.write(f"來回距離：{round_km:.2f} km")

mode = st.selectbox("交通工具", ["走路", "機車", "汽車", "貨車"])

if mode == "走路":
    transport_cf = 0
elif mode == "機車":
    transport_cf = round_km * EF_MOTOR
elif mode == "汽車":
    transport_cf = round_km * EF_CAR
else:
    transport_cf = round_km * (total_weight/1000) * EF_TRUCK

# -----------------
# Result
# -----------------
st.subheader("📊 結果")
st.write(f"食材總重量：{total_weight:.3f} kg")
st.write(f"料理＋飲料碳足跡：{cook_cf:.3f} kgCO₂e")
st.write(f"交通碳足跡：{transport_cf:.3f} kgCO₂e")
st.success(f"總碳足跡：{cook_cf + transport_cf:.3f} kgCO₂e")
