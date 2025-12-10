import streamlit as st
import pandas as pd
import random
from pathlib import Path

st.set_page_config(
    page_title="番茄炒蛋 & 隨機菜單碳足跡練習",
    page_icon="🥚",
)

# -----------------------------
# 一、讀取 Excel：產品碳足跡資料
# -----------------------------
@st.cache_data
def load_cf_products(path: str = "產品碳足跡.xlsx") -> pd.DataFrame:
    df = pd.read_excel(path)

    def parse_cf(value):
        """把 '450.00g' / '1.00kg' 轉成 kgCO2e（float）"""
        if isinstance(value, str):
            v = value.strip().lower()
            if v.endswith("kg"):
                return float(v[:-2])
            if v.endswith("g"):
                return float(v[:-1]) / 1000.0
        # 如果本來就是數字，就直接當作 kg
        return float(value)

    df["cf_per_pack_kg"] = df["product_carbon_footprint_data"].apply(parse_cf)
    return df


# -----------------------------
# 二、番茄炒蛋碳足跡計算
# -----------------------------
EF_EGG = 0.162        # 雞蛋排放係數 kgCO2e / kg
EF_TOMATO = 0.50      # 番茄排放係數 kgCO2e / kg（示意）
COOKING_FACTOR = 1.2  # 炒的倍數
EF_SCOOTER = 0.08     # 機車排放係數 kgCO2e / km（示意）

def calc_tomato_egg(egg_g, tomato_g, distance_km):
    # 食材排放
    food_emission = EF_EGG * (egg_g / 1000) + EF_TOMATO * (tomato_g / 1000)
    # 炒的烹調排放
    food_with_cooking = food_emission * COOKING_FACTOR
    # 機車來回路程（單趟 distance_km，來回乘 2）
    transport_emission = distance_km * 2 * EF_SCOOTER
    # 總排放
    total = food_with_cooking + transport_emission
    return total, food_with_cooking, transport_emission


# -----------------------------
# 三、側邊欄：選擇模式
# -----------------------------
mode = st.sidebar.radio(
    "選擇練習模式",
    ["番茄炒蛋計算練習", "隨機菜單練習（從 Excel）"],
)

# -----------------------------
# 四、番茄炒蛋 練習頁面
# -----------------------------
if mode == "番茄炒蛋計算練習":
    st.title("番茄炒蛋碳足跡計算練習")

    st.subheader("情境說明")
    st.markdown(
        f"""
- 雞蛋排放係數：`{EF_EGG:.3f} kgCO₂e / kg`
- 番茄排放係數：`{EF_TOMATO:.2f} kgCO₂e / kg`（示意用）
- 烹調方式：炒（倍數 `{COOKING_FACTOR}`）
- 機車排放係數：`{EF_SCOOTER:.2f} kgCO₂e / km`
- 預設來回騎車買菜
        """
    )

    st.markdown("### 請輸入你這份番茄炒蛋的設定")

    egg_g = st.number_input("雞蛋總重量 (g)", min_value=0.0, value=20.0, step=5.0)
    tomato_g = st.number_input("番茄重量 (g)", min_value=0.0, value=30.0, step=5.0)
    distance_km = st.number_input("去買菜的單程距離 (km)", min_value=0.0, value=6.0, step=0.5)

    st.markdown(
        "👉 請自己先算一算，輸入你估計的 **總碳足跡**（kgCO₂e），例如 `0.589`："
    )
    guess = st.text_input("輸入你的估計值：", key="guess_tomato_egg")

    if st.button("顯示系統計算結果"):
        total, food_with_cooking, transport_emission = calc_tomato_egg(
            egg_g, tomato_g, distance_km
        )

        st.success(f"系統計算結果：**{total:.3f} kgCO₂e**")

        st.markdown(
            f"""
**拆解說明：**

- 食材 + 烹調碳足跡：`{food_with_cooking:.3f} kgCO₂e`
- 交通碳足跡（機車來回）：`{transport_emission:.3f} kgCO₂e`
- 總碳足跡：`{total:.3f} kgCO₂e`
            """
        )

        if guess.strip():
            try:
                g = float(guess)
                diff = abs(g - total)
                st.info(f"你的估計：`{g:.3f}`，與正確值差 **{diff:.3f}** kgCO₂e。")
            except ValueError:
                st.error("你的估計值格式怪怪的，請確認是數字，例如 `0.589`。")


