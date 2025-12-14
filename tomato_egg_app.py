import re
import random
from pathlib import Path

import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt


# =============================
# 基本設定
# =============================
st.set_page_config(
    page_title="🍽️ 一餐的碳足跡大冒險：從農場到你的胃",
    page_icon="🍽️",
    layout="wide",
)

EXCEL_PATH = "產品碳足跡3.xlsx"

GROUP_ING = "1"     # 食材
GROUP_OIL = "1-1"   # 油（煎炸）
GROUP_WATER = "1-2" # 水（水煮）

N_INGREDIENTS = 3


# =============================
# 工具：碳足跡字串解析（修掉 1.00k、900g、0.9kg...）
# 統一回傳 kgCO2e（float）
# =============================
def parse_cf_to_kg(value) -> float:
    """
    支援：
      - 900.00g / 900g -> 0.9
      - 1.00kg / 1kg -> 1.0
      - 1.00k -> 視為 1.00kg（修正你遇到的資料）
      - 純數字 -> 視為 kg
      - 含逗號/空白/中文單位 -> 盡量抽取數字
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0

    # 已經是數字
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip().lower()
    s = s.replace("，", ",").replace(" ", "")
    s = s.replace("kgco2e", "").replace("co2e", "")
    s = s.replace("公斤", "kg").replace("公克", "g").replace("克", "g")

    # 你遇到的：'1.00k' -> 當成 kg
    if re.fullmatch(r"[-+]?\d+(\.\d+)?k", s):
        s = s[:-1] + "kg"

    # 常見：帶逗號的數字
    s = s.replace(",", "")

    # 先抓「數字 + 單位」
    m = re.match(r"^([-+]?\d+(\.\d+)?)(kg|g)?$", s)
    if m:
        num = float(m.group(1))
        unit = m.group(3)
        if unit == "g":
            return num / 1000.0
        # unit is kg or None => 當 kg
        return num

    # 若整串很亂（例如 "900.00g(示意)"），抽第一個數字+後面單位
    m2 = re.search(r"([-+]?\d+(\.\d+)?)\s*(kg|g|k)", s)
    if m2:
        num = float(m2.group(1))
        unit = m2.group(3)
        if unit == "g":
            return num / 1000.0
        # unit == k -> kg
        return num

    # 最後兜底：抽第一個數字當 kg
    m3 = re.search(r"([-+]?\d+(\.\d+)?)", s)
    if m3:
        return float(m3.group(1))

    return 0.0


# =============================
# 讀取 Excel（欄位自動對應）
# 你檔案不一定叫 product_name / declared_unit，所以用「猜欄位」方式
# =============================
@st.cache_data(show_spinner=False)
def load_data(excel_path: str) -> pd.DataFrame:
    path = Path(excel_path)
    if not path.exists():
        raise FileNotFoundError(f"找不到檔案：{excel_path}（請放在 repo 根目錄）")

    df = pd.read_excel(path)

    # 若有全空欄，先移除
    df = df.dropna(axis=1, how="all").copy()

    # 嘗試找「編號/群組」欄
    col_group = None
    for c in df.columns:
        s = str(c).lower()
        if any(k in s for k in ["group", "編號", "分類", "類別"]):
            col_group = c
            break
    if col_group is None:
        col_group = df.columns[0]  # 兜底：第一欄

    # 嘗試找「品名」欄
    col_name = None
    for c in df.columns:
        s = str(c).lower()
        if any(k in s for k in ["product_name", "品名", "名稱", "產品"]):
            col_name = c
            break
    if col_name is None:
        col_name = df.columns[1] if len(df.columns) > 1 else df.columns[0]

    # 嘗試找「碳足跡」欄
    col_cf = None
    for c in df.columns:
        s = str(c).lower()
        if any(k in s for k in ["carbon", "footprint", "碳足跡", "kgco2e", "co2"]):
            col_cf = c
            break
    if col_cf is None:
        col_cf = df.columns[2] if len(df.columns) > 2 else df.columns[0]

    # 嘗試找「宣告單位」欄
    col_unit = None
    for c in df.columns:
        s = str(c).lower()
        if any(k in s for k in ["declared_unit", "單位", "功能單位", "每", "unit"]):
            col_unit = c
            break
    if col_unit is None:
        col_unit = df.columns[3] if len(df.columns) > 3 else df.columns[-1]

    out = pd.DataFrame({
        "group": df[col_group].astype(str).str.strip(),
        "name": df[col_name].astype(str).str.strip(),
        "cf_raw": df[col_cf],
        "unit": df[col_unit].astype(str).str.strip(),
    })

    out["cf_kgco2e"] = out["cf_raw"].apply(parse_cf_to_kg)
    out = out.dropna(subset=["group", "name"]).reset_index(drop=True)

    return out


# =============================
# Session helpers
# =============================
def ss_init():
    st.session_state.setdefault("picked_ing_indices", [])
    st.session_state.setdefault("cook_method", {})      # key: i -> "煎炸"/"水煮"
    st.session_state.setdefault("picked_oil", {})       # key: i -> row_index
    st.session_state.setdefault("picked_water", {})     # key: i -> row_index
    st.session_state.setdefault("drink_mode", "不喝飲料")
    st.session_state.setdefault("picked_drink", None)   # row_index or None

ss_init()


def pick_new_ingredients(df_ing: pd.DataFrame):
    n = min(N_INGREDIENTS, len(df_ing))
    idxs = random.sample(list(df_ing.index), n)
    st.session_state.picked_ing_indices = idxs

    # 預設料理方式：水煮
    st.session_state.cook_method = {i: "水煮" for i in range(n)}
    st.session_state.picked_oil = {}
    st.session_state.picked_water = {}
    st.session_state.picked_drink = None


def pick_random_oil(df_oil: pd.DataFrame) -> int:
    return int(random.choice(list(df_oil.index)))


def pick_random_water(df_water: pd.DataFrame) -> int:
    return int(random.choice(list(df_water.index)))


# =============================
# 主程式
# =============================
st.title("🍽️ 一餐的碳足跡大冒險：從農場到你的胃")
st.caption("規則：編號 1 算食材；編號 1-1 / 1-2 算料理方式（油 / 水）。選項一改，表格與圖表會即時更新。")

# 讀取資料
try:
    df = load_data(EXCEL_PATH)
except Exception as e:
    st.error("讀取 Excel 失敗：請確認 `產品碳足跡3.xlsx` 放在專案根目錄，且 Streamlit Cloud 有安裝 openpyxl（requirements.txt）。")
    st.exception(e)
    st.stop()

df_ing = df[df["group"] == GROUP_ING].copy()
df_oil = df[df["group"] == GROUP_OIL].copy()
df_water = df[df["group"] == GROUP_WATER].copy()

if df_ing.empty:
    st.error("在 Excel 中找不到 group=1 的食材資料（請確認 A 欄編號是否為 1）。")
    st.stop()
if df_oil.empty:
    st.warning("找不到 group=1-1（油品）。如果你要用『煎炸』，請在 Excel 補上 1-1。")
if df_water.empty:
    st.warning("找不到 group=1-2（水）。如果你要用『水煮』，請在 Excel 補上 1-2。")

# （可選）飲料：先不分類別
# 這裡做一個「合理的兜底」：排除 1 / 1-1 / 1-2 以外的資料都當飲料池
df_drink = df[~df["group"].isin([GROUP_ING, GROUP_OIL, GROUP_WATER])].copy()


# =============================
# 左側：操作區
# =============================
left, right = st.columns([1.05, 1.0], gap="large")

with left:
    st.subheader("① 隨機抽 3 項食材（編號=1）")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("抽新食材", use_container_width=True):
            pick_new_ingredients(df_ing)
    with c2:
        if st.button("全部重置", use_container_width=True):
            st.session_state.picked_ing_indices = []
            st.session_state.cook_method = {}
            st.session_state.picked_oil = {}
            st.session_state.picked_water = {}
            st.session_state.drink_mode = "不喝飲料"
            st.session_state.picked_drink = None

    if not st.session_state.picked_ing_indices:
        st.info("請先按「抽新食材」。")
        st.stop()

    # 取出抽到的食材（固定不因選項改變）
    picked_ing = df_ing.loc[st.session_state.picked_ing_indices, ["group", "name", "cf_kgco2e", "unit"]].reset_index(drop=True)
    picked_ing = picked_ing.rename(columns={
        "group": "食材編號",
        "name": "食材名稱",
        "cf_kgco2e": "食材碳足跡(kgCO₂e)",
        "unit": "宣告單位",
    })
    picked_ing["食材碳足跡(kgCO₂e)"] = picked_ing["食材碳足跡(kgCO₂e)"].round(3)

    st.subheader("② 逐項選擇料理方式（煎炸 / 水煮）")
    methods = []
    for i in range(len(picked_ing)):
        m = st.radio(
            f"食材 {i+1} 的料理方式",
            ["水煮", "煎炸"],
            horizontal=True,
            key=f"cook_method_{i}",
        )
        st.session_state.cook_method[i] = m
        methods.append(m)

        # 為每個食材建立（或沿用）對應的油/水
        if m == "煎炸":
            if not df_oil.empty and i not in st.session_state.picked_oil:
                st.session_state.picked_oil[i] = pick_random_oil(df_oil)
        else:
            if not df_water.empty and i not in st.session_state.picked_water:
                st.session_state.picked_water[i] = pick_random_water(df_water)

    st.subheader("③ 飲料（可選）")
    drink_mode = st.radio(
        "飲料選項",
        ["隨機生成飲料", "不喝飲料"],
        horizontal=True,
        key="drink_mode",
    )

    if drink_mode == "隨機生成飲料":
        if df_drink.empty:
            st.info("目前 Excel 沒有可用的飲料資料（非 1/1-1/1-2 的列）。先當作不喝飲料。")
            st.session_state.picked_drink = None
        else:
            if st.session_state.picked_drink is None:
                st.session_state.picked_drink = int(random.choice(list(df_drink.index)))

            if st.button("換一杯飲料", use_container_width=True):
                st.session_state.picked_drink = int(random.choice(list(df_drink.index)))


# =============================
# 組合表格（右側也會用到）
# =============================
rows = []
food_sum = 0.0
cook_sum = 0.0

for i in range(len(picked_ing)):
    ing_name = picked_ing.loc[i, "食材名稱"]
    ing_cf = float(picked_ing.loc[i, "食材碳足跡(kgCO₂e)"])
    ing_unit = picked_ing.loc[i, "宣告單位"]
    food_sum += ing_cf

    method = st.session_state.cook_method.get(i, "水煮")

    if method == "煎炸" and not df_oil.empty:
        oil_idx = st.session_state.picked_oil.get(i)
        oil_row = df_oil.loc[oil_idx]
        cook_name = oil_row["name"]
        cook_cf = float(oil_row["cf_kgco2e"])
        cook_unit = oil_row["unit"]
        cook_group = oil_row["group"]
    elif method == "水煮" and not df_water.empty:
        water_idx = st.session_state.picked_water.get(i)
        water_row = df_water.loc[water_idx]
        cook_name = water_row["name"]
        cook_cf = float(water_row["cf_kgco2e"])
        cook_unit = water_row["unit"]
        cook_group = water_row["group"]
    else:
        cook_name = "（資料不足）"
        cook_cf = 0.0
        cook_unit = ""
        cook_group = ""

    cook_sum += cook_cf

    rows.append({
        "食材編號": GROUP_ING,
        "食材名稱": ing_name,
        "食材碳足跡(kgCO₂e)": round(ing_cf, 3),
        "料理方式": method,
        "油/水編號": cook_group,
        "油/水品名": cook_name,
        "油/水碳足跡(kgCO₂e)": round(cook_cf, 3),
        "油/水宣告單位": cook_unit,
        "食材宣告單位": ing_unit,
    })

table_df = pd.DataFrame(rows)

drink_cf = 0.0
drink_name = ""
if st.session_state.drink_mode == "隨機生成飲料" and st.session_state.picked_drink is not None and not df_drink.empty:
    d = df_drink.loc[st.session_state.picked_drink]
    drink_cf = float(d["cf_kgco2e"])
    drink_name = str(d["name"])

total_sum = food_sum + cook_sum + drink_cf


# =============================
# 右側：結果、表格、圖表
# =============================
with right:
    st.subheader("④ 本餐組合（表格即時更新）")

    # 表格上色：食材欄固定底色（你要的效果：食材不因選項改變，所以視覺上區隔）
    def style_food_cols(row):
        return [
            "background-color: rgba(76, 175, 80, 0.20);" if col in ["食材編號", "食材名稱", "食材碳足跡(kgCO₂e)", "食材宣告單位"] else ""
            for col in row.index
        ]

    st.dataframe(
        table_df.style.apply(style_food_cols, axis=1),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("⑤ 碳足跡加總（sum）")
    st.markdown(
        f"""
