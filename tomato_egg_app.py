import re
import random
from typing import Optional, Tuple, Dict

import pandas as pd
import streamlit as st

# =========================
# 基本設定
# =========================
st.set_page_config(
    page_title="一餐的碳足跡大冒險：從農場到你的胃",
    page_icon="🍽️",
    layout="wide",
)

EXCEL_PATH = "產品碳足跡3.xlsx"

# 學號對應
STUDENT_MAP = {
    "BEE114105": "黃文瑜",
    "BEE114108": "陳依萱",
}

WELCOME_SCRIPT = {
    "黃文瑜": (
        "文瑜您好，歡迎來到「碳足跡觀光工廠」！\n\n"
        "今天你會拿到一張「點餐任務卡」，從三道主餐開始，選擇每道餐要用煎炸或水煮。\n"
        "系統會偷偷幫你抽出對應的油品或礦泉水，然後立刻計算這一餐的碳足跡。\n\n"
        "你可以一邊選，一邊觀察圖表的變化：\n"
        "到底是食材本身比較「碳」？還是料理方式才是隱藏的大魔王？\n\n"
        "準備好了就按下「開始體驗」吧！"
    ),
    "陳依萱": (
        "依萱您好，歡迎來到「碳足跡觀光工廠」！\n\n"
        "你即將體驗一場「從農場到你的胃」的碳足跡冒險。\n"
        "待會系統會隨機出三道主餐食材，請你為每一道餐選擇煎炸或水煮。\n"
        "同時，系統會隨機配給你一款油品或礦泉水，並把它的碳足跡一起算進去。\n\n"
        "每改一次選項，表格與圖表會即時更新。\n"
        "你會很直觀地看到：你的料理選擇，如何改變整餐的碳排結構。\n\n"
        "準備好了就按下「開始體驗」開始點餐！"
    ),
}


# =========================
# 小工具：欄位自動辨識
# =========================
def _normalize_col(s: str) -> str:
    return re.sub(r"[\s\-\_（）\(\)]+", "", str(s).strip().lower())


def pick_column(df: pd.DataFrame, candidates) -> Optional[str]:
    """
    candidates: list[list[str]]  每組是一組同義詞
    """
    norm_map = {_normalize_col(c): c for c in df.columns}
    norm_cols = set(norm_map.keys())

    for group in candidates:
        # 先找完全匹配（normalize後）
        for k in group:
            kk = _normalize_col(k)
            if kk in norm_cols:
                return norm_map[kk]

        # 再用包含關係粗略匹配
        for col_norm in norm_cols:
            for k in group:
                kk = _normalize_col(k)
                if kk and (kk in col_norm or col_norm in kk):
                    return norm_map[col_norm]

    return None


# =========================
# 碳足跡解析：更強的 parse
# =========================
def parse_cf_to_kg(v) -> float:
    """
    目標：回傳 kgCO2e (float)
    接受：
      - "900.00g" -> 0.9
      - "1.00kg" -> 1.0
      - "1.00k"  -> 1.0  (把 k 當成 kg)
      - "0.45" / 0.45 -> 0.45 (當作 kg)
      - "398.00gCO2e" 之類：會抓第一個數字 + 單位
    """
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return 0.0

    # 已是數字
    if isinstance(v, (int, float)):
        return float(v)

    s = str(v).strip().lower()
    if s == "":
        return 0.0

    # 抓數字（允許逗號）
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)", s.replace(",", ""))
    if not m:
        return 0.0
    num = float(m.group(1))

    # 判斷單位（用尾巴或字串包含）
    # g 優先（避免 "kg" 被 g 誤判：先判 kg）
    if "kg" in s:
        return num
    # 允許 "1.00k" -> 當成 kg
    if re.search(r"(^|[^a-z])k($|[^a-z])", s) or s.endswith("k"):
        return num
    if "g" in s:
        return num / 1000.0

    # 沒單位就當 kg
    return num


