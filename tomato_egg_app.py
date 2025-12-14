import re
import random
from io import BytesIO

import pandas as pd
import streamlit as st
import altair as alt


# =========================
# 0) 基本設定（手機直式友好）
# =========================
st.set_page_config(
    page_title="一餐的碳足跡大冒險：從農場到你的胃",
    page_icon="🍽️",
    layout="centered",
)

# 小字體 + 卡片感（不靠外部 CSS 檔）
st.markdown(
    """
<style>
/* 讓整體更像「有頁面區隔」的互動體驗 */
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
h1, h2, h3 { letter-spacing: 0.2px; }
.small-note { opacity: 0.8; font-size: 0.92rem; }
.card {
  padding: 14px 14px 10px 14px;
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.10);
  background: rgba(255,255,255,0.03);
}
</style>
""",
    unsafe_allow_html=True,
)

APP_TITLE = "🍽️ 一餐的碳足跡大冒險：從農場到你的胃"
EXCEL_PATH_DEFAULT = "產品碳足跡3.xlsx"

# 學號/預約號碼（照你要求硬寫）
VALID_IDS = {
    "BEE114105黃文瑜": {"name": "文瑜"},
    "BEE114108陳依萱": {"name": "依萱"},
}


# =========================
# 1) 工具：碳足跡字串解析
#    支援: 900g / 1.00kg / 1.00k / "450.00gCO2e" 等
#    一律轉成 kgCO2e (float)
# =========================
def parse_cf_to_kg(value) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return float("nan")

    # 本來就是數字 -> 當成 kg
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip().lower()
    s = s.replace(" ", "")
    s = s.replace("kgco2e", "kg").replace("gco2e", "g")

    # 常見：1.00k（你遇到的）
    # 視為 1.00kg
    if re.fullmatch(r"[-+]?\d*\.?\d+k", s):
        return float(s[:-1])

    # 抓出數字 + 單位
    m = re.match(r"([-+]?\d*\.?\d+)(kg|g)?$", s)
    if m:
        num = float(m.group(1))
        unit = m.group(2)
        if unit == "g":
            return num / 1000.0
        # unit == "kg" 或 None：當作 kg
        return num

    # 若字串內含 g 或 kg，但不是純尾綴形式（例如：'900.00g(每瓶...)'）
    m2 = re.search(r"([-+]?\d*\.?\d+)\s*(kg|g)", s)
    if m2:
        num = float(m2.group(1))
        unit = m2.group(2)
        return num / 1000.0 if unit == "g" else num

    # 最後兜底：只抓第一個數字（當 kg）
    m3 = re.search(r"([-+]?\d*\.?\d+)", s)
    if m3:
        return float(m3.group(1))

    raise ValueError(f"無法解析碳足跡數值：{value}")


# =========================
# 2) 讀取 Excel（不要求欄名叫 group）
#    直接取前 4 欄：編號 / 品名 / 碳足跡 / 宣告單位
# =========================
@st.cache_data(show_spinner=False)
def load_data_from_excel(file_bytes: bytes, filename: str) -> pd.DataFrame:
    df = pd.read_excel(BytesIO(file_bytes), engine="openpyxl")

    if df.shape[1] < 4:
        raise ValueError(
            f"Excel 欄位太少（目前 {df.shape[1]} 欄）。至少需要 4 欄：編號、品名、碳足跡、宣告單位。"
        )

    # 直接取前四欄，避免你卡在欄位命名
    cols = list(df.columns[:4])
    df = df[cols].copy()
    df.columns = ["code", "product_name", "product_carbon_footprint_data", "declared_unit"]

    # 正規化 code：全部轉字串、去空白
    df["code"] = df["code"].astype(str).str.strip()

    # 碳足跡轉成 kgCO2e
    df["cf_kgco2e"] = df["product_carbon_footprint_data"].apply(parse_cf_to_kg)

    # 基本清理
    df["product_name"] = df["product_name"].astype(str).str.strip()
    df["declared_unit"] = df["declared_unit"].astype(str).str.strip()

    # 去掉 cf 無法解析造成的 NaN
    df = df.dropna(subset=["cf_kgco2e"]).reset_index(drop=True)

    return df


