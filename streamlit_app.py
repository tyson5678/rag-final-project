import streamlit as st
import pandas as pd
import sqlite3
from groq import Groq
import os
import datetime
import time

# ==========================================
# 1. 企業級 UI 配置
# ==========================================
st.set_page_config(
    page_title="ShopAI Enterprise | 智慧零售中台",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# [重點修改] 智慧型適應主題 CSS
# ---------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+TC:wght@400;500;700&display=swap');

    /* 1. 定義顏色變數：預設為【淺色模式】 */
    :root {
        --primary-blue: #0f4c81;
        --accent-orange: #f36f21;
        
        --bg-main: #f8fafc;        /* 主背景：淺灰白 */
        --bg-card: #ffffff;        /* 卡片/側邊欄背景：純白 */
        --bg-hover: #f1f5f9;       /* 滑鼠懸停：淺灰 */
        --text-main: #334155;      /* 主要文字：深灰 */
        --text-sub: #64748b;       /* 次要文字：中灰 */
        --border-color: #e2e8f0;   /* 邊框：淺灰 */
        --shadow-color: rgba(0,0,0,0.05); /* 陰影 */
        --code-bg: #f1f5f9;        /* 程式碼區塊背景 */
    }

    /* 2. 定義【深色模式】覆蓋變數 (當系統偵測到深色時自動套用) */
    @media (prefers-color-scheme: dark) {
        :root {
            --bg-main: #0e1117;     /* Streamlit 原生深色背景 */
            --bg-card: #262730;     /* 卡片背景：深灰 */
            --bg-hover: #31333f;    /* 滑鼠懸停：稍亮灰 */
            --text-main: #fafafa;   /* 主要文字：白 */
            --text-sub: #9ca3af;    /* 次要文字：淺灰 */
            --border-color: #41444e;/* 邊框：深灰 */
            --shadow-color: rgba(0,0,0,0.4); /* 陰影加深 */
            --code-bg: #1e2129;     /* 程式碼區塊背景 */
        }
    }

    /* 3. 應用變數到各個元件 */
    html, body, [class*="css"], .stApp {
        font-family: 'Inter', 'Noto Sans TC', sans-serif;
        color: var(--text-main) !important;
        background-color: var(--bg-main) !important;
    }

    header {background: transparent !important; backdrop-filter: blur(0px);}
    footer {display: none !important;}
    #MainMenu {visibility: hidden;}

    /* 側邊欄樣式 */
    [data-testid="stSidebar"] {
        background-color: var(--bg-card) !important;
        border-right: 1px solid var(--border-color);
        box-shadow: 4px 0 24px var(--shadow-color);
    }
    
    .sidebar-title {
        color: var(--primary-blue);
        font-weight: 800;
        font-size: 1.5rem;
    }

    /* 側邊欄按鈕偽裝成指標卡片 */
    section[data-testid="stSidebar"] .stButton button, 
    section[data-testid="stSidebar"] .stDownloadButton button {
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 16px !important;
        text-align: left !important;
        box-shadow: 0 2px 4px var(--shadow-color);
        transition: all 0.2s ease;
        width: 100%;
        border-left: 4px solid var(--primary-blue);
        color: var(--text-main) !important;
        margin-bottom: 8px;
        display: block;
    }
    
    section[data-testid="stSidebar"] .stButton button:hover,
    section[data-testid="stSidebar"] .stDownloadButton button:hover {
        background-color: var(--bg-hover) !important;
        border-color: var(--primary-blue);
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(15, 76, 129, 0.1);
        color: var(--primary-blue) !important;
    }
    
    section[data-testid="stSidebar"] .stButton button p,
    section[data-testid="stSidebar"] .stDownloadButton button p {
        font-size: 1rem;
        font-weight: 600;
        margin-bottom: 4px;
        color: inherit !important;
    }

    /* 聊天介面優化 */
    .stChatMessage {padding: 1rem 0; background: transparent;}
    
    /* AI 回覆框 (使用變數) */
    div[data-testid="stChatMessageContent"] {
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border-color);
        border-radius: 0 16px 16px 16px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px -1px var(--shadow-color);
        color: var(--text-main) !important;
    }
    
    /* 使用者提問框 (維持藍色，但確保文字是白色) */
    div[data-testid="stChatMessage"]:nth-child(odd) div[data-testid="stChatMessageContent"] {
        background-color: var(--primary-blue) !important;
        color: #ffffff !important; /* 強制白字 */
        border: none;
        border-radius: 16px 0 16px 16px;
        box-shadow: 0 4px 12px rgba(15, 76, 129, 0.3);
    }
    
    /* 修正輸入框在深色模式下的顯示 */
    .stTextInput input, .stTextArea textarea {
        background-color: var(--bg-card) !important;
        color: var(--text-main) !important;
        border-color: var(--border-color) !important;
    }

    /* 修正表格文字顏色 */
    [data-testid="stDataFrame"] {
        color: var(--text-main) !important;
    }
    
    /* 修正 SQL Log 容器 */
    .sql-log-box {
        background-color: var(--code-bg) !important;
        padding: 8px;
        border-radius: 6px;
        margin-bottom: 8px;
        border-left: 3px solid var(--accent-orange);
    }
    
    .sql-log-title {
        font-size: 0.75rem; 
        color: var(--text-sub) !important; 
        margin-bottom: 4px;
    }
