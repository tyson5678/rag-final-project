import streamlit as st
import os
import sys
import tempfile
import uuid
import pandas as pd
import plotly.graph_objects as go # 🌟 繪圖神器

# ================= 1. 雲端資料庫修正 =================
try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

# ================= 2. 頁面設定 =================
st.set_page_config(
    page_title="AI 智能投資分析師", 
    page_icon="📈", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📈 AI 智能投資分析師")
st.caption("🚀 雙引擎架構：Google Gemini + Groq | 支援 K 線圖繪製與財報分析")

# ================= 3. 匯入必要套件 =================
try:
    import langchain
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_groq import ChatGroq
    
    from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
    from langchain_community.vectorstores import Chroma
    from langchain.prompts import ChatPromptTemplate, PromptTemplate
    
    from langchain.agents import initialize_agent, AgentType, Tool
    from langchain.chains import RetrievalQA
    import yfinance as yf
    from googlesearch import search as google_search
    
except ImportError as e:
    st.error(f"❌ 系統啟動失敗！原因: {e}")
    st.stop()

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ================= 4. API Key 設定 =================
GOOGLE_API_KEY = st.secrets.get("GOOGLE_API_KEY", "")
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")

# ================= 5. 定義工具 (Tools) =================

def get_stock_price_func(symbol: str):
    """查詢股票即時數據"""
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        currency = info.get('currency', 'USD')
        price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('ask') or 'N/A'
        pe = info.get('trailingPE', 'N/A')
        eps = info.get('trailingEps', 'N/A')
        return f"【{symbol}】現價: {price} {currency}, 本益比(PE): {pe}, EPS: {eps}"
    except Exception as e:
        return f"查詢失敗: {e}"

def get_google_news_func(query: str):
    """Google 搜尋"""
    try:
        results = google_search(query, num_results=3, advanced=True)
        output_text = f"【Google 搜尋結果 - {query}】\n"
        count = 0
        for r in results:
            count += 1
            output_text += f"{count}. {r.title}\n   {r.description}\n\n"
        if count == 0: return "未搜尋到相關結果。"
        return output_text
    except Exception as e:
        return f"搜尋失敗: {e}"

def draw_stock_kline(symbol: str):
    """
    繪製股票 K 線圖 (Candlestick Chart)。
    輸入參數：股票代碼 (如 2330.TW)。
    """
    try:
        # 下載最近 3 個月的歷史數據
        df = yf.download(symbol, period="3mo", interval="1d")
        
        if df.empty:
            return f"無法獲取 {symbol} 的歷史數據，無法繪圖。"

        # 建立 Plotly K 線圖
        fig = go.Figure(data=[go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name=symbol
        )])

        fig.update_layout(
            title=f'{symbol} 近三個月 K 線走勢圖',
            yaxis_title='股價',
            xaxis_title='日期',
            template="plotly_white",
            height=500
        )
        
        # 🌟 關鍵：直接在 Streamlit 介面顯示圖表
        st.plotly_chart(fig, use_container_width=True)
        
        return f"已成功在畫面上繪製 {symbol} 的 K 線圖，請參考圖表進行趨勢分析。"
    except Exception as e:
        return f"繪圖失敗: {e}"

# ================= 6. 核心邏輯 =================

if "uploader_id" not in st.session_state:
    st.session_state.uploader_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "vector_db" not in st.session_state:
    st.session_state.vector_db = None
if "processed_files" not in st.session_state:
    st.session_state.processed_files = [] 

def nuke_reset():
    st.session_state.messages = []
    st.session_state.vector_db = None
    st.session_state.processed_files = []
    st.session_state.uploader_id = str(uuid.uuid4()) 