# =========================
# 讀 Excel + 清理
# =========================
@st.cache_data
def load_data(path: str) -> Tuple[pd.DataFrame, Dict[str, str]]:
    df = pd.read_excel(path)

    col_group = pick_column(df, [
        ["group", "編號", "分類", "類別", "群組", "分組", "編碼", "代碼"]
    ])
    col_name = pick_column(df, [
        ["product_name", "品名", "產品名稱", "名稱", "商品名稱"]
    ])
    col_cf = pick_column(df, [
        ["product_carbon_footprint_data", "碳足跡", "carbonfootprint", "cf", "co2e", "kgco2e"]
    ])
    col_unit = pick_column(df, [
        ["declared_unit", "宣告單位", "單位", "功能單位", "包裝單位"]
    ])

    missing = [k for k, v in {
        "group": col_group,
        "product_name": col_name,
        "product_carbon_footprint_data": col_cf,
        "declared_unit": col_unit,
    }.items() if v is None]

    if missing:
        raise ValueError(
            "Excel 欄位辨識失敗，缺少欄位："
            + ", ".join(missing)
            + "。請確認至少有：編號/群組、品名、碳足跡、宣告單位。"
        )

    df = df[[col_group, col_name, col_cf, col_unit]].copy()
    df.columns = ["group", "product_name", "product_carbon_footprint_data", "declared_unit"]

    # group 一律轉字串（避免 1.0 之類）
    df["group"] = df["group"].astype(str).str.strip()

    # 解析碳足跡（kg）
    df["cf_kgco2e"] = df["product_carbon_footprint_data"].apply(parse_cf_to_kg).astype(float)

    return df, {
        "group": col_group,
        "product_name": col_name,
        "product_carbon_footprint_data": col_cf,
        "declared_unit": col_unit,
    }


def df_by_group(df: pd.DataFrame, group_value: str) -> pd.DataFrame:
    gv = str(group_value).strip()
    out = df[df["group"].str.strip() == gv].copy()
    return out.reset_index(drop=True)


# =========================
# Session 初始化
# =========================
def init_state():
    if "stage" not in st.session_state:
        st.session_state.stage = "home"  # home -> order

    if "student_id" not in st.session_state:
        st.session_state.student_id = ""

    if "student_name" not in st.session_state:
        st.session_state.student_name = ""

    if "picked_food_idx" not in st.session_state:
        st.session_state.picked_food_idx = []  # index in group=1 dataframe

    if "cook_choice" not in st.session_state:
        st.session_state.cook_choice = {}  # i -> "煎炸"/"水煮"

    if "cook_item_idx" not in st.session_state:
        st.session_state.cook_item_idx = {}  # i -> index in oil/water df

    if "drink_mode" not in st.session_state:
        st.session_state.drink_mode = "我不喝飲料"  # or 隨機生成飲料

    if "drink_idx" not in st.session_state:
        st.session_state.drink_idx = None  # index in drink df


init_state()