def read_excel_source() -> pd.DataFrame:
    """
    優先讀 repo 根目錄的 產品碳足跡3.xlsx，
    若沒有，就讓使用者上傳（避免 Streamlit Cloud 路徑/檔案不同步）
    """
    st.caption("📄 資料來源：優先讀取專案根目錄的 Excel；若讀不到可改用上傳。")

    # 1) 先試 repo 檔
    try:
        with open(EXCEL_PATH_DEFAULT, "rb") as f:
            file_bytes = f.read()
        df = load_data_from_excel(file_bytes, EXCEL_PATH_DEFAULT)
        return df
    except Exception:
        pass

    # 2) 讓使用者上傳兜底
    up = st.file_uploader("或改用上傳 Excel（.xlsx）", type=["xlsx"])
    if up is None:
        raise FileNotFoundError(
            f"讀取失敗：請確認 {EXCEL_PATH_DEFAULT} 放在 repo 根目錄，或改用上傳。"
        )
    df = load_data_from_excel(up.getvalue(), up.name)
    return df


# =========================
# 3) 隨機抽題邏輯
# =========================
def sample_rows(df: pd.DataFrame, code_value: str, n: int) -> pd.DataFrame:
    sub = df[df["code"] == code_value].copy()
    if len(sub) == 0:
        raise ValueError(f"在 Excel 中找不到 code = {code_value} 的資料。")
    n = min(n, len(sub))
    return sub.sample(n=n, replace=False, random_state=random.randint(1, 10_000)).reset_index(drop=True)


def pick_one(df: pd.DataFrame, code_value: str) -> dict:
    sub = df[df["code"] == code_value]
    if len(sub) == 0:
        raise ValueError(f"在 Excel 中找不到 code = {code_value} 的資料。")
    row = sub.sample(n=1, random_state=random.randint(1, 10_000)).iloc[0]
    return {
        "code": row["code"],
        "product_name": row["product_name"],
        "cf_kgco2e": float(row["cf_kgco2e"]),
        "declared_unit": row["declared_unit"],
    }


# =========================
# 4) Session 初始化
# =========================
if "page" not in st.session_state:
    st.session_state.page = "home"  # home -> main

if "visitor_id" not in st.session_state:
    st.session_state.visitor_id = ""

if "meal_items" not in st.session_state:
    st.session_state.meal_items = None  # DataFrame (code=1 的 3 項)

if "cook_picks" not in st.session_state:
    # 每道餐的油/水隨機結果
    st.session_state.cook_picks = {}  # {idx: {...}}

if "cook_method" not in st.session_state:
    st.session_state.cook_method = {}  # {idx: "煎炸"/"水煮"}

if "drink_mode" not in st.session_state:
    st.session_state.drink_mode = "隨機生成飲料"

if "drink_pick" not in st.session_state:
    st.session_state.drink_pick = None


# =========================
# 5) 母頁（預約號碼）
# =========================
st.title(APP_TITLE)

if st.session_state.page == "home":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🏷️ 母頁：報到與入場")
    st.write("請輸入您的預約號碼（學號＋姓名）。")

    visitor_id = st.text_input(
        "您的預約號碼：",
        value=st.session_state.visitor_id,
        placeholder="例如：BEE114108陳依萱",
    )

    colA, colB = st.columns([1, 1])
    with colA:
        if st.button("確認報到", use_container_width=True):
            st.session_state.visitor_id = visitor_id.strip()

    with colB:
        if st.button("直接開始（跳過）", use_container_width=True):
            # 若沒輸入就當訪客
            if not st.session_state.visitor_id:
                st.session_state.visitor_id = "訪客"
            st.session_state.page = "main"
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    # 顯示歡迎詞
    vid = st.session_state.visitor_id.strip()
    if vid:
        if vid in VALID_IDS:
            name = VALID_IDS[vid]["name"]
            st.success(f"{name}您好，報到成功 ✅")

            welcome_text = f"""
{name}您好，歡迎來到「碳足跡觀光工廠」！

接下來你會體驗一場「從農場到你的胃」的碳足跡大冒險：
- 你會先抽到 3 項食材（每項都有產品碳足跡）。
- 接著你要替每一道餐決定料理方式：**煎炸** 或 **水煮**。
- 系統會自動替你配對一種油或水（也有它的碳足跡）。
- 最後你可以選擇是否要喝飲料，看看總量怎麼變。

準備好就按下「開始點餐」吧！
"""
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.write(welcome_text)
            if st.button("🍴 開始點餐", use_container_width=True):
                st.session_state.page = "main"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.warning("目前此預約號碼不在名單內（可按「直接開始（跳過）」當訪客進入）。")

    st.stop()


