import streamlit as st
import pandas as pd
import random
import re
from pathlib import Path
import matplotlib.pyplot as plt

# =========================
# 基本設定
# =========================
st.set_page_config(
    page_title="一餐的碳足跡大冒險：從農場到你的胃",
    page_icon="🍽️",
    layout="centered",
)

EXCEL_PATH = "產品碳足跡3.xlsx"

# =========================
# 手機友善 CSS（9:16 直式也好看）
# =========================
st.markdown(
    """
<style>
/* 讓內容不要太寬，手機看更舒服 */
.block-container {max-width: 980px; padding-top: 1.2rem; padding-bottom: 2rem;}
/* 表格字體稍微小一點 */
[data-testid="stDataFrame"] {font-size: 0.92rem;}
/* 手機螢幕（窄）時：縮標題、減間距 */
@media (max-width: 640px){
  h1 {font-size: 1.55rem !important;}
  h2 {font-size: 1.2rem !important;}
  h3 {font-size: 1.05rem !important;}
  .block-container {padding-left: 0.9rem; padding-right: 0.9rem;}
}
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# 解析碳足跡字串（處理 900.00g / 1.00kg / 1.00k / 0.45 等）
# 回傳：kgCO2e (float)
# =========================
def parse_cf_to_kg(value) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0

    # 本來就是數字 → 當作 kg
    if isinstance(value, (int, float)):
        return float(value)

    v = str(value).strip().lower()
    v = v.replace(",", "").replace(" ", "")

    # 常見單位：g / kg / k（有人會把 kg 寫成 k）
    # 也有人會混入文字：kgco2e、co2e
    v = re.sub(r"(kgco2e|kgco₂e|co2e|co₂e)", "", v)

    # 只抓「數字 + (可選單位)」
    # 例：900.00g、1.00kg、1.00k、0.45
    m = re.match(r"^([0-9]*\.?[0-9]+)(g|kg|k)?$", v)
    if not m:
        # 如果像 "900.00g/瓶" 這種：把前面的數字+單位抓出來
        m2 = re.search(r"([0-9]*\.?[0-9]+)\s*(g|kg|k)", v)
        if not m2:
            # 最後手段：只抓數字
            m3 = re.search(r"([0-9]*\.?[0-9]+)", v)
            return float(m3.group(1)) if m3 else 0.0
        num = float(m2.group(1))
        unit = m2.group(2)
    else:
        num = float(m.group(1))
        unit = m.group(2)

    if unit == "g":
        return num / 1000.0
    if unit in ("kg", "k") or unit is None:
        return num
    return float(num)


# =========================
# 讀取 Excel（自動抓欄位）
# 你給的示例：A欄=編號(group)、B=品名、C=碳足跡、D=宣告單位
# 但有些檔案可能還有其他欄位，所以這裡用「前四欄」兜底。
# =========================
@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"找不到檔案：{path}（請放在 repo 根目錄）")

    # 指定 engine 避免環境差異
    df = pd.read_excel(p, engine="openpyxl")

    # 若欄名很亂：直接用前四欄當 A/B/C/D
    if df.shape[1] < 4:
        raise ValueError("Excel 欄位不足：至少要 4 欄（編號、名稱、碳足跡、宣告單位）")

    # 嘗試找可能欄名
    cols = [str(c).strip().lower() for c in df.columns]
    def find_col(keywords):
        for i, c in enumerate(cols):
            if any(k in c for k in keywords):
                return df.columns[i]
        return None

    col_group = find_col(["group", "編號", "分類", "類別"]) or df.columns[0]
    col_name  = find_col(["product_name", "品名", "名稱", "產品名稱"]) or df.columns[1]
    col_cf    = find_col(["product_carbon_footprint_data", "碳足跡", "footprint"]) or df.columns[2]
    col_unit  = find_col(["declared_unit", "宣告單位", "單位"]) or df.columns[3]

    out = df[[col_group, col_name, col_cf, col_unit]].copy()
    out.columns = ["group", "product_name", "product_carbon_footprint_data", "declared_unit"]

    # group 統一成字串（"1" / "1-1" / "1-2" / "2"）
    out["group"] = out["group"].astype(str).str.strip()

    # 轉成 kgCO2e
    out["cf_kgco2e"] = out["product_carbon_footprint_data"].apply(parse_cf_to_kg)

    # 清掉空白列
    out = out.dropna(subset=["product_name"]).reset_index(drop=True)
    out["product_name"] = out["product_name"].astype(str).str.strip()
    out["declared_unit"] = out["declared_unit"].astype(str).str.strip()

    return out


# =========================
# UI：標題
# =========================
st.title("🍽️ 一餐的碳足跡大冒險：從農場到你的胃")
st.caption("規則：編號 1 算食材；編號 1-1 / 1-2 算料理方式（油 / 水）；編號 2 只用於飲料。選項一改，表格與圖表即時更新。")

# =========================
# 讀資料
# =========================
try:
    df = load_data(EXCEL_PATH)
except Exception as e:
    st.error(f"讀取 Excel 失敗：請確認 `{EXCEL_PATH}` 放在專案根目錄，且欄位正確。")
    st.exception(e)
    st.stop()

df_ingredients = df[df["group"] == "1"].copy()
df_oils = df[df["group"] == "1-1"].copy()
df_waters = df[df["group"] == "1-2"].copy()
df_drinks = df[df["group"] == "2"].copy()

if df_ingredients.empty:
    st.error("在 Excel 中找不到 group = 1 的食材資料（編號欄需包含 '1'）。")
    st.stop()
if df_oils.empty:
    st.warning("找不到 group = 1-1（油品）。若你會用到煎炸，請補資料。")
if df_waters.empty:
    st.warning("找不到 group = 1-2（用水）。若你會用到水煮，請補資料。")
if df_drinks.empty:
    st.warning("找不到 group = 2（飲料）。飲料功能會先顯示但抽不到資料。")


# =========================
# Session：抽題、油水、飲料記憶
# =========================
def reset_meal():
    # 抽 3 食材
    k = min(3, len(df_ingredients))
    picks = random.sample(list(df_ingredients.index), k)
    st.session_state["picked_ing_idx"] = picks

    # 每項食材先預設水煮
    st.session_state["cook_method"] = {i: "水煮" for i in range(k)}

    # 對應油/水隨機（等使用者選到時再決定，這樣更合理）
    st.session_state["method_item_idx"] = {i: None for i in range(k)}  # 存油/水的 df index
    st.session_state["method_group"] = {i: None for i in range(k)}     # "1-1" or "1-2"

    # 飲料狀態
    st.session_state["drink_mode"] = "隨機生成飲料"
    st.session_state["drink_idx"] = None

def ensure_init():
    if "picked_ing_idx" not in st.session_state:
        reset_meal()

ensure_init()

# =========================
# 控制按鈕
# =========================
col_a, col_b = st.columns(2)
with col_a:
    if st.button("🎲 抽新的一餐（重抽食材/油水/飲料）", use_container_width=True):
        reset_meal()
with col_b:
    if st.button("↩️ 全部重置（回預設）", use_container_width=True):
        reset_meal()

# =========================
# ① 本次隨機 3 食材（固定不因選項改變）→ 先顯示表格 + 底色
# =========================
picked_df = df_ingredients.loc[st.session_state["picked_ing_idx"], ["group", "product_name", "cf_kgco2e", "declared_unit"]].reset_index(drop=True)
picked_df = picked_df.rename(columns={
    "product_name": "食材名稱",
    "cf_kgco2e": "食材碳足跡(kgCO₂e)",
    "declared_unit": "宣告單位"
})
picked_df.insert(0, "食材#", [f"食材 {i+1}" for i in range(len(picked_df))])

st.subheader("① 本次隨機 3 項食材（固定）")

def highlight_ingredient_rows(_row):
    # 整列上底色（食材列固定）
    return ["background-color: rgba(0, 200, 0, 0.15);"] * len(picked_df.columns)

st.dataframe(
    picked_df.style.apply(highlight_ingredient_rows, axis=1).format({"食材碳足跡(kgCO₂e)": "{:.3f}"}),
    use_container_width=True,
    hide_index=True
)

# =========================
# ② 逐項選擇料理方式（煎炸/水煮）
#     - 煎炸 → 從 1-1 隨機挑油
#     - 水煮 → 從 1-2 隨機挑水
#     - 並顯示「系統隨機挑到的油/水」與其碳足跡
# =========================
st.subheader("② 逐項選擇料理方式（煎炸 / 水煮）")

k = len(picked_df)

for i in range(k):
    st.markdown(f"**{picked_df.loc[i,'食材#']}：{picked_df.loc[i,'食材名稱']}**")

    method = st.radio(
        label="料理方式",
        options=["水煮", "煎炸"],
        horizontal=True,
        key=f"method_{i}"
    )

    # 更新 session_state
    st.session_state["cook_method"][i] = method

    # 依照料理方式決定要抽哪一組
    if method == "煎炸":
        if df_oils.empty:
            st.error("目前沒有 group=1-1 的油品資料，無法進行煎炸。")
            st.session_state["method_item_idx"][i] = None
            st.session_state["method_group"][i] = None
        else:
            # 若之前不是煎炸，或尚未抽過 → 抽一次
            if st.session_state["method_group"][i] != "1-1" or st.session_state["method_item_idx"][i] is None:
                st.session_state["method_item_idx"][i] = random.choice(list(df_oils.index))
                st.session_state["method_group"][i] = "1-1"

            oil_row = df_oils.loc[st.session_state["method_item_idx"][i]]
            st.info(
                f"系統配對油品：**{oil_row['product_name']}**｜碳足跡 **{oil_row['cf_kgco2e']:.3f} kgCO₂e**｜單位：{oil_row['declared_unit']}"
            )

    else:  # 水煮
        if df_waters.empty:
            st.error("目前沒有 group=1-2 的用水資料，無法進行水煮。")
            st.session_state["method_item_idx"][i] = None
            st.session_state["method_group"][i] = None
        else:
            if st.session_state["method_group"][i] != "1-2" or st.session_state["method_item_idx"][i] is None:
                st.session_state["method_item_idx"][i] = random.choice(list(df_waters.index))
                st.session_state["method_group"][i] = "1-2"

            water_row = df_waters.loc[st.session_state["method_item_idx"][i]]
            st.info(
                f"系統配對用水：**{water_row['product_name']}**｜碳足跡 **{water_row['cf_kgco2e']:.3f} kgCO₂e**｜單位：{water_row['declared_unit']}"
            )

    st.divider()

# =========================
# ③ 飲料（可選）：只有兩個選項
#     - 隨機生成飲料（只從 group=2）
#     - 我不喝飲料
# =========================
st.subheader("③ 飲料（可選）")

drink_mode = st.radio(
    "飲料選項",
    ["隨機生成飲料", "我不喝飲料"],
    horizontal=True,
    key="drink_mode"
)
st.session_state["drink_mode"] = drink_mode

if drink_mode == "隨機生成飲料":
    if df_drinks.empty:
        st.warning("目前 group=2 沒有飲料資料，所以抽不到飲料。")
        st.session_state["drink_idx"] = None
    else:
        # 如果還沒抽過，或按按鈕換一杯
        if st.session_state.get("drink_idx") is None:
            st.session_state["drink_idx"] = random.choice(list(df_drinks.index))

        col_c, col_d = st.columns([1, 1])
        with col_c:
            if st.button("🥤 換一杯飲料", use_container_width=True):
                st.session_state["drink_idx"] = random.choice(list(df_drinks.index))
        with col_d:
            st.button("（保持目前飲料）", disabled=True, use_container_width=True)

        drow = df_drinks.loc[st.session_state["drink_idx"]]
        st.success(
            f"本次飲料：**{drow['product_name']}**｜碳足跡 **{drow['cf_kgco2e']:.3f} kgCO₂e**｜單位：{drow['declared_unit']}"
        )
else:
    st.session_state["drink_idx"] = None
    st.info("本次選擇：不喝飲料 ✅")

# =========================
# ④ 本餐組合（表格即時更新）
# =========================
st.subheader("④ 本餐組合（即時更新）")

rows = []
food_sum = 0.0
method_sum = 0.0

for i in range(k):
    ing = df_ingredients.loc[st.session_state["picked_ing_idx"][i]]
    food_cf = float(ing["cf_kgco2e"])
    food_sum += food_cf

    m_group = st.session_state["method_group"][i]
    m_idx = st.session_state["method_item_idx"][i]
    cook = st.session_state["cook_method"][i]

    m_name, m_cf, m_unit = "", 0.0, ""
    if m_group and (m_idx is not None):
        mrow = df.loc[m_idx]
        m_name = mrow["product_name"]
        m_cf = float(mrow["cf_kgco2e"])
        m_unit = mrow["declared_unit"]
        method_sum += m_cf

    rows.append({
        "食材#": f"食材 {i+1}",
        "食材名稱": ing["product_name"],
        "食材碳足跡(kgCO₂e)": food_cf,
        "料理方式": cook,
        "油/水編號": m_group if m_group else "",
        "油/水名稱": m_name,
        "油/水碳足跡(kgCO₂e)": m_cf,
        "油/水宣告單位": m_unit,
    })

meal_df = pd.DataFrame(rows)

# 食材列加底色（左半部欄位）
def style_meal_table(df_show: pd.DataFrame):
    def _row_style(_):
        # 只把「食材相關欄」上底色，讓你一眼區分：食材 vs 油水
        styles = []
        for col in df_show.columns:
            if col in ["食材#", "食材名稱", "食材碳足跡(kgCO₂e)"]:
                styles.append("background-color: rgba(0, 200, 0, 0.15);")
            else:
                styles.append("")
        return styles
    return df_show.style.apply(_row_style, axis=1).format({
        "食材碳足跡(kgCO₂e)": "{:.3f}",
        "油/水碳足跡(kgCO₂e)": "{:.3f}",
    })

st.dataframe(
    style_meal_table(meal_df),
    use_container_width=True,
    hide_index=True
)

# =========================
# ⑤ 總碳足跡（sum）
# =========================
drink_cf = 0.0
drink_name = "（不喝飲料）"
if st.session_state.get("drink_idx") is not None:
    drow = df_drinks.loc[st.session_state["drink_idx"]]
    drink_cf = float(drow["cf_kgco2e"])
    drink_name = drow["product_name"]

total = food_sum + method_sum + drink_cf

st.subheader("⑤ 碳足跡加總（sum）")
st.write(f"- 食材合計：**{food_sum:.3f} kgCO₂e**")
st.write(f"- 料理方式（油/水）合計：**{method_sum:.3f} kgCO₂e**")
st.write(f"- 飲料：**{drink_cf:.3f} kgCO₂e**（{drink_name}）")
st.success(f"✅ 本餐總碳足跡：**{total:.3f} kgCO₂e**")

# =========================
# ⑥ 圖表（選項一改就更新）
#     - 長條圖：食材 / 料理方式 / 飲料
#     - 圓餅圖：比例，並修正「圖例不出現」問題（legend 外掛）
# =========================
st.subheader("⑥ 圖表（選項一改就更新）")

chart_labels = ["食材", "料理方式(油/水)", "飲料"]
chart_values = [food_sum, method_sum, drink_cf]

# 長條圖：縮小尺寸
fig1, ax1 = plt.subplots(figsize=(5.2, 2.8), dpi=150)
ax1.bar(chart_labels, chart_values)
ax1.set_ylabel("kgCO₂e")
ax1.set_title("本餐碳足跡拆解（長條圖）")
st.pyplot(fig1, use_container_width=True)

# 圓餅圖：縮小尺寸 + legend 強制顯示（避免你遇到的「圖例不出現」）
nonzero = [(l, v) for l, v in zip(chart_labels, chart_values) if v > 0]
if len(nonzero) == 0:
    st.info("目前總量為 0，圓餅圖不顯示。")
else:
    pie_labels, pie_values = zip(*nonzero)

    fig2, ax2 = plt.subplots(figsize=(4.6, 3.4), dpi=150)
    wedges, texts, autotexts = ax2.pie(
        pie_values,
        autopct=lambda p: f"{p:.1f}%",
        startangle=90,
        pctdistance=0.72,
        textprops={"fontsize": 9},
    )
    ax2.set_title("本餐碳足跡比例（圓餅圖）")

    # ✅ 圖例固定顯示在右側（你之前「圖例不出現」多半是位置/空間/label 問題）
    ax2.legend(
        wedges,
        [f"{l}：{v:.3f}" for l, v in zip(pie_labels, pie_values)],
        title="圖例",
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        fontsize=9,
        title_fontsize=10,
        frameon=False,
    )
    ax2.axis("equal")

    st.pyplot(fig2, use_container_width=True)

st.caption("提示：煎炸/水煮一改，油/水會重新配對一次（每項食材各自記住）。如果你想「每次切換都重新抽」，我也可以幫你改成那種規則。")
