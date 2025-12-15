
# tomato_egg_app_ALL_1_to_5.py
# 完整版：
# 1. 讀取 Excel（產品碳足跡3.xlsx）
# 2. 地圖抓距離（OSM + folium）
# 3. 主食 → 水煮/煎炸 → 飲料 → 甜點 → 運輸（pkm / tkm / 走路）
# 4. 圓餅圖 + 長條圖
# 5. 學生姓名 + 第幾次測試，自動寫入 Google Sheet

import streamlit as st
import pandas as pd
import random
import math
from datetime import datetime
import altair as alt
import folium
from streamlit_folium import st_folium
from io import BytesIO
import requests
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="一餐的碳足跡", layout="centered")

# ------------------ 工具函數 ------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def parse_gco2e(v):
    if pd.isna(v):
        return 0.0
    s = str(v).lower()
    num = float("".join(c for c in s if c.isdigit() or c=="."))
    if "kg" in s:
        return num * 1000
    return num

# ------------------ 讀取 Excel ------------------
@st.cache_data
def load_data():
    df = pd.read_excel("產品碳足跡3.xlsx")
    df.columns = ["code","name","cf","unit","weight"]
    df["cf_g"] = df["cf"].apply(parse_gco2e)
    df["cf_kg"] = df["cf_g"] / 1000
    df["weight_kg"] = df["weight"].fillna(0)
    return df

df = load_data()

# ------------------ 學生身份 ------------------
st.title("🍱 一餐的碳足跡")

student = st.text_input("請輸入姓名")
if "round" not in st.session_state:
    st.session_state.round = 1

# ------------------ 主食 ------------------
st.header("① 主食")
foods = df[df.code=="1"].sample(3)
st.table(foods[["name","cf_kg"]])

# ------------------ 料理方式 ------------------
st.header("② 料理方式")
cook_cf = 0
for i,row in foods.iterrows():
    method = st.radio(
        f"{row['name']}",
        ["水煮","煎炸"],
        key=f"cook_{i}"
    )
    if method=="水煮":
        cook_cf += df[df.code=="1-2"].sample(1).cf_kg.values[0]
    else:
        cook_cf += df[df.code=="1-1"].sample(1).cf_kg.values[0]

# ------------------ 飲料 ------------------
st.header("③ 飲料")
drink_cf = 0
if st.checkbox("我要飲料"):
    drink = df[df.code=="2"].sample(1)
    st.write(drink.name.values[0])
    drink_cf = drink.cf_kg.values[0]

# ------------------ 甜點 ------------------
st.header("④ 甜點（選 2）")
dessert_pool = df[df.code=="3"].sample(5)
dessert_sel = st.multiselect(
    "選擇兩種",
    dessert_pool.name.tolist()
)
dessert_cf = dessert_pool[dessert_pool.name.isin(dessert_sel)].cf_kg.sum()

# ------------------ 運輸 ------------------
st.header("⑤ 運輸")

mode = st.radio("方式",["走路","自己去買(pkm)","貨車配送(tkm)"])

transport_cf = 0
formula = ""

if mode!="走路":
    lat = st.number_input("起點緯度", value=24.1477)
    lon = st.number_input("起點經度", value=120.6736)
    lat2 = st.number_input("目的地緯度", value=24.1500)
    lon2 = st.number_input("目的地經度", value=120.6700)
    dist = haversine(lat,lon,lat2,lon2)

    if mode=="自己去買(pkm)":
        ef = st.number_input("pkm 係數", value=0.115)
        transport_cf = dist * ef
        formula = f"{dist:.2f} × {ef}"
    else:
        total_weight_ton = foods.weight_kg.sum()/1000
        ef = 2.71
        transport_cf = dist * total_weight_ton * ef
        formula = f"{dist:.2f} × {total_weight_ton:.4f} × {ef}"

    st.info(f"計算式：{formula} = {transport_cf:.3f} kgCO₂e")

# ------------------ 總計 ------------------
total = foods.cf_kg.sum() + cook_cf + drink_cf + dessert_cf + transport_cf

st.subheader(f"🌍 總碳足跡：{total:.3f} kgCO₂e")

# ------------------ 圖表 ------------------
chart_df = pd.DataFrame({
    "類別":["主食","料理","飲料","甜點","運輸"],
    "kgCO2e":[foods.cf_kg.sum(),cook_cf,drink_cf,dessert_cf,transport_cf]
})
chart_df = chart_df[chart_df.kgCO2e>0]

pie = alt.Chart(chart_df).mark_arc().encode(
    theta="kgCO2e",
    color="類別",
    tooltip=["類別","kgCO2e"]
)
st.altair_chart(pie, use_container_width=True)

# ------------------ Google Sheet ------------------
if st.button("送出給老師"):
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    sh = gc.open(st.secrets["google_sheet"]["spreadsheet_name"])
    ws = sh.sheet1

    ws.append_row([
        datetime.now().isoformat(),
        student,
        st.session_state.round,
        total
    ])
    st.session_state.round += 1
    st.success("已送出")
