
# tomato_egg_app_v3.py
# 一餐的碳足跡大冒險（穩定版 v3）
# - 不再硬編碼 Excel 路徑，避免 FileNotFoundError
# - 支援上傳【碳足跡4.xlsx】
# - 主食可更換
# - 水煮 / 油炸 對應 group 1-2 / 1-1
# - 飲料 group2、甜點 group3
# - 可下載 CSV

import streamlit as st
import pandas as pd
import random

st.set_page_config(page_title="一餐的碳足跡大冒險", layout="centered")
st.title("🍽️ 一餐的碳足跡大冒險")

@st.cache_data
def load_excel(file):
    df = pd.read_excel(file)
    df.columns = ["group", "name", "cf_kg"]
    df["group"] = df["group"].astype(str)
    df["cf_kg"] = pd.to_numeric(df["cf_kg"], errors="coerce")
    return df.dropna(subset=["cf_kg"])

st.subheader("📂 上傳資料檔案（碳足跡4.xlsx）")
uploaded = st.file_uploader("請上傳 Excel", type=["xlsx"])

if uploaded is None:
    st.warning("請先上傳 Excel 檔案")
    st.stop()

df = load_excel(uploaded)

food_df = df[df["group"] == "1"]
oil_df = df[df["group"] == "1-1"]
water_df = df[df["group"] == "1-2"]
drink_df = df[df["group"] == "2"]
dessert_df = df[df["group"] == "3"]

st.subheader("👤 使用者")
student = st.text_input("請輸入你的名字")

st.subheader("🍚 主食（3 道）")
if "meal" not in st.session_state:
    st.session_state.meal = food_df.sample(min(3, len(food_df)))

if st.button("🔄 更換主食"):
    st.session_state.meal = food_df.sample(min(3, len(food_df)))

meal = st.session_state.meal.reset_index(drop=True)
st.dataframe(meal[["name", "cf_kg"]])

food_cf = meal["cf_kg"].sum()

st.subheader("🍳 料理方式")
cook_cf = 0
for i, row in meal.iterrows():
    method = st.radio(
        f"{row['name']} 的料理方式",
        ["水煮", "油炸"],
        key=f"cook_{i}",
        horizontal=True,
    )
    if method == "水煮" and len(water_df) > 0:
        pick = water_df.sample(1).iloc[0]
    elif method == "油炸" and len(oil_df) > 0:
        pick = oil_df.sample(1).iloc[0]
    else:
        pick = None

    if pick is not None:
        cook_cf += pick["cf_kg"]
        st.caption(f"→ 使用：{pick['name']}（{pick['cf_kg']} kgCO₂e）")

st.subheader("🥤 飲料")
drink_cf = 0
drink_opts = ["不喝"] + [
    f"{r['name']}（{r['cf_kg']} kgCO₂e）" for _, r in drink_df.iterrows()
]
drink_choice = st.selectbox("選擇飲料", drink_opts)
if drink_choice != "不喝":
    idx = drink_opts.index(drink_choice) - 1
    drink_cf = drink_df.iloc[idx]["cf_kg"]

st.subheader("🍰 甜點")
dessert_cf = 0
dessert_opts = [
    f"{r['name']}（{r['cf_kg']} kgCO₂e）" for _, r in dessert_df.iterrows()
]
dessert_choice = st.multiselect("選擇甜點", dessert_opts)
for d in dessert_choice:
    idx = dessert_opts.index(d)
    dessert_cf += dessert_df.iloc[idx]["cf_kg"]

total = food_cf + cook_cf + drink_cf + dessert_cf

st.subheader("✅ 總碳足跡")
st.success(f"{total:.2f} kgCO₂e")

result = pd.DataFrame([{
    "student": student,
    "food": food_cf,
    "cooking": cook_cf,
    "drink": drink_cf,
    "dessert": dessert_cf,
    "total": total
}])

st.download_button(
    "⬇️ 下載 CSV",
    data=result.to_csv(index=False).encode("utf-8-sig"),
    file_name="carbon_result.csv",
    mime="text/csv"
)
