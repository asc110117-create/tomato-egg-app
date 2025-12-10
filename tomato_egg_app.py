import streamlit as st
import pandas as pd
import random

st.set_page_config(
    page_title="隨機菜單 + 料理方式碳足跡練習（產品碳足跡2）",
    page_icon="🥦",
)

# -----------------------------
# 一、讀取 Excel：產品碳足跡2
# -----------------------------
@st.cache_data
def load_cf_products(path: str = "產品碳足跡3.xlsx") -> pd.DataFrame:
    """讀取產品碳足跡3.xlsx，並把碳足跡欄位轉成 kgCO2e（float）"""

    df = pd.read_excel(path)

    # 依你給的檔案結構，主要欄位長這樣：
    # 'Unnamed: 0', 'product_name', 'product_carbon_footprint_data', 'declared_unit'
    group_col = df.columns[0]  # 通常是 'Unnamed: 0'
    name_col = "product_name"
    cf_col = "product_carbon_footprint_data"

    def parse_cf(value):
        """把 '450.00g' / '1.00kg' 轉成 kg（float）"""
        if pd.isna(value):
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)

        v = str(value).strip().lower()
        if v.endswith("kg"):
            return float(v[:-2])
        if v.endswith("g"):
            return float(v[:-1]) / 1000.0
        # 其它情況就直接硬轉
        try:
            return float(v)
        except Exception:
            return 0.0

    df["group"] = df[group_col]
    df["cf_kg"] = df[cf_col].apply(parse_cf)

    return df


# -----------------------------
# 二、主畫面：隨機菜單 + 料理方式練習
# -----------------------------
def main():
    st.title("隨機菜單 + 料理方式練習（產品碳足跡2）")

    # 讀 Excel
    try:
        df = load_cf_products("產品碳足跡2.xlsx")
    except Exception as e:
        st.error("❌ 無法讀取檔案 `產品碳足跡2.xlsx`，請確認檔案有放在 repo 根目錄。")
        st.exception(e)
        return

    name_col = "product_name"
    unit_col = "declared_unit"

    # 分組資料
    df_food = df[df["group"] == 1]        # 主食材
    df_fry  = df[df["group"] == "1-1"]    # 煎用油
    df_boil = df[df["group"] == "1-2"]    # 水煮用

    if df_food.empty:
        st.error("在 `產品碳足跡2.xlsx` 中找不到 group = 1 的食材資料。")
        return

    if df_fry.empty or df_boil.empty:
        st.warning("找不到 group = '1-1' 或 '1-2' 的資料，『煎 / 水煮』可能無法正常運作。")

    st.markdown(
        """
這個練習會：

1. 從 **group = 1** 的食材中隨機抽出三種食材  
2. 你可以為每個食材選擇 **煎 / 水煮**  
3. 按下按鈕後：  
   - 若選「煎」：系統會從 **group = 1-1** 隨機抽一個油品  
   - 若選「水煮」：系統會從 **group = 1-2** 隨機抽一個品項  
4. 最後會計算 **食材 + 油 / 水** 的碳足跡總和，並顯示拆解表  
        """
    )

    # -------------------------
    # 抽食材（group = 1 中選三個）
    # -------------------------
    if "ingredients" not in st.session_state:
        st.session_state.ingredients = sample_ingredients(df_food, name_col, unit_col)

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("重新抽食材"):
            st.session_state.ingredients = sample_ingredients(df_food, name_col, unit_col)
    with col_btn2:
        st.write("")  # 只是排版

    ingredients = st.session_state.ingredients

    st.subheader("本次隨機食材（group = 1，每項 1 份）")

    # 顯示食材 + 料理方式選項
    method_choices = {}
    for idx, item in enumerate(ingredients):
        row = st.container()
        with row:
            c1, c2 = st.columns([3, 2])
            with c1:
                st.markdown(f"**食材 {idx+1}：{item[name_col]}**")
                st.caption(f"單位：{item[unit_col]}")
            with c2:
                method = st.radio(
                    "料理方式",
                    ["煎", "水煮"],
                    key=f"method_{idx}",
                    horizontal=True,
                )
                method_choices[idx] = method

    st.markdown("---")

    # 讓使用者先自己估 total（可選填）
    st.markdown("👉 可以先自己估算這份餐的 **總碳足跡 (kgCO₂e)**：")
    guess_val = st.text_input("輸入你的估計值（可以空白略過）：", key="guess_total")

    if st.button("顯示系統計算結果"):
        if df_fry.empty or df_boil.empty:
            st.error("缺少 group = '1-1' 或 '1-2' 的資料，無法完成計算。")
            return

        # -------------------------
        # 根據料理方式，抽對應油 / 水，並計算總碳足跡
        # -------------------------
        result_rows = []
        total_cf = 0.0

        for idx, item in enumerate(ingredients):
            method = method_choices[idx]

            # 食材本身
            food_name = item[name_col]
            food_unit = item[unit_col]
            food_cf = float(item["cf_kg"])

            # 依料理方式抽對應品項
            if method == "煎":
                extra_df = df_fry
            else:  # 水煮
                extra_df = df_boil

            extra_row = extra_df.sample(1).iloc[0]
            extra_name = extra_row[name_col]
            extra_unit = extra_row[unit_col]
            extra_cf = float(extra_row["cf_kg"])

            subtotal = food_cf + extra_cf
            total_cf += subtotal

            result_rows.append(
                {
                    "食材": food_name,
                    "料理方式": method,
                    "食材單位": food_unit,
                    "食材碳足跡 (kgCO₂e)": round(food_cf, 3),
                    "搭配品項": extra_name,
                    "搭配品單位": extra_unit,
                    "搭配品碳足跡 (kgCO₂e)": round(extra_cf, 3),
                    "小計 (kgCO₂e)": round(subtotal, 3),
                }
            )

        st.subheader("碳足跡拆解結果")

        result_df = pd.DataFrame(result_rows)
        st.table(result_df)

        st.success(f"這份餐點的 **總碳足跡：約 {total_cf:.3f} kgCO₂e**")

        # 若有輸入估計值，給一點回饋
        if guess_val.strip():
            try:
                g = float(guess_val)
                diff = abs(g - total_cf)
                st.info(f"你的估計：`{g:.3f}`，與系統值差 **{diff:.3f}** kgCO₂e。")
            except ValueError:
                st.warning("你輸入的估計值無法轉成數字，已略過比較。")


def sample_ingredients(df_food: pd.DataFrame, name_col: str, unit_col: str):
    """從 group = 1 的食材中隨機抽 3 個，回傳 dict list（方便放進 session_state）"""
    n = min(3, len(df_food))
    sampled = df_food.sample(n).reset_index(drop=True)
    # 只保留必要欄位 + cf_kg + group
    cols = ["group", name_col, unit_col, "cf_kg"]
    sampled = sampled[cols]
    return sampled.to_dict(orient="records")


if __name__ == "__main__":
    main()