# -----------------------------
# 五、隨機菜單 練習頁面（從 Excel 讀）
# -----------------------------
# -----------------------------
# 五、隨機菜單 練習頁面（從 Excel 讀）
# -----------------------------
else:
    st.title("隨機菜單碳足跡練習（從 Excel 讀取產品）")

    # 讀 Excel（放在同一個 GitHub repo 目錄）
    try:
        df = load_cf_products()
    except Exception as e:
        st.error("讀取 `產品碳足跡.xlsx` 失敗，請確認檔案有放在 repo 根目錄。")
        st.exception(e)
        st.stop()

    st.markdown(
        """
這個練習會：  
1. 從 **產品碳足跡 Excel** 中隨機抽幾個商品，組成一份「菜單」  
2. 顯示每個商品 **每份碳足跡 (kgCO₂e)** 和 **本題吃幾份**  
3. 你先用這些數字自己計算一餐的 **總碳足跡**，再輸入答案  
4. 按按鈕查看系統計算結果與拆解
        """
    )

    # 用 session_state 記住這次抽到的菜單
    if "menu_df" not in st.session_state:
        st.session_state.menu_df = None

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("抽一份新的隨機菜單"):
            # 一次抽 3 個商品（你可以自己改數量）
            n_items = min(3, len(df))
            idx = random.sample(range(len(df)), n_items)

            menu_df = df.loc[
                idx,
                ["product_name", "declared_unit", "cf_per_pack_kg"],
            ].copy()

            # 隨機決定這一題要吃幾「份」
            possible_servings = [0.5, 1, 2, 3]
            menu_df["servings"] = [
                random.choice(possible_servings) for _ in range(len(menu_df))
            ]

            # 這一題每個商品實際產生的碳足跡
            menu_df["cf_this_item_kg"] = (
                menu_df["cf_per_pack_kg"] * menu_df["servings"]
            )

            st.session_state.menu_df = menu_df

    with col_btn2:
        if st.button("清空菜單"):
            st.session_state.menu_df = None

    if st.session_state.menu_df is None:
        st.info("請先按「抽一份新的隨機菜單」。")
        st.stop()

    menu_df = st.session_state.menu_df

    st.subheader("本次隨機菜單（每項吃幾份）")

    show_df = menu_df.copy()
    show_df["cf_per_pack_kg"] = show_df["cf_per_pack_kg"].round(3)

    show_df = show_df.rename(
        columns={
            "product_name": "產品名稱",
            "declared_unit": "宣告單位",
            "cf_per_pack_kg": "每份碳足跡 (kgCO₂e)",
            "servings": "本題食用份數",
        }
    )

    st.table(show_df[["產品名稱", "宣告單位", "每份碳足跡 (kgCO₂e)", "本題食用份數"]])

    # 正確答案：所有商品這一題的碳足跡總和
    correct_total = float(menu_df["cf_this_item_kg"].sum())

    st.markdown(
        "👉 請用上面表格裡的數字，先自己計算這一份菜單的 **總碳足跡 (kgCO₂e)**，再輸入在下面："
    )
    guess_menu = st.text_input("輸入你算出的總碳足跡 (kgCO₂e)：", key="guess_menu")

    if st.button("顯示系統計算結果"):
        st.success(f"這份菜單的總碳足跡：約 **{correct_total:.3f} kgCO₂e**")

        st.markdown("**各商品碳足跡拆解：**")
        detail_df = menu_df.copy()
        detail_df["cf_per_pack_kg"] = detail_df["cf_per_pack_kg"].round(3)
        detail_df["cf_this_item_kg"] = detail_df["cf_this_item_kg"].round(3)

        detail_df = detail_df.rename(
            columns={
                "product_name": "產品名稱",
                "declared_unit": "宣告單位",
                "cf_per_pack_kg": "每份碳足跡 (kgCO₂e)",
                "servings": "本題食用份數",
                "cf_this_item_kg": "本題此商品碳足跡 (kgCO₂e)",
            }
        )

        st.table(
            detail_df[
                [
                    "產品名稱",
                    "宣告單位",
                    "每份碳足跡 (kgCO₂e)",
                    "本題食用份數",
                    "本題此商品碳足跡 (kgCO₂e)",
                ]
            ]
        )

        if guess_menu.strip():
            try:
                g = float(guess_menu)
                diff = abs(g - correct_total)
                st.info(f"你的答案：`{g:.3f}`，與正確值差 **{diff:.3f}** kgCO₂e。")
            except ValueError:
                st.error("你的答案不是數字，請重新輸入，例如 `1.234`。")

  

