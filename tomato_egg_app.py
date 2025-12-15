
# =============================================================
# 🍅🍳 一餐的碳足跡計算（教學完整版）
# - 主餐（抽 3 樣食材）
# - 飲料（可選）
# - 甜點（5 選 2）
# - 餐具 / 包材（可複選）
# - 圖表（長條圖 + 圓餅圖）
# - 自動判斷第幾次測試（同一學生）
# - CSV 下載
# - （可選）寫入 Google Sheet
# =============================================================

import streamlit as st
import pandas as pd
import random
import re
from io import BytesIO
from datetime import datetime

import altair as alt

# =============================================================
# 基本設定
# =============================================================
st.set_page_config(
    page_title="一餐的碳足跡計算（教學版）",
    page_icon="🍅",
    layout="centered"
)

st.title("🍅🍳 一餐的碳足跡計算（教學版）")

# =============================================================
# 工具函式：碳足跡統一轉為 kgCO2e
# =============================================================
def parse_cf_to_kg(value):
    if pd.isna(value):
        return 0.0

    if isinstance(value, (int, float)):
        # 小於 50 視為 kg，大於視為 g
        return value if value <= 50 else value / 1000

    s = str(value).lower().replace(" ", "")
    s = s.replace("kgco2e", "kg").replace("gco2e", "g")

    m = re.search(r"([\d\.]+)(kg|g)?", s)
    if not m:
        return 0.0

    num = float(m.group(1))
    unit = m.group(2)

    if unit == "kg" or (unit is None and num <= 50):
        return num
    else:
        return num / 1000


# =============================================================
# 讀取 Excel
# =============================================================
@st.cache_data
def load_excel(file):
    df = pd.read_excel(file)
    df = df.iloc[:, :4]
    df.columns = ["code", "product_name", "cf_raw", "declared_unit"]
    df["cf_kgco2e"] = df["cf_raw"].apply(parse_cf_to_kg)
    return df


st.subheader("📂 載入碳足跡資料")
uploaded = st.file_uploader("請上傳碳足跡 Excel（產品碳足跡3.xlsx）", type=["xlsx"])

if not uploaded:
    st.stop()

df_all = load_excel(uploaded)

df_food = df_all[df_all["code"] == 1]
df_drink = df_all[df_all["code"] == 2]
df_dessert = df_all[df_all["code"] == 3]
df_packaging = df_all[df_all["code"].astype(str).str.startswith("4")]

# =============================================================
# 基本資料
# =============================================================
st.subheader("👤 基本資料")

student_name = st.text_input("請輸入你的名字")

if "history" not in st.session_state:
    st.session_state.history = []

# 自動判斷第幾次測試
previous = [r for r in st.session_state.history if r["student_name"] == student_name]
test_round = len(previous) + 1 if student_name else None

if student_name:
    st.info(f"📌 這是 **第 {test_round} 次測試**")

# =============================================================
# 主餐（抽 3 樣）
# =============================================================
st.subheader("🍚 主餐（抽 3 樣）")

if st.button("🎲 抽主餐"):
    st.session_state.food_pick = df_food.sample(3)

if "food_pick" not in st.session_state:
    st.session_state.food_pick = df_food.sample(3)

food_df = st.session_state.food_pick
st.dataframe(food_df[["product_name", "cf_kgco2e"]])

food_sum = food_df["cf_kgco2e"].sum()

# =============================================================
# 飲料
# =============================================================
st.subheader("🥤 飲料")

drink_option = st.radio("是否喝飲料？", ["不喝", "隨機一杯"])

drink_cf = 0.0
drink_name = "不喝飲料"

if drink_option == "隨機一杯" and len(df_drink) > 0:
    drink = df_drink.sample(1).iloc[0]
    drink_cf = drink["cf_kgco2e"]
    drink_name = drink["product_name"]
    st.info(f"你喝的是：{drink_name}（{drink_cf:.2f} kgCO₂e）")

# =============================================================
# 甜點（5 選 2）
# =============================================================
st.subheader("🍰 甜點（5 選 2）")

dessert_sum = 0.0
dessert_selected = []

if len(df_dessert) > 0:
    if "dessert_pool" not in st.session_state:
        st.session_state.dessert_pool = df_dessert.sample(min(5, len(df_dessert)))

    options = st.session_state.dessert_pool["product_name"].tolist()
    dessert_selected = st.multiselect("請選 2 種甜點", options)

    if len(dessert_selected) == 2:
        dessert_sum = st.session_state.dessert_pool[
            st.session_state.dessert_pool["product_name"].isin(dessert_selected)
        ]["cf_kgco2e"].sum()

# =============================================================
# 餐具 / 包材
# =============================================================
st.subheader("🍴 餐具 / 包材（可複選）")

packaging_selected = st.multiselect(
    "你使用了哪些？",
    df_packaging["product_name"].tolist()
)

packaging_sum = df_packaging[
    df_packaging["product_name"].isin(packaging_selected)
]["cf_kgco2e"].sum()

# =============================================================
# 結果計算
# =============================================================
total = food_sum + drink_cf + dessert_sum + packaging_sum

st.subheader("✅ 計算結果")
st.markdown(f"""
- 🍚 主餐：{food_sum:.2f} kgCO₂e  
- 🥤 飲料：{drink_cf:.2f} kgCO₂e  
- 🍰 甜點：{dessert_sum:.2f} kgCO₂e  
- 🍴 餐具：{packaging_sum:.2f} kgCO₂e  

### 🌍 **總計：{total:.2f} kgCO₂e**
""")

# =============================================================
# 圖表
# =============================================================
chart_df = pd.DataFrame({
    "category": ["Food", "Drink", "Dessert", "Packaging"],
    "kgCO2e": [food_sum, drink_cf, dessert_sum, packaging_sum]
})
chart_df = chart_df[chart_df["kgCO2e"] > 0]

bar = alt.Chart(chart_df).mark_bar().encode(
    x="kgCO2e:Q",
    y="category:N"
)

pie = alt.Chart(chart_df).mark_arc().encode(
    theta="kgCO2e:Q",
    color="category:N"
)

st.subheader("📊 碳足跡分佈圖")
st.altair_chart(bar, use_container_width=True)
st.altair_chart(pie, use_container_width=True)

# =============================================================
# 儲存結果
# =============================================================
if st.button("💾 儲存結果"):
    row = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "student_name": student_name,
        "test_round": test_round,
        "food_kgco2e": food_sum,
        "drink_kgco2e": drink_cf,
        "dessert_kgco2e": dessert_sum,
        "packaging_kgco2e": packaging_sum,
        "total_kgco2e": total,
    }
    st.session_state.history.append(row)
    st.success("已儲存！")

# =============================================================
# 下載 CSV
# =============================================================
if st.session_state.history:
    df_hist = pd.DataFrame(st.session_state.history)
    csv = df_hist.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        "⬇️ 下載個人結果 CSV",
        data=csv,
        file_name=f"{student_name}_carbon_results.csv",
        mime="text/csv"
    )
