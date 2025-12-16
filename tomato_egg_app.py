# tomato_egg_app_MAIN_DISH_NO_CRASH.py
# 主食：group=1，隨機5選2（不閃退版本）

import streamlit as st
import pandas as pd
import random

st.set_page_config(page_title="主食選擇（不閃退）", layout="centered")
st.title("🍚 主食（隨機 5 選 2）")

# ---------- 讀取 Excel（三欄位固定） ----------
@st.cache_data
def load_excel(file_bytes):
    df = pd.read_excel(file_bytes)
    df.columns = [c.strip() for c in df.columns]
    required = ["族群", "產品名稱", "碳足跡(kg)"]
    for c in required:
        if c not in df.columns:
            raise ValueError(f"缺少欄位：{c}")
    df["碳足跡(kg)"] = pd.to_numeric(df["碳足跡(kg)"], errors="coerce").fillna(0.0)
    return df

uploaded = st.file_uploader("請上傳《碳足跡4.xlsx》", type=["xlsx"])
if not uploaded:
    st.stop()

df = load_excel(uploaded.getvalue())

# ---------- 主食 group=1 ----------
food_df = df[df["族群"] == 1].reset_index(drop=True)
if len(food_df) < 2:
    st.error("group=1 主食資料不足")
    st.stop()

# ---------- 隨機抽 5 ----------
if "food_pool" not in st.session_state:
    st.session_state.food_pool = food_df.sample(
        n=min(5, len(food_df)),
        replace=False,
        random_state=random.randint(1, 99999)
    ).reset_index(drop=True)

pool = st.session_state.food_pool

# ---------- UI label 與資料分離（關鍵不閃退） ----------
labels = []
label_to_name = {}
for _, r in pool.iterrows():
    label = f"{r['產品名稱']}（{r['碳足跡(kg)']:.3f} kgCO₂e）"
    labels.append(label)
    label_to_name[label] = r["產品名稱"]

chosen_labels = st.multiselect(
    "請選 2 種主食",
    options=labels,
    max_selections=2
)

# ---------- 顯示結果 ----------
if len(chosen_labels) == 2:
    chosen_names = [label_to_name[l] for l in chosen_labels]
    chosen_df = pool[pool["產品名稱"].isin(chosen_names)]

    st.success("您所選的食材為：")
    total = 0.0
    for _, r in chosen_df.iterrows():
        st.write(f"- {r['產品名稱']}（{r['碳足跡(kg)']:.3f} kgCO₂e）")
        total += r["碳足跡(kg)"]

    st.markdown(f"### 主食碳足跡小計：**{total:.3f} kgCO₂e**")

# ---------- 下載檔案（測試用） ----------
st.download_button(
    "⬇️ 下載本程式檔（測試）",
    data=code.encode("utf-8"),
    file_name="tomato_egg_app_MAIN_DISH_NO_CRASH.py",
    mime="text/x-python"
)