- **食材合計**：`{food_sum:.3f}` kgCO₂e  
- **料理方式（油/水）合計**：`{cook_sum:.3f}` kgCO₂e  
- **飲料**：`{drink_cf:.3f}` kgCO₂e {f"（{drink_name}）" if drink_name else ""}  
- **總計**：✅ **`{total_sum:.3f}` kgCO₂e**
        """
    )

    st.subheader("⑥ 圖表（選項一改就更新）")

    # 長條圖：三塊組成
    fig1, ax1 = plt.subplots()
    parts = ["食材", "油/水", "飲料"]
    vals = [food_sum, cook_sum, drink_cf]
    ax1.bar(parts, vals)
    ax1.set_ylabel("kgCO₂e")
    ax1.set_title("碳足跡組成（長條圖）")
    st.pyplot(fig1, use_container_width=True)

    # 圓餅圖：圖例顯示不出通常是因為 labels/legend 沒有正確設定或被擠出畫布
    # 這裡用「legend 放右側」並保留 bbox_to_anchor，通常就會穩定顯示
    fig2, ax2 = plt.subplots()
    pie_labels = []
    pie_vals = []
    for p, v in zip(parts, vals):
        if v > 0:
            pie_labels.append(p)
            pie_vals.append(v)

    wedges, texts, autotexts = ax2.pie(
        pie_vals,
        autopct=lambda pct: f"{pct:.1f}%" if pct > 0 else "",
        startangle=90,
    )
    ax2.set_title("碳足跡組成（圓餅圖）")

    # ✅ 關鍵：用 wedges 建 legend，不靠 labels 直接畫在 pie 上（避免被擠掉）
    ax2.legend(
        wedges,
        pie_labels,
        title="組成",
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        frameon=True,
    )
    st.pyplot(fig2, use_container_width=True)


# =============================
# 小提示（部署必要）
# =============================
with st.expander("部署提醒（Streamlit Cloud 需要）"):
    st.write("1) repo 根目錄放：`產品碳足跡3.xlsx`")
    st.write("2) repo 根目錄新增：`requirements.txt`，內容：")
    st.code("openpyxl", language="text")
