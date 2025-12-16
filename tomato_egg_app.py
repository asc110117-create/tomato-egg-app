
import random
import pandas as pd
import streamlit as st
from io import BytesIO
import matplotlib.pyplot as plt
import seaborn as sns
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2 import service_account

# Streamlit 設置
st.set_page_config(page_title="一餐的碳足跡大冒險", layout="centered")
st.title("🍽️ 一餐的碳足跡大冒險")

# -----------------------------
# Helper Functions
# -----------------------------
def require_cols(df):
    cols = ["族群", "產品名稱", "碳足跡(kg)"]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        st.error(f"Excel 缺少必要欄位：{missing}")
        st.stop()
    return df[cols].copy()

def label_with_cf(row):
    return f"{row['產品名稱']} ({row['碳足跡(kg)']:.3f} kgCO₂e)"

def create_pie_chart(data, labels):
    fig, ax = plt.subplots()
    ax.pie(data, labels=labels, autopct='%1.1f%%', startangle=90)
    ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
    st.pyplot(fig)

def create_bar_chart(df, title):
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(x='產品名稱', y='碳足跡(kg)', data=df, ax=ax)
    ax.set_title(title)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
    st.pyplot(fig)

# -----------------------------
# Google Sheets Integration
# -----------------------------
def append_result_to_google_sheet(row):
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["google_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    service = build("sheets", "v4", credentials=credentials)
    sheet_id = st.secrets["google_sheet_id"]
    range_name = "Sheet1!A1"
    values = [[
        row['timestamp'],
        row['student_name'],
        row['visitor_id'],
        row['device_id'],
        row['total_kgco2e'],
        row['food_kgco2e'],
        row['cooking_kgco2e'],
        row['drink_name'],
        row['drink_kgCO2e'],
        row['dessert_selected'],
        row['packaging_selected']
    ]]
    body = {'values': values}
    service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=range_name,
        valueInputOption="RAW",
        body=body
    ).execute()

# -----------------------------
# Upload Excel
# -----------------------------
up = st.file_uploader("請上傳《產品碳足跡4.xlsx》", type=["xlsx"])
if up is None:
    st.stop()

df = pd.read_excel(BytesIO(up.getvalue()))
df = require_cols(df)
df["碳足跡(kg)"] = pd.to_numeric(df["碳足跡(kg)"], errors="coerce").fillna(0.0)

# Split groups
g1 = df[df["族群"] == 1].reset_index(drop=True)      # 主食
g11 = df[df["族群"] == "1-1"].reset_index(drop=True) # 油品
g12 = df[df["族群"] == "1-2"].reset_index(drop=True) # 礦泉水
g2 = df[df["族群"] == 2].reset_index(drop=True)      # 飲料

if len(g1) == 0:
    st.error("找不到 主食（族群=1）")
    st.stop()

# -----------------------------
# Session State Initialization
# -----------------------------
st.session_state.setdefault("pool", None)
st.session_state.setdefault("picked", [])
st.session_state.setdefault("cook_choice", {})  # idx -> '水煮'/'油炸'
st.session_state.setdefault("cook_item", {})    # idx -> row
st.session_state.setdefault("drink", None)

# -----------------------------
# Main Dish (Random 5 choose 2)
# -----------------------------
st.header("🍚 主食（隨機 5 選 2）")

if st.button("🎲 重新抽 5 種主食"):
    st.session_state.pool = g1.sample(n=min(5, len(g1)), replace=False).reset_index(drop=True)
    st.session_state.picked = []
    st.session_state.cook_choice = {}
    st.session_state.cook_item = {}

if st.session_state.pool is None:
    st.session_state.pool = g1.sample(n=min(5, len(g1)), replace=False).reset_index(drop=True)

pool = st.session_state.pool
options = pool.apply(label_with_cf, axis=1).tolist()

picked_labels = st.multiselect("請選 2 種主食", options=options, max_selections=2)
st.session_state.picked = picked_labels