with st.sidebar:
    st.header("🤖 模型設定")
    model_option = st.selectbox(
        "選擇 AI 模型引擎",
        ("Google Gemini Pro (推薦)", "Groq Llama 3.1 8B (備用)"),
        index=0
    )
    
    st.divider()
    st.header("🗂️ 財報上傳")
    
    uploaded_files = st.file_uploader(
        "上傳文件", type=["pdf", "docx"], accept_multiple_files=True,
        key=st.session_state.uploader_id 
    )
    
    current_files_sig = [(f.name, f.size) for f in uploaded_files] if uploaded_files else []
    
    if uploaded_files:
        if current_files_sig != st.session_state.processed_files:
            with st.spinner("🧠 讀取並向量化文件 (FastEmbed)..."):
                try:
                    all_splits = []
                    for uploaded_file in uploaded_files:
                        file_name = uploaded_file.name
                        file_ext = os.path.splitext(file_name)[1].lower()
                        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            tmp_path = tmp_file.name
                        if file_ext == ".pdf": loader = PyPDFLoader(tmp_path)
                        elif file_ext == ".docx": loader = Docx2txtLoader(tmp_path)
                        else: continue
                        docs = loader.load()
                        text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
                        splits = text_splitter.split_documents(docs)
                        all_splits.extend(splits)
                        os.remove(tmp_path)

                    if all_splits:
                        embeddings = FastEmbedEmbeddings()
                        unique_collection_name = f"collection_{uuid.uuid4()}"
                        vector_db = Chroma.from_documents(
                            documents=all_splits, 
                            embedding=embeddings,
                            collection_name=unique_collection_name 
                        )
                        st.session_state.vector_db = vector_db
                        st.session_state.processed_files = current_files_sig
                        st.toast(f"✅ 資料庫建立完成！", icon="📚")
                    else:
                        st.warning("⚠️ 檔案內容為空")
                except Exception as e:
                    st.error(f"❌ 錯誤: {e}")
    else:
        if st.session_state.vector_db is not None:
            st.session_state.vector_db = None
            st.session_state.processed_files = []
            st.rerun()

    st.markdown("") 
    if st.button("🔄 重置系統", type="primary", use_container_width=True, on_click=nuke_reset):
        pass

# ================= 聊天介面 =================

if not st.session_state.messages:
    st.info("👋 我是 AI 投資分析師。我可以查股價、畫 K 線圖、搜新聞並分析財報。")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("請輸入問題 (例如：畫出 2330.TW 的走勢圖並分析)..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        try:
            llm = None
            if "Gemini" in model_option:
                if not GOOGLE_API_KEY: st.error("❌ 缺少 GOOGLE_API_KEY"); st.stop()
                message_placeholder.markdown("💎 Gemini 正在分析...")
                llm = ChatGoogleGenerativeAI(google_api_key=GOOGLE_API_KEY, model="gemini-pro", temperature=0.1)
            elif "Groq" in model_option:
                if not GROQ_API_KEY: st.error("❌ 缺少 GROQ_API_KEY"); st.stop()
                message_placeholder.markdown("⚡ Groq 正在分析...")
                llm = ChatGroq(groq_api_key=GROQ_API_KEY, model_name="llama-3.1-8b-instant", temperature=0.1)

            # 🌟 定義工具箱
            tools = [
                Tool(
                    name="Stock_Price",
                    func=get_stock_price_func,
                    description="輸入股票代碼(如 2330.TW)，查詢『即時股價、本益比、EPS』。"
                ),
                Tool(
                    name="Google_Search",
                    func=get_google_news_func,
                    description="輸入搜尋關鍵字，查詢『最新新聞、市場動態』。"
                ),
                Tool(
                    name="Draw_Kline_Chart",
                    func=draw_stock_kline,
                    description="輸入股票代碼(如 2330.TW)，『繪製 K 線圖』並顯示在畫面上。"
                )
            ]
            
            if st.session_state.vector_db:
                qa = RetrievalQA.from_chain_type(
                    llm=llm,
                    retriever=st.session_state.vector_db.as_retriever(search_kwargs={"k": 5})
                )
                tools.append(
                    Tool(
                        name="Financial_Report_RAG",
                        func=qa.run,
                        description="用於查詢使用者上傳的財報、PDF 文件內容。"
                    )
                )

            # 🌟 Agent 指令設定 (System Prompt)
            agent_prefix = """
            你是一個專業的華爾街投資顧問。你的任務是綜合利用多種工具來回答使用者的投資問題。
            
            【你的工具箱】：
            1. Stock_Price: 查即時股價、PE、EPS。
            2. Draw_Kline_Chart: 當使用者提到「走勢圖」、「K線」、「畫圖」時，務必使用此工具。
            3. Google_Search: 查最近的新聞利多/利空。
            4. Financial_Report_RAG: (若有上傳文件) 查財報細節。

            【回答策略】：
            - 必須先調用工具獲取真實數據，不要憑空猜測。
            - 若使用者要求畫圖，請優先調用 Draw_Kline_Chart。
            - 最後請根據 股價表現 + 技術面(K線) + 基本面(財報) + 消息面(新聞) 給出綜合投資建議 (Buy/Hold/Sell)。
            """

            agent = initialize_agent(
                tools, 
                llm, 
                agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                verbose=False,
                handle_parsing_errors=True,
                agent_kwargs={'prefix': agent_prefix} # 注入更強的 Prompt
            )
            
            response = agent.run(prompt)
            
            message_placeholder.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
            
        except Exception as e:
            st.error(f"❌ 發生錯誤: {e}")