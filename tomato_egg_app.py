
# tomato_egg_app_full_integrated.py
# 一餐的碳足跡大冒險（完整版｜含主食、水煮/油炸、飲料、甜點、交通地圖、重量、Google Sheet、CSV）

import streamlit as st
import pandas as pd
import math
import requests
from datetime import datetime
from io import BytesIO
import folium
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation

# =======================
# 基本設定
# =======================
st.set_page_config(page_title="一餐的碳足跡大冒險", page_icon="🍽️", layout="centered")

st.title("🍽️ 一餐的碳足跡大冒險")

# =======================
# 交通係數（老師指定，不可改）
# =======================
TRANSPORT_FACTORS = {
    "機車": {
        "factor": 9.51e-2,
        "unit": "kgCO₂e / 人公里 (pkm)",
        "type": "pkm",
    },
    "自用小客車（汽油）": {
        "factor": 1.15e-1,
        "unit": "kgCO₂e / 人公里 (pkm)",
        "type": "pkm",
    },
    "3.49噸低溫貨車": {
        "factor": 2.71,
        "unit": "kgCO₂e / 噸公里 (tkm)",
        "type": "tkm",
    },
}

# =======================
# Excel 讀取（碳足跡4.xlsx）
# 欄位：族群、產品名稱、碳足跡(kg)、重量(kg)
# =======================
@st.cache_data
def load_excel(bytes_data):
    df = pd.read_excel(BytesIO(bytes_data))
    df = df.rename(columns={
        "族群": "group",
        "產品名稱": "name",
        "碳足跡(kg)": "cf_kg",
        "重量(kg)": "weight_kg",
    })
    df["cf_kg"] = df["cf_kg"].astype(float)
    df["weight_kg"] = df["weight_kg"].fillna(0.0)
    return df

uploaded = st.file_uploader("請上傳《碳足跡4.xlsx》", type=["xlsx"])
if uploaded is None:
    st.stop()

df = load_excel(uploaded.getvalue())

# 分群
df_food = df[df["group"] == 1]      # 主食
df_oil = df[df["group"] == "1-1"]   # 油
df_water = df[df["group"] == "1-2"] # 水
df_drink = df[df["group"] == 2]     # 飲料
df_dessert = df[df["group"] == 3]   # 甜點

# =======================
# 使用者資訊
# =======================
student = st.text_input("請輸入姓名")
if not student:
    st.stop()

if "round" not in st.session_state:
    st.session_state.round = 1

st.info(f"📘 這是你第 {st.session_state.round} 次測試")

# =======================
# 主食（隨機 5 選 2）
# =======================
st.header("🍚 主食（請選 2 種）")

food_pool = df_food.sample(n=min(5, len(df_food)), random_state=st.session_state.round)
food_options = {
    f"{r['name']} ({r['cf_kg']} kgCO₂e)": r
    for _, r in food_pool.iterrows()
}

selected_food_labels = st.multiselect("選擇主食", list(food_options.keys()), max_selections=2)

if len(selected_food_labels) != 2:
    st.warning("請選 2 種主食")
    st.stop()

selected_foods = [food_options[l] for l in selected_food_labels]

total_food_cf = sum(r["cf_kg"] for r in selected_foods)
total_food_weight = sum(r["weight_kg"] for r in selected_foods)

# =======================
# 料理方式
# =======================
st.header("🍳 料理方式")

cook_cf = 0.0
for r in selected_foods:
    method = st.radio(
        f"{r['name']} 的料理方式",
        ["水煮", "油炸"],
        horizontal=True,
        key=r["name"],
    )
    if method == "水煮":
        pick = df_water.sample(1).iloc[0]
    else:
        pick = df_oil.sample(1).iloc[0]

    cook_cf += pick["cf_kg"]
    st.caption(f"→ 使用 {pick['name']}（{pick['cf_kg']} kgCO₂e）")

# =======================
# 飲料
# =======================
st.header("🥤 飲料")

drink_label = st.selectbox(
    "選擇飲料",
    ["不喝"] + [f"{r['name']} ({r['cf_kg']} kgCO₂e)" for _, r in df_drink.iterrows()]
)

drink_cf = 0.0
if drink_label != "不喝":
    drink_cf = float(drink_label.split("(")[-1].replace(" kgCO₂e)", ""))

# =======================
# 甜點
# =======================
st.header("🍰 甜點")

dessert_label = st.selectbox(
    "選擇甜點",
    ["不吃"] + [f"{r['name']} ({r['cf_kg']} kgCO₂e)" for _, r in df_dessert.iterrows()]
)

dessert_cf = 0.0
if dessert_label != "不吃":
    dessert_cf = float(dessert_label.split("(")[-1].replace(" kgCO₂e)", ""))

# =======================
# 交通（定位＋地圖）
# =======================
st.header("🚗 採買交通")

geo = streamlit_geolocation()
if not geo or not geo["latitude"]:
    st.warning("請允許定位")
    st.stop()

lat, lon = geo["latitude"], geo["longitude"]

transport_choice = st.selectbox(
    "選擇交通工具",
    [f"{k}（{v['unit']}）" for k, v in TRANSPORT_FACTORS.items()]
)

# 搜尋附近全聯
def search_store(lat, lon):
    r = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={
            "q": "全聯",
            "format": "json",
            "limit": 5,
            "lat": lat,
            "lon": lon,
        },
        headers={"User-Agent": "carbon-app"},
    )
    return r.json()

stores = search_store(lat, lon)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

m = folium.Map(location=[lat, lon], zoom_start=14)
folium.Marker([lat, lon], tooltip="你的位置").add_to(m)

dist_km = None
for s in stores:
    d = haversine(lat, lon, float(s["lat"]), float(s["lon"]))
    folium.Marker([float(s["lat"]), float(s["lon"])], tooltip=f"{s['display_name']}").add_to(m)
    dist_km = d * 2
    break

st_folium(m, height=350)

# 交通碳足跡
transport_key = transport_choice.split("（")[0]
tf = TRANSPORT_FACTORS[transport_key]

if tf["type"] == "pkm":
    transport_cf = dist_km * tf["factor"]
    formula = f"{dist_km:.2f} × {tf['factor']} = {transport_cf:.3f}"
else:
    transport_cf = dist_km * (total_food_weight / 1000) * tf["factor"]
    formula = f"{dist_km:.2f} × {(total_food_weight/1000):.3f} × {tf['factor']} = {transport_cf:.3f}"

st.info(f"📐 交通碳足跡計算：{formula} kgCO₂e")

# =======================
# 總計
# =======================
total_cf = total_food_cf + cook_cf + drink_cf + dessert_cf + transport_cf

st.header("✅ 總碳足跡")
st.metric("總計（kgCO₂e）", round(total_cf, 3))

# =======================
# CSV 下載
# =======================
result = {
    "student": student,
    "round": st.session_state.round,
    "food_cf": total_food_cf,
    "cook_cf": cook_cf,
    "drink_cf": drink_cf,
    "dessert_cf": dessert_cf,
    "transport_cf": transport_cf,
    "total_cf": total_cf,
    "timestamp": datetime.now().isoformat(),
}

csv = pd.DataFrame([result]).to_csv(index=False).encode("utf-8-sig")
st.download_button("⬇️ 下載結果 CSV", csv, "carbon_result.csv")

st.session_state.round += 1
