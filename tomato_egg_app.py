import random
from pathlib import Path

import pandas as pd
import streamlit as st

# -----------------------------
# 基本設定
# -----------------------------
st.set_page_config(
    page_title="隨機菜單 + 料理方式練習（產品碳足跡2）",
    page_icon="🥗",
    layout="centered",
)


# -----------------------------
# 讀取 Excel，並切成 3 類：
# 1：食材；1-1：油品；1-2：水／水煮介質
# -----------------------------
@st.cache_data
def load_products(path: str = "產品碳足跡3.xlsx"):
    xlsx_path = Path(path)
    if not xlsx_path.exists():
        raise FileNotFoundError(f"找不到檔案：{xlsx_path}")

    df = pd.read_excel(xlsx_path)

    # 統一欄位名稱
    df = df.rename(
        columns={
            "Unnamed: 0": "group",
            "product_name": "product_name",
            "product_carbon_footprint_data": "cf_raw",
            "declared_unit": "declared_unit",
        }
    )

    # group 轉成字串，方便用 "1" / "1-1" / "1-2" 篩選
    df["group"] = df["group"].astype(str)

    # 把 900.00g / 1.00kg 轉成「以 kg 為單位的 float」
    def parse_cf_to_kg(value):
        if isinstance(value, str):
            v = value.strip().lower()
            if v.endswith("kg"):
                return float(v[:-2])
            if v.endswith("g"):
                return float(v[:-1]) / 1000.0
        return float(value)

    df["cf_kg"] = df["cf_raw"].apply(parse_cf_to_kg)

    # 分三類
    df_food = df[df["group"] == "1"].reset_index(drop=True)
    df_oil = df[df["group"] == "1-1"].reset_index(drop=True)
    df_water = df[df["group"] == "1-2"].reset_index(drop=True)

    return df_food, df_oil, df_water


# -----------------------------
# 主程式
# -----------------------------
def main():
    st.title("隨機菜單 + 料理方式練習（產品碳足跡2）")

    # 讀檔
    try:
        df_food, df_oil, df_water = load_products()
    except Exception as e:
        st.error("❌ 無法讀取 `產品碳足跡2.xlsx`，請確認檔案已放在 repo 根目錄。")
        st.exception(e)
        return

    if df_food.empty:
        st.error("在 `產品碳足跡2.xlsx` 中找不到 group = 1 的食材資料。")
        return
    if df_oil.empty:
        st.error("在 `產品碳足跡2.xlsx` 中找不到 group = 1-1 的油品資料。")
        return
    if df_water.empty:
        st.error("在 `產品碳足跡2.xlsx` 中找不到 group = 1-2 的水煮介質資料。")
        return

    st.markdown(
        """
這個練習會：

1. 從 **group = 1 的食材** 隨機抽出三種，當作今天的「菜單」  
2. 你替每一個食材選擇 **料理方式**：「煎」或「水煮」  
3. 如果選「煎」，系統會從 **group = 1-1** 的油品中隨機挑一種；  
   如果選「水煮」，會從 **group = 1-2** 中隨機挑一種水／介質  
4. 系統會幫你計算：**食材碳足跡 + 料理方式碳足跡**，並加總成整份菜單的總碳足跡  
        """
    )

    # -------------------------
    # 抽菜單（3 個食材）
    # -------------------------
    N_DISHES = 3

    if "menu_indices" not in st.session_state:
        st.session_state.menu_indices = []

    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("🔄 抽一份新的隨機菜單", use_container_width=True) or not st.session_state.menu_indices:
            n = min(N_DISHES, len(df_food))
            st.session_state.menu_indices = random.sample(list(df_food.index), n)
            # 清掉舊的料理方式選擇
            for i in range(N_DISHES):
                st.session_state.pop(f"method_{i}", None)

    with col_btn2:
        if st.button("🧹 清除目前菜單", use_container_width=True):
            st.session_state.menu_indices = []
            for i in range(N_DISHES):
                st.session_state.pop(f"method_{i}", None)

    if not st.session_state.menu_indices:
        st.info("請先按「🔄 抽一份新的隨機菜單」。")
        return

    # 取出菜單
    menu_df = df_food.loc[st.session_state.menu_indices].reset_index(drop=True)

    st.subheader("本次隨機菜單（每項 1 份）")
    st.table(menu_df[["product_name", "declared_unit"]])

    # -------------------------
    # 選擇料理方式
    # -------------------------
    st.markdown("### 請為每一個食材選擇料理方式")

    for idx, row in menu_df.iterrows():
        st.markdown(
            f"**第 {idx + 1} 道：{row['product_name']}**　（宣告單位：{row['declared_unit']}）"
        )
        st.selectbox(
            "選擇料理方式",
            ["請選擇", "煎", "水煮"],
            key=f"method_{idx}",
            label_visibility="collapsed",
        )

    st.markdown("---")

    # -------------------------
    # 計算碳足跡
    # -------------------------
    if st.button("📊 計算這份菜單的碳足跡", use_container_width=True):
        methods = [
            st.session_state.get(f"method_{i}", "請選擇")
            for i in range(len(menu_df))
        ]
        if any(m == "請選擇" for m in methods):
            st.warning("請先為每一個食材選擇「煎」或「水煮」。")
            return

        results = []
        for i, row in menu_df.iterrows():
            food_name = row["product_name"]
            food_unit = row["declared_unit"]
            food_cf = float(row["cf_kg"])
            method = methods[i]

            # 依照料理方式，隨機選油品或水煮介質
            if method == "煎":
                cook_row = df_oil.sample(1).iloc[0]
            else:  # 水煮
                cook_row = df_water.sample(1).iloc[0]

            cook_name = cook_row["product_name"]
            cook_unit = cook_row["declared_unit"]
            cook_cf = float(cook_row["cf_kg"])

            subtotal = food_cf + cook_cf

            results.append(
                {
                    "食材": food_name,
                    "食材宣告單位": food_unit,
                    "料理方式": method,
                    "料理用料": cook_name,
                    "料理用料宣告單位": cook_unit,
                    "食材碳足跡 (kgCO₂e)": round(food_cf, 3),
                    "料理用料碳足跡 (kgCO₂e)": round(cook_cf, 3),
                    "小計 (kgCO₂e)": round(subtotal, 3),
                }
            )

        result_df = pd.DataFrame(results)

        st.subheader("系統計算結果")
        st.table(result_df)

        total_cf = result_df["小計 (kgCO₂e)"].sum()
        st.success(f"這份菜單的 **總碳足跡約為 {total_cf:.3f} kgCO₂e**。")


if __name__ == "__main__":
    main()
