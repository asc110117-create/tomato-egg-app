import streamlit as st
import pandas as pd
import random

# -----------------------------------
# Streamlit 基本設定
# -----------------------------------
st.set_page_config(
    page_title="番茄炒蛋 & 隨機菜單碳足跡練習",
    page_icon="🥚",
)

# -----------------------------------
# 一、讀取 Excel：產品碳足跡 2
# -----------------------------------
@st.cache_data
def load_cf_products(path: str = "產品碳足跡2.xlsx") -> pd.DataFrame:
    """讀取產品碳足跡2.xlsx，並把碳足跡欄位轉成 kgCO2e（數值）"""
    df = pd.read_excel(path)

    def parse_cf(value):
        """把 '900.00g' / '1.00kg' 轉成 kg（float）"""
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


# -----------------------------------
# 二、番茄炒蛋碳足跡計算（示範用）
# -----------------------------------
EF_EGG = 0.162       # 雞蛋排放係數 kgCO2e / kg
EF_TOMATO = 0.50     # 番茄排放係數 kgCO2e / kg（示意）
COOKING_FACTOR = 1.2 # 炒的倍數
EF_SCOOTER = 0.08    # 機車排放係數 kgCO2e / km（示意）


def calc_tomato_egg(egg_g, tomato_g, distance_km):
    """計算一份番茄炒蛋 + 機車買菜的碳足跡"""
    # 食材排放
    food_emission = EF_EGG * (egg_g / 1000) + EF_TOMATO * (tomato_g / 1000)
    # 炒的烹調排放
    food_with_cooking = food_emission * COOKING_FACTOR
    # 機車來回路程（單趟 distance_km，來回乘 2）
    transport_emission = distance_km * 2 * EF_SCOOTER
    # 總排放
    total = food_with_cooking + transport_emission
    return total, food_with_cooking, transport_emission


# -----------------------------------
# 三、側邊欄：選擇模式
# -----------------------------------
mode = st.sidebar.radio(
    "選擇練習模式",
    ["番茄炒蛋計算練習", "隨機菜單 + 料理方式練習（產品碳足跡2）"],
)

# -----------------------------------
# 四、模式 1：番茄炒蛋 練習
# -----------------------------------
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
    egg_g = st.number_input("雞蛋總重量 (g)", min_value=0.0, value=200.0, step=10.0)
    tomato_g = st.number_input("番茄重量 (g)", min_value=0.0, value=150.0, step=10.0)
    distance_km = st.number_input("去買菜的單程距離 (km)", min_value=0.0, value=3.0, step=0.5)

    st.markdown(
        "👉 請自己先算一算，輸入你估計的 **總碳足跡**（kgCO₂e），例如 `0.589`："
    )
    guess = st.text_input("輸入你的估計值：", key="guess_tomato_egg")

    if st.button("顯示系統計算結果", key="btn_tomato_egg"):
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


