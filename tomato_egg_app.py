
# tomato_egg_app_COMPLETE_EXTENDED.py
# 一餐的碳足跡大冒險（Streamlit）— 完整擴充版
# 保留你提供的架構，補齊：地圖選分店、走路=0、延噸公里、圖表（長條＋圓餅）

import re
import random
import math
import uuid
from io import BytesIO
from datetime import datetime

import pandas as pd
import streamlit as st
import altair as alt
import requests
import folium
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation

# =========================
# 0) 基本設定
# =========================
st.set_page_config(
    page_title="一餐的碳足跡大冒險：從農場到你的胃",
    page_icon="🍽️",
    layout="centered",
)

APP_TITLE = "🍽️ 一餐的碳足跡大冒險：從農場到你的胃"
EXCEL_PATH_DEFAULT = "產品碳足跡3.xlsx"

# 台中教育大學（預設座標）
NTSU_LAT = 24.1477
NTSU_LNG = 120.6736

# =========================
# 1) CF 解析：統一成 gCO2e
# =========================
def parse_cf_to_g(value) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return float("nan")
    if isinstance(value, (int, float)):
        v = float(value)
        return v * 1000.0 if v <= 50 else v
    s = str(value).strip().lower().replace(" ", "")
    s = s.replace("kgco2e", "kg").replace("gco2e", "g")
    if re.fullmatch(r"[-+]?\d*\.?\d+k", s):
        return float(s[:-1]) * 1000.0
    m = re.match(r"([-+]?\d*\.?\d+)(kg|g)?$", s)
    if m:
        num = float(m.group(1))
        unit = m.group(2)
        if unit == "kg":
            return num * 1000.0
        if unit == "g":
            return num
        return num * 1000.0 if num <= 50 else num
    m2 = re.search(r"([-+]?\d*\.?\d+)\s*(kg|g)", s)
    if m2:
        num = float(m2.group(1))
        unit = m2.group(2)
        return num * 1000.0 if unit == "kg" else num
    m3 = re.search(r"([-+]?\d*\.?\d+)", s)
    if m3:
        num = float(m3.group(1))
        return num * 1000.0 if num <= 50 else num
    return float("nan")

def g_to_kg(g):
    return float(g) / 1000.0

# =========================
# 2) 距離
# =========================
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))

