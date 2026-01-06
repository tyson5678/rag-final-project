import streamlit as st
import pandas as pd
import sqlite3
from groq import Groq
import json
import os

# ==========================================
# 1. 設定與初始化
# ==========================================
st.set_page_config(
    page_title="AI 智慧超市查詢",
    page_icon="🛒",
    layout="wide"
)

# 🔑 API Key 讀取邏輯 (修正版)
# ------------------------------------------
api_key = None # 初始化變數

# 優先嘗試從 Streamlit Secrets 讀取
if "GROQ_API_KEY" in st.secrets:
    api_key = st.secrets["GROQ_API_KEY"]
# 其次嘗試從環境變數讀取 (本地開發用)
elif os.getenv("GROQ_API_KEY"):
    api_key = os.getenv("GROQ_API_KEY")

# 檢查是否成功取得 Key
if not api_key:
    st.error("🚨 未偵測到 API Key！")
    st.info("""
        請檢查 Streamlit Cloud 的 Secrets 設定，或本地的 .streamlit/secrets.toml 檔案。
        格式應為: GROQ_API_KEY = "gsk_xxxxxx"
    """)
    st.stop()

# 設定環境變數 (為了相容性)
os.environ["GROQ_API_KEY"] = api_key

# 初始化 Groq Client (⚠️ 這裡修正了：使用 api_key 變數)
client = Groq(api_key=api_key)

# ==========================================
# 2. 建置真實的 SQLite 資料庫 (In-Memory)
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
    
    products_data = [
        (1, "富士蘋果", "水果", 35, 120, "正常"),
        (2, "金鑽鳳梨", "水果", 89, 8, "補貨中"),
        (3, "巨峰葡萄", "水果", 150, 50, "正常"),
        (4, "澳洲和牛M9", "肉類", 1200, 3, "缺貨"),
        (5, "梅花豬肉片", "肉類", 220, 40, "正常"),
        (6, "全脂鮮乳", "飲料", 92, 10, "補貨中"),
        (7, "無糖綠茶", "飲料", 25, 200, "正常"),
        (8, "厚切洋芋片", "零食", 45, 150, "正常"),
        (9, "70%黑巧克力", "零食", 85, 0, "缺貨")
    ]
    c.executemany('INSERT INTO products VALUES (?,?,?,?,?,?)', products_data)
    conn.commit()
    return conn

conn = init_db()

# ==========================================
# 3. 定義 Schema 與 AI Prompt
# ==========================================
DB_SCHEMA = """
Table: products
Columns:
- id (INTEGER)
- name (TEXT): 商品名稱
- category (TEXT): 類別 ('水果', '肉類', '飲料', '零食')
- price (INTEGER): 價格
- stock (INTEGER): 庫存
- status (TEXT): 狀態 ('正常', '缺貨', '補貨中')
"""

SYSTEM_PROMPT = f"""
你是一位 SQL 專家。將使用者的自然語言轉換為 SQLite 語法的 SQL 查詢。

【資料庫結構】
{DB_SCHEMA}

【規則】
1. 只回傳 SQL 語句，不要有 Markdown (```sql) 或解釋。
2. 確保語法符合 SQLite 標準。
3. 如果使用者問「還有貨嗎」，代表 stock > 0。
4. 如果使用者查詢模糊，請用 LIKE 或適當的數值比較。
5. 只要 SELECT 語句，不要輸出分號結尾。
"""

# ==========================================
# 4. 核心功能函式
# ==========================================
def get_sql_from_llm(query):
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": query}
            ],
            temperature=0.1,
            max_tokens=200
        )
        sql = completion.choices[0].message.content.strip()
        # 清理可能的回傳格式
        sql = sql.replace("```sql", "").replace("```", "").replace("\n", " ").strip()
        return sql
    except Exception as e:
        return f"Error: {str(e)}"

def execute_sql(sql):
    try:
        return pd.read_sql_query(sql, conn)
    except Exception as e:
        return None

# ==========================================
# 5. Streamlit UI 介面
# ==========================================
with st.sidebar:
    st.header("🗄️ 資料庫預覽")
    st.info("這是一個運行在記憶體中的 SQLite 真實資料庫。")
    df_all = pd.read_sql_query("SELECT * FROM products", conn)
    st.dataframe(df_all, use_container_width=True, hide_index=True)
    st.markdown("---")
    st.markdown("### 💡 提示")
    st.caption("試試看詢問：\n- 庫存最少的 3 樣商品\n- 算出水果類別的平均價格\n- 有哪些飲料正在補貨？")

st.title("🛒 AI 智慧超市查詢器 (Streamlit × Groq)")
st.caption("Powered by Llama 3 & SQLite")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "你好！我是你的數據助理。這裡連接著真實的 SQL 資料庫，你可以考考我更複雜的問題，例如「平均價格」或「排序」。"}
    ]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sql" in msg:
            st.code(msg["sql"], language="sql")
        if "data" in msg:
            st.dataframe(msg["data"], hide_index=True)

if prompt := st.chat_input("請輸入查詢 (例如：列出價格大於 50 的水果)"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("正在思考 SQL 邏輯..."):
            sql_query = get_sql_from_llm(prompt)
            
            if sql_query.startswith("Error"):
                st.error(f"API 連線失敗：{sql_query}")
            else:
                st.markdown(f"已生成 SQL 查詢：")
                st.code(sql_query, language="sql")
                
                result_df = execute_sql(sql_query)
                
                if result_df is not None and not result_df.empty:
                    st.success(f"查詢成功！找到 {len(result_df)} 筆資料。")
                    st.dataframe(result_df, hide_index=True)
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": "這是查詢結果：",
                        "sql": sql_query,
                        "data": result_df
                    })
                elif result_df is not None:
                    st.warning("SQL 執行成功，但沒有找到符合條件的資料。")
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": "查無資料。",
                        "sql": sql_query
                    })
                else:
                    st.error("SQL 語法錯誤或無法執行。")