# =========================
# 6) 主頁：點餐 + 即時更新
# =========================
# 讀 Excel
try:
    df_all = read_excel_source()
except Exception as e:
    st.error("讀取 Excel 失敗：請確認檔案在 repo 根目錄，或用上傳功能。")
    st.exception(e)
    st.stop()

# 分類
df_food = df_all[df_all["code"] == "1"].copy()     # 食材
df_oil = df_all[df_all["code"] == "1-1"].copy()    # 油
df_water = df_all[df_all["code"] == "1-2"].copy()  # 水
df_drink = df_all[df_all["code"] == "2"].copy()    # 飲料（只允許 2）

if len(df_food) == 0:
    st.error("Excel 裡找不到 code=1 的食材。請確認你的『編號』欄有 1。")
    st.stop()

# 上方控制：抽食材 / 重置
c1, c2 = st.columns([1, 1])
with c1:
    if st.button("🎲 抽 3 項食材（主餐）", use_container_width=True):
        st.session_state.meal_items = sample_rows(df_all, "1", 3)
        st.session_state.cook_method = {i: "水煮" for i in range(len(st.session_state.meal_items))}
        st.session_state.cook_picks = {}
        st.session_state.drink_pick = None
        st.rerun()
with c2:
    if st.button("♻️ 全部重置", use_container_width=True):
        for k in ["meal_items", "cook_picks", "cook_method", "drink_pick"]:
            st.session_state[k] = None if k in ["meal_items", "drink_pick"] else {}
        st.rerun()

# 若還沒抽就先抽一次（你說希望表格一開始就能看到）
if st.session_state.meal_items is None:
    st.session_state.meal_items = sample_rows(df_all, "1", 3)
    st.session_state.cook_method = {i: "水煮" for i in range(len(st.session_state.meal_items))}
    st.session_state.cook_picks = {}
    st.session_state.drink_pick = None

meal_df = st.session_state.meal_items.reset_index(drop=True)

st.subheader("🍛 開始點餐：主餐（3 項食材）")
st.caption("規則：編號 1 算食材；編號 1-1 / 1-2 算料理方式（油/水）；編號 2 算飲料。")

# 食材表格（固定底色）
food_table = meal_df[["product_name", "cf_kgco2e", "declared_unit"]].copy()
food_table.columns = ["食材名稱", "食材碳足跡(kgCO₂e)", "宣告單位"]
food_table["食材碳足跡(kgCO₂e)"] = food_table["食材碳足跡(kgCO₂e)"].astype(float).round(3)

def style_food_table(df):
    return df.style.apply(
        lambda _: ["background-color: rgba(46, 204, 113, 0.20)"] * df.shape[1],
        axis=1
    )

st.dataframe(style_food_table(food_table), use_container_width=True, height=160)

# 料理選擇（逐道餐）
st.subheader("🍳 選擇調理方式（每道餐各選一次）")

