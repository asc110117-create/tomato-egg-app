
# tomato_egg_app_with_charts_and_round.py
# -------------------------------------
# 重點功能：
# 1. 保留並顯示圓餅圖、長條圖
# 2. 將「一開始輸入的名字 student_name」寫入結果
# 3. 新增 test_round（第一次測試 / 第二次測試）欄位
# 4. 使用 spreadsheet_id + open_by_key（不需 Drive API）

import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials


# =========================
# Google Sheet helper
# =========================
def get_gspread_client():
    creds_dict = dict(st.secrets["gcp_service_account"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)


def append_row_to_sheet(row: dict):
    gc = get_gspread_client()
    sh = gc.open_by_key(st.secrets["google_sheet"]["spreadsheet_id"])
    ws = sh.worksheet(st.secrets["google_sheet"]["worksheet_name"])

    existing = ws.get_all_values()
    if not existing:
        ws.append_row(list(row.keys()))

    ws.append_row(list(row.values()))


# =========================
# Session state
# =========================
st.session_state.setdefault("student_name", "")
st.session_state.setdefault("test_round", "第一次測試")


# =========================
# UI：基本資料
# =========================
st.title("🍅🥚 一餐的碳足跡計算（教學版）")

st.subheader("👤 基本資料")

st.session_state.student_name = st.text_input(
    "請輸入你的名字",
    value=st.session_state.student_name,
)

st.session_state.test_round = st.radio(
    "這是第幾次測試？",
    ["第一次測試", "第二次測試"],
    horizontal=True,
)


# =========================
# 假資料（示範用，可換成你原本計算結果）
# =========================
food = 1.2
drink = 0.4
transport = 0.8
dessert = 0.6

total = food + drink + transport + dessert


# =========================
# 圖表資料
# =========================
chart_df = pd.DataFrame(
    [
        {"category": "Food", "kgCO2e": food},
        {"category": "Drink", "kgCO2e": drink},
        {"category": "Transport", "kgCO2e": transport},
        {"category": "Dessert", "kgCO2e": dessert},
    ]
)

chart_df["percent"] = chart_df["kgCO2e"] / chart_df["kgCO2e"].sum()


# =========================
# 顯示圖表
# =========================
st.subheader("📊 碳足跡分布圖")

bar = (
    alt.Chart(chart_df)
    .mark_bar()
    .encode(
        y=alt.Y("category:N", sort="-x", title=""),
        x=alt.X("kgCO2e:Q", title="kg CO₂e"),
        tooltip=["category", "kgCO2e"],
    )
)

pie = (
    alt.Chart(chart_df)
    .mark_arc()
    .encode(
        theta="kgCO2e:Q",
        color="category:N",
        tooltip=["category", "kgCO2e"],
    )
)

st.altair_chart(bar, use_container_width=True)
st.altair_chart(pie, use_container_width=True)


# =========================
# 結果顯示
# =========================
st.subheader("✅ 計算結果")

st.markdown(f"""
- **學生姓名**：{st.session_state.student_name}
- **測試次數**：{st.session_state.test_round}
- **總碳足跡**：**{total:.2f} kgCO₂e**
""")


# =========================
# 寫入 Google Sheet
# =========================
st.subheader("🧾 寫入全班 Google Sheet")

if st.button("📤 送出結果"):
    row = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "student_name": st.session_state.student_name,
        "test_round": st.session_state.test_round,
        "food_kgco2e": food,
        "drink_kgco2e": drink,
        "transport_kgco2e": transport,
        "dessert_kgco2e": dessert,
        "total_kgco2e": total,
    }

    append_row_to_sheet(row)
    st.success("✅ 已成功寫入 Google Sheet！")


# =========================
# CSV 下載
# =========================
st.subheader("⬇️ 下載個人結果")

csv = pd.DataFrame([row]).to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "下載 CSV",
    data=csv,
    file_name=f"{st.session_state.student_name}_{st.session_state.test_round}.csv",
    mime="text/csv",
)