# =========================
# 3) Nominatim 搜尋附近分店
# =========================
def nominatim_search_nearby(query, lat, lng, radius_km=5, limit=30):
    if not query.strip():
        return []
    lat_delta = radius_km / 111.0
    lng_delta = radius_km / (111.0 * max(0.1, math.cos(math.radians(lat))))
    viewbox = f"{lng-lng_delta},{lat+lat_delta},{lng+lng_delta},{lat-lat_delta}"
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": str(limit),
        "addressdetails": 1,
        "viewbox": viewbox,
        "bounded": 1,
    }
    headers = {
        "User-Agent": "carbon-footprint-edu-app/1.0",
        "Accept-Language": "zh-TW,zh,en",
    }
    r = requests.get("https://nominatim.openstreetmap.org/search", params=params, headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()
    out = []
    for x in data:
        out.append({
            "display_name": x.get("display_name",""),
            "name": (x.get("display_name","").split(",")[0]).strip(),
            "lat": float(x["lat"]),
            "lng": float(x["lon"]),
        })
    return out

# =========================
# 4) 讀 Excel
# =========================
@st.cache_data(show_spinner=False)
def load_data_from_excel(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_excel(BytesIO(file_bytes), engine="openpyxl")
    df = df.iloc[:, :4].copy()
    df.columns = ["code", "product_name", "product_carbon_footprint_data", "declared_unit"]
    df["code"] = df["code"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    df["product_name"] = df["product_name"].astype(str).str.strip()
    df["declared_unit"] = df["declared_unit"].astype(str).str.strip()
    df["cf_gco2e"] = df["product_carbon_footprint_data"].apply(parse_cf_to_g)
    df = df.dropna(subset=["cf_gco2e"]).reset_index(drop=True)
    df["cf_kgco2e"] = df["cf_gco2e"].apply(g_to_kg)
    return df

def read_excel_source() -> pd.DataFrame:
    try:
        with open(EXCEL_PATH_DEFAULT, "rb") as f:
            return load_data_from_excel(f.read())
    except Exception:
        up = st.file_uploader("上傳 Excel（.xlsx）", type=["xlsx"])
        if up is None:
            raise FileNotFoundError(f"請放置 {EXCEL_PATH_DEFAULT} 或上傳檔案。")
        return load_data_from_excel(up.getvalue())

# =========================
# 5) 抽樣工具
# =========================
def safe_sample(sub_df: pd.DataFrame, n: int) -> pd.DataFrame:
    if len(sub_df) == 0:
        return sub_df.copy()
    return sub_df.sample(n=min(n,len(sub_df)), replace=False, random_state=random.randint(1,10000)).reset_index(drop=True)

def pick_one(df: pd.DataFrame, code_value: str) -> dict:
    sub = df[df["code"] == code_value]
    row = sub.sample(1, random_state=random.randint(1,10000)).iloc[0]
    return {
        "code": row["code"],
        "product_name": row["product_name"],
        "cf_gco2e": float(row["cf_gco2e"]),
        "cf_kgco2e": float(row["cf_kgco2e"]),
        "declared_unit": row["declared_unit"],
    }

# =========================
# 6) Session 初始化
# =========================
st.session_state.setdefault("meal_items", None)
st.session_state.setdefault("cook_method", {})
st.session_state.setdefault("cook_picks", {})
st.session_state.setdefault("drink_pick", None)
st.session_state.setdefault("dessert_pool", None)
st.session_state.setdefault("dessert_pick_names", [])
st.session_state.setdefault("origin", {"lat": None, "lng": None})
st.session_state.setdefault("selected_store", None)
st.session_state.setdefault("transport_mode", "走路")

# =========================
# 7) 定位
# =========================
geo = streamlit_geolocation()
if geo and st.session_state.origin["lat"] is None:
    st.session_state.origin = {"lat": geo.get("latitude"), "lng": geo.get("longitude")}

# =========================
# 8) 主畫面
# =========================
st.title(APP_TITLE)
df_all = read_excel_source()

df_food = df_all[df_all["code"]=="1"]
df_oil = df_all[df_all["code"]=="1-1"]
df_water = df_all[df_all["code"]=="1-2"]
df_drink = df_all[df_all["code"]=="2"]
df_dessert = df_all[df_all["code"]=="3"]

# ---- 主食
st.subheader("🥬 主食")
if st.button("🔄 更換食材"):
    st.session_state.meal_items = safe_sample(df_food, 3)
    st.session_state.cook_method = {}
    st.session_state.cook_picks = {}

if st.session_state.meal_items is None:
    st.session_state.meal_items = safe_sample(df_food, 3)

meal_df = st.session_state.meal_items.reset_index(drop=True)
st.dataframe(meal_df[["product_name","cf_gco2e","declared_unit"]])

# ---- 料理
st.subheader("🍳 料理方式")
cook_sum = 0.0
for i in range(len(meal_df)):
    name = meal_df.loc[i,"product_name"]
    method = st.radio(name, ["水煮","煎炸"], key=f"cook_{i}", horizontal=True)
    if method == "水煮":
        pick = pick_one(df_all, "1-2")
    else:
        pick = pick_one(df_all, "1-1")
    cook_sum += pick["cf_kgco2e"]
    st.caption(f"使用：{pick['product_name']}（{pick['cf_kgco2e']:.3f} kgCO₂e）")

# ---- 飲料
st.subheader("🥤 飲料")
drink_cf = 0.0
if st.checkbox("我要飲料") and len(df_drink)>0:
    d = pick_one(df_all,"2")
    drink_cf = d["cf_kgco2e"]
    st.info(f"{d['product_name']}（{drink_cf:.3f} kgCO₂e）")

# ---- 甜點
st.subheader("🍰 甜點（選 2）")
dessert_cf = 0.0
if st.session_state.dessert_pool is None:
    st.session_state.dessert_pool = safe_sample(df_dessert,5)
opts = st.session_state.dessert_pool["product_name"].tolist()
chosen = st.multiselect("選 2 種", opts, max_selections=2)
if len(chosen)==2:
    dessert_cf = float(st.session_state.dessert_pool[st.session_state.dessert_pool["product_name"].isin(chosen)]["cf_kgco2e"].sum())

# ---- 地圖 + 運輸
st.subheader("🗺️ 採買與運輸")
origin = st.session_state.origin
q = st.text_input("搜尋分店（如：全聯）")
stores = nominatim_search_nearby(q, origin["lat"] or NTSU_LAT, origin["lng"] or NTSU_LNG) if q else []

m = folium.Map(location=[origin["lat"] or NTSU_LAT, origin["lng"] or NTSU_LNG], zoom_start=13)
if origin["lat"]:
    folium.Marker([origin["lat"],origin["lng"]], tooltip="起點").add_to(m)

for s in stores[:10]:
    folium.Marker([s["lat"],s["lng"]], tooltip=s["name"]).add_to(m)

mp = st_folium(m, height=320)

transport_cf = 0.0
formula = ""
EF = {
    "走路": 0.0,
    "機車": 0.0951,
    "汽車": 0.115,
    "3.49噸低溫貨車": 2.71,
}
mode = st.selectbox("交通方式", list(EF.keys()))
if mp.get("last_clicked"):
    lat, lng = mp["last_clicked"]["lat"], mp["last_clicked"]["lng"]
    dist = haversine_km(origin["lat"] or NTSU_LAT, origin["lng"] or NTSU_LNG, lat, lng)
    if mode=="3.49噸低溫貨車":
        weight_ton = meal_df["cf_gco2e"].sum()/1000/1000
        transport_cf = dist * weight_ton * EF[mode]
        formula = f"{dist:.1f} × {weight_ton:.4f} × {EF[mode]} = {transport_cf:.3f}"
    else:
        transport_cf = dist * EF[mode]
        formula = f"{dist:.1f} × {EF[mode]} = {transport_cf:.3f}"
    st.info("運輸公式：" + formula)

# ---- 加總
food_sum = float(meal_df["cf_kgco2e"].sum())
total = food_sum + cook_sum + drink_cf + dessert_cf + transport_cf

st.subheader("✅ 總計")
st.write(f"**{total:.3f} kgCO₂e**")

# ---- 圖表（你喜歡的 Altair）
chart_df = pd.DataFrame([
    {"項目":"主食","kgCO2e":food_sum},
    {"項目":"烹調","kgCO2e":cook_sum},
    {"項目":"飲料","kgCO2e":drink_cf},
    {"項目":"甜點","kgCO2e":dessert_cf},
    {"項目":"運輸","kgCO2e":transport_cf},
])

bar = alt.Chart(chart_df).mark_bar().encode(
    x="kgCO2e:Q",
    y=alt.Y("項目:N", sort="-x")
)
pie = alt.Chart(chart_df[chart_df.kgCO2e>0]).mark_arc().encode(
    theta="kgCO2e:Q",
    color="項目:N"
)

st.altair_chart(bar, use_container_width=True)
st.altair_chart(pie, use_container_width=True)
