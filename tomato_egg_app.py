
# carbon_meal_app_COMPLETE.py
# 單頁版｜含主食、水煮/油炸、飲料、甜點、地圖選分店、延噸公里運輸、圖表、寫回 Google Sheet

import streamlit as st
import pandas as pd
import random
import math
import altair as alt
import folium
from streamlit_folium import st_folium
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# =====================
# 基本設定
# =====================
st.set_page_config(page_title="一餐的碳足跡（FINAL）", layout="centered")
st.title("🍱 一餐的碳足跡（FINAL）")

# =====================
# 讀取資料（安全版）
# =====================
@st.cache_data
def load_data():
    df = pd.read_excel("產品碳足跡3.xlsx")
    # 至少取前 4 欄，多的忽略
    df = df.iloc[:, :5]
    cols = ["code", "name", "cf", "unit", "weight"][: len(df.columns)]
    df.columns = cols
    if "weight" not in df.columns:
        df["weight"] = 0.0
    return df

df = load_data()

# 分類
food_df = df[df["code"] == "1"]
oil_df = df[df["code"] == "1-1"]
water_df = df[df["code"] == "1-2"]
drink_df = df[df["code"] == "2"]
dessert_df = df[df["code"] == "3"]

# =====================
# 學生資訊
# =====================
st.subheader("👩‍🎓 學生資訊")
student_name = st.text_input("姓名（必填）")
round_tag = st.radio("測驗次數", ["第一次測試", "第二次測試"], horizontal=True)

# =====================
# 主食
# =====================
st.subheader("① 主食（抽 3 項）")
meal = food_df.sample(n=3, replace=False).reset_index(drop=True)
st.write(meal[["name", "cf"]])

cook_cf_total = 0.0
cook_detail = []

st.subheader("② 料理方式（每項）")
for i, row in meal.iterrows():
    choice = st.radio(
        f"{row['name']} 的料理方式",
        ["水煮", "油炸"],
        key=f"cook_{i}",
        horizontal=True,
    )
    if choice == "水煮" and not water_df.empty:
        pick = water_df.sample(1).iloc[0]
    elif choice == "油炸" and not oil_df.empty:
        pick = oil_df.sample(1).iloc[0]
    else:
        pick = None

    if pick is not None:
        cook_cf_total += float(pick["cf"])
        cook_detail.append(pick["name"])

# =====================
# 飲料
# =====================
st.subheader("③ 飲料")
drink_cf = 0.0
drink_name = "不喝"
if st.checkbox("我要飲料"):
    d = drink_df.sample(1).iloc[0]
    drink_cf = float(d["cf"])
    drink_name = d["name"]
    st.info(f"{drink_name}：{drink_cf} kgCO₂e")

# =====================
# 甜點
# =====================
st.subheader("④ 甜點（選 2）")
dessert_pick = st.multiselect(
    "選擇甜點",
    dessert_df["name"].tolist(),
    max_selections=2,
)
dessert_cf = dessert_df[dessert_df["name"].isin(dessert_pick)]["cf"].sum()

# =====================
# 運輸（地圖＋延噸公里）
# =====================
st.subheader("⑤ 運輸（地圖選分店）")

transport_mode = st.radio("交通方式", ["走路", "汽車"], horizontal=True)

m = folium.Map(location=[24.15, 120.67], zoom_start=13)
m_state = st_folium(m, height=300)

transport_cf = 0.0
formula_text = ""

if transport_mode != "走路" and m_state.get("last_clicked"):
    lat = m_state["last_clicked"]["lat"]
    lng = m_state["last_clicked"]["lng"]

    # 假設距離（km）
    distance_km = 12
    total_weight_ton = meal["weight"].sum() / 1000
    tkm_factor = 2.71

    transport_cf = distance_km * total_weight_ton * tkm_factor
    formula_text = f"{distance_km} × {total_weight_ton:.4f} × {tkm_factor} = {transport_cf:.3f} kgCO₂e"

# =====================
# 總計
# =====================
food_cf = meal["cf"].sum()
total = food_cf + cook_cf_total + drink_cf + dessert_cf + transport_cf

st.subheader("✅ 計算結果")
st.markdown(f"""
- 主食：{food_cf:.3f}
- 料理：{cook_cf_total:.3f}
- 飲料：{drink_cf:.3f}
- 甜點：{dessert_cf:.3f}
- 運輸：{transport_cf:.3f}
- **總計：{total:.3f} kgCO₂e**
""")

if formula_text:
    st.caption("運輸計算公式：" + formula_text)

# =====================
# 圖表
# =====================
chart_df = pd.DataFrame([
    {"item": "主食", "kg": food_cf},
    {"item": "料理", "kg": cook_cf_total},
    {"item": "飲料", "kg": drink_cf},
    {"item": "甜點", "kg": dessert_cf},
    {"item": "運輸", "kg": transport_cf},
])

bar = alt.Chart(chart_df).mark_bar().encode(
    x="item",
    y="kg"
)
pie = alt.Chart(chart_df).mark_arc().encode(
    theta="kg",
    color="item"
)

st.altair_chart(bar, use_container_width=True)
st.altair_chart(pie, use_container_width=True)

# =====================
# Google Sheet
# =====================
if "gcp_service_account" in st.secrets:
    if st.button("📤 寫回老師 Google Sheet"):
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(st.secrets["google_sheet"]["spreadsheet_id"])
        ws = sh.sheet1
        ws.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            student_name,
            round_tag,
            total,
        ])
        st.success("已寫入 Google Sheet")
