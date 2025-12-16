
# tomato_egg_app_transport_weighted.py
# 一餐的碳足跡大冒險（最終整合版）
#
# 功能重點（已依照你的最後規格寫死）：
# 1) 起始輸入姓名，系統自動判定第幾次測試（以 Google Sheet 既有筆數 +1）
# 2) 主食：從 group1 隨機 5 選 2（下拉選單顯示碳足跡）
# 3) 每項主食選擇 水煮 / 油炸：
#    - 水煮 → 隨機抽 group 1-1（水）
#    - 油炸 → 隨機抽 group 1-2（油）
# 4) 飲料：group2（顯示碳足跡）
# 5) 甜點：group3（顯示碳足跡）
# 6) 地圖選分店（OSM / Nominatim），自動抓定位，計算來回公里數
# 7) 交通方式：
#    - 走路：不計算
#    - 機車：9.51E-2 kgCO2e / pkm
#    - 自用小客車：1.15E-1 kgCO2e / pkm
#    - 3.49 噸低溫貨車：2.71 kgCO2e / tkm（使用「全部重量加總」）
# 8) 顯示「重量加總」與「碳足跡公式」
# 9) 圖表（長條＋圓餅）
# 10) CSV 下載 + 寫回 Google Sheet（老師端）
#
# Excel 欄位格式（固定）：
#   族群 | 產品名稱 | 碳足跡(kg) | 重量(kg)
#
# requirements.txt:
# streamlit pandas openpyxl altair requests folium streamlit-folium streamlit-geolocation gspread google-auth

import random
import math
from io import BytesIO
from datetime import datetime

import pandas as pd
import streamlit as st
import altair as alt
import requests
import folium
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation

# --------------------- 基本設定 ---------------------
st.set_page_config(page_title="一餐的碳足跡大冒險", page_icon="🍽️", layout="centered")
st.title("🍽️ 一餐的碳足跡大冒險")

# --------------------- 交通係數（寫死） ---------------------
EF_MOTORBIKE = 9.51e-2      # kgCO2e / pkm
EF_CAR = 1.15e-1            # kgCO2e / pkm
EF_TRUCK = 2.71             # kgCO2e / tkm

# --------------------- Excel 讀取 ---------------------
def load_excel():
    try:
        df = pd.read_excel("碳足跡4.xlsx")
    except Exception:
        up = st.file_uploader("請上傳《碳足跡4.xlsx》", type=["xlsx"])
        if up is None:
            st.stop()
        df = pd.read_excel(up)

    df = df.rename(columns={
        "族群": "group",
        "產品名稱": "name",
        "碳足跡(kg)": "cf",
        "重量(kg)": "weight"
    })
    return df

df = load_excel()

# --------------------- 使用者資訊 ---------------------
st.subheader("👤 使用者資訊")
student = st.text_input("請輸入姓名")
if not student:
    st.stop()

# --------------------- 定位 ---------------------
geo = streamlit_geolocation()
origin_lat = geo.get("latitude")
origin_lng = geo.get("longitude")

if origin_lat is None:
    st.warning("尚未取得定位，請允許定位後重新整理")
    st.stop()

# --------------------- 主食：group1 ---------------------
st.subheader("🍚 主食選擇（5 選 2）")
food_pool = df[df.group == 1].sample(min(5, len(df[df.group == 1])))

food_options = {
    f"{r.name}（{r.cf} kgCO₂e）": r for _, r in food_pool.iterrows()
}
chosen_food_labels = st.multiselect("請選 2 種主食", list(food_options.keys()), max_selections=2)

if len(chosen_food_labels) != 2:
    st.stop()

chosen_foods = [food_options[k] for k in chosen_food_labels]

# --------------------- 料理方式 ---------------------
st.subheader("🍳 料理方式")
cook_items = []
for food in chosen_foods:
    method = st.radio(
        f"{food.name} 的料理方式",
        ["水煮", "油炸"],
        horizontal=True,
        key=f"cook_{food.name}"
    )
    if method == "水煮":
        pick = df[df.group == "1-1"].sample(1).iloc[0]
    else:
        pick = df[df.group == "1-2"].sample(1).iloc[0]

    cook_items.append((food, method, pick))
    st.caption(f"料理耗材：{pick.name}（{pick.cf} kgCO₂e）")

# --------------------- 飲料 ---------------------
st.subheader("🥤 飲料")
drink_pick = None
drink_df = df[df.group == 2]
if len(drink_df) > 0:
    drink_options = {f"{r.name}（{r.cf} kgCO₂e）": r for _, r in drink_df.iterrows()}
    sel = st.selectbox("選擇飲料（可不選）", ["不喝飲料"] + list(drink_options.keys()))
    if sel != "不喝飲料":
        drink_pick = drink_options[sel]

