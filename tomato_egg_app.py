# carbon_meal_app.py
# Streamlit 教學版：一餐的碳足跡（主食→料理→飲料→甜點→運輸）
# - 水煮 / 煎炸
# - 走路（不計算）
# - 延噸公里 tkm 計算 + 顯示公式
# - 可讀取 Excel（gCO2e / kgCO2e 混用）
# - 不會因欄位數不同而炸

import streamlit as st
import pandas as pd
import math
import re

st.set_page_config(page_title="一餐的碳足跡", layout="centered")

st.title("🍽 一餐的碳足跡（教學版）")

# ---------- 工具 ----------
def parse_cf_to_kg(v):
    if pd.isna(v):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v) if v < 50 else float(v) / 1000
    s = str(v).lower().replace(" ", "")
    m = re.search(r"([\d\.]+)(kg|g)?", s)
    if not m:
        return 0.0
    num = float(m.group(1))
    unit = m.group(2)
    if unit == "g":
        return num / 1000
    return num

# ---------- 讀資料 ----------
@st.cache_data
def load_data():
    df = pd.read_excel("產品碳足跡3.xlsx")
    df = df.iloc[:, :4]
    df.columns = ["code", "name", "cf_raw", "unit"]
    df["cf_kg"] = df["cf_raw"].apply(parse_cf_to_kg)

    if "weight" not in df.columns:
        df["weight"] = 0.0

    return df

df = load_data()

# ---------- 主食 ----------
st.header("① 主食")
foods = df[df["code"] == "1"]
selected_foods = st.multiselect(
    "選擇主食（可多選）",
    foods["name"].tolist(),
)

food_df = foods[foods["name"].isin(selected_foods)]
food_cf = food_df["cf_kg"].sum()
food_weight = food_df["weight"].sum() / 1000  # g → ton

# ---------- 料理 ----------
st.header("② 料理方式（水煮 / 煎炸）")
cook_cf = 0.0
for _, row in food_df.iterrows():
    method = st.radio(
        f"{row['name']} 的料理方式",
        ["水煮", "煎炸"],
        horizontal=True,
        key=row["name"]
    )
    if method == "煎炸":
        cook_cf += 0.02  # 教學示意用

# ---------- 飲料 ----------
st.header("③ 飲料")
drink = st.radio("是否喝飲料", ["不喝", "喝"], horizontal=True)
drink_cf = 0.1 if drink == "喝" else 0.0

# ---------- 甜點 ----------
st.header("④ 甜點（最多 2 種）")
desserts = df[df["code"] == "3"]
dessert_sel = st.multiselect(
    "選擇甜點",
    desserts["name"].tolist(),
    max_selections=2
)
dessert_cf = desserts[desserts["name"].isin(dessert_sel)]["cf_kg"].sum()

# ---------- 運輸 ----------
st.header("⑤ 運輸（延噸公里）")
mode = st.radio("交通方式", ["走路", "貨車"], horizontal=True)

transport_cf = 0.0
formula_text = ""

if mode == "貨車":
    distance = st.number_input("距離 (km)", min_value=0.0, value=12.0)
    tkm_factor = st.number_input("tkm 係數 (kgCO₂e / tkm)", value=2.71)
    transport_cf = distance * food_weight * tkm_factor
    formula_text = f"""
    **碳足跡公式：**  
    距離 × 貨物重量(噸) × tkm係數  
    `{distance} × {food_weight:.4f} × {tkm_factor} = {transport_cf:.3f} kgCO₂e`
    """
else:
    st.info("走路 → 不計算碳足跡")

# ---------- 總結 ----------
total = food_cf + cook_cf + drink_cf + dessert_cf + transport_cf

st.markdown("---")
st.subheader("✅ 總碳足跡")

st.markdown(f"""
- 主食：{food_cf:.3f} kgCO₂e  
- 料理：{cook_cf:.3f} kgCO₂e  
- 飲料：{drink_cf:.3f} kgCO₂e  
- 甜點：{dessert_cf:.3f} kgCO₂e  
- 運輸：{transport_cf:.3f} kgCO₂e  

### 🌍 **總計：{total:.3f} kgCO₂e**
""")

if formula_text:
    st.markdown(formula_text)
