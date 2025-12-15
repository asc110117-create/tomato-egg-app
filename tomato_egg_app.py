# app.py
import re
import random
import math
import datetime
import os
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
    page_title="一餐的碳足跡大冒險",
    page_icon="🍽️",
    layout="centered",
)

APP_TITLE = "🍽️ 一餐的碳足跡大冒險"
EXCEL_PATH = "產品碳足跡3.xlsx"

VALID_IDS = {
    "BEE114105黃文瑜": {"name": "文瑜"},
    "BEE114108陳依萱": {"name": "依萱"},
}

# =========================
# 工具函式
# =========================
def parse_cf_to_kg(v):
    if pd.isna(v):
        return None
    s = str(v).lower()
    m = re.search(r"[-+]?\d*\.?\d+", s)
    if not m:
        return None
    num = float(m.group())
    if "g" in s and "kg" not in s:
        return num / 1000
    return num


def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def search_nearby(q, lat, lng, radius_km=5):
    lat_d = radius_km / 111
    lng_d = radius_km / (111 * max(0.2, math.cos(math.radians(lat))))
    viewbox = f"{lng-lng_d},{lat+lat_d},{lng+lng_d},{lat-lat_d}"

    r = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={
            "q": q,
            "format": "jsonv2",
            "limit": 50,
            "viewbox": viewbox,
            "bounded": 1,
        },
        headers={"User-Agent": "edu-carbon-app"},
        timeout=10,
    )
    r.raise_for_status()
    out = []
    for x in r.json():
        out.append({
            "name": x["display_name"].split(",")[0],
            "lat": float(x["lat"]),
            "lng": float(x["lon"]),
        })
    return out


def save_result(name, total, detail):
    row = {
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "name": name,
        "total": round(total, 3),
        **detail,
    }
    df = pd.DataFrame([row])
    path = "results.csv"
    if os.path.exists(path):
        df.to_csv(path, mode="a", header=False, index=False, encoding="utf-8-sig")
    else:
        df.to_csv(path, index=False, encoding="utf-8-sig")


# =========================
# Session init
# =========================
for k, v in {
    "page": "home",
    "visitor_id": "",
    "origin": None,
    "meal": None,
    "drink": None,
    "stores": [],
    "dessert_pool": None,
}.items():
    st.session_state.setdefault(k, v)


# =========================
# 定位（只呼叫一次）
# =========================
if "geo" not in st.session_state:
    st.session_state.geo = streamlit_geolocation()

geo = st.session_state.geo or {}
if st.session_state.origin is None and geo.get("latitude"):
    st.session_state.origin = {
        "lat": geo["latitude"],
        "lng": geo["longitude"],
    }


# =========================
# 母頁
# =========================
st.title(APP_TITLE)

if st.session_state.page == "home":
    vid = st.text_input("輸入預約號碼（學號＋姓名）")
    if st.button("確認報到"):
        st.session_state.visitor_id = vid.strip()
        st.session_state.page = "main"
        st.rerun()
    st.stop()


# =========================
# 讀 Excel
# =========================
df = pd.read_excel(EXCEL_PATH)
df = df.iloc[:, :4]
df.columns = ["code", "name", "raw_cf", "unit"]
df["code"] = df["code"].astype(str)
df["cf"] = df["raw_cf"].apply(parse_cf_to_kg)
df = df.dropna(subset=["cf"])


# =========================
# 主餐 + 飲料
# =========================
if st.session_state.meal is None:
    st.session_state.meal = df[df.code == "1"].sample(3)

st.subheader("🍛 主餐")
food_cf = st.session_state.meal["cf"].sum()
st.write(st.session_state.meal[["name", "cf"]])

st.subheader("🥤 飲料")
if st.checkbox("我要喝飲料"):
    if st.session_state.drink is None:
        st.session_state.drink = df[df.code == "2"].sample(1).iloc[0]
    drink_cf = st.session_state.drink.cf
    st.info(f"{st.session_state.drink.name}：{drink_cf:.3f}")
else:
    drink_cf = 0.0


# =========================
# 採買交通
# =========================
st.subheader("🧭 採買交通")

if st.session_state.origin:
    q = st.text_input("搜尋附近分店", value="全聯")
    if st.button("搜尋"):
        stores = search_nearby(q, **st.session_state.origin)
        for s in stores:
            s["dist"] = haversine(
                st.session_state.origin["lat"],
                st.session_state.origin["lng"],
                s["lat"], s["lng"]
            )
        st.session_state.search = sorted(stores, key=lambda x: x["dist"])[:5]

    if "search" in st.session_state and st.session_state.search:
        m = folium.Map(
            location=[st.session_state.origin["lat"], st.session_state.origin["lng"]],
            zoom_start=14,
        )
        folium.Marker(
            [st.session_state.origin["lat"], st.session_state.origin["lng"]],
            tooltip="你的位置",
            icon=folium.Icon(color="blue"),
        ).add_to(m)

        for s in st.session_state.search:
            folium.Marker(
                [s["lat"], s["lng"]],
                tooltip=f"{s['name']} ({s['dist']:.2f} km)",
                icon=folium.Icon(color="orange"),
            ).add_to(m)

        st_folium(m, height=350)

        idx = st.selectbox(
            "選擇一家分店",
            range(len(st.session_state.search)),
            format_func=lambda i: st.session_state.search[i]["name"],
        )

        if st.button("確認此分店"):
            st.session_state.stores = [st.session_state.search[idx]]
            st.success("分店已確認")

if st.session_state.stores:
    dist = st.session_state.stores[0]["dist"] * 2
    transport_cf = dist * 0.115
else:
    transport_cf = 0.0


# =========================
# 第一階段總量 + 圖表
# =========================
total1 = food_cf + drink_cf + transport_cf

st.subheader("📊 第一階段碳足跡")

chart1 = pd.DataFrame([
    {"cat": "Food", "v": food_cf},
    {"cat": "Drink", "v": drink_cf},
    {"cat": "Transport", "v": transport_cf},
])

st.altair_chart(
    alt.Chart(chart1)
    .mark_arc()
    .encode(theta="v", color="cat"),
    use_container_width=True,
)


# =========================
# 甜點（完成第一階段才出現）
# =========================
dessert_cf = 0.0
selected = []

if st.session_state.stores:
    st.subheader("🍰 今日甜點（5 選 2）")

    if st.session_state.dessert_pool is None:
        st.session_state.dessert_pool = df[df.code == "3"].sample(5)

    opts = {
        r.name: r.cf for _, r in st.session_state.dessert_pool.iterrows()
    }

    selected = st.multiselect(
        "選 2 種甜點",
        list(opts.keys()),
        max_selections=2,
    )

    dessert_cf = sum(opts[n] for n in selected)


# =========================
# 最終結果 + 儲存
# =========================
total = total1 + dessert_cf

st.subheader("✅ 最終碳足跡")
st.metric("kgCO₂e", round(total, 3))

if selected and st.button("💾 儲存結果"):
    vid = st.session_state.visitor_id
    name = VALID_IDS.get(vid, {}).get("name", vid)

    save_result(
        name,
        total,
        {
            "food": food_cf,
            "drink": drink_cf,
            "transport": transport_cf,
            "dessert": dessert_cf,
        },
    )
    st.success("已儲存完成！")
