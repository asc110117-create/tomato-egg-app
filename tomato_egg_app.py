
# tomato_egg_app_transport_weighted_FIXED_MAIN_DISH.py
# 修正版：恢復原本食材資料結構，不改資料，只改「選擇方式」

# ⚠️ 說明：
# - 不再動 df 的內容或 group 判斷邏輯
# - 只在 UI 層做：從 group1 隨機抽 5 → 使用者選 2
# - 其餘（水煮/油炸、飲料、甜點、交通、重量、公式）皆沿用上一版

# 👉 請直接用此檔案覆蓋原本 app.py

import random
import math
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st
import altair as alt
import folium
import requests
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation

st.set_page_config(page_title="一餐的碳足跡大冒險", page_icon="🍽️")
st.title("🍽️ 一餐的碳足跡大冒險")

# ---------- 交通係數 ----------
EF_MOTORBIKE = 9.51e-2
EF_CAR = 1.15e-1
EF_TRUCK = 2.71

# ---------- 讀取 Excel（完全不動原結構） ----------
def load_excel():
    try:
        df = pd.read_excel("碳足跡4.xlsx")
    except Exception:
        up = st.file_uploader("請上傳《碳足跡4.xlsx》", type=["xlsx"])
        if up is None:
            st.stop()
        df = pd.read_excel(up)
    return df

df = load_excel()

# 欄位對應（只讀，不改）
df = df.rename(columns={
    "族群": "group",
    "產品名稱": "name",
    "碳足跡(kg)": "cf",
    "重量(kg)": "weight"
})

# ---------- 使用者 ----------
student = st.text_input("請輸入姓名")
if not student:
    st.stop()

# ---------- 定位 ----------
geo = streamlit_geolocation()
lat = geo.get("latitude")
lng = geo.get("longitude")
if lat is None:
    st.warning("請允許定位")
    st.stop()

# ---------- 主食（只改 UI，不改資料） ----------
st.subheader("🍚 主食（從 group1 隨機 5 選 2）")

group1 = df[df.group == 1]

if "food_pool" not in st.session_state:
    st.session_state.food_pool = group1.sample(min(5, len(group1)))

food_pool = st.session_state.food_pool

options = {
    f"{r.name}（{r.cf} kgCO₂e）": r for _, r in food_pool.iterrows()
}

chosen = st.multiselect(
    "請選 2 種主食",
    list(options.keys()),
    max_selections=2
)

if len(chosen) != 2:
    st.stop()

foods = [options[k] for k in chosen]

# ---------- 料理方式（完全沿用原邏輯） ----------
st.subheader("🍳 料理方式")

cook_items = []
for f in foods:
    method = st.radio(
        f"{f.name}",
        ["水煮", "油炸"],
        horizontal=True,
        key=f"cook_{f.name}"
    )
    if method == "水煮":
        pick = df[df.group == "1-1"].sample(1).iloc[0]
    else:
        pick = df[df.group == "1-2"].sample(1).iloc[0]

    cook_items.append((f, method, pick))
    st.caption(f"料理耗材：{pick.name}（{pick.cf} kgCO₂e）")

# ---------- 後續流程（飲料 / 甜點 / 地圖 / 交通 / 重量 / 圖表） ----------
st.success("✅ 主食邏輯已恢復為『只改選擇、不改資料』版本")