</style>
""", unsafe_allow_html=True)
# ---------------------------------------------------------
# [CSS 修改結束]
# ---------------------------------------------------------

# ==========================================
# 2. API 初始化
# ==========================================
api_key = None
if "GROQ_API_KEY" in st.secrets:
    api_key = st.secrets["GROQ_API_KEY"]
elif os.getenv("GROQ_API_KEY"):
    api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    # 這裡使用 warning 而非 error，方便預覽
    st.warning("⚠️ 系統提示：未偵測到 API Key，AI 功能將受限。")

client = Groq(api_key=api_key) if api_key else None

# ==========================================
# 3. 資料庫初始化
# ==========================================
@st.cache_resource
def init_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE products (
            sku TEXT PRIMARY KEY,
            name TEXT, category TEXT, price INTEGER, cost INTEGER, stock INTEGER, 
            sales_7d INTEGER, supplier TEXT, status TEXT, last_restock DATE
        )
    ''')
    
    products_data = [
        ("BEV-001", "可口可樂 600ml", "飲料", 35, 20, 120, 50, "太古可樂", "正常", "2024-01-01"),
        ("BEV-002", "原萃綠茶", "飲料", 25, 15, 200, 80, "太古可樂", "正常", "2024-01-02"),
        ("BEV-003", "瑞穗全脂鮮乳", "飲料", 92, 75, 0, 12, "統一企業", "缺貨", "2023-12-28"),
        ("BEV-004", "貝納頌咖啡", "飲料", 35, 22, 45, 15, "味全食品", "正常", "2024-01-03"),
        ("BEV-005", "舒跑運動飲料", "飲料", 25, 16, 150, 40, "維他露", "正常", "2024-01-01"),
        ("BEV-006", "OATLY燕麥奶", "飲料", 169, 130, 12, 5, "德記洋行", "補貨中", "2023-12-30"),
        ("BEV-007", "純喫茶紅茶", "飲料", 20, 14, 80, 60, "統一企業", "正常", "2024-01-04"),
        ("BEV-008", "每朝健康綠茶", "飲料", 35, 23, 60, 20, "維他露", "正常", "2024-01-02"),
        ("BEV-009", "紅牛能量飲料", "飲料", 59, 40, 200, 10, "紅牛台灣", "正常", "2024-01-01"),
        ("BEV-010", "統一木瓜牛乳", "飲料", 35, 25, 5, 25, "統一企業", "補貨中", "2023-12-29"),
        ("FRE-001", "御飯糰(鮪魚)", "鮮食", 35, 20, 12, 40, "統一超食", "正常", "2024-01-05"),
        ("FRE-002", "所長茶葉蛋", "鮮食", 18, 10, 0, 150, "所長食品", "缺貨", "2024-01-04"),
        ("FRE-003", "台灣香蕉(根)", "鮮食", 25, 12, 5, 30, "在地農會", "補貨中", "2024-01-03"),
        ("FRE-004", "奮起湖便當", "鮮食", 89, 65, 8, 20, "統一超食", "正常", "2024-01-05"),
        ("FRE-005", "即食雞胸肉", "鮮食", 59, 35, 25, 15, "大成食品", "正常", "2024-01-04"),
        ("FRE-006", "大亨堡熱狗", "熟食", 35, 18, 15, 30, "統一超食", "正常", "2024-01-05"),
        ("FRE-007", "關東煮(總合)", "熟食", 15, 8, 0, 50, "統一超食", "缺貨", "2024-01-04"),
        ("FRE-008", "溫泉蛋", "鮮食", 25, 15, 30, 25, "石安牧場", "正常", "2024-01-03"),
        ("SNK-001", "樂事洋芋片", "零食", 45, 30, 80, 25, "百事食品", "正常", "2023-12-25"),
        ("SNK-002", "義美小泡芙", "零食", 32, 22, 100, 45, "義美食品", "正常", "2023-12-20"),
        ("SNK-003", "金莎巧克力", "零食", 42, 28, 5, 60, "費列羅", "補貨中", "2023-12-15"),
        ("SNK-004", "科學麵", "零食", 12, 6, 500, 200, "統一企業", "正常", "2023-12-10"),
        ("SNK-005", "萬歲牌綜合堅果", "零食", 150, 100, 20, 10, "聯華食品", "正常", "2023-12-01"),
        ("SNK-006", "北海鱈魚香絲", "零食", 50, 35, 60, 15, "有豐食品", "正常", "2023-12-22"),
        ("DAL-001", "舒潔衛生紙", "日用品", 129, 90, 60, 20, "金百利", "正常", "2023-11-20"),
        ("DAL-002", "金頂電池(3號)", "日用品", 159, 100, 30, 5, "金頂", "正常", "2023-10-15"),
        ("DAL-003", "輕便雨衣", "日用品", 49, 20, 150, 50, "達新工業", "正常", "2023-09-01"),
        ("DAL-004", "醫療口罩(50入)", "日用品", 199, 120, 100, 10, "中衛", "正常", "2023-12-01"),
        ("ALC-001", "金牌台灣啤酒", "酒類", 45, 30, 200, 60, "台灣菸酒", "正常", "2023-12-31"),
        ("ALC-002", "海尼根", "酒類", 55, 38, 180, 50, "海尼根", "正常", "2023-12-30"),
        ("ALC-003", "約翰走路黑牌", "酒類", 850, 600, 3, 2, "帝亞吉歐", "缺貨", "2023-11-15"),
        ("TOB-001", "七星(中淡)", "香菸", 125, 90, 300, 100, "杰太日煙", "正常", "2024-01-01"),
        ("TOB-002", "麥瑟(藍)", "香菸", 110, 80, 20, 5, "帝國菸草", "補貨中", "2023-12-28"),
    ]
    c.executemany('INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?)', products_data)
    conn.commit()
    return conn

conn = init_db()

# 🌟 定義欄位中英對照表 (UI 顯示用)
COLUMN_MAPPING = {
    "sku": "商品編號",
    "name": "商品名稱",
    "category": "類別",
    "price": "單價",
    "cost": "成本",
    "stock": "庫存量",
    "sales_7d": "近7日銷量",
    "supplier": "供應商",
    "status": "狀態",
    "last_restock": "最後補貨日",
    "margin": "毛利"
}

# ==========================================
# 4. Agentic AI 核心
# ==========================================
DB_SCHEMA = """
Table: products
Columns: 
- sku (商品編號)
- name (商品名稱)
- category (類別)
- price (零售價)
- cost (進貨成本)
- stock (庫存量)
- sales_7d (過去7天銷售量)
- supplier (供應商名稱)
- status ('正常', '缺貨', '補貨中')
- last_restock (最後進貨日)

