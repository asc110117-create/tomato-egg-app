
# tomato_egg_app_auto_round.py
# 說明：
# 1. 自動判斷第幾次測試（依 student_name + Google Sheet 已存在次數）
# 2. 保留圖表、CSV 下載、Google Sheet 寫入
# 3. 若 Google Sheet 不可用，仍可正常跑完整流程
#
# ⚠️ 這是「示範完整版骨架」，你可以直接覆蓋原本 tomato_egg_app.py 使用

import streamlit as st
import pandas as pd
from datetime import datetime
import altair as alt

# =========================
# Google Sheet utilities
# =========================
def get_gspread_client():
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)


def get_test_round(student_name: str) -> str:
    """依 Google Sheet 內該學生出現次數，自動判斷第幾次測試"""
    try:
        gc = get_gspread_client()
        sheet_id = st.secrets["google_sheet"]["spreadsheet_id"]
        ws_name = st.secrets["google_sheet"]["worksheet_name"]

        sh = gc.open_by_key(sheet_id)
        ws = sh.worksheet(ws_name)

        records = ws.get_all_records()
        df = pd.DataFrame(records)

        if "student_name" not in df.columns:
            return "第一次測試"

        count = (df["student_name"] == student_name).sum()
        return f"第{count + 1}次測試"

    except Exception:
        return "第一次測試"


def append_to_sheet(row: dict):
    gc = get_gspread_client()
    sheet_id = st.secrets["google_sheet"]["spreadsheet_id"]
    ws_name = st.secrets["google_sheet"]["worksheet_name"]

    sh = gc.open_by_key(sheet_id)
    ws = sh.worksheet(ws_name)

    if not ws.get_all_values():
        ws.append_row(list(row.keys()))

    ws.append_row(list(row.values()))


# =========================
# UI
# =========================
st.set_page_config(page_title="一餐的碳足跡計算（教學版）", page_icon="🍅")

st.title("🍅🥚 一餐的碳足跡計算（教學版）")

student_name = st.text_input("請輸入姓名")

if student_name:
    test_round = get_test_round(student_name)
    st.info(f"系統判斷：**{test_round}**")

    # 假資料（你可以接回原本完整計算結果）
    food = 1.2
    drink = 0.5
    transport = 1.3

    total = food + drink + transport

    df_chart = pd.DataFrame(
        {
            "category": ["Food", "Drink", "Transport"],
            "kgCO2e": [food, drink, transport],
        }
    )

    st.subheader("📊 碳足跡分布圖")
    bar = (
        alt.Chart(df_chart)
        .mark_bar()
        .encode(x="kgCO2e:Q", y="category:N")
    )
    pie = (
        alt.Chart(df_chart)
        .mark_arc()
        .encode(theta="kgCO2e:Q", color="category:N")
    )

    st.altair_chart(bar, use_container_width=True)
    st.altair_chart(pie, use_container_width=True)

    st.subheader("✅ 計算結果")
    st.write(f"學生姓名：{student_name}")
    st.write(f"測試次數：{test_round}")
    st.write(f"總碳排：{total:.2f} kgCO₂e")

    row = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "student_name": student_name,
        "test_round": test_round,
        "total_kgco2e": total,
        "food_kgco2e": food,
        "drink_kgco2e": drink,
        "transport_kgco2e": transport,
    }

    # CSV 下載
    csv = pd.DataFrame([row]).to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ 下載個人結果",
        data=csv,
        file_name=f"{student_name}_{test_round}.csv",
        mime="text/csv",
    )

    # Google Sheet
    if st.button("📤 寫入全班 Google Sheet"):
        try:
            append_to_sheet(row)
            st.success("已成功寫入 Google Sheet")
        except Exception as e:
            st.error("寫入失敗")
            st.exception(e)
