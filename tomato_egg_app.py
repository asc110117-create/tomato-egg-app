
# carbon_meal_app_FINAL_FIXED.py
# 重點修正：
# 1) 水煮 → 使用 code = "1-2" 的碳足跡資料
# 2) 油炸 → 使用 code = "1-1" 的碳足跡資料
# 3) 每一道主食都會各自計入其對應的料理方式碳足跡

import streamlit as st
import pandas as pd

st.set_page_config(page_title="一餐的碳足跡（FINAL）", layout="centered")

@st.cache_data
def load_data():
    df = pd.read_excel("產品碳足跡3.xlsx")
    df = df.iloc[:, :5]
    df.columns = ["code","name","cf","unit","weight"]
    return df

df = load_data()

st.title("🍽 一餐的碳足跡（FINAL）")

# --------------------
# 學生資訊
# --------------------
student = st.text_input("學生姓名")

# --------------------
# 主食（code = 1）
# --------------------
st.header("① 主食")
foods = df[df["code"]=="1"]
selected_foods = st.multiselect(
    "選擇主食（可複選）",
    foods["name"].tolist()
)

# --------------------
# 料理方式（1-1 / 1-2）
# --------------------
st.header("② 料理方式（逐項）")

oil_df = df[df["code"]=="1-1"]
water_df = df[df["code"]=="1-2"]

cook_results = []
cook_cf_total = 0

for food in selected_foods:
    st.subheader(food)

    method = st.radio(
        f"{food} 的料理方式",
        ["水煮","油炸"],
        horizontal=True,
        key=f"cook_{food}"
    )

    if method == "水煮":
        row = water_df.sample(1).iloc[0]
    else:
        row = oil_df.sample(1).iloc[0]

    cf = float(row["cf"])
    cook_cf_total += cf

    cook_results.append({
        "食材": food,
        "料理方式": method,
        "料理碳足跡(kgCO2e)": cf
    })

# --------------------
# 飲料（code = 2）
# --------------------
st.header("③ 飲料")
drink_df = df[df["code"]=="2"]
drink = st.selectbox("選擇飲料", ["不喝"] + drink_df["name"].tolist())

drink_cf = 0
if drink != "不喝":
    drink_cf = float(drink_df[drink_df["name"]==drink]["cf"].iloc[0])

# --------------------
# 甜點（code = 3）
# --------------------
st.header("④ 甜點")
dessert_df = df[df["code"]=="3"]
desserts = st.multiselect("選擇甜點", dessert_df["name"].tolist())
dessert_cf = dessert_df[dessert_df["name"].isin(desserts)]["cf"].astype(float).sum()

# --------------------
# 加總
# --------------------
food_cf = foods[foods["name"].isin(selected_foods)]["cf"].astype(float).sum()
total = food_cf + cook_cf_total + drink_cf + dessert_cf

st.header("✅ 計算結果")

st.write(f"主食碳足跡：{food_cf:.3f} kgCO₂e")
st.write(f"料理方式碳足跡：{cook_cf_total:.3f} kgCO₂e")
st.write(f"飲料碳足跡：{drink_cf:.3f} kgCO₂e")
st.write(f"甜點碳足跡：{dessert_cf:.3f} kgCO₂e")

st.success(f"🌍 總碳足跡：{total:.3f} kgCO₂e")

if cook_results:
    st.subheader("料理方式明細")
    st.dataframe(pd.DataFrame(cook_results))
