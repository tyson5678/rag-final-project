import streamlit as st
import pandas as pd
import sqlite3
from groq import Groq
import os
import datetime

# ==========================================
# 1. 企業級 UI 配置與 CSS 系統
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
        --primary-color: #2563eb;
        --background-light: #f8fafc;
        --card-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        --text-primary: #1e293b;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', 'Noto Sans TC', sans-serif;
        color: var(--text-primary);
        background-color: var(--background-light);
    }

    /* 頂部導航列優化 */
    header {
        background: rgba(255, 255, 255, 0.9) !important;
        backdrop-filter: blur(10px);
        border-bottom: 1px solid #e2e8f0;
        height: 3.5rem !important;
    }
    
    /* 隱藏預設 Footer */
    footer {display: none !important;}
    #MainMenu {visibility: hidden;}

    /* 側邊欄：企業級深色風格或乾淨風格 */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e2e8f0;
        box-shadow: 2px 0 10px rgba(0,0,0,0.02);
    }

    /* 側邊欄標題固定效果 (透過 Padding 調整) */
    .css-1d391kg {
        padding-top: 1rem;
    }

    /* 指標卡片 (KPI Cards) - 更有質感的設計 */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        padding: 16px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        transition: all 0.2s ease;
    }
    div[data-testid="stMetric"]:hover {
        border-color: var(--primary-color);
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.1);
    }
    
    /* Metric Label */
    div[data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        color: #64748b;
        font-weight: 600;
    }

    /* 聊天區塊優化 */
    .stChatMessage {
        background-color: transparent;
        padding: 1rem 0;
    }
    
    /* 機器人回覆卡片 */
    div[data-testid="stChatMessage"] {
        align-items: flex-start;
    }
    
    div[data-testid="stChatMessageContent"] {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 0 12px 12px 12px;
        padding: 1.5rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        font-size: 0.95rem;
        line-height: 1.6;
    }

    /* 用戶回覆樣式 (右側對齊) */
    div[data-testid="stChatMessage"]:nth-child(odd) {
        flex-direction: row-reverse;
    }
    div[data-testid="stChatMessage"]:nth-child(odd) div[data-testid="stChatMessageContent"] {
        background: #2563eb;
        color: white;
        border: none;
        border-radius: 12px 0 12px 12px;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
    }

    /* 表格優化 */
    .stDataFrame {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* 輸入框固定底部優化 */
    .stChatInput {
        padding-bottom: 1rem;
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
# 3. 資料庫初始化 (真實超商模擬 - 60+ SKU)
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
    
    # 模擬真實超商數據 (包含 SKU 條碼格式)
    products_data = [
        # 飲料 (Beverages)
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
        
        # 鮮食/熟食 (Fresh Food)
        ("FRE-001", "御飯糰(鮪魚)", "鮮食", 35, 12, "正常", "2024-01-05"),
        ("FRE-002", "所長茶葉蛋", "鮮食", 18, 0, "缺貨", "2024-01-04"),
        ("FRE-003", "台灣香蕉(根)", "鮮食", 25, 5, "補貨中", "2024-01-03"),
        ("FRE-004", "奮起湖便當", "鮮食", 89, 8, "正常", "2024-01-05"),
        ("FRE-005", "即食雞胸肉", "鮮食", 59, 25, "正常", "2024-01-04"),
        ("FRE-006", "大亨堡熱狗", "熟食", 35, 15, "正常", "2024-01-05"),
        ("FRE-007", "關東煮(總合)", "熟食", 15, 0, "缺貨", "2024-01-04"),
        ("FRE-008", "溫泉蛋", "鮮食", 25, 30, "正常", "2024-01-03"),
        
        # 零食 (Snacks)
        ("SNK-001", "樂事洋芋片(原味)", "零食", 45, 80, "正常", "2023-12-25"),
        ("SNK-002", "義美小泡芙(巧克力)", "零食", 32, 100, "正常", "2023-12-20"),
        ("SNK-003", "金莎巧克力(3入)", "零食", 42, 5, "補貨中", "2023-12-15"),
        ("SNK-004", "科學麵", "零食", 12, 500, "正常", "2023-12-10"),
        ("SNK-005", "萬歲牌綜合堅果", "零食", 150, 20, "正常", "2023-12-01"),
        ("SNK-006", "北海鱈魚香絲", "零食", 50, 60, "正常", "2023-12-22"),
        ("SNK-007", "多力多滋", "零食", 45, 90, "正常", "2023-12-25"),
        ("SNK-008", "孔雀餅乾", "零食", 35, 40, "正常", "2023-12-18"),
        
        # 日用品 (Daily)
        ("DAL-001", "舒潔衛生紙", "日用品", 129, 60, "正常", "2023-11-20"),
        ("DAL-002", "金頂電池(3號)", "日用品", 159, 30, "正常", "2023-10-15"),
        ("DAL-003", "輕便雨衣", "日用品", 49, 150, "正常", "2023-09-01"),
        ("DAL-004", "醫療口罩(50入)", "日用品", 199, 100, "正常", "2023-12-01"),
        ("DAL-005", "免洗筷(包)", "日用品", 20, 200, "正常", "2023-10-01"),
        
        # 菸酒 (Alcohol & Tobacco - 模擬)
        ("ALC-001", "金牌台灣啤酒", "酒類", 45, 200, "正常", "2023-12-31"),
        ("ALC-002", "海尼根", "酒類", 55, 180, "正常", "2023-12-30"),
        ("ALC-003", "約翰走路黑牌", "酒類", 850, 3, "缺貨", "2023-11-15"),
        ("ALC-004", "18天生啤", "酒類", 65, 10, "補貨中", "2024-01-02"),
        ("ALC-005", "朝日啤酒", "酒類", 49, 120, "正常", "2023-12-29"),
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
- sku (TEXT): 商品條碼 (e.g., BEV-001)
- name (TEXT): 商品名稱
- category (TEXT): 類別 ('飲料', '鮮食', '熟食', '零食', '日用品', '酒類', '香菸')
- price (INTEGER): 價格
- stock (INTEGER): 庫存量
- status (TEXT): 狀態 ('正常', '缺貨', '補貨中')
- last_restock (DATE): 最後補貨日
"""

def generate_sql(query):
    system_prompt = f"""
    You are a SQL expert managing a retail database.
    Schema: {DB_SCHEMA}
    Rules:
    1. Output ONLY SQLite valid SQL. No markdown.
    2. Use `LIKE` for fuzzy search (e.g., name LIKE '%咖啡%').
    3. 'Out of stock' means status='缺貨' OR stock=0.
    4. Do not end with ';'.
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
    
    # 轉換數據為上下文
    if df is None or df.empty:
        data_context = "查詢結果：無資料 (Empty Set)。"
    else:
        # 限制 Context 長度，只取前 10 筆給 AI 參考，避免 Token 爆炸
        data_context = f"查詢結果 (前 10 筆):\n{df.head(10).to_string(index=False)}"

    system_prompt = f"""
    你是一位專業的「企業零售數據分析師」。
    使用者問題："{user_query}"
    數據結果：
    {data_context}
    
    【回覆準則】
    1. **專業語氣**：使用商業用語（如「SKU」、「庫存水位」、「補貨建議」）。
    2. **數據驅動**：直接引用數據回答。例如「目前庫存 120，屬於安全水位」。
    3. **空值處理**：若無資料，**必須**根據店內現有類別（飲料、鮮食、菸酒等）主動推薦相關替代品，不要只說沒有。
    4. **格式**：請勿輸出 Markdown 表格，用條列式或自然段落即可。
    """
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt}],
            temperature=0.7, max_tokens=350
        )
        return completion.choices[0].message.content
    except:
        return "系統忙碌中，請稍後再試。"

