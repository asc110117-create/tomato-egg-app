
# tomato_egg_app_EMPTY_TEMPLATE.py
import math
import random
import pandas as pd
import streamlit as st

st.set_page_config(page_title="碳足跡餐點（空白模板）", layout="centered")

st.title("🍽️ 碳足跡餐點計算｜空白模板")

st.info("這是一個『空檔可開、不會閃退』的基礎模板。請先上傳 Excel 再操作。")

# ---------- Upload ----------
uploaded = st.file_uploader("請上傳 Excel（3 欄：族群、產品名稱、碳足跡(kg)）", type=["xlsx"])
if uploaded is None:
    st.stop()

# ---------- Read Excel safely ----------
df = pd.read_excel(uploaded)
df = df.iloc[:, :3]
df.columns = ["group", "name", "cf_kg"]

st.success("Excel 讀取成功 ✅")
st.dataframe(df, use_container_width=True)

# ---------- Split groups ----------
food = df[df["group"] == 1]
oil = df[df["group"] == "1-1"]
water = df[df["group"] == "1-2"]
drink = df[df["group"] == 2]

# ---------- Main dish (safe even if empty) ----------
st.subheader("🥗 主食（示範）")
if food.empty:
    st.warning("目前 Excel 中沒有 group=1 的主食資料")
else:
    sample5 = food.sample(min(5, len(food)))
    chosen = st.multiselect("從 5 選 2", sample5["name"].tolist(), max_selections=2)
    for item in chosen:
        st.radio(f"{item} 的料理方式", ["水煮", "油炸"], key=item)

# ---------- Transport placeholder ----------
st.subheader("🚶‍♂️ 交通（示範）")
mode = st.selectbox("交通方式", ["走路", "機車", "汽車", "貨車"])
st.caption("此模板尚未計算距離與碳足跡，僅保留介面結構。")

# ---------- Result ----------
st.subheader("📊 結果（示範）")
st.write("此為空白模板，尚未進行實際計算。")

st.success("模板載入完成，可在此基礎上逐步加功能。")
