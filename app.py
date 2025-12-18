import streamlit as st
import os
import sys
import tempfile
import uuid

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
st.caption("🚀 Powered by Meta Llama 3.3 & Groq | Stable Version 0.2.14")

# ================= 3. 匯入必要套件 =================
try:
    import langchain
    from langchain_groq import ChatGroq
    from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    # 🌟 使用 FastEmbed 避免 GPU 錯誤
    from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
    from langchain_community.vectorstores import Chroma
    from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
    
    # 🌟 LangChain 0.2.x 依然支援 initialize_agent
    from langchain.agents import initialize_agent, AgentType, Tool
    from langchain_community.tools import DuckDuckGoSearchRun
    from langchain.chains import RetrievalQA
    import yfinance as yf
    
except ImportError as e:
    st.error(f"❌ 系統啟動失敗！原因: {e}")
    st.info("💡 請確認 requirements.txt 鎖定 langchain==0.2.14")
    st.stop()

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ================= 4. API Key =================
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    GROQ_API_KEY = "請填入Key"

# ================= 5. 定義工具 (Tools) =================

def get_stock_price_func(symbol: str):
    """查詢股票價格的實際函式"""
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        currency = info.get('currency', 'USD')
        # 多重欄位抓取，增加成功率
        price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('ask') or 'N/A'
        return f"【{symbol}】現價: {price} {currency}"
    except Exception as e:
        return f"查詢失敗: {e}"

def get_news_func(query: str):
    """查詢新聞的實際函式"""
    try:
        search = DuckDuckGoSearchRun()
        return search.run(query)
    except Exception as e:
        return f"搜尋失敗: {e}"

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
    """核彈級重置"""
    st.session_state.messages = []
    st.session_state.vector_db = None
    st.session_state.processed_files = []
    st.session_state.uploader_id = str(uuid.uuid4()) 

with st.sidebar:
    st.header("🗂️ 財報/文件上傳")
    
    uploaded_files = st.file_uploader(
        "上傳文件", 
        type=["pdf", "docx"], 
        accept_multiple_files=True,
        key=st.session_state.uploader_id 
    )
    
    current_files_sig = [(f.name, f.size) for f in uploaded_files] if uploaded_files else []
    
    if uploaded_files:
        if current_files_sig != st.session_state.processed_files:
            with st.spinner("🧠 正在讀取財報數據 (FastEmbed)..."):
                try:
                    all_splits = []
                    for uploaded_file in uploaded_files:
                        file_name = uploaded_file.name
                        file_ext = os.path.splitext(file_name)[1].lower()
                        
                        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            tmp_path = tmp_file.name

                        if file_ext == ".pdf":
                            loader = PyPDFLoader(tmp_path)
                        elif file_ext == ".docx":
                            loader = Docx2txtLoader(tmp_path)
                        else:
                            continue
                            
                        docs = loader.load()
                        text_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100)
                        splits = text_splitter.split_documents(docs)
                        all_splits.extend(splits)
                        os.remove(tmp_path)

                    if all_splits:
                        # 使用 FastEmbed，穩定且輕量
                        embeddings = FastEmbedEmbeddings()
                        unique_collection_name = f"collection_{uuid.uuid4()}"
                        
                        vector_db = Chroma.from_documents(
                            documents=all_splits, 
                            embedding=embeddings,
                            collection_name=unique_collection_name 
                        )
                        
                        st.session_state.vector_db = vector_db
                        st.session_state.processed_files = current_files_sig
                        st.toast(f"✅ 財報資料庫建立完成！", icon="📊")
                    else:
                        st.warning("⚠️ 檔案內容為空")
                except Exception as e:
                    st.error(f"❌ 錯誤: {e}")
    else:
        if st.session_state.vector_db is not None:
            st.session_state.vector_db = None
            st.session_state.processed_files = []
            st.rerun()

    st.divider()
    st.markdown("### 💡 使用範例")
    st.markdown("- 查股價：`2330.TW 股價`")
    st.markdown("- 查新聞：`NVDA 最新新聞`")
    st.markdown("- 綜合：(需上傳) `結合股價分析這份財報`")
    
    st.markdown("") 
    if st.button("🔄 重置系統", type="primary", use_container_width=True, on_click=nuke_reset):
        pass

# ================= 聊天介面 =================

if not st.session_state.messages:
    st.info("👋 我是 AI 投資分析師，請下達指令。")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("請輸入問題..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("🤔 AI 正在思考與調用工具...")
        
        try:
            llm = ChatGroq(groq_api_key=GROQ_API_KEY, model_name="llama-3.3-70b-versatile", temperature=0.1)
            
            # 定義工具
            tools = [
                Tool(
                    name="Stock_Price",
                    func=get_stock_price_func,
                    description="輸入股票代碼(如 2330.TW)，回傳即時股價。"
                ),
                Tool(
                    name="Google_Search",
                    func=get_news_func,
                    description="輸入搜尋關鍵字，回傳網路新聞。"
                )
            ]
            
            if st.session_state.vector_db:
                # 使用 RetrievalQA
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

            # 🌟 0.2.14 版本：支援 initialize_agent 且修復了 datetime bug
            agent = initialize_agent(
                tools, 
                llm, 
                agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                verbose=False, # 關閉 verbose 以防萬一
                handle_parsing_errors=True
            )
            
            response = agent.run(prompt)
            
            message_placeholder.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
            
        except Exception as e:
            st.error(f"❌ 錯誤: {e}")