# ==========================================
# 5. UI 佈局 (企業級儀表板)
# ==========================================

# --- 側邊欄 (Sidebar) ---
with st.sidebar:
    # Header Area
    st.markdown("### 🏢 ShopAI Enterprise")
    st.caption(f"System Status: 🟢 Online | {datetime.date.today()}")
    st.markdown("---")
    
    # KPI Metrics Area
    df_all = pd.read_sql_query("SELECT * FROM products", conn)
    
    # 使用 container 包裝以控制佈局
    with st.container():
        st.markdown("**營運關鍵指標 (KPIs)**")
        col_kpi1, col_kpi2 = st.columns(2)
        with col_kpi1:
            st.metric("總 SKU 數", f"{len(df_all)}", delta="Item")
        with col_kpi2:
            # 庫存總值估算
            total_val = (df_all['price'] * df_all['stock']).sum()
            st.metric("庫存總值", f"${total_val/1000:.1f}K", help="當前庫存總零售價")
            
    # Alert Area
    low_stock = df_all[df_all['stock'] < 10]
    out_of_stock = df_all[df_all['status'] == '缺貨']
    
    st.markdown("#### 🚨 異常監控")
    col_alert1, col_alert2 = st.columns(2)
    with col_alert1:
         st.metric("缺貨品項", f"{len(out_of_stock)}", delta_color="inverse", delta=f"{len(out_of_stock)} 警示")
    with col_alert2:
         st.metric("低水位", f"{len(low_stock)}", delta_color="inverse")

    st.markdown("---")
    
    # Navigation / Quick Actions (模擬企業選單)
    st.markdown("**快速存取**")
    st.button("📊 匯出銷售報表", use_container_width=True)
    st.button("🔄 同步 ERP 數據", use_container_width=True)
    
    st.markdown("---")
    # Mini Table for quick glance
    st.markdown("<small>最近補貨清單</small>", unsafe_allow_html=True)
    st.dataframe(
        df_all.sort_values("last_restock", ascending=False).head(5)[['name', 'last_restock']],
        hide_index=True,
        use_container_width=True,
        height=150
    )