picked_rows = []
for lbl in picked_labels:
    name = lbl.split(" (")[0]
    picked_rows.append(pool[pool["產品名稱"] == name].iloc[0])

# -----------------------------
# Cooking choice per dish
# -----------------------------
st.subheader("🍳 料理方式（每道）")
cook_sum = 0.0
food_sum = 0.0

for i, row in enumerate(picked_rows):
    food_sum += float(row["碳足跡(kg)"])
    c = st.radio(
        f"{row['產品名稱']}（{row['碳足跡(kg)']:.3f} kgCO₂e）",
        ["水煮（用礦泉水）", "油炸（用油品）"],
        key=f"cook_{i}",
        horizontal=True
    )
    st.session_state.cook_choice[i] = c

    if "水煮" in c:
        if len(g12) == 0:
            st.warning("沒有礦泉水（族群=1-2）")
            continue
        pick = g12.sample(1).iloc[0]
    else:
        if len(g11) == 0:
            st.warning("沒有油品（族群=1-1）")
            continue
        pick = g11.sample(1).iloc[0]

    st.session_state.cook_item[i] = pick
    cook_sum += float(pick["碳足跡(kg)"])
    st.caption(f"料理耗材：{pick['產品名稱']}（{pick['碳足跡(kg)']:.3f} kgCO₂e）")

# -----------------------------
# Drink (group2)
# -----------------------------
st.header("🥤 飲料")
drink_cf = 0.0
drink_name = "不喝"

if len(g2) > 0:
    drink_opts = ["不喝"] + g2.apply(label_with_cf, axis=1).tolist()
    choice = st.selectbox("選擇飲料", drink_opts)
    if choice != "不喝":
        name = choice.split(" (")[0]
        drow = g2[g2["產品名稱"] == name].iloc[0]
        drink_cf = float(drow["碳足跡(kg)"])
        drink_name = name
        st.info(f"飲料：{drink_name}（{drink_cf:.3f} kgCO₂e）")

# -----------------------------
# Summary
# -----------------------------
st.divider()
total = food_sum + cook_sum + drink_cf
st.subheader("✅ 本餐小結")
st.write({
    "主食合計(kgCO₂e)": round(food_sum, 3),
    "料理合計(kgCO₂e)": round(cook_sum, 3),
    "飲料(kgCO₂e)": round(drink_cf, 3),
    "總計(kgCO₂e)": round(total, 3),
})

# -----------------------------
# Charts (Pie and Bar)
# -----------------------------
create_pie_chart([food_sum, cook_sum, drink_cf], ["主食", "料理", "飲料"])
create_bar_chart(pd.DataFrame({
    "產品名稱": ["主食", "料理", "飲料"],
    "碳足跡(kg)": [food_sum, cook_sum, drink_cf]
}), "各項碳足跡長條圖")

# -----------------------------
# Download CSV
# -----------------------------
row = {
    "food_sum_kgCO2e": round(food_sum, 6),
    "cooking_sum_kgCO2e": round(cook_sum, 6),
    "drink_name": drink_name,
    "drink_kgCO2e": round(drink_cf, 6),
    "total_kgCO2e": round(total, 6),
}

st.download_button(
    "⬇️ 下載本次結果 CSV",
    data=pd.DataFrame([row]).to_csv(index=False).encode("utf-8-sig"),
    file_name="meal_result.csv",
    mime="text/csv",
    use_container_width=True,
)

# -----------------------------
# Google Sheets Integration
# -----------------------------
if st.button("📤 送出並寫入 Google Sheet（全班彙整）", use_container_width=True):
    try:
        append_result_to_google_sheet(row)
        st.success("✅ 已成功寫入 Google Sheet（回去刷新試算表）")
    except Exception as e:
        st.error("寫入失敗：請檢查 ①服務帳戶是否已被共用為「編輯者」 ② spreadsheet_id / worksheet_name 是否正確 ③ Sheets API 是否已啟用。")
        st.exception(e)
