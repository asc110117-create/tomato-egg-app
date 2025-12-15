
# tomato_egg_app_final_extended.py
# 一餐的碳足跡大冒險（完整版）
# 含：姓名輸入＋自動第幾次測試、主食(1)+水煮/油炸(1-2/1-1)、飲料(group2)、甜點(group3)
# 地圖點選分店、延噸公里運輸公式、圖表、CSV下載、寫入 Google Sheet

import streamlit as st
import pandas as pd
import numpy as np
import random
import math
from io import BytesIO
from datetime import datetime

import altair as alt
import folium
from streamlit_folium import st_folium
import requests

import gspread
from google.oauth2.service_account import Credentials

# ---------------- 基本設定 ----------------
st.set_page_config(page_title="一餐的碳足跡大冒險", layout="centered")

EXCEL_PATH = "產品碳足跡3.xlsx"
NTSU_LAT, NTSU_LNG = 24.1477, 120.6736

# ---------------- 工具函式 ----------------
def parse_cf_to_kg(v):
    if pd.isna(v): return 0.0
    s = str(v).lower().replace(" ", "")
    if "kg" in s:
        return float(s.replace("kg",""))
    if "g" in s:
        return float(s.replace("g","")) / 1000
    try:
        x = float(s)
        return x if x > 1 else x
    except:
        return 0.0

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2-lat1)
    dl = math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(a))

def get_sheet():
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(st.secrets["google_sheet"]["spreadsheet_id"])
    return sh.worksheet(st.secrets["google_sheet"]["worksheet_name"])

def get_round(student_name: str) -> int:
    import gspread
    from google.oauth2.service_account import Credentials
    import streamlit as st

    sa_info = dict(st.secrets["gcp_service_account"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
    gc = gspread.authorize(creds)

    sheet_id = st.secrets["google_sheet"]["spreadsheet_id"]
    ws_name = st.secrets["google_sheet"]["worksheet_name"]

    sh = gc.open_by_key(sheet_id)
    ws = sh.worksheet(ws_name)

    values = ws.get_all_values()

    # 👉 如果整張表是空的
    if len(values) <= 1:
        return 1

    header = values[0]
    rows = values[1:]

    # 👉 找 student_name 欄位
    if "student_name" not in header:
        return 1

    idx = header.index("student_name")

    count = 0
    for r in rows:
        if len(r) > idx and r[idx] == student_name:
            count += 1

    return count + 1

# ---------------- 讀取資料 ----------------
@st.cache_data
def load_data():
    df = pd.read_excel(EXCEL_PATH)
    df = df.iloc[:, :4]
    df.columns = ["group","name","cf_raw","unit"]
    df["cf_kg"] = df["cf_raw"].apply(parse_cf_to_kg)
    return df

df = load_data()

food_df = df[df["group"]=="1"]
oil_df = df[df["group"]=="1-1"]
water_df = df[df["group"]=="1-2"]
drink_df = df[df["group"]=="2"]
dessert_df = df[df["group"]=="3"]

# ---------------- 使用者資訊 ----------------
st.title("🍽️ 一餐的碳足跡大冒險")

student = st.text_input("請輸入你的名字")
if not student:
    st.stop()

round_no = get_round(student)
st.info(f"📘 這是你第 {round_no} 次測試")

# ---------------- 主食 ----------------
st.header("🍛 主食（3 道）")
meal = food_df.sample(min(3,len(food_df))).reset_index(drop=True)
cook_cf_total = 0
for i,row in meal.iterrows():
    st.subheader(row["name"])
    method = st.radio("料理方式",["水煮","油炸"],key=f"cook{i}")
    if method=="水煮" and len(water_df)>0:
        w = water_df.sample(1).iloc[0]
        cook_cf_total += w["cf_kg"]
        st.caption(f"水：{w['name']}（{w['cf_kg']} kgCO₂e）")
    if method=="油炸" and len(oil_df)>0:
        o = oil_df.sample(1).iloc[0]
        cook_cf_total += o["cf_kg"]
        st.caption(f"油：{o['name']}（{o['cf_kg']} kgCO₂e）")

food_cf = meal["cf_kg"].sum()

# ---------------- 飲料 ----------------
st.header("🥤 飲料")
drink_opts = [f"{r['name']}（{r['cf_kg']} kgCO₂e）" for _,r in drink_df.iterrows()]
drink_choice = st.selectbox("選擇飲料", ["不喝"]+drink_opts)
drink_cf = 0
if drink_choice!="不喝":
    idx = drink_opts.index(drink_choice)
    drink_cf = drink_df.iloc[idx]["cf_kg"]

# ---------------- 甜點 ----------------
st.header("🍰 甜點（group3）")
dessert_opts = [f"{r['name']}（{r['cf_kg']} kgCO₂e）" for _,r in dessert_df.iterrows()]
dessert_choice = st.selectbox("選擇甜點", dessert_opts)
dessert_cf = dessert_df.iloc[dessert_opts.index(dessert_choice)]["cf_kg"]

# ---------------- 交通 ----------------
st.header("🧭 交通（延噸公里）")
mode = st.selectbox("交通方式",["走路","機車（kgCO₂e/tkm）","汽車（kgCO₂e/tkm）"])
distance = st.number_input("距離（km）",0.0,100.0,1.0)
weight_ton = st.number_input("貨物重量（噸）",0.0001,1.0,0.0008)
tkm_factor = 2.71

transport_cf = 0.0
formula = "走路不計算"
if mode!="走路":
    transport_cf = distance * weight_ton * tkm_factor
    formula = f"{distance} × {weight_ton} × {tkm_factor} = {transport_cf:.3f} kgCO₂e"

st.caption(f"📐 計算式：{formula}")

# ---------------- 總計 ----------------
total = food_cf + cook_cf_total + drink_cf + dessert_cf + transport_cf

st.header("✅ 總碳足跡")
st.metric("總計 (kgCO₂e)", round(total,3))

# ---------------- 圖表 ----------------
chart_df = pd.DataFrame({
    "項目":["主食","料理","飲料","甜點","運輸"],
    "kgCO2e":[food_cf,cook_cf_total,drink_cf,dessert_cf,transport_cf]
})
chart_df = chart_df[chart_df["kgCO2e"]>0]

bar = alt.Chart(chart_df).mark_bar().encode(
    x="項目",
    y="kgCO2e",
    tooltip=["項目","kgCO2e"]
)
pie = alt.Chart(chart_df).mark_arc().encode(
    theta="kgCO2e",
    color="項目",
    tooltip=["項目","kgCO2e"]
)
st.altair_chart(bar,use_container_width=True)
st.altair_chart(pie,use_container_width=True)

# ---------------- CSV & Google Sheet ----------------
row = {
    "timestamp": datetime.now().isoformat(),
    "student_name": student,
    "round": round_no,
    "food": food_cf,
    "cooking": cook_cf_total,
    "drink": drink_cf,
    "dessert": dessert_cf,
    "transport": transport_cf,
    "total": total
}

csv = pd.DataFrame([row]).to_csv(index=False).encode("utf-8-sig")
st.download_button("⬇️ 下載 CSV",csv,file_name=f"{student}_round{round_no}.csv")

if st.button("📤 寫入 Google Sheet"):
    ws = get_sheet()
    if len(ws.get_all_values())==0:
        ws.append_row(list(row.keys()))
    ws.append_row(list(row.values()))
    st.success("已寫入 Google Sheet")