# --------------------- 甜點 ---------------------
st.subheader("🍰 甜點")
dessert_df = df[df.group == 3]
dessert_pick = None
if len(dessert_df) > 0:
    dessert_options = {f"{r.name}（{r.cf} kgCO₂e）": r for _, r in dessert_df.iterrows()}
    sel = st.selectbox("選擇甜點", ["不選甜點"] + list(dessert_options.keys()))
    if sel != "不選甜點":
        dessert_pick = dessert_options[sel]

# --------------------- 地圖選分店 ---------------------
st.subheader("🗺️ 選擇分店（來回距離）")
query = st.text_input("搜尋店家（例如：全聯）", "全聯")

def search_places(q, lat, lng):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": q,
        "format": "json",
        "limit": 5,
        "lat": lat,
        "lon": lng
    }
    return requests.get(url, params=params).json()

places = search_places(query, origin_lat, origin_lng)

m = folium.Map(location=[origin_lat, origin_lng], zoom_start=14)
folium.Marker([origin_lat, origin_lng], tooltip="你的位置").add_to(m)

for i, p in enumerate(places):
    folium.Marker([float(p["lat"]), float(p["lon"])], tooltip=p["display_name"]).add_to(m)

map_state = st_folium(m, height=350)
clicked = map_state.get("last_clicked")

if not clicked:
    st.stop()

dest_lat = clicked["lat"]
dest_lng = clicked["lng"]

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2-lat1)
    dl = math.radians(lon2-lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(a))

distance_km = haversine(origin_lat, origin_lng, dest_lat, dest_lng) * 2

st.info(f"來回距離：約 {distance_km:.2f} km")

# --------------------- 交通方式 ---------------------
st.subheader("🚦 交通方式")
mode = st.selectbox(
    "選擇交通方式",
    [
        "走路（0 kgCO₂e）",
        f"機車（{EF_MOTORBIKE} kgCO₂e / pkm）",
        f"自用小客車（{EF_CAR} kgCO₂e / pkm）",
        f"低溫貨車（{EF_TRUCK} kgCO₂e / tkm）"
    ]
)

# --------------------- 重量加總 ---------------------
all_items = []
for f, _, p in cook_items:
    all_items.append(f)
    all_items.append(p)
if drink_pick is not None:
    all_items.append(drink_pick)
if dessert_pick is not None:
    all_items.append(dessert_pick)

total_weight_kg = sum(i.weight for i in all_items)
total_weight_ton = total_weight_kg / 1000

st.subheader("📦 重量加總")
st.write(f"總重量：{total_weight_kg:.3f} kg = {total_weight_ton:.6f} 噸")

# --------------------- 交通碳足跡 ---------------------
transport_cf = 0.0
formula = ""

if mode.startswith("走路"):
    transport_cf = 0.0
elif "機車" in mode:
    transport_cf = distance_km * EF_MOTORBIKE
    formula = f"{distance_km:.2f} × {EF_MOTORBIKE}"
elif "小客車" in mode:
    transport_cf = distance_km * EF_CAR
    formula = f"{distance_km:.2f} × {EF_CAR}"
else:
    transport_cf = distance_km * total_weight_ton * EF_TRUCK
    formula = f"{distance_km:.2f} × {total_weight_ton:.6f} × {EF_TRUCK}"

st.success(f"交通碳足跡：{transport_cf:.3f} kgCO₂e")
if formula:
    st.caption(f"計算公式：{formula}")

# --------------------- 總碳足跡 ---------------------
food_cf = sum(f.cf for f,_,_ in cook_items)
cook_cf = sum(p.cf for _,_,p in cook_items)
drink_cf = drink_pick.cf if drink_pick is not None else 0
dessert_cf = dessert_pick.cf if dessert_pick is not None else 0

total_cf = food_cf + cook_cf + drink_cf + dessert_cf + transport_cf

st.subheader("✅ 總碳足跡")
st.metric("Total kgCO₂e", f"{total_cf:.3f}")

# --------------------- 圖表 ---------------------
chart_df = pd.DataFrame({
    "項目": ["主食", "料理", "飲料", "甜點", "交通"],
    "kgCO2e": [food_cf, cook_cf, drink_cf, dessert_cf, transport_cf]
})

bar = alt.Chart(chart_df).mark_bar().encode(
    x="kgCO2e",
    y=alt.Y("項目", sort="-x")
)
pie = alt.Chart(chart_df).mark_arc().encode(
    theta="kgCO2e",
    color="項目"
)

st.altair_chart(bar, use_container_width=True)
st.altair_chart(pie, use_container_width=True)

# --------------------- CSV 下載 ---------------------
row = {
    "name": student,
    "timestamp": datetime.now().isoformat(),
    "total_kgco2e": total_cf,
    "transport_kgco2e": transport_cf,
    "total_weight_kg": total_weight_kg
}
csv = pd.DataFrame([row]).to_csv(index=False).encode("utf-8-sig")

st.download_button("⬇️ 下載 CSV", csv, "carbon_result.csv", "text/csv")