for i in range(len(meal_df)):
    item_name = meal_df.loc[i, "product_name"]
    item_cf = float(meal_df.loc[i, "cf_kgco2e"])

    # 每次 render 先確保有 pick（油/水）可顯示在選項括弧內
    if i not in st.session_state.cook_picks:
        # 預設依 cook_method 先抽一個
        method = st.session_state.cook_method.get(i, "水煮")
        if method == "煎炸":
            st.session_state.cook_picks[i] = pick_one(df_all, "1-1")
        else:
            st.session_state.cook_picks[i] = pick_one(df_all, "1-2")

    pick = st.session_state.cook_picks[i]

    # 組選項文字（括弧附：隨機油/水名稱與碳足跡）
    # 煎炸 -> 1-1；水煮 -> 1-2
    # 注意：若 해당 code 資料不存在，要提示但不中斷整體
    oil_text = "（找不到油品資料 code=1-1）"
    water_text = "（找不到水品資料 code=1-2）"
    if len(df_oil) > 0:
        oil_text = f"（{pick['product_name']} / {pick['cf_kgco2e']:.3f}）" if pick["code"] == "1-1" else f"（隨機油品 / 參考 {df_oil.iloc[0]['cf_kgco2e']:.3f}）"
    if len(df_water) > 0:
        water_text = f"（{pick['product_name']} / {pick['cf_kgco2e']:.3f}）" if pick["code"] == "1-2" else f"（隨機水品 / 參考 {df_water.iloc[0]['cf_kgco2e']:.3f}）"

    st.markdown(f"**第 {i+1} 道餐：{item_name}**（食材 {item_cf:.3f} kgCO₂e）")

    # 用 key 保證不會寫 session_state 造成 StreamlitAPIException
    options = [
        f"水煮 {water_text}",
        f"煎炸 {oil_text}",
    ]

    # 目前選擇
    current_method = st.session_state.cook_method.get(i, "水煮")
    current_idx = 0 if current_method == "水煮" else 1

    chosen = st.radio(
        " ",
        options,
        index=current_idx,
        horizontal=True,
        key=f"cook_choice_{i}",
        label_visibility="collapsed",
    )

    # 根據使用者改變 → 立刻重新抽對應油/水，並更新 cook_method
    new_method = "水煮" if chosen.startswith("水煮") else "煎炸"
    if new_method != st.session_state.cook_method.get(i, "水煮"):
        st.session_state.cook_method[i] = new_method
        st.session_state.cook_picks[i] = pick_one(df_all, "1-2" if new_method == "水煮" else "1-1")
        st.rerun()

    st.divider()


# 飲料（兩個選項：隨機生成 or 不喝）
st.subheader("🥤 飲料（可選）")
drink_mode = st.radio(
    "飲料選項",
    ["隨機生成飲料", "我不喝飲料"],
    index=0 if st.session_state.drink_mode == "隨機生成飲料" else 1,
    horizontal=True,
    key="drink_mode_radio",
)

# 不要直接在同一次 render 寫 st.session_state['drink_mode']=...（容易出你截圖那種 APIException）
if drink_mode != st.session_state.drink_mode:
    st.session_state.drink_mode = drink_mode
    if drink_mode == "我不喝飲料":
        st.session_state.drink_pick = None
    else:
        # 若切回隨機，先抽一杯（只從 code=2）
        if len(df_drink) > 0:
            st.session_state.drink_pick = pick_one(df_all, "2")
        else:
            st.session_state.drink_pick = None
    st.rerun()

colD1, colD2 = st.columns([1, 1])
with colD1:
    if st.session_state.drink_mode == "隨機生成飲料":
        if st.button("🔄 換一杯飲料", use_container_width=True):
            if len(df_drink) > 0:
                st.session_state.drink_pick = pick_one(df_all, "2")
            else:
                st.session_state.drink_pick = None
            st.rerun()
with colD2:
    st.write("")

drink_cf = 0.0
drink_name = "不喝飲料"
drink_unit = ""
if st.session_state.drink_mode == "隨機生成飲料":
    if len(df_drink) == 0:
        st.warning("找不到 code=2 的飲料資料，因此目前飲料固定為：不喝飲料。")
        st.session_state.drink_pick = None
    else:
        if st.session_state.drink_pick is None:
            st.session_state.drink_pick = pick_one(df_all, "2")
        dp = st.session_state.drink_pick
        drink_cf = float(dp["cf_kgco2e"])
        drink_name = dp["product_name"]
        drink_unit = dp["declared_unit"]
        st.info(f"本次飲料：**{drink_name}**（{drink_cf:.3f} kgCO₂e）")


