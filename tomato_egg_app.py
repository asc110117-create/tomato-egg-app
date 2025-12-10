import streamlit as st
import pandas as pd
import random

st.set_page_config(page_title="隨機菜單 + 料理方式（產品碳足跡2）", page_icon="🥗")

# -----------------------------
# 一、讀取 Excel 產品資料
# -----------------------------
@st.cache_data
def load_cf_products(path="產品碳足跡2.xlsx"):
    df = pd.read_excel(path)
    df.columns = ["group", "product_name", "cf_g", "unit"]
    df["cf_kg"] = df["cf_g"] / 1000.0
    return df


# -----------------------------
# UI 主頁
# -----------------------------
st.title("隨機菜單 + 料理方式練習（產品碳足跡2）")

# 讀取 Excel
try:
    df = load_cf_products()
except Exception as e:
    st.error("❌ 無法讀取檔案 `產品碳足跡2.xlsx`，請確認檔案已放在 repo 根目錄。")
    st.exception(e)
    st.stop()

# -----------------------------
# 二、隨機抽三種「食材（group=1）」 
# -----------------------------
df_food = df[df["group"] == "1"].reset_index(drop=True)

if st.button("抽 3 種隨機食材"):
    st.session_state.food_choices = random.sample(list(df_food.index), 3)

if "food_choices" not in st.session_state:
    st.info("請按「抽 3 種隨機食材」開始練習")
    st.stop()

selected_food = df_food.loc[st.session_state.food_choices].reset_index(drop=True)

st.subheader("本次食材（每項 1 份）")
st.table(selected_food[["product_name", "unit", "cf_kg"]])


# -----------------------------
# 三、為每項食材選擇料理方式（煎 / 水煮）
# -----------------------------
st.subheader("選擇每種食材的料理方式")

cooking_method = {}
oil_results = []

df_fry = df[df["group"] == "1-1"].reset_index(drop=True)   # 煎用油
df_boiled = df[df["group"] == "1-2"].reset_index(drop=True)  # 水煮用品

for i, row in selected_food.iterrows():
    st.write(f"### 食材 {i+1}: {row['product_name']}")
    method = st.radio(
        f"選擇料理方式（食材：{row['product_name']}）",
        ["煎", "水煮"],
        key=f"cook_{i}"
    )
    cooking_method[i] = method

    if method == "煎":
        oil_item = df_fry.sample(1).iloc[0]
    else:
        oil_item = df_boiled.sample(1).iloc[0]

    oil_results.append(oil_item)

# 顯示料理方式表格
st.subheader("本次料理方式附加品（油 / 水煮用品）")
oil_df = pd.DataFrame(oil_results)
st.table(oil_df[["group", "product_name", "unit", "cf_kg"]])


# -----------------------------
# 四、計算總碳足跡：食材 + 料理方式
# -----------------------------
total_food_cf = selected_food["cf_kg"].sum()
total_oil_cf = oil_df["cf_kg"].sum()
total_cf = total_food_cf + total_oil_cf

st.subheader("碳足跡計算結果")
st.markdown(f"""
- 食材碳足跡合計：**{total_food_cf:.3f} kgCO₂e**
- 料理方式碳足跡合計：**{total_oil_cf:.3f} kgCO₂e**
- 👉 **總碳足跡：{total_cf:.3f} kgCO₂e**
""")
