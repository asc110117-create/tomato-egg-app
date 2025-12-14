import re
import random
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

st.set_page_config(page_title="一餐的碳足跡大冒險：從農場到你的胃", page_icon="🍽️", layout="wide")

EXCEL_PATH = "產品碳足跡3.xlsx"

# -----------------------------
# 1) 讀取與清理
# -----------------------------
def parse_cf_to_kg(v) -> float:
    """
    把 '450.00g' / '1.00kg' / '1.00k' / 數字 轉成 kgCO2e(float)
    """
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return 0.0

    if isinstance(v, (int, float)):
        return float(v)

    s = str(v).strip().lower().replace(" ", "")
    # 常見怪字：'1.00k'（少了 g）
    # 用 regex 抓數字 + 單位
    m = re.match(r"^([0-9]*\.?[0-9]+)\s*(kg|g|k)?$", s)
    if not m:
        # 再寬鬆一點：抽出第一個數字與最後的單位字母
        num_m = re.search(r"([0-9]*\.?[0-9]+)", s)
        unit_m = re.search(r"(kg|g|k)\b", s)
        num = float(num_m.group(1)) if num_m else 0.0
        unit = unit_m.group(1) if unit_m else "kg"
    else:
        num = float(m.group(1))
        unit = m.group(2) or "kg"

    if unit == "g":
        return num / 1000.0
    # unit == "kg" 或 "k" 都視為 kg
    return num