# -----------------------------------
# 五、模式 2：隨機菜單 + 料理方式（用 產品碳足跡2）
# -----------------------------------
else:
    st.title("隨機菜單 + 料理方式練習（產品碳足跡2）")

    # 讀 Excel
    try:
        df = load_cf_products()
    except Exception as e:
        st.error("讀取 `產品碳足跡2.xlsx` 失敗，請確認檔案有放在 repo 根目錄。")
        st.exception(e)
        st.stop()

    # 用 Unnamed: 0 作為群組：
    # 1   → 一般食材
    # 1-1 → 油品
    # 1-2 → 水類 / 湯底
    group_main = df[df["Unnamed: 0"] == 1]
    group_oil = df[df["Unnamed: 0"] == "1-1"]
    group_water = df[df["Unnamed: 0"] == "1-2"]

    if "main_indices" not in st.session_state:
        st.session_state.main_indices = []

    st.markdown(
        """
### 操作流程

1. 先從群組 **1** 中隨機抽出三種「食材」  
2. 每一個食材右邊選擇料理方式：**煎** 或 **水煮**  
3. 若選「煎」 → 會從 **1-1 (油品)** 隨機配對一個油品  
4. 若選「水煮」 → 會從 **1-2 (水類)** 隨機配對一個產品  
5. 最後會計算：每一道菜的「食材 + 料理產品」碳足跡小計，並做 **總和 (sum)**。
        """
    )

    # 抽食材 / 清空按鈕
    col1, col2 = st.columns(2)
    with col1:
        if st.button("抽出 3 種食材", key="btn_draw_main"):
            if len(group_main) == 0:
                st.warning("群組 1 沒有任何食材資料。")
            else:
                n_items = min(3, len(group_main))
                st.session_state.main_indices = random.sample(
                    list(group_main.index), n_items
                )
                # 清空舊的料理方式與油/水選擇
                for k in list(st.session_state.keys()):
                    if str(k).startswith("method_") or str(k).startswith("cook_item_"):
                        del st.session_state[k]

    with col2:
        if st.button("清空目前食材", key="btn_clear_main"):
            st.session_state.main_indices = []
            for k in list(st.session_state.keys()):
                if str(k).startswith("method_") or str(k).startswith("cook_item_"):
                    del st.session_state[k]

    if not st.session_state.main_indices:
        st.info("請先按「抽出 3 種食材」。")
    else:
        # 取出這次抽到的主食材
        menu_main = df.loc[
            st.session_state.main_indices,
            ["product_name", "product_carbon_footprint_data", "declared_unit", "cf_per_pack_kg"],
        ].reset_index(drop=True)

        st.subheader("本次抽出的食材（群組 1）")
        st.table(menu_main[["product_name", "declared_unit", "product_carbon_footprint_data"]])

        st.markdown("### 請為每一個食材選擇料理方式")

        # 讓使用者為每一個食材選「煎 / 水煮」
        methods = {}
        for i, idx in enumerate(st.session_state.main_indices):
            base_row = df.loc[idx]
            label = f"{i+1}. {base_row['product_name']}"
            key = f"method_{idx}"
            methods[idx] = st.selectbox(
                f"{label} 的料理方式：",
                ["請選擇", "煎", "水煮"],
                key=key,
            )

        # 計算按鈕：配對油品/水 + 計算 sum
        if st.button("配對油品/水並計算碳足跡", key="btn_calc_menu"):
            rows_for_table = []
            total_sum = 0.0

            for i, idx in enumerate(st.session_state.main_indices):
                base_row = df.loc[idx]
                method = methods.get(idx, "請選擇")

                if method == "請選擇":
                    st.warning(f"第 {i+1} 個食材尚未選擇料理方式。")
                    continue

                # 根據料理方式，從 1-1 / 1-2 群組隨機選擇一個產品
                cook_product = None
                if method == "煎":
                    if len(group_oil) == 0:
                        st.error("群組 1-1 沒有任何油品資料，無法配對。")
                        continue
                    key_oil = f"cook_item_{idx}_oil_index"
                    if key_oil not in st.session_state:
                        st.session_state[key_oil] = random.choice(list(group_oil.index))
                    cook_product = df.loc[st.session_state[key_oil]]
                else:  # 水煮
                    if len(group_water) == 0:
                        st.error("群組 1-2 沒有任何水產品資料，無法配對。")
                        continue
                    key_water = f"cook_item_{idx}_water_index"
                    if key_water not in st.session_state:
                        st.session_state[key_water] = random.choice(list(group_water.index))
                    cook_product = df.loc[st.session_state[key_water]]

                # 各自的碳足跡（以「每宣告單位」為 1 份來算）
                base_cf = float(base_row["cf_per_pack_kg"])
                cook_cf = float(cook_product["cf_per_pack_kg"])
                subtotal = base_cf + cook_cf
                total_sum += subtotal

                rows_for_table.append({
                    "食材名稱": base_row["product_name"],
                    "食材宣告單位": base_row["declared_unit"],
                    "食材碳足跡 (kgCO₂e/單位)": round(base_cf, 3),
                    "料理方式": method,
                    "烹調用產品名稱": cook_product["product_name"],
                    "烹調宣告單位": cook_product["declared_unit"],
                    "烹調碳足跡 (kgCO₂e/單位)": round(cook_cf, 3),
                    "小計 (食材 + 料理產品)": round(subtotal, 3),
                })

            if rows_for_table:
                result_df = pd.DataFrame(rows_for_table)
                st.subheader("本次菜單與料理方式的碳足跡拆解")
                st.table(result_df)

                st.success(
                    f"這三道食材 + 對應料理產品的碳足跡總和：約 **{total_sum:.3f} kgCO₂e**"
                )
