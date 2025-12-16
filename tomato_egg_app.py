
import streamlit as st
import pandas as pd
import random

st.set_page_config(page_title="一餐的碳足跡大冒險", layout="centered")
st.title("🍽️ 一餐的碳足跡大冒險")

@st.cache_data
def load_excel():
    try:
        return pd.read_excel("碳足跡4.xlsx")
    except FileNotFoundError:
        up = st.file_uploader("請上傳《碳足跡4.xlsx》", type=["xlsx"])
        if up is None:
            st.stop()
        return pd.read_excel(up)

df = load_excel()

# Expect columns: group, name, cf (kg)
df["cf"] = df["cf"].astype(float)

st.header("👤 基本資料")
student = st.text_input("請輸入你的名字")

st.divider()
st.header("🍚 主食（5 選 2）")

food_pool = df[df["group"] == "1"].sample(n=min(5, len(df[df["group"]=="1"])), random_state=random.randint(1,10000))
options = {f'{r["name"]}（{r["cf"]} kgCO₂e）': r for _, r in food_pool.iterrows()}

selected = st.multiselect("請選 2 種主食", list(options.keys()), max_selections=2)

water_df = df[df["group"] == "1-1"]
oil_df = df[df["group"] == "1-2"]

total = 0.0

if len(selected) == 2:
    st.subheader("🍳 你的選擇")
    for key in selected:
        r = options[key]
        st.write(f'### {r["name"]}（{r["cf"]} kgCO₂e）')
        method = st.radio("料理方式", ["水煮", "油炸"], key=r["name"])
        total += r["cf"]

        if method == "水煮" and not water_df.empty:
            w = water_df.sample(1).iloc[0]
            st.caption(f'搭配礦泉水：{w["name"]}（{w["cf"]} kgCO₂e）')
            total += w["cf"]
        if method == "油炸" and not oil_df.empty:
            o = oil_df.sample(1).iloc[0]
            st.caption(f'搭配油品：{o["name"]}（{o["cf"]} kgCO₂e）')
            total += o["cf"]

    st.success(f"✅ 主食階段總碳足跡：{total:.3f} kgCO₂e")

    out = {
        "student": student,
        "total_kgco2e": total,
        "foods": ", ".join([options[k]["name"] for k in selected])
    }

    st.download_button(
        "⬇️ 下載結果 CSV",
        data=pd.DataFrame([out]).to_csv(index=False, encoding="utf-8-sig"),
        file_name=f"{student}_result.csv",
        mime="text/csv"
    )