@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_excel(path)

    # 你的編號欄目前叫 Unnamed: 0（若之後你改欄名，這裡也能改）
    code_col = "Unnamed: 0"
    required = {code_col, "product_name", "product_carbon_footprint_data", "declared_unit"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Excel 欄位缺少：{missing}")

    df = df.copy()
    df[code_col] = df[code_col].astype(str).str.strip()
    df["cf_kgco2e"] = df["product_carbon_footprint_data"].apply(parse_cf_to_kg)

    return df

# -----------------------------
# 2) 抽題 / 維持狀態
# -----------------------------
def pick_random_rows(df_pool: pd.DataFrame, n: int) -> pd.DataFrame:
    n = min(n, len(df_pool))
    if n <= 0:
        return df_pool.head(0)
    idx = random.sample(list(df_pool.index), n)
    return df_pool.loc[idx].reset_index(drop=True)

def ensure_state():
    st.session_state.setdefault("ingredients", None)        # DataFrame: 3 items from code=1
    st.session_state.setdefault("methods", {})              # {row_i: "煎" or "水煮"}
    st.session_state.setdefault("addons", {})               # {row_i: dict(addon info)}
    st.session_state.setdefault("drink_mode", "隨機生成飲料")
    st.session_state.setdefault("drink_item", None)         # dict
    st.session_state.setdefault("last_methods", {})         # to detect change

def addon_for_method(oils_df, waters_df, method: str) -> dict:
    if method == "煎":
        if len(oils_df) == 0:
            return {"type": "油品(缺資料)", "product_name": "（找不到 1-1 油品資料）", "cf_kgco2e": 0.0, "declared_unit": ""}
        row = oils_df.sample(1).iloc[0]
        return {"type": "油品", "product_name": row["product_name"], "cf_kgco2e": float(row["cf_kgco2e"]), "declared_unit": row["declared_unit"]}
    else:
        if len(waters_df) == 0:
            return {"type": "用水(缺資料)", "product_name": "（找不到 1-2 用水資料）", "cf_kgco2e": 0.0, "declared_unit": ""}
        row = waters_df.sample(1).iloc[0]
        return {"type": "用水", "product_name": row["product_name"], "cf_kgco2e": float(row["cf_kgco2e"]), "declared_unit": row["declared_unit"]}

def pick_drink(df_drink_pool: pd.DataFrame) -> dict:
    if len(df_drink_pool) == 0:
        return {"product_name": "（找不到飲料資料）", "cf_kgco2e": 0.0, "declared_unit": ""}
    row = df_drink_pool.sample(1).iloc[0]
    return {"product_name": row["product_name"], "cf_kgco2e": float(row["cf_kgco2e"]), "declared_unit": row["declared_unit"]}

# -----------------------------
# 3) UI
# -----------------------------
st.title("🍽️ 一餐的碳足跡大冒險：從農場到你的胃")
st.caption("規則：編號 1 算食材；編號 1-1 / 1-2 算料理方式（油 / 水）。選項一改，表格與圖表會即時更新。")

ensure_state()

# 讀取資料
try:
    df = load_data(EXCEL_PATH)
except Exception as e:
    st.error(f"讀取 Excel 失敗：請確認 {EXCEL_PATH} 放在專案根目錄，且欄位正確。")
    st.exception(e)
    st.stop()

code_col = "Unnamed: 0"
df_ing = df[df[code_col] == "1"].copy()
df_oil = df[df[code_col] == "1-1"].copy()
df_water = df[df[code_col] == "1-2"].copy()
df_drink = df[df[code_col] == "2-1"].copy()  # 你檔案裡有 2-1：茶飲

# 若你未來想用 code=2 當飲料池，可改成： df[df[code_col].isin(["2-1","2"])]

left, right = st.columns([1.15, 1])

with left:
    st.subheader("① 隨機抽 3 項食材（編號=1）")
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        if st.button("抽新食材"):
            st.session_state.ingredients = pick_random_rows(df_ing, 3)
            st.session_state.methods = {}
            st.session_state.addons = {}
            st.session_state.last_methods = {}
    with c2:
        if st.button("全部重置"):
            st.session_state.ingredients = None
            st.session_state.methods = {}
            st.session_state.addons = {}
            st.session_state.last_methods = {}
            st.session_state.drink_item = None
    with c3:
        st.write("")  # spacer

    if st.session_state.ingredients is None or len(st.session_state.ingredients) == 0:
        st.info("請先按「抽新食材」。")
        st.stop()

    ing_df = st.session_state.ingredients.copy()

    # 建立每列的料理方式選擇（每個食材分別選）
    st.subheader("② 逐項選擇料理方式（煎 / 水煮）")
    methods = {}
    for i in range(len(ing_df)):
        default = st.session_state.methods.get(i, "水煮")
        methods[i] = st.radio(
            f"食材 {i+1} 的料理方式",
            ["水煮", "煎"],
            index=0 if default == "水煮" else 1,
            horizontal=True,
            key=f"method_{i}",
        )

    # 如果方法有改變，就重抽對應的油/水
    for i, m in methods.items():
        prev = st.session_state.last_methods.get(i)
        if prev != m:
            st.session_state.addons[i] = addon_for_method(df_oil, df_water, m)
    st.session_state.methods = methods
    st.session_state.last_methods = methods.copy()

    # 飲料選擇（兩選項）
    st.subheader("③ 飲料（可選）")
    drink_mode = st.radio("飲料選項", ["隨機生成飲料", "我不喝飲料"], horizontal=True, key="drink_mode_radio")
    st.session_state.drink_mode = drink_mode

    if drink_mode == "隨機生成飲料":
        if st.session_state.drink_item is None:
            st.session_state.drink_item = pick_drink(df_drink)
        colx, coly = st.columns([1, 1])
        with colx:
            if st.button("換一杯飲料"):
                st.session_state.drink_item = pick_drink(df_drink)
        with coly:
            st.write("")

    # 組合呈現：同一張表，左邊食材，右邊顯示油/水資訊
    st.subheader("④ 本餐組合（表格即時更新）")

    rows = []
    for i in range(len(ing_df)):
        add = st.session_state.addons.get(i, {"type": "", "product_name": "", "cf_kgco2e": 0.0, "declared_unit": ""})
        rows.append({
            "食材編號": "1",
            "食材名稱": ing_df.loc[i, "product_name"],
            "食材碳足跡(kgCO₂e)": float(ing_df.loc[i, "cf_kgco2e"]),
            "料理方式": methods[i],
            "油/水類型": add["type"],
            "油/水品名": add["product_name"],
            "油/水碳足跡(kgCO₂e)": float(add["cf_kgco2e"]),
            "油/水宣告單位": add["declared_unit"],
        })

    table_df = pd.DataFrame(rows)
    st.dataframe(table_df, use_container_width=True, hide_index=True)

    # 加上飲料列（若有）
    drink_cf = 0.0
    drink_label = "（無）"
    if st.session_state.drink_mode == "隨機生成飲料" and st.session_state.drink_item:
        drink_cf = float(st.session_state.drink_item["cf_kgco2e"])
        drink_label = f'{st.session_state.drink_item["product_name"]} / {st.session_state.drink_item["declared_unit"]}'

    # 總和
    ing_sum = float(table_df["食材碳足跡(kgCO₂e)"].sum())
    addon_sum = float(table_df["油/水碳足跡(kgCO₂e)"].sum())
    total_sum = ing_sum + addon_sum + drink_cf

    st.subheader("⑤ 碳足跡加總（sum）")
    st.write(f"- 食材合計：**{ing_sum:.3f} kgCO₂e**")
    st.write(f"- 料理方式（油/水）合計：**{addon_sum:.3f} kgCO₂e**")
    st.write(f"- 飲料：**{drink_cf:.3f} kgCO₂e**（{drink_label}）")
    st.success(f"✅ 本餐總碳足跡：**{total_sum:.3f} kgCO₂e**")

with right:
    st.subheader("⑥ 圖表（選項一改就更新）")

    # 長條圖：食材 vs 油/水 vs 飲料
    comp_df = pd.DataFrame({
        "項目": ["食材", "油/水", "飲料"],
        "kgCO₂e": [ing_sum, addon_sum, drink_cf]
    })
    st.bar_chart(comp_df.set_index("項目"))

    # 圓餅圖（matplotlib）
    labels = comp_df["項目"].tolist()
    values = comp_df["kgCO₂e"].tolist()
    # 避免全 0
    if sum(values) > 0:
        fig, ax = plt.subplots()
        ax.pie(values, labels=labels, autopct="%1.1f%%")
        ax.set_title("碳足跡組成比例")
        st.pyplot(fig)
    else:
        st.info("目前碳足跡總量為 0，圓餅圖不顯示。")

st.divider()
st.caption("提醒：本工具使用 Excel 內的產品碳足跡資料作為教學練習；不同資料庫/邊界（cradle-to-gate、cradle-to-grave）會有差異。")