# =========================
# UI：一些 CSS（讓手機直式也比較舒服）
# =========================
st.markdown(
    """
<style>
/* 讓內容區不要太寬，手機直式更舒服 */
.block-container {max-width: 1100px; padding-top: 1.2rem; padding-bottom: 2rem;}

/* 表格字稍微小一點 */
[data-testid="stDataFrame"] {font-size: 0.9rem;}
/* 大標題在手機別太爆 */
h1 {font-size: 2.0rem;}
h2 {font-size: 1.4rem;}
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# 讀資料
# =========================
try:
    df_all, colmap = load_data(EXCEL_PATH)
except Exception as e:
    st.error(f"讀取 Excel 失敗：請確認 `{EXCEL_PATH}` 放在專案根目錄，且欄位正確。")
    st.exception(e)
    st.stop()

df_food = df_by_group(df_all, "1")     # 食材
df_oil = df_by_group(df_all, "1-1")    # 油品（煎炸）
df_water = df_by_group(df_all, "1-2")  # 水（水煮）
df_drink = df_by_group(df_all, "2")    # 飲料（只允許 group=2）

# =========================
# 母頁（首頁）
# =========================
st.title("🍽️ 一餐的碳足跡大冒險：從農場到你的胃")

if st.session_state.stage == "home":
    st.subheader("母頁：報到")

    sid = st.text_input("您的預約號碼：輸入學號", value=st.session_state.student_id, placeholder="例如：BEE114108")
    sid = sid.strip().upper()
    st.session_state.student_id = sid

    name = STUDENT_MAP.get(sid, "")
    st.session_state.student_name = name

    if name:
        st.success(f"{name} 您好！已完成識別。")
        st.markdown(WELCOME_SCRIPT.get(name, "歡迎來到碳足跡觀光工廠！"))
        if st.button("✅ 開始體驗（開始點餐）"):
            st.session_state.stage = "order"

            # 第一次進入就先抽食材
            if len(df_food) >= 3:
                st.session_state.picked_food_idx = random.sample(range(len(df_food)), 3)
            else:
                st.session_state.picked_food_idx = list(range(len(df_food)))

            # 重置料理選擇
            st.session_state.cook_choice = {}
            st.session_state.cook_item_idx = {}

            # 預設：都先水煮（避免一進來就全部油）
            for i in range(len(st.session_state.picked_food_idx)):
                st.session_state.cook_choice[i] = "水煮"
                if len(df_water) > 0:
                    st.session_state.cook_item_idx[i] = random.randrange(len(df_water))
                else:
                    st.session_state.cook_item_idx[i] = None

            # 飲料預設不喝
            st.session_state.drink_mode = "我不喝飲料"
            st.session_state.drink_idx = None

            st.rerun()
    else:
        st.info("請輸入指定學號（目前內建：BEE114105、BEE114108）。")

    st.stop()

# =========================
# 點餐頁（主流程）
# =========================
st.subheader("開始點餐：主餐")

# ---- 控制按鈕列
c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    if st.button("🎲 重新抽 3 項食材"):
        if len(df_food) >= 3:
            st.session_state.picked_food_idx = random.sample(range(len(df_food)), 3)
        else:
            st.session_state.picked_food_idx = list(range(len(df_food)))

        # 重置選擇
        st.session_state.cook_choice = {}
        st.session_state.cook_item_idx = {}
        for i in range(len(st.session_state.picked_food_idx)):
            st.session_state.cook_choice[i] = "水煮"
            st.session_state.cook_item_idx[i] = random.randrange(len(df_water)) if len(df_water) else None

        st.rerun()

with c2:
    if st.button("🔄 全部重置"):
        st.session_state.stage = "home"
        st.session_state.student_id = ""
        st.session_state.student_name = ""
        st.session_state.picked_food_idx = []
        st.session_state.cook_choice = {}
        st.session_state.cook_item_idx = {}
        st.session_state.drink_mode = "我不喝飲料"
        st.session_state.drink_idx = None
        st.rerun()

with c3:
    st.caption("規則：編號 1 算食材；編號 1-1 / 1-2 算料理方式（油 / 水）。選項一改，表格與圖表會即時更新。")


# ---- 確保已抽到食材
if not st.session_state.picked_food_idx:
    if len(df_food) >= 3:
        st.session_state.picked_food_idx = random.sample(range(len(df_food)), 3)
    else:
        st.session_state.picked_food_idx = list(range(len(df_food)))

# ---- 取出三項食材
foods = df_food.loc[st.session_state.picked_food_idx, ["product_name", "cf_kgco2e", "declared_unit"]].copy()
foods = foods.reset_index(drop=True)
foods["餐序"] = [f"第一道餐", f"第二道餐", f"第三道餐"][:len(foods)]
foods = foods[["餐序", "product_name", "cf_kgco2e", "declared_unit"]]
foods = foods.rename(columns={
    "product_name": "食材名稱",
    "cf_kgco2e": "食材碳足跡(kgCO₂e)",
    "declared_unit": "宣告單位",
})

# ---- 主區：手機直式友善（用 tabs 讓畫面不擠）
tab1, tab2 = st.tabs(["🍲 點餐與表格", "📊 圖表（即時更新）"])

# =========================
# Tab1：點餐與表格
# =========================
with tab1:
    st.markdown("### ① 本次主餐食材（先顯示，且食材列底色固定）")

    # 讓食材列有底色（整列）
    def _style_food_rows(df_show: pd.DataFrame):
        # 食材列底色（淡綠）
        return pd.DataFrame(
            [["background-color: rgba(46, 204, 113, 0.18)"] * df_show.shape[1]] * df_show.shape[0],
            columns=df_show.columns,
            index=df_show.index,
        )

    st.dataframe(
        foods.style.apply(_style_food_rows, axis=None).format({"食材碳足跡(kgCO₂e)": "{:.3f}"}),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### ② 選擇每道餐的調理方式（煎炸 / 水煮）")

    # 每道餐：radio + 顯示系統隨機油/水
    cook_rows = []
    for i in range(len(foods)):
        meal_name = foods.loc[i, "餐序"]

        st.markdown(f"**{meal_name}：**")

        # radio 的 key 要固定，避免 session_state 寫入衝突
        choice_key = f"cook_choice_{i}"

        # 讀目前選擇
        default_choice = st.session_state.cook_choice.get(i, "水煮")
        choice = st.radio(
            label="",
            options=["水煮", "煎炸"],
            horizontal=True,
            index=0 if default_choice == "水煮" else 1,
            key=choice_key,
        )
        st.session_state.cook_choice[i] = choice

        # 決定要抽油或水（該餐對應一個隨機項目，且一旦選擇就固定，除非使用者改模式）
        item_key = f"cook_item_{i}"

        def ensure_cook_item(i_: int, mode_: str):
            # 若該餐尚未設定，或 mode 改變，就重新抽
            prev_mode = st.session_state.get(f"_prev_mode_{i_}", None)
            if (i_ not in st.session_state.cook_item_idx) or (prev_mode != mode_):
                if mode_ == "煎炸":
                    st.session_state.cook_item_idx[i_] = random.randrange(len(df_oil)) if len(df_oil) else None
                else:
                    st.session_state.cook_item_idx[i_] = random.randrange(len(df_water)) if len(df_water) else None
            st.session_state[f"_prev_mode_{i_}"] = mode_

        ensure_cook_item(i, choice)

        if choice == "煎炸":
            if len(df_oil) == 0:
                st.warning("找不到 1-1（油品）資料。")
                cook_name, cook_cf, cook_unit = "（無油品資料）", 0.0, ""
                cook_group = "1-1"
            else:
                idx = st.session_state.cook_item_idx[i]
                row = df_oil.loc[idx]
                cook_name = str(row["product_name"])
                cook_cf = float(row["cf_kgco2e"])
                cook_unit = str(row["declared_unit"])
                cook_group = "1-1"
        else:
            if len(df_water) == 0:
                st.warning("找不到 1-2（水）資料。")
                cook_name, cook_cf, cook_unit = "（無水資料）", 0.0, ""
                cook_group = "1-2"
            else:
                idx = st.session_state.cook_item_idx[i]
                row = df_water.loc[idx]
                cook_name = str(row["product_name"])
                cook_cf = float(row["cf_kgco2e"])
                cook_unit = str(row["declared_unit"])
                cook_group = "1-2"

        st.caption(f"系統隨機配給：{cook_name}（{cook_cf:.3f} kgCO₂e）")

        cook_rows.append({
            "餐序": meal_name,
            "調理方式": choice,
            "油/水編號": cook_group,
            "油/水名稱": cook_name,
            "油/水碳足跡(kgCO₂e)": cook_cf,
            "油/水宣告單位": cook_unit,
        })

    st.markdown("### ③ 飲料（可選）")
    # 飲料只有兩選項：隨機生成飲料 / 我不喝飲料
    drink_mode = st.radio(
        "飲料選項",
        options=["隨機生成飲料", "我不喝飲料"],
        horizontal=True,
        index=0 if st.session_state.drink_mode == "隨機生成飲料" else 1,
        key="drink_mode_radio",
    )
    st.session_state.drink_mode = drink_mode

    drink_name, drink_cf, drink_unit = "（不喝飲料）", 0.0, ""
    if drink_mode == "隨機生成飲料":
        if len(df_drink) == 0:
            st.warning("找不到 group=2（飲料）資料。請在 Excel 把飲料列標成 2。")
        else:
            if st.session_state.drink_idx is None:
                st.session_state.drink_idx = random.randrange(len(df_drink))
            # 提供換一杯
            if st.button("🥤 換一杯飲料"):
                st.session_state.drink_idx = random.randrange(len(df_drink))
                st.rerun()

            drow = df_drink.loc[st.session_state.drink_idx]
            drink_name = str(drow["product_name"])
            drink_cf = float(drow["cf_kgco2e"])
            drink_unit = str(drow["declared_unit"])
            st.info(f"本次飲料：{drink_name}（{drink_cf:.3f} kgCO₂e）")

    # 組合表格（食材底色、油水不底色）
    cook_df = pd.DataFrame(cook_rows)

    combo = foods.copy()
    combo["食材編號"] = "1"
    combo = combo[["食材編號", "餐序", "食材名稱", "食材碳足跡(kgCO₂e)", "宣告單位"]]

    combo = combo.merge(
        cook_df[["餐序", "調理方式", "油/水編號", "油/水名稱", "油/水碳足跡(kgCO₂e)", "油/水宣告單位"]],
        on="餐序",
        how="left",
    )

    st.markdown("### ④ 本餐組合（表格即時更新）")

    def style_combo(df_show: pd.DataFrame):
        styles = pd.DataFrame("", index=df_show.index, columns=df_show.columns)
        # 食材欄位上底色（淡綠）
        food_cols = ["食材編號", "餐序", "食材名稱", "食材碳足跡(kgCO₂e)", "宣告單位"]
        for c in food_cols:
            if c in styles.columns:
                styles[c] = "background-color: rgba(46, 204, 113, 0.18);"
        return styles

    st.dataframe(
        combo.style.apply(style_combo, axis=None).format({
            "食材碳足跡(kgCO₂e)": "{:.3f}",
            "油/水碳足跡(kgCO₂e)": "{:.3f}",
        }),
        use_container_width=True,
        hide_index=True,
    )

    # 總和
    food_sum = float(combo["食材碳足跡(kgCO₂e)"].sum())
    cook_sum = float(combo["油/水碳足跡(kgCO₂e)"].sum())
    total_sum = food_sum + cook_sum + float(drink_cf)

    st.markdown("### ⑤ 碳足跡加總（sum）")
    st.write(f"- 食材合計：**{food_sum:.3f} kgCO₂e**")
    st.write(f"- 料理方式（油/水）合計：**{cook_sum:.3f} kgCO₂e**")
    st.write(f"- 飲料：**{float(drink_cf):.3f} kgCO₂e**（{drink_name if drink_mode=='隨機生成飲料' else '不喝'}）")
    st.success(f"✅ 總計：**{total_sum:.3f} kgCO₂e**")


# =========================
# Tab2：圖表（即時更新）
# =========================
with tab2:
    st.markdown("### ⑥ 圖表（選項一改就更新）")

    # 資料彙總（避免中文字型問題：若顯示不出，就改英文）
    # 這裡用簡短標籤，降低字型出錯率
    labels_zh = ["食材", "油/水", "飲料"]
    labels_en = ["Food", "Oil/Water", "Drink"]

    food_sum = float(foods["食材碳足跡(kgCO₂e)"].sum())
    cook_sum = float(pd.DataFrame(cook_rows)["油/水碳足跡(kgCO₂e)"].sum()) if cook_rows else 0.0
    drink_sum = float(drink_cf) if st.session_state.drink_mode == "隨機生成飲料" else 0.0

    parts = [food_sum, cook_sum, drink_sum]

    # A) 主餐食材橫條圖（小一點）
    st.markdown("#### 主餐食材（橫條圖）")
    bar_df = foods.copy()
    bar_df["食材碳足跡(kgCO₂e)"] = bar_df["食材碳足跡(kgCO₂e)"].astype(float)

    # 用 st.bar_chart（簡潔、手機友善）
    bar_show = bar_df.set_index("食材名稱")[["食材碳足跡(kgCO₂e)"]]
    st.bar_chart(bar_show, height=240, use_container_width=True)

    # B) 圓餅圖（用 matplotlib，強制 legend 在旁邊）
    st.markdown("#### 碳足跡結構（圓餅圖）")

    # 若某一塊是 0 就不要畫，避免 legend 怪
    filtered = [(labels_zh[i], labels_en[i], parts[i]) for i in range(3) if parts[i] > 0]
    if not filtered:
        st.info("目前沒有可視化的碳足跡數值（全部為 0）。")
    else:
        try:
            import matplotlib.pyplot as plt

            # 嘗試中文標籤，若字型不支援也至少不會中斷（必要時改英文）
            use_labels = [x[0] for x in filtered]
            values = [x[2] for x in filtered]

            fig, ax = plt.subplots(figsize=(5.2, 3.2), dpi=150)
            wedges, texts, autotexts = ax.pie(
                values,
                autopct=lambda p: f"{p:.1f}%" if p > 0 else "",
                startangle=90,
            )
            ax.axis("equal")

            # legend 放右側（避免擋圖）
            ax.legend(
                wedges,
                use_labels,
                title="圖例",
                loc="center left",
                bbox_to_anchor=(1.02, 0.5),
                frameon=False,
            )
            ax.set_title("碳足跡占比")

            st.pyplot(fig, use_container_width=True)

        except Exception:
            # 若中文字型導致問題，用英文再畫一次
            import matplotlib.pyplot as plt

            use_labels = [x[1] for x in filtered]
            values = [x[2] for x in filtered]

            fig, ax = plt.subplots(figsize=(5.2, 3.2), dpi=150)
            wedges, texts, autotexts = ax.pie(
                values,
                autopct=lambda p: f"{p:.1f}%" if p > 0 else "",
                startangle=90,
            )
            ax.axis("equal")
            ax.legend(
                wedges,
                use_labels,
                title="Legend",
                loc="center left",
                bbox_to_anchor=(1.02, 0.5),
                frameon=False,
            )
            ax.set_title("Carbon Footprint Share")
            st.pyplot(fig, use_container_width=True)
