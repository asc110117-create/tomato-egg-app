

# tomato_egg_app.py
import streamlit as st
import pandas as pd
import math
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="一餐的碳足跡大冒險", layout="centered")
st.title("🍽️ 一餐的碳足跡大冒險")

def load_excel():
    df = pd.read_excel("產品碳足跡3.xlsx")
    df = df.iloc[:, :4]
    df.columns = ["group","name","cf","unit"]
    df["cf"] = df["cf"].astype(float)
    return df

def sheet_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(st.secrets["google_sheet"]["spreadsheet_id"])
    return sh.worksheet(st.secrets["google_sheet"]["worksheet_name"])

def get_round(student):
    ws = sheet_client()
    rows = ws.get_all_values()
    if len(rows) <= 1:
        return 1
    df = pd.DataFrame(rows[1:], columns=rows[0])
    return df[df["student_name"] == student].shape[0] + 1

df = load_excel()

food_df = df[df.group == "1"]
oil_df = df[df.group == "1-1"]
water_df = df[df.group == "1-2"]
drink_df = df[df.group == "2"]
dessert_df = df[df.group == "3"]

student = st.text_input("請輸入你的名字")
if not student:
    st.stop()

round_no = get_round(student)
st.info(f"這是你第 {round_no} 次測試")

st.header("🍛 主食（3 道）")
meal = food_df.sample(3).reset_index(drop=True)

food_total = meal.cf.sum()
cook_total = 0

for i, r in meal.iterrows():
    st.subheader(r["name"])
    method = st.radio("料理方式", ["水煮","油炸"], key=f"cook_{i}")
    if method == "水煮":
        pick = water_df.sample(1).iloc[0]
    else:
        pick = oil_df.sample(1).iloc[0]
    cook_total += pick.cf
    st.caption(f"{pick.name}：{pick.cf} kgCO₂e / {pick.unit}")

st.header("🥤 飲料")
drink_options = ["不喝"] + [f"{r.name} ({r.cf} kgCO₂e/{r.unit})" for _, r in drink_df.iterrows()]
drink_choice = st.selectbox("選擇飲料", drink_options)
drink_cf = 0 if drink_choice == "不喝" else drink_df.iloc[drink_options.index(drink_choice)-1].cf

st.header("🍰 甜點")
dessert_options = [f"{r.name} ({r.cf} kgCO₂e/{r.unit})" for _, r in dessert_df.iterrows()]
dessert_choice = st.selectbox("選擇甜點", dessert_options)
dessert_cf = dessert_df.iloc[dessert_options.index(dessert_choice)].cf

st.header("🛵 交通")
transport = st.selectbox("交通方式", ["走路","機車","汽車"])
distance = st.number_input("距離(km)", 0.0)
weight = st.number_input("食材重量(kg)", 0.0)

transport_cf = 0
if transport != "走路":
    factor = 2.71 if transport == "機車" else 0.25
    transport_cf = distance * (weight/1000) * factor
    st.caption(f"公式：{distance} × {weight/1000:.4f} × {factor}")

total = food_total + cook_total + drink_cf + dessert_cf + transport_cf
st.metric("總碳足跡", f"{total:.3f} kgCO₂e")

row = {
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "student_name": student,
    "round": round_no,
    "total_kgco2e": total
}

st.download_button(
    "⬇️ 下載 CSV",
    pd.DataFrame([row]).to_csv(index=False).encode("utf-8-sig"),
    file_name=f"{student}_round{round_no}.csv"
)

if st.button("📤 寫入 Google Sheet"):
    ws = sheet_client()
    if len(ws.get_all_values()) == 0:
        ws.append_row(list(row.keys()))
    ws.append_row(list(row.values()))
    st.success("已寫入 Google Sheet")