# =========================
# 7) 組合表格（食材底色 + 料理方式資訊）
# =========================
rows = []
food_sum = 0.0
cook_sum = 0.0

for i in range(len(meal_df)):
    food_name = meal_df.loc[i, "product_name"]
    food_cf_i = float(meal_df.loc[i, "cf_kgco2e"])
    food_unit_i = str(meal_df.loc[i, "declared_unit"])

    method = st.session_state.cook_method.get(i, "水煮")
    pick = st.session_state.cook_picks.get(i)

    cook_type = "水品" if method == "水煮" else "油品"
    pick_name = pick["product_name"] if pick else "（未抽到）"
    pick_cf = float(pick["cf_kgco2e"]) if pick else 0.0
    pick_unit = pick["declared_unit"] if pick else ""

    food_sum += food_cf_i
    cook_sum += pick_cf

    rows.append(
        {
            "食材名稱": food_name,
            "食材碳足跡(kgCO₂e)": round(food_cf_i, 3),
            "宣告單位": food_unit_i,
            "料理方式": method,
            "油/水類型": cook_type,
            "油/水名稱": pick_name,
            "油/水碳足跡(kgCO₂e)": round(pick_cf, 3),
            "油/水宣告單位": pick_unit,
        }
    )

combo_df = pd.DataFrame(rows)

def style_combo(df):
    # 只把「食材三欄」上底色（你說食材不會變，希望視覺固定）
    food_cols = ["食材名稱", "食材碳足跡(kgCO₂e)", "宣告單位"]
    def row_style(_row):
        styles = []
        for c in df.columns:
            if c in food_cols:
                styles.append("background-color: rgba(46, 204, 113, 0.18)")
            else:
                styles.append("")
        return styles
    return df.style.apply(row_style, axis=1)

st.subheader("📋 本餐組合（表格即時更新）")
st.dataframe(style_combo(combo_df), use_container_width=True, height=220)


# =========================
# 8) 總碳足跡 + 圖表（小一點、即時更新）
# =========================
total = food_sum + cook_sum + drink_cf

st.subheader("✅ 碳足跡加總（sum）")
st.markdown(
    f"""
- **食材合計**：`{food_sum:.3f}` kgCO₂e  
- **料理方式（油/水）合計**：`{cook_sum:.3f}` kgCO₂e  
- **飲料**：`{drink_cf:.3f}` kgCO₂e（{drink_name}）  
- **總計**：✅ **`{total:.3f}` kgCO₂e**
"""
)

st.subheader("📊 圖表（選項一改就更新）")

chart_data = pd.DataFrame(
    [
        {"項目": "Food", "kgCO2e": food_sum},
        {"項目": "Cooking", "kgCO2e": cook_sum},
        {"項目": "Drink", "kgCO2e": drink_cf},
    ]
)

# 長條圖（橫向、縮小）
bar = (
    alt.Chart(chart_data)
    .mark_bar()
    .encode(
        y=alt.Y("項目:N", sort="-x", title=""),
        x=alt.X("kgCO2e:Q", title="kgCO₂e"),
        tooltip=["項目", alt.Tooltip("kgCO2e:Q", format=".3f")],
    )
    .properties(height=140)
)

st.altair_chart(bar, use_container_width=True)

# 圓餅圖（legend 一定要顯示：用 Altair，且 legend 放右側）
pie = (
    alt.Chart(chart_data[chart_data["kgCO2e"] > 0])
    .mark_arc()
    .encode(
        theta=alt.Theta("kgCO2e:Q"),
        color=alt.Color("項目:N", legend=alt.Legend(orient="right", title="")),
        tooltip=["項目", alt.Tooltip("kgCO2e:Q", format=".3f")],
    )
    .properties(height=220)
)

st.altair_chart(pie, use_container_width=True)

st.caption("如果中文在某些環境字型顯示不完整，圖表分類已改用英文（Food/Cooking/Drink）以避免缺字。")
