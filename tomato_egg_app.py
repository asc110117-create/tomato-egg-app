
# tomato_egg_app_full_integrated_FIXED.py
# 一餐的碳足跡大冒險（教學完整版）
# Excel 欄位需求：族群、產品名稱、碳足跡(kg)
# 重量從「產品名稱」自動解析（g / kg）
# 交通：機車 / 自用小客車 / 3.49 噸低溫貨車（延噸公里）
# 含定位＋地圖選分店、來回距離、CSV 下載、Google Sheet 寫入

import re
import math
import random
from io import BytesIO
from datetime import datetime

import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation
import altair as alt

# ================= 基本設定 =================
st.set_page_config(page_title="一餐的碳足跡大冒險", page_icon="🍽️", layout="centered")
st.title("🍽️ 一餐的碳足跡大冒險")

# ================= 工具函式 =================
def parse_weight_kg(name: str) -> float:
    """從產品名稱解析重量（kg）"""
    if not isinstance(name, str):
        return 0.0
    m = re.search(r"(\\d+(?:\\.\\d+)?)(kg|g)", name.lower())
    if not m:
        return 0.0
    val = float(m.group(1))
    unit = m.group(2)
    return val if unit == "kg" else val / 1000.0


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))


@st.cache_data
def load_excel(file_bytes):
    df = pd.read_excel(BytesIO(file_bytes))
    df.columns = ["group", "name", "cf_kg"]
    df["cf_kg"] = pd.to_numeric(df["cf_kg"], errors="coerce").fillna(0.0)
    df["weight_kg"] = df["name"].apply(parse_weight_kg)
    return df


# ================= 使用者資料 =================
student = st.text_input("請輸入你的名字")
if not student:
    st.stop()

st.success(f"你好，{student}！")

# ================= 讀取資料 =================
uploaded = st.file_uploader("請上傳《碳足跡4.xlsx》", type=["xlsx"])
if not uploaded:
    st.stop()

df = load_excel(uploaded.getvalue())

# ================= 主食（group 1） =================
st.subheader("🍛 主食（隨機 5 選 2）")
food_df = df[df["group"] == 1].sample(n=min(5, len(df[df["group"] == 1])), random_state=42)

options = {
    f"{r.name} ({r.cf_kg} kgCO₂e)": i
    for i, r in food_df.iterrows()
}

chosen_labels = st.multiselect("請選 2 種主食", options=list(options.keys()))
if len(chosen_labels) != 2:
    st.warning("請選 2 種主食")
    st.stop()

chosen_rows = food_df.loc[[options[l] for l in chosen_labels]]

total_food_cf = chosen_rows["cf_kg"].sum()
total_weight_kg = chosen_rows["weight_kg"].sum()

st.markdown("### 你選擇的主食：")
for _, r in chosen_rows.iterrows():
    st.write(f"- {r.name}（{r.cf_kg} kgCO₂e）")

st.info(f"主食總重量：{total_weight_kg:.3f} kg")

# ================= 交通 =================
st.subheader("🚚 交通（定位＋地圖）")

geo = streamlit_geolocation()
if not geo or geo.get("latitude") is None:
    st.warning("請允許定位")
    st.stop()

lat, lon = geo["latitude"], geo["longitude"]

m = folium.Map(location=[lat, lon], zoom_start=13)
folium.Marker([lat, lon], tooltip="你的位置").add_to(m)
map_state = st_folium(m, height=300)

if not map_state.get("last_clicked"):
    st.info("請在地圖上點選採買分店位置")
    st.stop()

shop_lat = map_state["last_clicked"]["lat"]
shop_lon = map_state["last_clicked"]["lng"]

dist_km = haversine_km(lat, lon, shop_lat, shop_lon)
round_km = dist_km * 2

st.write(f"來回距離：約 {round_km:.2f} km")

transport = st.selectbox(
    "交通工具",
    [
        "機車（9.51E-2 kgCO₂e / pkm）",
        "自用小客車（汽油，1.15E-1 kgCO₂e / pkm）",
        "3.49 噸低溫貨車（2.71 kgCO₂e / tkm）",
    ]
)

if transport.startswith("機車"):
    transport_cf = round_km * 9.51e-2
elif transport.startswith("自用"):
    transport_cf = round_km * 1.15e-1
else:
    transport_cf = round_km * (total_weight_kg / 1000) * 2.71

st.success(f"交通碳足跡：{transport_cf:.3f} kgCO₂e")

# ================= 總計 =================
total_cf = total_food_cf + transport_cf

st.subheader("✅ 總碳足跡")
st.write(f"主食：{total_food_cf:.3f} kgCO₂e")
st.write(f"交通：{transport_cf:.3f} kgCO₂e")
st.markdown(f"### 🌍 總計：**{total_cf:.3f} kgCO₂e**")

# ================= CSV 下載 =================
row = {
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "student": student,
    "food_items": ", ".join(chosen_rows["name"]),
    "food_cf_kg": total_food_cf,
    "food_weight_kg": total_weight_kg,
    "round_trip_km": round_km,
    "transport": transport,
    "transport_cf_kg": transport_cf,
    "total_cf_kg": total_cf,
}

csv = pd.DataFrame([row]).to_csv(index=False).encode("utf-8-sig")
st.download_button("⬇️ 下載結果 CSV", csv, file_name=f"{student}_carbon_result.csv", mime="text/csv")