# --- 主畫面 (Main Content) ---
st.markdown("#### 👋 歡迎回到戰情室，店長。")

# 模擬 System Message
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "系統已連線至 SQLite 資料庫。您可以查詢全店 60+ 項商品的即時庫存狀態。"}
    ]

# 顯示對話紀錄
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="👨‍💼" if msg["role"]=="user" else "🤖"):
        st.markdown(msg["content"])
        
        # 數據展示區塊 (企業級設計：使用 Tab 分頁展示不同視圖)
        if "data" in msg and msg["data"] is not None and not msg["data"].empty:
            df_result = msg["data"]
            # 建立 Tabs: 數據表 | 簡易圖表
            tab1, tab2 = st.tabs(["📄 詳細數據表", "📈 數據可視化"])
            
            with tab1:
                st.dataframe(
                    df_result, 
                    hide_index=True, 
                    use_container_width=True,
                    column_config={
                        "price": st.column_config.NumberColumn("單價", format="$%d"),
                        "stock": st.column_config.ProgressColumn("庫存水位", format="%d", min_value=0, max_value=200),
                        "status": st.column_config.TextColumn("狀態")
                    }
                )
            with tab2:
                if len(df_result) > 1 and "name" in df_result.columns and "stock" in df_result.columns:
                    st.bar_chart(df_result.set_index("name")["stock"], color="#2563eb")
                else:
                    st.caption("資料筆數不足，無法產生圖表。")

# 輸入區
if prompt := st.chat_input("請輸入查詢指令... (e.g., 查詢庫存價值最高的酒類)"):
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
            
            # 人性化回覆
            reply = generate_human_response(prompt, result, error)
            st.markdown(reply)
            
            # 更新 Session
            st.session_state.messages.append({
                "role": "assistant",
                "content": reply,
                "data": result
            })
            
            # 重新整理頁面以顯示最新的資料表 (如果需要的話，這邊選擇不強制重整以保持體驗流暢)
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
                    if "name" in result.columns and "stock" in result.columns:
                        st.bar_chart(result.set_index("name")["stock"], color="#2563eb")