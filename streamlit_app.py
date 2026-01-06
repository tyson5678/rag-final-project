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

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+TC:wght@400;500;700&display=swap');

    :root {
        --primary-blue: #0f4c81;
        --accent-orange: #f36f21;
        --background-light: #f8fafc;
        --border-color: #e2e8f0;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', 'Noto Sans TC', sans-serif;
        color: #334155;
        background-color: var(--background-light);
    }

    header {background: transparent !important; backdrop-filter: blur(0px);}
    footer {display: none !important;}
    #MainMenu {visibility: hidden;}

    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid var(--border-color);
        box-shadow: 4px 0 24px rgba(0,0,0,0.02);
    }
    
    .sidebar-title {
        color: var(--primary-blue);
        font-weight: 800;
        font-size: 1.5rem;
    }

    /* ★ 關鍵 CSS 修改：同時統一下載按鈕 (.stDownloadButton) 與普通按鈕 (.stButton) 的風格 ★ */
    section[data-testid="stSidebar"] .stButton button, 
    section[data-testid="stSidebar"] .stDownloadButton button {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px !important;
        text-align: left !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        transition: all 0.2s ease;
        width: 100%;
        border-left: 4px solid var(--primary-blue); /* 統一藍色裝飾條 */
        color: #1e293b;
        margin-bottom: 8px; /* 增加一點間距 */
        display: block;
    }
    
    /* 滑鼠懸停特效 */
    section[data-testid="stSidebar"] .stButton button:hover,
    section[data-testid="stSidebar"] .stDownloadButton button:hover {
        background-color: #f8fafc;
        border-color: var(--primary-blue);
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(15, 76, 129, 0.1);
        color: var(--primary-blue);
    }
    
    /* 按鈕內的文字排版 */
    section[data-testid="stSidebar"] .stButton button p,
    section[data-testid="stSidebar"] .stDownloadButton button p {
        font-size: 1rem;
        font-weight: 600;
        margin-bottom: 4px;
    }

    /* 聊天介面優化 */
    .stChatMessage {padding: 1rem 0; background: transparent;}
    div[data-testid="stChatMessageContent"] {
        background: #ffffff;
        border: 1px solid var(--border-color);
        border-radius: 0 16px 16px 16px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        color: #1e293b;
    }
    div[data-testid="stChatMessage"]:nth-child(odd) div[data-testid="stChatMessageContent"] {
        background: var(--primary-blue);
        color: white;
        border: none;
        border-radius: 16px 0 16px 16px;
        box-shadow: 0 4px 12px rgba(15, 76, 129, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. API 初始化
# ==========================================
api_key = None
if "GROQ_API_KEY" in st.secrets:
    api_key = st.secrets["GROQ_API_KEY"]
elif os.getenv("GROQ_API_KEY"):
    api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    st.error("🚨 系統錯誤：未偵測到 API Key")
    st.stop()

client = Groq(api_key=api_key)

# ==========================================
# 3. 資料庫初始化 (60+ SKU)
# ==========================================
@st.cache_resource
def init_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE products (
            sku TEXT PRIMARY KEY,
            name TEXT, category TEXT, price INTEGER, stock INTEGER, status TEXT, last_restock DATE
        )
    ''')
    
    products_data = [
        ("BEV-001", "可口可樂 600ml", "飲料", 35, 120, "正常", "2024-01-01"),
        ("BEV-002", "原萃綠茶", "飲料", 25, 200, "正常", "2024-01-02"),
        ("BEV-003", "瑞穗全脂鮮乳", "飲料", 92, 0, "缺貨", "2023-12-28"),
        ("BEV-004", "貝納頌咖啡", "飲料", 35, 45, "正常", "2024-01-03"),
        ("BEV-005", "舒跑運動飲料", "飲料", 25, 150, "正常", "2024-01-01"),
        ("BEV-006", "OATLY燕麥奶", "飲料", 169, 12, "補貨中", "2023-12-30"),
        ("BEV-007", "純喫茶紅茶", "飲料", 20, 80, "正常", "2024-01-04"),
        ("BEV-008", "每朝健康綠茶", "飲料", 35, 60, "正常", "2024-01-02"),
        ("BEV-009", "紅牛能量飲料", "飲料", 59, 200, "正常", "2024-01-01"),
        ("BEV-010", "統一木瓜牛乳", "飲料", 35, 5, "補貨中", "2023-12-29"),
        ("FRE-001", "御飯糰(鮪魚)", "鮮食", 35, 12, "正常", "2024-01-05"),
        ("FRE-002", "所長茶葉蛋", "鮮食", 18, 0, "缺貨", "2024-01-04"),
        ("FRE-003", "台灣香蕉(根)", "鮮食", 25, 5, "補貨中", "2024-01-03"),
        ("FRE-004", "奮起湖便當", "鮮食", 89, 8, "正常", "2024-01-05"),
        ("FRE-005", "即食雞胸肉", "鮮食", 59, 25, "正常", "2024-01-04"),
        ("FRE-006", "大亨堡熱狗", "熟食", 35, 15, "正常", "2024-01-05"),
        ("FRE-007", "關東煮(總合)", "熟食", 15, 0, "缺貨", "2024-01-04"),
        ("FRE-008", "溫泉蛋", "鮮食", 25, 30, "正常", "2024-01-03"),
        ("SNK-001", "樂事洋芋片(原味)", "零食", 45, 80, "正常", "2023-12-25"),
        ("SNK-002", "義美小泡芙(巧克力)", "零食", 32, 100, "正常", "2023-12-20"),
        ("SNK-003", "金莎巧克力(3入)", "零食", 42, 5, "補貨中", "2023-12-15"),
        ("SNK-004", "科學麵", "零食", 12, 500, "正常", "2023-12-10"),
        ("SNK-005", "萬歲牌綜合堅果", "零食", 150, 20, "正常", "2023-12-01"),
        ("SNK-006", "北海鱈魚香絲", "零食", 50, 60, "正常", "2023-12-22"),
        ("DAL-001", "舒潔衛生紙", "日用品", 129, 60, "正常", "2023-11-20"),
        ("DAL-002", "金頂電池(3號)", "日用品", 159, 30, "正常", "2023-10-15"),
        ("DAL-003", "輕便雨衣", "日用品", 49, 150, "正常", "2023-09-01"),
        ("DAL-004", "醫療口罩(50入)", "日用品", 199, 100, "正常", "2023-12-01"),
        ("ALC-001", "金牌台灣啤酒", "酒類", 45, 200, "正常", "2023-12-31"),
        ("ALC-002", "海尼根", "酒類", 55, 180, "正常", "2023-12-30"),
        ("ALC-003", "約翰走路黑牌", "酒類", 850, 3, "缺貨", "2023-11-15"),
        ("TOB-001", "七星(中淡)", "香菸", 125, 300, "正常", "2024-01-01"),
        ("TOB-002", "麥瑟(藍)", "香菸", 110, 20, "補貨中", "2023-12-28"),
    ]
    c.executemany('INSERT INTO products VALUES (?,?,?,?,?,?,?)', products_data)
    conn.commit()
    return conn

conn = init_db()

# ==========================================
# 4. Agentic AI 核心
# ==========================================
DB_SCHEMA = """
Table: products
Columns: sku, name, category, price, stock, status ('正常', '缺貨', '補貨中'), last_restock
"""

def generate_sql(query, error_msg=None):
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
    if error:
        return f"⚠️ 系統無法理解您的查詢。(Error: {error})"
    if df is None or df.empty:
        data_context = "查詢結果：無資料。"
    else:
        data_context = f"查詢結果 (前 10 筆):\n{df.head(10).to_string(index=False)}"

    system_prompt = f"""
    你是一位「企業零售數據分析師」。問題："{user_query}"。數據：{data_context}
    準則：專業語氣、引用數據、若無資料則推薦同類別替代品。不使用 Markdown 表格。
    """
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt}],
            temperature=0.7, max_tokens=350
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
        if st.button(f"📦 總 SKU\n\n{len(df_all)}", key="card_sku", use_container_width=True):
            set_prompt("列出所有商品清單，並依照類別排序")
            
    with c2:
        val = (df_all['price'] * df_all['stock']).sum()
        if st.button(f"💰 庫存總值\n\n${val/1000:.1f}K", key="card_val", use_container_width=True):
            set_prompt("統計各類別的庫存總金額，並畫圖顯示")

    c3, c4 = st.columns(2)
    with c3:
         missing = len(df_all[df_all['status'] == '缺貨'])
         if st.button(f"🚨 缺貨品項\n\n{missing}", key="card_missing", use_container_width=True):
             set_prompt("列出所有缺貨或補貨中的商品")
             
    with c4:
         low = len(df_all[df_all['stock'] < 10])
         if st.button(f"⚠️ 低水位\n\n{low}", key="card_low", use_container_width=True):
             set_prompt("列出庫存低於 10 的商品，並依照庫存量由少到多排序")

    st.markdown("---")
    st.markdown("**快速操作**")
    
    # 這裡的樣式現在會跟上面的卡片一致（白底、藍邊）
    st.download_button(
        label="📊 匯出報表 (CSV)",
        data=df_all.to_csv(index=False).encode('utf-8'),
        file_name=f"report.csv",
        mime="text/csv",
        use_container_width=True
    )
    
    if st.button("🔄 同步 ERP", use_container_width=True):
        with st.spinner("Syncing..."):
            time.sleep(1)
        st.toast("✅ 同步完成！", icon="🎉")
        
    st.markdown("---")

# --- 主畫面 ---
st.markdown("#### 👋 歡迎回到戰情室，店長。")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "系統已連線。您可以查詢全店 60+ 項商品的即時庫存狀態。"}]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="👨‍💼" if msg["role"]=="user" else "🤖"):
        st.markdown(msg["content"])
        if "data" in msg and msg["data"] is not None and not msg["data"].empty:
            t1, t2 = st.tabs(["📄 數據表", "📈 圖表"])
            with t1: st.dataframe(msg["data"], hide_index=True, use_container_width=True)
            with t2: 
                if len(msg["data"]) > 1 and "stock" in msg["data"].columns:
                    st.bar_chart(msg["data"].set_index("name")["stock"], color="#0f4c81")

# 快捷膠囊按鈕
st.markdown("###### 💡 快速提問：")
col_chip1, col_chip2, col_chip3, col_chip4 = st.columns(4)
with col_chip1:
    if st.button("🏆 庫存最多", use_container_width=True): set_prompt("庫存最多的前 10 名商品")
with col_chip2:
    if st.button("🚨 缺貨清單", use_container_width=True): set_prompt("列出所有缺貨或補貨中的商品")
with col_chip3:
    if st.button("💰 價值最高", use_container_width=True): set_prompt("依據單價從高到低列出所有商品")
with col_chip4:
    if st.button("🥤 飲料概況", use_container_width=True): set_prompt("統計飲料類別的完整明細")

# 處理 Prompt 邏輯
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
                with t1: st.dataframe(result, hide_index=True, use_container_width=True)
                with t2: 
                     if "stock" in result.columns:
                        st.bar_chart(result.set_index("name")["stock"], color="#0f4c81")
    
    if default_prompt:
        st.rerun()

# --- 側邊欄 Part 2 (SQL Log) ---
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
                    st.markdown(f"""
                    <div style="background:#f1f5f9; padding:8px; border-radius:6px; margin-bottom:8px; border-left:3px solid #f36f21;">
                        <div style="font-size:0.75rem; color:#64748b; margin-bottom:4px;">SQL Logic</div>
                        <code style="font-size:0.7rem; color:#0f4c81;">{log['sql']}</code>
                    </div>
                    """, unsafe_allow_html=True)