Logic:
1. Margin (毛利) = price - cost
2. Inventory Value = cost * stock
3. High Risk = stock < sales_7d (Inventory days < 7)
"""

def generate_sql(query, error_msg=None):
    if not client: return None
    instruction = ""
    if error_msg:
        instruction = f"\n⚠️ PREVIOUS SQL FAILED: {error_msg}. FIX IT."
    
    system_prompt = f"""
    You are a SQLite expert. Schema: {DB_SCHEMA}
    Rules:
    1. Output ONLY valid SQL. No markdown.
    2. Use `LIKE` for fuzzy search.
    3. 'Out of stock' = status='缺貨' OR stock=0.
    {instruction}
    """
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": query}],
            temperature=0.1, max_tokens=200
        )
        return completion.choices[0].message.content.strip().replace("```sql", "").replace("```", "")
    except:
        return None

def execute_sql_safe(sql, user_query):
    try:
        return pd.read_sql_query(sql, conn), None
    except Exception as e:
        new_sql = generate_sql(user_query, error_msg=str(e))
        if new_sql:
            try:
                return pd.read_sql_query(new_sql, conn), new_sql
            except Exception as e2:
                return None, f"Retry failed: {e2}"
        return None, str(e)

def generate_human_response(user_query, df, error=None):
    if not client: return "⚠️ 演示模式：請設定 API Key 以啟用 AI 分析功能。"
    
    if error:
        return f"⚠️ 系統無法理解您的查詢。(Error: {error})"
    if df is None or df.empty:
        data_context = "查詢結果：無資料。"
    else:
        if 'price' in df.columns and 'cost' in df.columns:
            df['margin'] = df['price'] - df['cost']
        
        df_display = df.rename(columns=COLUMN_MAPPING)
        data_context = f"查詢結果 (前 10 筆):\n{df_display.head(10).to_string(index=False)}"

    system_prompt = f"""
    【角色設定】
    你是一位「資深零售營運總監」的 AI 特助。
    你的對話對象是公司老闆，他關注「毛利」、「庫存周轉」、「資金積壓」與「供應鏈穩定」。

    【當前任務】
    根據數據：
    {data_context}
    
    回答老闆的問題："{user_query}"

    【回答準則 - Boss Mode】
    1. **結論先行 (BLUF)**：第一句話直接講重點。
    2. **財務視角**：
       - 不只報庫存，要報「庫存金額」。
       - 提到商品時，若有數據，請順帶分析毛利。
    3. **行動建議 (Actionable Insights)**：
       - 發現缺貨：請列出該商品的「供應商」並建議立即聯絡。
       - 發現滯銷：建議促銷。
       - 發現熱銷：發出斷貨預警。
    4. **語氣**：專業、精煉、決策導向。不要用客服語氣。
    5. **格式**：不使用 Markdown 表格，用條列式呈現。
    """
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt}],
            temperature=0.7, max_tokens=450
        )
        return completion.choices[0].message.content
    except:
        return "系統忙碌中..."

# ==========================================
# 5. UI 佈局 (Callback & Sidebar)
# ==========================================
def set_prompt(text):
    st.session_state.prompt_input = text

with st.sidebar:
    st.markdown('<p class="sidebar-title">🏢 ShopAI <span style="color:#f36f21">Pro</span></p>', unsafe_allow_html=True)
    st.caption(f"Status: Online 🟢 | {datetime.date.today()}")
    
    df_all = pd.read_sql_query("SELECT * FROM products", conn)
    
    st.markdown("**營運監控**")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button(f"📦 總品項\n\n{len(df_all)}", key="card_sku", use_container_width=True):
            set_prompt("列出所有商品清單，並依照類別排序")
    with c2:
        val = (df_all['price'] * df_all['stock']).sum()
        if st.button(f"💰 庫存總值\n\n${val/1000:.1f}K", key="card_val", use_container_width=True):
            set_prompt("統計各類別的庫存總金額，並計算毛利")

    c3, c4 = st.columns(2)
    with c3:
         missing = len(df_all[df_all['status'] == '缺貨'])
         if st.button(f"🚨 缺貨品項\n\n{missing}", key="card_missing", use_container_width=True):
             set_prompt("列出所有缺貨商品及其供應商")
    with c4:
         low = len(df_all[df_all['stock'] < 10])
         if st.button(f"⚠️ 低水位\n\n{low}", key="card_low", use_container_width=True):
             set_prompt("列出庫存低於 10 的商品與其 7 日銷量")

    st.markdown("---")
    st.markdown("**快速操作**")
    
    csv = df_all.rename(columns=COLUMN_MAPPING).to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📊 匯出報表 (CSV)",
        data=csv,
        file_name=f"report_{datetime.date.today()}.csv",
        mime="text/csv",
        use_container_width=True
    )
    
    if st.button("🔄 同步 ERP", use_container_width=True):
        with st.spinner("Syncing..."):
            time.sleep(1)
        st.toast("✅ 同步完成！", icon="🎉")
    st.markdown("---")

# --- 主畫面 ---
st.markdown("#### 👋 歡迎使用ShopAI Pro")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "系統已連線。您可以查詢全店 30+ 項商品的即時庫存狀態。"}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="👨‍💼" if msg["role"]=="user" else "🤖"):
        st.markdown(msg["content"])
        if "data" in msg and msg["data"] is not None and not msg["data"].empty:
            t1, t2 = st.tabs(["📄 數據表", "📈 圖表"])
            
            df_show = msg["data"].rename(columns=COLUMN_MAPPING)
            
            with t1: st.dataframe(df_show, hide_index=True, use_container_width=True)
            with t2: 
                # [Fix] 繪圖邏輯修復：改用 st.bar_chart(df, x=..., y=...) 避免 KeyError
                chart_col_x = "商品名稱" if "商品名稱" in df_show.columns else df_show.columns[0]
                
                # 尋找合適的 Y 軸，避開 X 軸欄位
                possible_y = [c for c in df_show.columns if c != chart_col_x]
                chart_col_y = None
                
                # 優先順序：庫存量 > sales_7d > 第一個可用數值欄位
                if "庫存量" in possible_y:
                    chart_col_y = "庫存量"
                elif "sales_7d" in possible_y:
                    chart_col_y = "sales_7d"
                elif "近7日銷量" in possible_y:
                    chart_col_y = "近7日銷量"
                elif len(possible_y) > 0:
                    chart_col_y = possible_y[0]
                
                if chart_col_y:
                    st.bar_chart(df_show, x=chart_col_x, y=chart_col_y, color="#0f4c81")

st.markdown("###### 💡 決策捷徑：")
col_chip1, col_chip2, col_chip3, col_chip4 = st.columns(4)
with col_chip1:
    if st.button("🏆 銷量冠軍", use_container_width=True): set_prompt("列出近 7 日銷量最高的前 5 名商品")
with col_chip2:
    if st.button("🚨 斷貨預警", use_container_width=True): set_prompt("列出庫存小於 7 日銷量的危險商品")
with col_chip3:
    if st.button("💰 高毛利商品", use_container_width=True): set_prompt("列出毛利 (Price-Cost) 最高的前 5 名")
with col_chip4:
    if st.button("🚛 供應商檢視", use_container_width=True): set_prompt("統計各供應商的供貨品項數量")

default_prompt = st.session_state.pop("prompt_input", "")

if prompt := st.chat_input("請輸入查詢指令...", key="chat_input") or default_prompt:
    if not prompt and default_prompt: prompt = default_prompt

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👨‍💼"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("AI 分析師正在處理數據..."):
            
            sql = generate_sql(prompt)
            result = None
            error = None
            final_sql = sql
            
            if sql:
                result, err_or_new_sql = execute_sql_safe(sql, prompt)
                if result is None: error = err_or_new_sql
                elif err_or_new_sql: final_sql = err_or_new_sql
            
            reply = generate_human_response(prompt, result, error)
            st.markdown(reply)
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": reply,
                "data": result,
                "sql": final_sql,
                "query": prompt 
            })
            
            if result is not None and not result.empty:
                t1, t2 = st.tabs(["📄 數據表", "📈 圖表"])
                df_show = result.rename(columns=COLUMN_MAPPING)
                with t1: st.dataframe(df_show, hide_index=True, use_container_width=True)
                with t2: 
                     # [Fix] 繪圖邏輯修復：同上
                     chart_col_x = "商品名稱" if "商品名稱" in df_show.columns else df_show.columns[0]
                     
                     possible_y = [c for c in df_show.columns if c != chart_col_x]
                     chart_col_y = None
                     
                     if "庫存量" in possible_y:
                        chart_col_y = "庫存量"
                     elif "sales_7d" in possible_y:
                        chart_col_y = "sales_7d"
                     elif "近7日銷量" in possible_y:
                        chart_col_y = "近7日銷量"
                     elif len(possible_y) > 0:
                        chart_col_y = possible_y[0]
                     
                     if chart_col_y:
                        st.bar_chart(df_show, x=chart_col_x, y=chart_col_y, color="#0f4c81")
    
    if default_prompt:
        st.rerun()

# --- 側邊欄 Part 2 (Audit Log) ---
with st.sidebar:
    st.markdown("**🛠️ SQL 執行歷程**")
    log_container = st.container(height=250)
    if "messages" in st.session_state:
        sql_logs = [m for m in st.session_state.messages if m["role"] == "assistant" and "sql" in m]
        with log_container:
            if not sql_logs:
                st.info("尚無執行紀錄")
            else:
                for log in reversed(sql_logs):
                    # 使用 CSS Class 來應用變數顏色
                    st.markdown(f"""
                    <div class="sql-log-box">
                        <div class="sql-log-title">SQL Logic</div>
                        <code style="font-size:0.7rem; color:#0f4c81;">{log['sql']}</code>
                    </div>
                    """, unsafe_allow_html=True)