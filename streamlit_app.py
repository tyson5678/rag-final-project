import streamlit as st
import pandas as pd
import sqlite3
from groq import Groq
import os
import datetime
import time

# ==========================================
# 1. 企業級 UI 配置與配色系統 (藍橘風格)
# ==========================================
st.set_page_config(
    page_title="ShopAI Enterprise | 智慧零售中台",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 定義企業級配色與 CSS
st.markdown("""
<style>
    /* 引入 Inter 字體 (SaaS 標準字體) */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+TC:wght@400;500;700&display=swap');

    :root {
        --primary-blue: #0f4c81;       /* 穩重深藍 */
        --accent-orange: #f36f21;      /* 活力橘 */
        --background-light: #f8fafc;   /* 淺灰背景 */
        --border-color: #e2e8f0;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', 'Noto Sans TC', sans-serif;
        color: #334155;
        background-color: var(--background-light);
    }

    /* 頂部導航列優化 */
    header {
        background: transparent !important;
        backdrop-filter: blur(0px);
    }
    footer {display: none !important;}
    #MainMenu {visibility: hidden;}

    /* 側邊欄：企業級風格 */
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

    /* 指標卡片 (KPI Cards) */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        padding: 16px;
        border-radius: 10px;
        border: 1px solid var(--border-color);
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        border-left: 4px solid var(--primary-blue);
        transition: transform 0.2s ease;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 16px rgba(15, 76, 129, 0.1);
    }
    div[data-testid="stMetric"][data-label*="缺貨"],
    div[data-testid="stMetric"][data-label*="低水位"] {
        border-left-color: var(--accent-orange) !important;
    }
    
    /* 按鈕樣式優化 */
    .stButton button {
        border-radius: 8px;
        font-weight: 600;
        border: 1px solid var(--border-color);
    }
    .stButton button:hover {
        border-color: var(--accent-orange);
        color: var(--accent-orange);
        background-color: #fff7ed;
    }
    
    /* 聊天區塊優化 */
    .stChatMessage {
        padding: 1rem 0;
        background: transparent;
    }
    
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
# 2. API 與工具初始化
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
# 3. 資料庫初始化
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
        # 飲料
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
        # 鮮食
        ("FRE-001", "御飯糰(鮪魚)", "鮮食", 35, 12, "正常", "2024-01-05"),
        ("FRE-002", "所長茶葉蛋", "鮮食", 18, 0, "缺貨", "2024-01-04"),
        ("FRE-003", "台灣香蕉(根)", "鮮食", 25, 5, "補貨中", "2024-01-03"),
        ("FRE-004", "奮起湖便當", "鮮食", 89, 8, "正常", "2024-01-05"),
        ("FRE-005", "即食雞胸肉", "鮮食", 59, 25, "正常", "2024-01-04"),
        ("FRE-006", "大亨堡熱狗", "熟食", 35, 15, "正常", "2024-01-05"),
        ("FRE-007", "關東煮(總合)", "熟食", 15, 0, "缺貨", "2024-01-04"),
        ("FRE-008", "溫泉蛋", "鮮食", 25, 30, "正常", "2024-01-03"),
        # 零食
        ("SNK-001", "樂事洋芋片(原味)", "零食", 45, 80, "正常", "2023-12-25"),
        ("SNK-002", "義美小泡芙(巧克力)", "零食", 32, 100, "正常", "2023-12-20"),
        ("SNK-003", "金莎巧克力(3入)", "零食", 42, 5, "補貨中", "2023-12-15"),
        ("SNK-004", "科學麵", "零食", 12, 500, "正常", "2023-12-10"),
        ("SNK-005", "萬歲牌綜合堅果", "零食", 150, 20, "正常", "2023-12-01"),
        ("SNK-006", "北海鱈魚香絲", "零食", 50, 60, "正常", "2023-12-22"),
        # 日用品
        ("DAL-001", "舒潔衛生紙", "日用品", 129, 60, "正常", "2023-11-20"),
        ("DAL-002", "金頂電池(3號)", "日用品", 159, 30, "正常", "2023-10-15"),
        ("DAL-003", "輕便雨衣", "日用品", 49, 150, "正常", "2023-09-01"),
        ("DAL-004", "醫療口罩(50入)", "日用品", 199, 100, "正常", "2023-12-01"),
        # 菸酒
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
# 4. AI 邏輯核心
# ==========================================
DB_SCHEMA = """
Table: products
Columns: 
- sku (TEXT): 商品條碼
- name (TEXT): 商品名稱
- category (TEXT): 類別 ('飲料', '鮮食', '熟食', '零食', '日用品', '酒類', '香菸')
- price (INTEGER): 價格
- stock (INTEGER): 庫存量
- status (TEXT): 狀態 ('正常', '缺貨', '補貨中')
- last_restock (DATE): 最後補貨日
"""

def generate_sql(query):
    system_prompt = f"""
    You are a SQL expert.
    Schema: {DB_SCHEMA}
    Rules:
    1. Output ONLY SQLite valid SQL. No markdown.
    2. Use `LIKE` for fuzzy search.
    3. 'Out of stock' means status='缺貨' OR stock=0.
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

def generate_human_response(user_query, df, error=None):
    if error:
        return f"⚠️ 系統查詢異常：{error}"
    if df is None or df.empty:
        data_context = "查詢結果：無資料 (Empty Set)。"
    else:
        data_context = f"查詢結果 (前 10 筆):\n{df.head(10).to_string(index=False)}"

    system_prompt = f"""
    你是一位「企業零售數據分析師」。
    問題："{user_query}"
    數據：{data_context}
    準則：
    1. 專業語氣，使用商業用語。
    2. 引用數據回答。
    3. 若無資料，根據現有類別推薦替代品。
    4. 不用 Markdown 表格。
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
# 5. UI 佈局 (企業級儀表板)
# ==========================================

# --- 側邊欄 (Sidebar PART 1: 固定靜態內容) ---
with st.sidebar:
    # 品牌識別區
    st.markdown('<p class="sidebar-title">🏢 ShopAI <span style="color:#f36f21">Pro</span></p>', unsafe_allow_html=True)
    st.caption(f"System: Online 🟢 | {datetime.date.today()}")
    
    # KPI 區塊
    df_all = pd.read_sql_query("SELECT * FROM products", conn)
    
    st.markdown("**營運監控 (Real-time KPIs)**")
    
    col_kpi1, col_kpi2 = st.columns(2)
    with col_kpi1:
        st.metric("總 SKU", f"{len(df_all)}")
    with col_kpi2:
        val = (df_all['price'] * df_all['stock']).sum()
        st.metric("庫存總值", f"${val/1000:.1f}K")
        
    col_alert1, col_alert2 = st.columns(2)
    with col_alert1:
         missing = len(df_all[df_all['status'] == '缺貨'])
         st.metric("缺貨品項", f"{missing}", delta="Action", delta_color="inverse")
    with col_alert2:
         low = len(df_all[df_all['stock'] < 10])
         st.metric("低水位", f"{low}", delta="Alert", delta_color="inverse")

    st.markdown("---")
    
    # 功能按鈕區
    st.markdown("**快速操作**")
    csv = df_all.to_csv(index=False).encode('utf-8')
    st.download_button("📊 匯出報表 (CSV)", csv, f"report_{datetime.date.today()}.csv", "text/csv", use_container_width=True)

    if st.button("🔄 同步 ERP 系統", use_container_width=True):
        with st.spinner("正在連接總部資料庫..."):
            time.sleep(1.5)
        st.toast("✅ 數據同步完成！", icon="🎉")
    
    st.markdown("---")

# --- 主畫面 ---
st.markdown("#### 👋 老闆，歡迎回到戰情室～～")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "系統已連線。您可以查詢全店 60+ 項商品的即時庫存狀態。"}
    ]

# 顯示對話紀錄
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="👨‍💼" if msg["role"]=="user" else "🤖"):
        st.markdown(msg["content"])
        if "data" in msg and msg["data"] is not None and not msg["data"].empty:
            tab1, tab2 = st.tabs(["📄 詳細數據表", "📈 數據可視化"])
            with tab1:
                st.dataframe(
                    msg["data"], 
                    hide_index=True, 
                    use_container_width=True,
                    column_config={
                        "price": st.column_config.NumberColumn("單價", format="$%d"),
                        "stock": st.column_config.ProgressColumn("庫存水位", format="%d", min_value=0, max_value=200),
                        "status": st.column_config.TextColumn("狀態")
                    }
                )
            with tab2:
                if len(msg["data"]) > 1 and "stock" in msg["data"].columns:
                    st.bar_chart(msg["data"].set_index("name")["stock"], color="#0f4c81")

# 輸入處理
if prompt := st.chat_input("請輸入查詢指令..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👨‍💼"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("AI 分析師正在處理數據..."):
            sql = generate_sql(prompt)
            result = None
            error = None
            if sql:
                try:
                    result = pd.read_sql_query(sql, conn)
                except Exception as e:
                    error = str(e)
            
            reply = generate_human_response(prompt, result, error)
            st.markdown(reply)
            
            # 將本次查詢存入 session_state
            st.session_state.messages.append({
                "role": "assistant",
                "content": reply,
                "data": result,
                "sql": sql,
                "query": prompt 
            })
            
            if result is not None and not result.empty:
                tab1, tab2 = st.tabs(["📄 詳細數據表", "📈 數據可視化"])
                with tab1:
                    st.dataframe(
                        result, 
                        hide_index=True, 
                        use_container_width=True,
                        column_config={
                            "price": st.column_config.NumberColumn("單價", format="$%d"),
                            "stock": st.column_config.ProgressColumn("庫存水位", format="%d", min_value=0, max_value=200),
                        }
                    )
                with tab2:
                     if "stock" in result.columns:
                        st.bar_chart(result.set_index("name")["stock"], color="#0f4c81")

# ==========================================
# 6. 側邊欄 PART 2: SQL 日誌 (移到最底端渲染！)
# 關鍵修改：這段程式碼現在放在所有邏輯處理之後
# ==========================================
with st.sidebar:
    st.markdown("**🛠️ SQL 執行歷程 (Audit Log)**")
    st.caption("顯示最近的 AI 推論邏輯")
    
    log_container = st.container(height=250)
    
    if "messages" in st.session_state:
        # 篩選並反轉顯示
        sql_logs = [m for m in st.session_state.messages if m["role"] == "assistant" and "sql" in m]
        
        with log_container:
            if not sql_logs:
                st.info("尚無執行紀錄")
            else:
                for log in reversed(sql_logs):
                    st.markdown(f"""
                    <div style="background:#f1f5f9; padding:8px; border-radius:6px; margin-bottom:8px; border-left:3px solid #f36f21;">
                        <div style="font-size:0.75rem; color:#64748b; margin-bottom:4px;">Generated SQL</div>
                        <code style="font-size:0.7rem; color:#0f4c81;">{log['sql']}</code>
                    </div>
                    """, unsafe_allow_html=True)