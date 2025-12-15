
# tomato_egg_app_ALL_1_to_5_WITH_MAP.py

import streamlit as st
import pandas as pd
import random, math, requests
from datetime import datetime
import altair as alt
import folium
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="一餐的碳足跡（地圖版）", layout="centered")

# ---------------- 工具 ----------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def parse_gco2e(v):
    if pd.isna(v): return 0.0
    s = str(v).lower()
    num = float("".join(c for c in s if c.isdigit() or c=="."))
    return num*1000 if "kg" in s else num

def search_places(query, lat, lon, limit=5):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "json",
        "limit": limit,
        "lat": lat,
        "lon": lon,
    }
    r = requests.get(url, params=params, headers={"User-Agent":"edu-app"})
    return r.json()

# ---------------- 資料 ----------------
@st.cache_data
def load_data():
    df = pd.read_excel("產品碳足跡3.xlsx")
    df.columns = ["code","name","cf","unit","weight"]
    df["cf_g"] = df["cf"].apply(parse_gco2e)
    df["cf_kg"] = df["cf_g"]/1000
    df["weight_kg"] = df["weight"].fillna(0)
    return df

df = load_data()

# ---------------- 學生 ----------------
st.title("🍱 一餐的碳足跡（地圖版）")
student = st.text_input("請輸入姓名")
if "round" not in st.session_state:
    st.session_state.round = 1

# ---------------- 主食 ----------------
st.header("① 主食")
foods = df[df.code=="1"].sample(3, random_state=1)
st.table(foods[["name","cf_kg"]])

# ---------------- 料理 ----------------
st.header("② 料理方式")
cook_cf = 0
for i,row in foods.iterrows():
    method = st.radio(row["name"], ["水煮","煎炸"], key=f"cook{i}")
    if method=="水煮":
        cook_cf += df[df.code=="1-2"].sample(1).cf_kg.values[0]
    else:
        cook_cf += df[df.code=="1-1"].sample(1).cf_kg.values[0]

# ---------------- 飲料 ----------------
st.header("③ 飲料")
drink_cf = 0
if st.checkbox("我要飲料"):
    d = df[df.code=="2"].sample(1)
    st.write(d.name.values[0])
    drink_cf = d.cf_kg.values[0]

# ---------------- 甜點 ----------------
st.header("④ 甜點（選 2）")
dessert_pool = df[df.code=="3"].sample(5)
dessert_sel = st.multiselect("選兩種", dessert_pool.name.tolist())
dessert_cf = dessert_pool[dessert_pool.name.isin(dessert_sel)].cf_kg.sum()

# ---------------- 地圖＋運輸 ----------------
st.header("⑤ 運輸（地圖點選分店）")

mode = st.radio("方式",["走路","自己去買(pkm)","貨車配送(tkm)"])
transport_cf = 0

if mode!="走路":
    st.subheader("設定起點")
    lat = st.number_input("起點緯度", value=24.1477)
    lon = st.number_input("起點經度", value=120.6736)

    q = st.text_input("搜尋分店", value="全聯")
    places = search_places(q, lat, lon, 5)

    if places:
        m = folium.Map(location=[lat,lon], zoom_start=14)
        folium.Marker([lat,lon], tooltip="起點", icon=folium.Icon(color="blue")).add_to(m)

        for i,p in enumerate(places):
            folium.Marker(
                [float(p["lat"]), float(p["lon"])],
                tooltip=f"{i+1}. {p['display_name']}"
            ).add_to(m)

        state = st_folium(m, height=350)

        idx = st.number_input("選擇分店編號", min_value=1, max_value=len(places), value=1)
        dest = places[int(idx)-1]

        dist = haversine(lat, lon, float(dest["lat"]), float(dest["lon"]))

        if mode=="自己去買(pkm)":
            ef = st.number_input("pkm 係數", value=0.115)
            transport_cf = dist * ef
            st.info(f"{dist:.2f} × {ef} = {transport_cf:.3f} kgCO₂e")
        else:
            total_weight_ton = foods.weight_kg.sum()/1000
            ef = 2.71
            transport_cf = dist * total_weight_ton * ef
            st.info(f"{dist:.2f} × {total_weight_ton:.4f} × {ef} = {transport_cf:.3f} kgCO₂e")

# ---------------- 總計 ----------------
total = foods.cf_kg.sum()+cook_cf+drink_cf+dessert_cf+transport_cf
st.subheader(f"🌍 總碳足跡：{total:.3f} kgCO₂e")

# ---------------- 圖表 ----------------
chart_df = pd.DataFrame({
    "類別":["主食","料理","飲料","甜點","運輸"],
    "kgCO2e":[foods.cf_kg.sum(),cook_cf,drink_cf,dessert_cf,transport_cf]
})
chart_df = chart_df[chart_df.kgCO2e>0]

st.altair_chart(
    alt.Chart(chart_df).mark_arc().encode(theta="kgCO2e", color="類別"),
    use_container_width=True
)

# ---------------- Google Sheet ----------------
if st.button("送出給老師"):
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    sh = gc.open(st.secrets["google_sheet"]["spreadsheet_name"])
    ws = sh.sheet1
    ws.append_row([datetime.now().isoformat(), student, st.session_state.round, total])
    st.session_state.round += 1
    st.success("已送出")
