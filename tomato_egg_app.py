
import streamlit as st
import pandas as pd
import random

st.set_page_config(page_title="一餐的碳足跡大冒險", page_icon="🍽️")

st.title("🍽️ 一餐的碳足跡大冒險")

@st.cache_data
def load_excel():
    df = pd.read_excel("碳足跡4.xlsx")
    df.columns = ["group", "name", "cf"]
    df["cf"] = df["cf"].astype(float)
    return df

df = load_excel()

df_food = df[df["group"] == 1]
df_water = df[df["group"] == "1-1"]
df_oil = df[df["group"] == "1-2"]

student = st.text_input("請輸入你的名字")

st.divider()

st.subheader("🍚 主食（隨機 5 選 2）")

if "food_pool" not in st.session_state:
    st.session_state.food_pool = df_food.sample(n=min(5, len(df_food)), replace=False)

food_pool = st.session_state.food_pool

food_options = [
    f"{row['name']}（{row['cf']} kgCO₂e）"
    for _, row in food_pool.iterrows()
]

selected_foods = st.multiselect(
    "請選擇 2 種主食",
    options=food_options,
    max_selections=2
)

results = []

if len(selected_foods) == 2:
    st.markdown("### 🍳 你所選的食材為：")

    for idx, choice in enumerate(selected_foods):
        row = food_pool.iloc[food_options.index(choice)]
        food_name = row["name"]
        food_cf = row["cf"]

        method = st.radio(
            f"{food_name}（{food_cf} kgCO₂e）料理方式",
            ["水煮", "油炸"],
            key=f"method_{idx}",
            horizontal=True
        )

        if method == "水煮":
            pick = df_water.sample(1).iloc[0]
        else:
            pick = df_oil.sample(1).iloc[0]

        cook_name = pick["name"]
        cook_cf = pick["cf"]

        st.caption(f"👉 料理耗材：{cook_name}（{cook_cf} kgCO₂e）")

        results.append({
            "food": food_name,
            "food_cf": food_cf,
            "method": method,
            "cook_item": cook_name,
            "cook_cf": cook_cf
        })

if results:
    st.divider()
    total_cf = sum(r["food_cf"] + r["cook_cf"] for r in results)
    st.success(f"🌱 主食階段碳足跡小計：{total_cf:.2f} kgCO₂e")

    df_out = pd.DataFrame(results)
    df_out["student"] = student
    df_out["total_item_cf"] = df_out["food_cf"] + df_out["cook_cf"]

    csv = df_out.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ 下載主食計算結果 CSV",
        data=csv,
        file_name=f"{student}_主食碳足跡.csv",
        mime="text/csv"
    )
