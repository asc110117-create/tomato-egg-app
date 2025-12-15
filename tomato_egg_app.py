
# tomato_egg_app_final.py
# Streamlit app: Meal Carbon Footprint
# Features:
# 1) User inputs name at start
# 2) Auto-detect test round number from Google Sheet (count previous entries by name + 1)
# 3) Dessert dropdown shows carbon footprint in parentheses
# 4) Transport mode dropdown shows carbon footprint factor with declared unit
# 5) Calculate transport carbon footprint
# 6) Allow CSV download for the user
# 7) Append results to Google Sheet
#
# requirements.txt:
# streamlit
# pandas
# gspread
# google-auth
# openpyxl
# altair

import streamlit as st
import pandas as pd
from datetime import datetime
import altair as alt

import gspread
from google.oauth2.service_account import Credentials

# ------------------
# Page config
# ------------------
st.set_page_config(page_title="一餐的碳足跡計算", page_icon="🍽️", layout="centered")

# ------------------
# Google Sheet helpers
# ------------------
def get_gspread_client():
    sa_info = dict(st.secrets["gcp_service_account"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
    return gspread.authorize(creds)

def open_worksheet():
    gc = get_gspread_client()
    sheet_id = st.secrets["google_sheet"]["spreadsheet_id"]
    ws_name = st.secrets["google_sheet"]["worksheet_name"]
    sh = gc.open_by_key(sheet_id)
    return sh.worksheet(ws_name)

def get_test_round(user_name: str) -> int:
    """Count how many times this user already exists in the sheet."""
    ws = open_worksheet()
    records = ws.get_all_records()
    if not records:
        return 1
    df = pd.DataFrame(records)
    if "student_name" not in df.columns:
        return 1
    return int((df["student_name"] == user_name).sum()) + 1

def append_to_sheet(row: dict):
    ws = open_worksheet()
    existing = ws.get_all_values()
    if len(existing) == 0:
        ws.append_row(list(row.keys()))
    ws.append_row(list(row.values()))

# ------------------
# Sample data (replace with your Excel-loaded data if needed)
# ------------------
desserts = [
    {"name": "布丁", "cf": 0.35},
    {"name": "蛋糕", "cf": 0.55},
    {"name": "餅乾", "cf": 0.25},
]

transport_modes = [
    {"name": "走路", "factor": 0.0, "unit": "kgCO₂e/km"},
    {"name": "機車", "factor": 0.095, "unit": "kgCO₂e/km"},
    {"name": "汽車", "factor": 0.120, "unit": "kgCO₂e/km"},
]

# ------------------
# UI
# ------------------
st.title("🍽️ 一餐的碳足跡計算")

# 1) User name
student_name = st.text_input("請輸入姓名")
if not student_name:
    st.stop()

# 2) Auto test round
try:
    test_round = get_test_round(student_name)
except Exception:
    test_round = 1

st.info(f"📘 這是 **第 {test_round} 次測試**")

# 3) Dessert selection with CF in label
dessert_labels = [f"{d['name']}（{d['cf']} kgCO₂e）" for d in desserts]
dessert_choice = st.selectbox("選擇甜點", dessert_labels)
dessert_cf = desserts[dessert_labels.index(dessert_choice)]["cf"]

# 4) Transport selection with CF + unit
transport_labels = [
    f"{t['name']}（{t['factor']} {t['unit']}）" for t in transport_modes
]
transport_choice = st.selectbox("交通工具", transport_labels)
transport = transport_modes[transport_labels.index(transport_choice)]

distance_km = st.number_input("交通距離（km）", min_value=0.0, value=5.0, step=0.5)
transport_cf = distance_km * transport["factor"]

# ------------------
# Results
# ------------------
total_cf = dessert_cf + transport_cf

st.subheader("📊 碳足跡結果")
st.write(f"甜點碳足跡：{dessert_cf:.3f} kgCO₂e")
st.write(f"交通碳足跡：{transport_cf:.3f} kgCO₂e")
st.success(f"總碳足跡：{total_cf:.3f} kgCO₂e")

# Chart
chart_df = pd.DataFrame({
    "Category": ["Dessert", "Transport"],
    "kgCO2e": [dessert_cf, transport_cf]
})
chart = alt.Chart(chart_df).mark_bar().encode(
    x="Category",
    y="kgCO2e"
)
st.altair_chart(chart, use_container_width=True)

# ------------------
# CSV + Google Sheet
# ------------------
row = {
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "student_name": student_name,
    "test_round": test_round,
    "dessert": dessert_choice,
    "dessert_kgco2e": dessert_cf,
    "transport_mode": transport["name"],
    "distance_km": distance_km,
    "transport_kgco2e": transport_cf,
    "total_kgco2e": total_cf,
}

df_out = pd.DataFrame([row])

st.download_button(
    "⬇️ 下載 CSV",
    data=df_out.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"{student_name}_round{test_round}.csv",
    mime="text/csv"
)

if st.button("📤 寫入 Google Sheet"):
    try:
        append_to_sheet(row)
        st.success("已成功寫入 Google Sheet")
    except Exception as e:
        st.error("寫入 Google Sheet 失敗")
        st.exception(e)
