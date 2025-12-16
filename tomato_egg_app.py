
import streamlit as st
import pandas as pd
import random
import math
import requests
from streamlit_geolocation import streamlit_geolocation
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="一餐的碳足跡大冒險", layout="centered")

st.title("🚚 交通碳足跡（修正版一定顯示）")

# ===== 基本工具 =====
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2-lat1)
    dl = math.radians(lon2-lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(a))

# ===== 交通係數（你指定的） =====
TRANSPORT = {
    "走路": {"factor": 0.0, "unit": "kgCO₂e / km"},
    "機車": {"factor": 9.51e-2, "unit": "kgCO₂e / pkm"},
    "汽車": {"factor": 1.15e-1, "unit": "kgCO₂e / pkm"},
    "貨車": {"factor": 2.71, "unit": "kgCO₂e / tkm"},
}

# ===== 取得定位 =====
geo = streamlit_geolocation()
if geo and geo.get("latitude"):
    origin = (geo["latitude"], geo["longitude"])
    st.success(f"📍 已抓到定位：{origin[0]:.4f}, {origin[1]:.4f}")
else:
    st.warning("⚠️ 尚未取得定位，使用預設（台中教育大學）")
    origin = (24.1477, 120.6736)

# ===== 搜尋全聯 =====
def search_pxmart(lat, lon):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": "全聯",
        "format": "json",
        "limit": 5,
        "viewbox": f"{lon-0.03},{lat+0.03},{lon+0.03},{lat-0.03}",
        "bounded": 1
    }
    r = requests.get(url, params=params, headers={"User-Agent": "edu-app"})
    return r.json()

stores = search_pxmart(origin[0], origin[1])

st.subheader("🏪 附近全聯（請點選）")

if stores:
    m = folium.Map(location=origin, zoom_start=14)
    folium.Marker(origin, tooltip="你的位置", icon=folium.Icon(color="blue")).add_to(m)

    for i, s in enumerate(stores):
        folium.Marker(
            (float(s["lat"]), float(s["lon"])),
            tooltip=f"{i+1}. {s['display_name']}"
        ).add_to(m)

    st_folium(m, height=350)

    store_names = [f"{i+1}. {s['display_name']}" for i,s in enumerate(stores)]
    pick = st.selectbox("選擇一間全聯", store_names)

    idx = store_names.index(pick)
    dest = (float(stores[idx]["lat"]), float(stores[idx]["lon"]))

    d_km = haversine(origin[0], origin[1], dest[0], dest[1])
    round_km = d_km * 2

    st.info(f"📏 來回距離：約 {round_km:.2f} km")

    st.subheader("🚦 選擇交通方式（一定顯示）")
    mode = st.radio("交通工具", list(TRANSPORT.keys()))

    if mode == "貨車":
        total_weight_ton = 0.8 / 1000  # 教學用固定值（0.8 kg）
        cf = round_km * total_weight_ton * TRANSPORT[mode]["factor"]
        st.write(f"計算式：{round_km:.2f} × {total_weight_ton:.4f} × {TRANSPORT[mode]['factor']}")
    else:
        cf = round_km * TRANSPORT[mode]["factor"]
        st.write(f"計算式：{round_km:.2f} × {TRANSPORT[mode]['factor']}")

    st.success(f"🚚 交通碳足跡 = **{cf:.3f} kgCO₂e**")

else:
    st.error("找不到附近全聯")
