import streamlit as st
import pandas as pd
import sqlite3
from groq import Groq
import os
import json

# ==========================================
# 1. 介面設計與 CSS 注入 (修正側邊欄按鈕消失問題)
# ==========================================
st.set_page_config(
    page_title="ShopAI - 智慧零售助手",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded" # 預設展開側邊欄
)

# 專業級 CSS 樣式 (修正版)
st.markdown("""
<style>
    /* 引入現代字體 */
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Noto Sans TC', sans-serif;
    }

    /* 隱藏預設 Footer 和漢堡選單 (右上的三點)，但保留 Header 以便顯示側邊欄按鈕 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* 關鍵修正：不要隱藏 header，改為讓它變透明或與背景融合。
       這樣左上角的 ">" 箭頭按鈕才會出現！
    */
    header {
        visibility: visible !important;
        background-color: transparent !important;
    }
    
    /* 移除 Header 的裝飾線 (如果你不想看到彩色的線) */
    [data-testid="stDecoration"] {
        display: none;
    }

    /* 側邊欄美化 */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
        border-right: 1px solid #e9ecef;
    }

    /* 指標卡片 (Metrics) */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid #edf2f7;
    }

    /* 聊天氣泡容器 */
    .stChatMessage {
        background-color: transparent;
        border: none;
    }

    /* 用戶氣泡 */
    div[data-testid="stChatMessage"]:nth-child(odd) {
        flex-direction: row-reverse;
        background-color: transparent;
    }

    /* 表格樣式優化 */
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    
    /* 自定義按鈕 */
    .stButton button {
        border-radius: 20px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 安全 API Key 與 Client 初始化
# ==========================================
api_key = None
if "GROQ_API_KEY" in st.secrets:
    api_key = st.secrets["GROQ_API_KEY"]
elif os.getenv("GROQ_API_KEY"):
    api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    st.error("🚨 系統未偵測到 API Key，請檢查設定。")
    st.stop()

client = Groq(api_key=api_key)

# ==========================================
# 3. 資料庫初始化 (維持擴充版數據)
# ==========================================
@st.cache_resource
def init_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT, category TEXT, price INTEGER, stock INTEGER, status TEXT
        )
    ''')
    
    products_data = [
        (101, "可口可樂 600ml", "飲料", 35, 120, "正常"),
        (102, "原萃綠茶", "飲料", 25, 200, "正常"),
        (103, "瑞穗全脂鮮乳", "飲料", 92, 0, "缺貨"),
        (104, "貝納頌咖啡", "飲料", 35, 45, "正常"),
        (105, "舒跑運動飲料", "飲料", 25, 150, "正常"),
        (106, "OATLY燕麥奶", "飲料", 169, 12, "補貨中"),
        (201, "樂事洋芋片(原味)", "零食", 45, 80, "正常"),
        (202, "義美小泡芙(巧克力)", "零食", 32, 100, "正常"),
        (203, "金莎巧克力(3入)", "零食", 42, 5, "補貨中"),
        (204, "科學麵", "零食", 12, 500, "正常"),
        (205, "萬歲牌綜合堅果", "零食", 150, 20, "正常"),
        (206, "北海鱈魚香絲", "零食", 50, 60, "正常"),
        (301, "御飯糰(鮪魚)", "生鮮", 35, 12, "正常"),
        (302, "所長茶葉蛋", "生鮮", 18, 0, "缺貨"),
        (303, "台灣香蕉", "生鮮", 25, 5, "補貨中"),
        (304, "奮起湖便當", "生鮮", 89, 8, "正常"),
        (305, "即食雞胸肉", "生鮮", 59, 25, "正常"),
        (401, "舒潔衛生紙", "日用品", 129, 60, "正常"),
        (402, "金頂電池(3號)", "日用品", 159, 30, "正常"),
        (403, "輕便雨衣", "日用品", 49, 150, "正常"),
        (404, "口罩(50入)", "日用品", 199, 100, "正常"),
        (501, "金牌台灣啤酒", "酒類", 45, 200, "正常"),
        (502, "海尼根", "酒類", 55, 180, "正常"),
        (503, "約翰走路黑牌", "酒類", 850, 3, "缺貨"),
        (504, "18天生啤", "酒類", 65, 10, "補貨中")
    ]
    c.executemany('INSERT INTO products VALUES (?,?,?,?,?,?)', products_data)
    conn.commit()
    return conn

conn = init_db()

# ==========================================
# 4. 雙階段 AI 核心 (維持人性化邏輯)
# ==========================================
DB_SCHEMA = """
Table: products
Columns: id, name, category, price, stock, status ('正常', '缺貨', '補貨中')
"""

def generate_sql(query):
    system_prompt = f"""
    You are a SQL expert. Convert user question to SQLite query.
    Schema: {DB_SCHEMA}
    Rules:
    1. Output ONLY the SQL. No markdown.
    2. Use `LIKE` for fuzzy search.
    3. If user asks for 'out of stock', use `status='缺貨'` or `stock=0`.
    """
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": query}],
            temperature=0.1, max_tokens=150
        )
        sql = completion.choices[0].message.content.strip().replace("```sql", "").replace("```", "")
        return sql
    except:
        return None

def generate_human_response(user_query, sql_result_df, sql_error=None):
    available_categories = "飲料, 零食, 生鮮, 日用品, 酒類"
    
    if sql_error:
        data_context = f"SQL Execution Failed: {sql_error}"
    elif sql_result_df is None or sql_result_df.empty:
        data_context = "Query returned NO DATA (Empty Result)."
    else:
        data_context = f"Query Results:\n{sql_result_df.to_string(index=False)}"

    system_prompt = f"""
    你是一位專業、親切的「智慧零售店長」。
    使用者的問題是："{user_query}"
    
    【資料庫回傳結果】
    {data_context}
    
    【你的任務】
    請根據回傳結果，用「繁體中文」回答使用者。
    
    【回答策略】
    1. **如果有資料**：直接總結數據。例如「目前庫存還有 120 個，價格是 35 元。」
    2. **如果沒有資料 (Empty Result)**：
       - **不要**說「查無資料」。
       - **要說**：「很抱歉，我們目前沒有這項商品。」
       - **然後主動推薦**：根據使用者的問題，從我們的類別 ({available_categories}) 中推薦替代品。
    3. **語氣**：專業、有禮貌、像真人對話。
    4. **格式**：不要使用 markdown 表格，用自然語言敘述即可。
    """

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt}],
            temperature=0.7,
            max_tokens=300
        )
        return completion.choices[0].message.content
    except:
        return "系統忙碌中，請稍後再試。"

# ==========================================
# 5. UI 佈局 (維持 Dashboard 設計)
# ==========================================

# 側邊欄
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3081/3081559.png", width=60)
    st.title("ShopAI 儀表板")
    st.markdown("Ver 2.1 Fixed")
    
    st.markdown("---")
    
    df_all = pd.read_sql_query("SELECT * FROM products", conn)
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("📦 總品項", f"{len(df_all)}")
    with col2:
        st.metric("💰 庫存價值", f"${(df_all['price'] * df_all['stock']).sum():,}")
        
    warning_count = len(df_all[df_all['stock'] < 10])
    st.metric("⚠️ 需補貨商品", f"{warning_count} 項", delta_color="inverse")
    
    st.markdown("### 🗂️ 快速庫存預覽")
    st.dataframe(
        df_all[['name', 'stock', 'status']], 
        height=300, 
        hide_index=True,
        column_config={
            "status": st.column_config.TextColumn("狀態"),
            "stock": st.column_config.ProgressColumn("庫存量", format="%d", min_value=0, max_value=200),
        }
    )

# 主畫面
st.markdown("## 👋 您好，我是您的 AI 智慧店長")
st.markdown("您可以問我任何關於庫存、價格或銷售的問題。")
st.markdown("---")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "歡迎光臨！今天想查點什麼？我可以幫您找商品、查價格，或是看看什麼東西快賣完了。"}
    ]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🧑‍💻" if msg["role"]=="user" else "🤖"):
        st.markdown(msg["content"])
        if "data" in msg and msg["data"] is not None and not msg["data"].empty:
            with st.expander("📊 查看詳細數據表"):
                st.dataframe(msg["data"], hide_index=True, use_container_width=True)

if prompt := st.chat_input("請輸入查詢 (例如：有沒有賣紅茶？)"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("店長正在查詢庫存..."):
            
            sql_query = generate_sql(prompt)
            result_df = None
            sql_error = None
            
            if sql_query:
                try:
                    result_df = pd.read_sql_query(sql_query, conn)
                except Exception as e:
                    sql_error = str(e)
            
            human_reply = generate_human_response(prompt, result_df, sql_error)
            
            st.markdown(human_reply)
            
            if result_df is not None and not result_df.empty:
                with st.expander("📊 查看詳細數據表"):
                    st.dataframe(result_df, hide_index=True, use_container_width=True)
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": human_reply,
                "data": result_df
            })