import streamlit as st
import pandas as pd
import random

st.set_page_config(
    page_title="隨機菜單 & 料理方式碳足跡練習",
    page_icon="🍚",
)

# -----------------------------
# 一、讀取 Excel：產品碳足跡資料
# -----------------------------
@st.cache_data
def load_cf_products(path: str = "產品碳足跡2.xlsx") -> pd.DataFrame:
    df = pd.read_excel(path)

    def parse_cf(value):
        """把 '450.00g' / '1.00kg' 轉成 kgCO₂e（float）"""
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
# 二、載入資料 & 分群
# -----------------------------
try:
    df = load_cf_products()
except Exception as e:
    st.error("讀取 `產品碳足跡2.xlsx` 失敗，請確認檔案有放在 repo 根目錄。")
    st.exception(e)
    st.stop()

# A欄 = Unnamed: 0
base_df = df[df["Unnamed: 0"] == 1]        # 食材
oil_df = df[df["Unnamed: 0"] == "1-1"]     # 油品
water_df = df[df["Unnamed: 0"] == "1-2"]   # 水 / 湯底


# -----------------------------
# 三、UI：說明
# -----------------------------
st.title("隨機菜單 + 料理方式碳足跡練習")

st.markdown(
    """
### 練習規則說明

1. 系統會從 **A欄=1 的食材群** 隨機抽出三種食材  
2. 每一個食材，你要選擇 **「煎」** 或 **「水煮」**  
3. 如果選擇：
   - **煎**：系統會從 **A欄 = 1-1（油品）** 隨機抽一種油品  
   - **水煮**：系統會從 **A欄 = 1-2（水）** 隨機抽一種產品  
4. 最後系統會計算：  
   **這三個食材 + 對應油品/水 的碳足跡總和 (kgCO₂e)**  
    """
)


# -----------------------------
# 四、隨機抽三個食材（A欄 = 1）
# -----------------------------
if "ingredients_indices" not in st.session_state:
    st.session_state.ingredients_indices = []

col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    if st.button("🎲 抽三種隨機食材"):
        if len(base_df) == 0:
            st.error("找不到 A欄=1 的食材資料。")
        else:
            n_items = min(3, len(base_df))
            st.session_state.ingredients_indices = random.sample(
                list(base_df.index), n_items
            )

with col_btn2:
    if st.button("🧹 清空重來"):
        st.session_state.ingredients_indices = []
        # 同時把料理方式的 state 也清空
        for i in range(3):
            st.session_state.pop(f"method_{i}", None)

if not st.session_state.ingredients_indices:
    st.info("請先按「🎲 抽三種隨機食材」。")
    st.stop()


st.subheader("本次抽出的食材（A欄 = 1）")

# -----------------------------
# 五、顯示食材 + 料理方式選擇
# -----------------------------
ingredients_rows = base_df.loc[st.session_state.ingredients_indices]

method_options = ["請選擇", "煎", "水煮"]

for i, (idx, row) in enumerate(ingredients_rows.iterrows()):
    st.markdown("---")
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown(
            f"""
**食材 {i+1}：**  
- 名稱：`{row['product_name']}`  
- 宣告單位：`{row['declared_unit']}`  
- 碳足跡（每單位）：`{row['cf_per_pack_kg']:.3f} kgCO₂e`
"""
        )

    with col2:
        st.selectbox(
            f"料理方式（食材 {i+1}）",
            method_options,
            key=f"method_{i}",
        )

st.markdown("---")

# -----------------------------
# 六、依料理方式抽 1-1 / 1-2，並計算總碳足跡
# -----------------------------
if st.button("📊 根據料理方式抽油 / 水，並計算碳足跡"):
    rows_for_table = []
    total_cf = 0.0

    if len(oil_df) == 0:
        st.warning("注意：A欄=1-1（油品） 沒有資料。")
    if len(water_df) == 0:
        st.warning("注意：A欄=1-2（水） 沒有資料。")

    for i, (idx, row) in enumerate(ingredients_rows.iterrows()):
        method = st.session_state.get(f"method_{i}", "請選擇")
        ingredient_name = row["product_name"]
        ingredient_unit = row["declared_unit"]
        ingredient_cf = float(row["cf_per_pack_kg"])

        cooking_name = "-"
        cooking_unit = "-"
        cooking_cf = 0.0

        # 料理方式判斷
        if method == "煎":
            if len(oil_df) > 0:
                oil_row = oil_df.sample(1).iloc[0]
                cooking_name = oil_row["product_name"]
                cooking_unit = oil_row["declared_unit"]
                cooking_cf = float(oil_row["cf_per_pack_kg"])
            else:
                st.warning(f"食材 {i+1} 選了「煎」，但找不到 1-1 油品資料。")
        elif method == "水煮":
            if len(water_df) > 0:
                water_row = water_df.sample(1).iloc[0]
                cooking_name = water_row["product_name"]
                cooking_unit = water_row["declared_unit"]
                cooking_cf = float(water_row["cf_per_pack_kg"])
            else:
                st.warning(f"食材 {i+1} 選了「水煮」，但找不到 1-2 水類資料。")
        else:
            # 未選擇
            st.warning(f"食材 {i+1} 尚未選擇料理方式，將不列入計算。")
            # 不計這一項
            continue

        # 加總碳足跡
        subtotal = ingredient_cf + cooking_cf
        total_cf += subtotal

        rows_for_table.append(
            {
                "食材名稱": ingredient_name,
                "食材宣告單位": ingredient_unit,
                "食材碳足跡(kgCO₂e/份)": round(ingredient_cf, 3),
                "料理方式": method,
                "搭配品名稱(油/水)": cooking_name,
                "搭配品宣告單位": cooking_unit,
                "搭配品碳足跡(kgCO₂e/份)": round(cooking_cf, 3),
                "此組小計(食材+搭配品)": round(subtotal, 3),
            }
        )

    if not rows_for_table:
        st.error("目前沒有任何完成設定（有選料理方式）的食材，無法計算。")
        st.stop()

    result_df = pd.DataFrame(rows_for_table)
    st.subheader("本次餐點碳足跡明細")
    st.table(result_df)

    st.success(f"👉 這一組餐點的總碳足跡：約 **{total_cf:.3f} kgCO₂e**（食材 + 油/水）")
