# tomato_egg_app_v6_COLUMN_SAFE.py
# 自動辨識欄位名稱（避免 KeyError: 'cf'）

import streamlit as st
import pandas as pd
import random

st.set_page_config(page_title="一餐的碳足跡大冒險", layout="centered")
st.title("🍽️ 一餐的碳足跡大冒險")

# =======================
# 1. 上傳 Excel
# =======================
uploaded = st.file_uploader("請上傳《碳足跡4.xlsx》", type=["xlsx"])
if uploaded is None:
    st.stop()

df = pd.read_excel(uploaded)

# =======================
# 2. 欄位安全處理
# =======================
# 嘗試常見欄位名稱對應
col_map = {}
for c in df.columns:
    c_low = c.lower()
    if c_low in ["group", "群組", "分類"]:
        col_map[c] = "group"
    elif c_low in ["name", "品名", "產品名稱"]:
        col_map[c] = "name"
    elif c_low in ["cf", "碳足跡", "carbon", "co2e"]:
        col_map[c] = "cf"

df = df.rename(columns=col_map)

required = {"group", "name", "cf"}
if not required.issubset(df.columns):
    st.error("Excel 欄位無法對應，請確認至少有：group / name / cf")
    st.write("目前欄位：", list(df.columns))
    st.stop()

df["cf"] = pd.to_numeric(df["cf"], errors="coerce")
df = df.dropna(subset=["cf"])

# =======================
# 3. 主食 5 選 2
# =======================
st.header("🍚 主食（隨機 5 選 2）")

food_df = df[df["group"] == "1"]
water_df = df[df["group"] == "1-1"]
oil_df = df[df["group"] == "1-2"]

if len(food_df) < 2:
    st.error("group=1 的主食資料不足")
    st.stop()

food_pool = food_df.sample(n=min(5, len(food_df)), random_state=random.randint(1,9999))

options = {
    f'{r["name"]}（{r["cf"]:.3f} kgCO₂e）': r
    for _, r in food_pool.iterrows()
}

selected = st.multiselect("請選 2 種主食", list(options.keys()), max_selections=2)

total = 0.0

if len(selected) == 2:
    st.subheader("🍳 料理方式")
    for key in selected:
        r = options[key]
        st.markdown(f"### {r['name']}（{r['cf']:.3f} kgCO₂e）")
        total += r["cf"]

        method = st.radio("料理方式", ["水煮", "油炸"], key=r["name"])
        if method == "水煮" and not water_df.empty:
            w = water_df.sample(1).iloc[0]
            st.caption(f"礦泉水：{w['name']}（{w['cf']:.3f} kgCO₂e）")
            total += w["cf"]
        if method == "油炸" and not oil_df.empty:
            o = oil_df.sample(1).iloc[0]
            st.caption(f"油品：{o['name']}（{o['cf']:.3f} kgCO₂e）")
            total += o["cf"]

    st.success(f"✅ 主食階段總碳足跡：{total:.3f} kgCO₂e")

    st.download_button(
        "⬇️ 下載 CSV",
        data=pd.DataFrame([{
            "foods": ", ".join([options[k]["name"] for k in selected]),
            "total_kgco2e": total
        }]).to_csv(index=False, encoding="utf-8-sig"),
        file_name="result.csv",
        mime="text/csv"
    )
