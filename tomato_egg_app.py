# app.py
# 一餐的碳足跡大冒險（完整版）
# 搜尋分店（以使用者定位為中心）→ 最近 5 家 → 做決策 → 才加入交通碳足跡

import re
import random
import math
from io import BytesIO

import pandas as pd
import streamlit as st
import altair as alt
import requests

import folium
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation


# =========================
# 基本設定
# =========================
st.set_page_config(
    page_title="一餐的碳足跡大冒險：從農場到你的胃",
    page_icon="🍽️",
    layout="centered",
)

st.markdown("""
<style>
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
.card {
  padding: 14px;
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.15);
  background: rgba(255,255,255,0.03);
}
</style>
""", unsafe_allow_html=True)

APP_TITLE = "🍽️ 一餐的碳足跡大冒險：從農場到你的胃"
EXCEL_PATH = "產品碳足跡3.xlsx"


# =========================
# 工具：碳足跡字串 → kgCO2e
# =========================
def parse_cf_to_kg(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return float("nan")
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).lower().replace(" ", "")
    s = s.replace("kgco2e", "kg").replace("gco2e", "g")

    if re.fullmatch(r"\d+(\.\d+)?k", s):
        return float(s[:-1])

    m = re.match(r"(\d+(\.\d+)?)(kg|g)?", s)
    if m:
        num = float(m.group(1))
        unit = m.group(3)
        return num / 1000 if unit == "g" else num

    return float("nan")


# =========================
# 工具：距離（km）
# =========================
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlmb/2)**2
    return 2 * R * math.asin(math.sqrt(a))


# =========================
# 工具：附近搜尋（Nominatim）
# =========================
def nominatim_search_nearby(query, lat, lng, radius_km=5, limit=30):
    if not query.strip():
        return []

    lat_delta = radius_km / 111
    lng_delta = radius_km / (111 * max(0.1, math.cos(math.radians(lat))))

    params = {
        "q": query,
        "format": "jsonv2",
        "limit": limit,
        "viewbox": f"{lng-lng_delta},{lat+lat_delta},{lng+lng_delta},{lat-lat_delta}",
        "bounded": 1,
    }

    headers = {
        "User-Agent": "carbon-footprint-edu-app",
        "Accept-Language": "zh-TW,zh,en",
    }

    r = requests.get("https://nominatim.openstreetmap.org/search",
                     params=params, headers=headers, timeout=10)
    r.raise_for_status()

    return [
        {
            "name": x.get("display_name", "").split(",")[0],
            "lat": float(x["lat"]),
            "lng": float(x["lon"]),
        }
        for x in r.json()
    ]


# =========================
# 讀 Excel
# =========================
@st.cache_data
def load_data():
    df = pd.read_excel(EXCEL_PATH)
    df = df.iloc[:, :4]
    df.columns = ["code", "name", "cf_raw", "unit"]
    df["cf"] = df["cf_raw"].apply(parse_cf_to_kg)
    return df.dropna(subset=["cf"])


df = load_data()


# =========================
# Session
# =========================
for k, v in {
    "meal": None,
    "cook": {},
    "drink": None,
    "stores": [],
    "search": [],
    "decision": 0,
}.items():
    st.session_state.setdefault(k, v)


# =========================
# 主標題
# =========================
st.title(APP_TITLE)


# =========================
# 抽食材
# =========================
if st.button("🎲 抽 3 項食材"):
    st.session_state.meal = df[df.code == "1"].sample(3).reset_index(drop=True)
    st.session_state.cook = {}

if st.session_state.meal is None:
    st.session_state.meal = df[df.code == "1"].sample(3).reset_index(drop=True)

meal = st.session_state.meal

st.subheader("🍛 主餐")
st.dataframe(meal[["name", "cf", "unit"]])


# =========================
# 採買地點（重點）
# =========================
st.subheader("🧭 採買地點與交通碳足跡（以你的位置為中心）")

loc = streamlit_geolocation()

if loc and loc.get("latitude"):
    u_lat, u_lng = loc["latitude"], loc["longitude"]
    st.success(f"你的位置：{u_lat:.5f}, {u_lng:.5f}")

    q = st.text_input("搜尋店名（例如：全聯）")

    if st.button("🔍 搜尋附近分店"):
        raw = nominatim_search_nearby(q, u_lat, u_lng, radius_km=5)
        if len(raw) < 3:
            raw = nominatim_search_nearby(q, u_lat, u_lng, radius_km=10)

        results = []
        for r in raw:
            d = haversine_km(u_lat, u_lng, r["lat"], r["lng"])
            r["dist"] = d
            results.append(r)

        results.sort(key=lambda x: x["dist"])
        st.session_state.search = results[:5]
        st.session_state.decision = 0

    # 地圖
    m = folium.Map(location=[u_lat, u_lng], zoom_start=14)
    folium.Marker([u_lat, u_lng], icon=folium.Icon(color="blue"), tooltip="你").add_to(m)

    bounds = [[u_lat, u_lng]]
    for i, r in enumerate(st.session_state.search, 1):
        bounds.append([r["lat"], r["lng"]])
        folium.Marker(
            [r["lat"], r["lng"]],
            tooltip=f"{i}. {r['name']} ({r['dist']:.2f} km)",
            icon=folium.Icon(color="orange"),
        ).add_to(m)

        folium.Marker(
            [r["lat"], r["lng"]],
            icon=folium.DivIcon(html=f"<div style='background:white;border:2px solid orange;border-radius:50%;width:24px;height:24px;text-align:center;font-weight:bold'>{i}</div>")
        ).add_to(m)

    if len(bounds) > 1:
        m.fit_bounds(bounds)

    st_folium(m, height=400)

    # 決策區
    if st.session_state.search:
        opts = [f"{i+1}. {r['name']}（{r['dist']:.2f} km）"
                for i, r in enumerate(st.session_state.search)]

        choice = st.radio("你實際會去哪一家？", opts,
                          index=st.session_state.decision)

        idx = int(choice.split(".")[0]) - 1
        st.session_state.decision = idx
        chosen = st.session_state.search[idx]

        if st.button("✅ 確認這個採買地點"):
            st.session_state.stores = [chosen]
            st.success("已加入採買點")

    # 計算交通碳足跡
    if st.session_state.stores:
        ef = st.number_input("交通排放係數（kgCO₂e/km）", value=0.115)
        dist = st.session_state.stores[0]["dist"] * 2
        cf = dist * ef
        st.info(f"來回距離：約 {dist:.2f} km")
        st.success(f"交通碳足跡：約 {cf:.3f} kgCO₂e")

else:
    st.warning("請允許定位")


# =========================
# 總計
# =========================
food_cf = meal.cf.sum()
transport_cf = 0
if st.session_state.stores:
    transport_cf = st.session_state.stores[0]["dist"] * 2 * 0.115

total = food_cf + transport_cf

st.subheader("✅ 總碳足跡")
st.write(f"食材：{food_cf:.3f} kgCO₂e")
st.write(f"交通：{transport_cf:.3f} kgCO₂e")
st.success(f"總計：{total:.3f} kgCO₂e")
