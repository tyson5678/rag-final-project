import streamlit as st
import pandas as pd
import sqlite3
from groq import Groq
import os

# ==========================================
# 1. 頁面設定與 CSS 美化 (UI 升級核心)
# ==========================================
st.set_page_config(
    page_title="AI 智慧店長 - 數據查詢系統",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 注入自定義 CSS 讓介面更有質感
st.markdown("""
<style>
    /* 全域字體優化 */
    .stApp {
        font-family: 'Inter', '微軟正黑體', sans-serif;
    }
    
    /* 聊天氣泡樣式優化 */
    .stChatMessage {
        padding: 1rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    
    /* 表格樣式優化 */
    .dataframe {
        font-size: 0.9rem !important;
        border-radius: 8px !important;
        overflow: hidden !important;
    }
    
    /* 側邊欄標題 */
    .css-1d391kg {
        padding-top: 2rem;
    }
    
    /* 關鍵指標卡片 (Metric) */
    div[data-testid="stMetric"] {
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 8px;
        border: 1px solid #e9ecef;
    }
    
    /* 隱藏 Streamlit 預設選單 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 安全 API Key 讀取
# ==========================================
api_key = None
if "GROQ_API_KEY" in st.secrets:
    api_key = st.secrets["GROQ_API_KEY"]
elif os.getenv("GROQ_API_KEY"):
    api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    st.error("🚨 系統未偵測到 API Key")
    st.info("請檢查 Streamlit Secrets 或環境變數設定。")
    st.stop()

client = Groq(api_key=api_key)

# ==========================================
# 3. 初始化資料庫 (擴充版數據)
# 模擬一家小型便利商店 (Mini Mart)
# ==========================================
@st.cache_resource
def init_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT,
            category TEXT,
            price INTEGER,
            stock INTEGER,
            status TEXT
        )
    ''')
    
    # 擴充後的 30+ 筆模擬資料
    products_data = [
        # 飲料類
        (101, "可口可樂 600ml", "飲料", 35, 120, "正常"),
        (102, "無糖綠茶", "飲料", 25, 200, "正常"),
        (103, "全脂鮮乳", "飲料", 92, 8, "補貨中"),
        (104, "拿鐵咖啡", "飲料", 55, 45, "正常"),
        (105, "礦泉水", "飲料", 20, 300, "正常"),
        (106, "燕麥奶", "飲料", 120, 15, "正常"),
        # 零食類
        (201, "洋芋片(原味)", "零食", 45, 80, "正常"),
        (202, "義美小泡芙", "零食", 32, 100, "正常"),
        (203, "70%黑巧克力", "零食", 89, 5, "補貨中"),
        (204, "科學麵", "零食", 12, 500, "正常"),
        (205, "綜合堅果", "零食", 150, 20, "正常"),
        # 生鮮食品
        (301, "御飯糰(鮪魚)", "生鮮", 35, 12, "正常"),
        (302, "茶葉蛋", "生鮮", 13, 0, "缺貨"),
        (303, "香蕉(根)", "生鮮", 20, 5, "補貨中"),
        (304, "國民便當", "生鮮", 89, 8, "正常"),
        (305, "雞胸肉", "生鮮", 59, 25, "正常"),
        # 日用品
        (401, "抽取式衛生紙", "日用品", 120, 60, "正常"),
        (402, "3號電池(4入)", "日用品", 89, 30, "正常"),
        (403, "輕便雨衣", "日用品", 40, 150, "正常"),
        (404, "醫用口罩(盒)", "日用品", 199, 100, "正常"),
        # 酒類
        (501, "金牌啤酒", "酒類", 45, 200, "正常"),
        (502, "紅酒", "酒類", 450, 10, "正常"),
        (503, "威士忌", "酒類", 800, 3, "缺貨"),
    ]
    
    c.executemany('INSERT INTO products VALUES (?,?,?,?,?,?)', products_data)
    conn.commit()
    return conn

conn = init_db()

# ==========================================
# 4. AI 邏輯與 Prompt 設定
# ==========================================
DB_SCHEMA = """
Table: products
Columns:
- id (INTEGER): 商品編號
- name (TEXT): 商品名稱
- category (TEXT): 類別 ('飲料', '零食', '生鮮', '日用品', '酒類')
- price (INTEGER): 價格 (TWD)
- stock (INTEGER): 庫存量
- status (TEXT): 庫存狀態 ('正常', '缺貨', '補貨中')
"""

SYSTEM_PROMPT = f"""
你是一位專業的資料庫管理員。請將使用者的自然語言轉換為 SQLite 語法的 SQL 查詢。

【資料庫結構】
{DB_SCHEMA}

【嚴格規則】
1. 僅回傳 SQL 語句，**嚴禁**包含 Markdown (如 ```sql) 或任何解釋文字。
2. 語法必須符合 standard SQLite。
3. 若使用者查詢「缺貨」或「沒貨」，請使用 status = '缺貨' 或 stock = 0。
4. 若使用者查詢「補貨」，請使用 status = '補貨中'。
5. 模糊搜尋請用 LIKE '%關鍵字%'。
6. 請勿輸出分號 (;) 結尾。
"""

def get_sql_from_llm(query):
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile", # 使用最新的模型
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": query}
            ],
            temperature=0.1,
            max_tokens=200
        )
        sql = completion.choices[0].message.content.strip()
        # 強制清理格式
        return sql.replace("```sql", "").replace("```", "").replace("\n", " ").strip()
    except Exception as e:
        return f"Error: {str(e)}"

def execute_sql(sql):
    try:
        return pd.read_sql_query(sql, conn)
    except Exception as e:
        return None

# ==========================================
# 5. UI 佈局：側邊欄儀表板 (Dashboard)
# ==========================================
with st.sidebar:
    st.title("🏪 門市數據總覽")
    
    # 計算即時指標
    df_all = pd.read_sql_query("SELECT * FROM products", conn)
    total_products = len(df_all)
    total_stock = df_all['stock'].sum()
    low_stock_count = len(df_all[df_all['stock'] < 10])
    
    # 顯示指標卡片
    col1, col2 = st.columns(2)
    with col1:
        st.metric("總商品數", f"{total_products}", delta="SKU")
    with col2:
        st.metric("總庫存", f"{total_stock:,}")
        
    st.metric("⚠️ 低庫存/缺貨商品", f"{low_stock_count}", delta_color="inverse")
    
    st.markdown("---")
    st.subheader("📋 完整庫存清單")
    # 使用 dataframe 顯示並隱藏索引，增加質感
    st.dataframe(
        df_all[['name', 'category', 'stock', 'status']], 
        use_container_width=True, 
        hide_index=True,
        height=300
    )
    
    st.markdown("---")
    st.markdown("Made with ❤️ by Streamlit & Llama 3")

# ==========================================
# 6. UI 佈局：主聊天視窗
# ==========================================

# 標題區
st.markdown("## 🤖 AI 智慧店長")
st.markdown("請直接輸入中文查詢，例如：「**幫我查所有酒類的庫存**」或「**還有哪些東西缺貨？**」")

# 初始化訊息紀錄
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "店長你好！我是你的 AI 助理。今天想查詢什麼銷售數據？"}
    ]

# 渲染歷史訊息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sql" in msg:
            # 使用 expander 收合 SQL 代碼，讓介面更乾淨
            with st.expander("查看生成的 SQL"):
                st.code(msg["sql"], language="sql")
        if "data" in msg:
            st.dataframe(msg["data"], hide_index=True)

# 輸入區
if prompt := st.chat_input("輸入查詢指令..."):
    # 1. 使用者訊息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. AI 處理
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        with st.spinner("AI 正在分析資料庫..."):
            sql_query = get_sql_from_llm(prompt)
            
            if sql_query.startswith("Error"):
                st.error("連線錯誤，請稍後再試。")
            else:
                # 執行查詢
                result_df = execute_sql(sql_query)
                
                # 構建回應
                if result_df is not None and not result_df.empty:
                    st.success(f"✅ 查詢完成，共找到 {len(result_df)} 筆資料")
                    st.dataframe(result_df, hide_index=True)
                    
                    # 更新紀錄
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": f"✅ 查詢完成，共找到 {len(result_df)} 筆資料",
                        "sql": sql_query,
                        "data": result_df
                    })
                elif result_df is not None:
                    st.warning("⚠️ 語法執行成功，但未找到符合條件的商品。")
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": "⚠️ 語法執行成功，但未找到符合條件的商品。",
                        "sql": sql_query
                    })
                else:
                    st.error("❌ SQL 語法錯誤，無法執行。")