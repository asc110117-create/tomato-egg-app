# tomato_egg_app_v5_NO_CACHE_WIDGET.py
# 主食 5 選 2 + 水煮 / 油炸（不使用 cache 內 widget，避免 CachedWidgetWarning）

import streamlit as st
import pandas as pd
import random

st.set_page_config(page_title="一餐的碳足跡大冒險", layout="centered")
st.title("🍽️ 一餐的碳足跡大冒險")

# =======================
# 讀取 Excel（UI 在外）
# =======================
st.header("📂 資料來源")

uploaded = st.file_uploader("請上傳《碳足跡4.xlsx》", type=["xlsx"])

@st.cache_data
def read_excel(file):
    return pd.read_excel(file)

if uploaded is None:
    st.info("請先上傳《碳足跡4.xlsx》")
    st.stop()

df = read_excel(uploaded)

# 預期欄位：group, name, cf（kgCO2e）
df["cf"] = df["cf"].astype(float)

# =======================
# 基本資料
# =======================
st.header("👤 學生資料")
student = st.text_input("請輸入你的名字")

# =======================
# 主食邏輯
# =======================
st.header("🍚 主食（隨機 5 選 2）")

food_df = df[df["group"] == "1"]
water_df = df[df["group"] == "1-1"]
oil_df = df[df["group"] == "1-2"]

if len(food_df) < 2:
    st.error("group=1 的主食不足")
    st.stop()

food_pool = food_df.sample(n=min(5, len(food_df)), random_state=random.randint(1, 9999))

options = {
    f'{r["name"]}（{r["cf"]:.3f} kgCO₂e）': r
    for _, r in food_pool.iterrows()
}

selected = st.multiselect("請選 2 種主食", list(options.keys()), max_selections=2)

total = 0.0
records = []

if len(selected) == 2:
    st.subheader("🍳 你的料理選擇")

    for key in selected:
        r = options[key]
        st.markdown(f"### {r['name']}（{r['cf']:.3f} kgCO₂e）")
        total += r["cf"]

        method = st.radio(
            "料理方式",
            ["水煮", "油炸"],
            key=f"cook_{r['name']}"
        )

        if method == "水煮" and not water_df.empty:
            w = water_df.sample(1).iloc[0]
            st.caption(f"搭配礦泉水：{w['name']}（{w['cf']:.3f} kgCO₂e）")
            total += w["cf"]
            records.append((r["name"], method, w["name"], w["cf"]))

        if method == "油炸" and not oil_df.empty:
            o = oil_df.sample(1).iloc[0]
            st.caption(f"搭配油品：{o['name']}（{o['cf']:.3f} kgCO₂e）")
            total += o["cf"]
            records.append((r["name"], method, o["name"], o["cf"]))

    st.success(f"✅ 主食階段總碳足跡：{total:.3f} kgCO₂e")

    out = {
        "student": student,
        "foods": ", ".join([options[k]['name'] for k in selected]),
        "total_kgco2e": total,
    }

    st.download_button(
        "⬇️ 下載結果 CSV",
        data=pd.DataFrame([out]).to_csv(index=False, encoding="utf-8-sig"),
        file_name=f"{student}_result.csv",
        mime="text/csv"
    )
