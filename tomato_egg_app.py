
# tomato_egg_app_goodV2_WITH_TRANSPORT_MAP.py
import math
import random
import requests
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation

st.set_page_config(page_title="一餐的碳足跡（完整版）", layout="centered")
st.title("🍽️ 一餐的碳足跡計算（主食＋料理＋飲料＋交通）")

# =========================
# Excel upload & read
# =========================
uploaded = st.file_uploader("請上傳 Excel（欄位：族群、產品名稱、碳足跡(kg)）", type=["xlsx"])
if uploaded is None:
    st.info("請先上傳 Excel 才能開始計算")
    st.stop()

df = pd.read_excel(uploaded)
df = df.iloc[:, :3]
df.columns = ["group", "name", "cf_kg"]

# =========================
# Group split
# =========================
g1 = df[df["group"] == 1]       # 主食
g11 = df[df["group"] == "1-1"]  # 油品
g12 = df[df["group"] == "1-2"]  # 水
g2 = df[df["group"] == 2]       # 飲料

# =========================
# Main dish selection
# =========================
st.subheader("🥗 主食選擇（5 選 2）")

if "main_pool" not in st.session_state:
    st.session_state.main_pool = g1.sample(min(5, len(g1)))

options = [
    f"{row['name']} ({row['cf_kg']} kgCO₂e)"
    for _, row in st.session_state.main_pool.iterrows()
]

chosen = st.multiselect("請選 2 種主食", options, max_selections=2)

main_total_cf = 0.0
main_weight = 0.0

for item in chosen:
    name = item.split(" (")[0]
    row = st.session_state.main_pool[st.session_state.main_pool["name"] == name].iloc[0]
    main_total_cf += row["cf_kg"]
    main_weight += 1.0  # 教學用：每份食材假設 1 kg

    method = st.radio(
        f"{name} 的料理方式",
        ["水煮", "油炸"],
        key=f"cook_{name}"
    )

    if method == "水煮" and not g12.empty:
        pick = g12.sample(1).iloc[0]
    elif method == "油炸" and not g11.empty:
        pick = g11.sample(1).iloc[0]
    else:
        pick = None

    if pick is not None:
        st.caption(f"料理耗材：{pick['name']}（{pick['cf_kg']} kgCO₂e）")
        main_total_cf += pick["cf_kg"]
        main_weight += 0.2  # 教學用：油或水 0.2 kg

# =========================
# Drink
# =========================
st.subheader("🥤 飲料")

drink_cf = 0.0
drink_weight = 0.0

if not g2.empty:
    drink_options = ["不喝飲料"] + [
        f"{row['name']} ({row['cf_kg']} kgCO₂e)"
        for _, row in g2.iterrows()
    ]
    drink_choice = st.selectbox("選擇飲料", drink_options)

    if drink_choice != "不喝飲料":
        name = drink_choice.split(" (")[0]
        row = g2[g2["name"] == name].iloc[0]
        drink_cf = row["cf_kg"]
        drink_weight = 0.5  # 教學用
else:
    st.info("Excel 中沒有飲料資料（group 2）")

# =========================
# Geolocation
# =========================
st.subheader("🗺️ 採買交通（全聯 PX Mart）")

geo = streamlit_geolocation()
if not geo or "latitude" not in geo:
    st.warning("無法取得定位")
    st.stop()

lat, lon = geo["latitude"], geo["longitude"]

# =========================
# Search PX Mart nearby
# =========================
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))

params = {
    "q": "全聯",
    "format": "json",
    "limit": 5,
    "lat": lat,
    "lon": lon
}
res = requests.get("https://nominatim.openstreetmap.org/search", params=params, headers={"User-Agent": "edu-app"})
stores = res.json() if res.ok else []

if not stores:
    st.warning("找不到附近全聯")
    st.stop()

m = folium.Map(location=[lat, lon], zoom_start=14)
folium.Marker([lat, lon], tooltip="你的位置", icon=folium.Icon(color="blue")).add_to(m)

store_names = []
for s in stores:
    folium.Marker([float(s["lat"]), float(s["lon"])], tooltip=s["display_name"]).add_to(m)
    store_names.append(s["display_name"])

out = st_folium(m, height=400, returned_objects=["last_clicked"])

target = None
if out and out.get("last_clicked"):
    target = out["last_clicked"]

# =========================
# Transport calculation
# =========================
if target:
    d = haversine(lat, lon, target["lat"], target["lng"])
    round_trip_km = d * 2
    st.write(f"📏 來回距離：約 {round_trip_km:.2f} km")

    total_weight_kg = main_weight + drink_weight
    total_weight_ton = total_weight_kg / 1000

    st.write(f"📦 食材總重量：約 {total_weight_kg:.2f} kg")

    mode = st.selectbox("交通方式", ["走路", "機車", "汽車", "貨車"])

    transport_cf = 0.0
    if mode == "機車":
        transport_cf = round_trip_km * 0.0951
    elif mode == "汽車":
        transport_cf = round_trip_km * 0.115
    elif mode == "貨車":
        transport_cf = round_trip_km * total_weight_ton * 2.71

    st.write(f"🚚 交通碳足跡：{transport_cf:.3f} kgCO₂e")

# =========================
# Total & download
# =========================
total_cf = main_total_cf + drink_cf + transport_cf
st.subheader(f"✅ 本餐總碳足跡：{total_cf:.3f} kgCO₂e")

result = pd.DataFrame([{
    "main_cf": main_total_cf,
    "drink_cf": drink_cf,
    "transport_cf": transport_cf,
    "total_cf": total_cf
}])

st.download_button(
    "⬇️ 下載結果 CSV",
    data=result.to_csv(index=False).encode("utf-8-sig"),
    file_name="carbon_meal_result.csv",
    mime="text/csv"
)
