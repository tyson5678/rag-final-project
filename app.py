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
    page_icon="💎", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("💎 AI 智能投資分析師 (Gemini Pro)")
st.caption("🚀 Powered by Google Gemini Pro | Stable & Free")

# ================= 3. 匯入必要套件 =================
try:
    import langchain
    # 🌟 Google 模型套件
    from langchain_google_genai import ChatGoogleGenerativeAI
    
    from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
    from langchain_community.vectorstores import Chroma
    from langchain.prompts import ChatPromptTemplate
    
    # Agent 模組
    from langchain.agents import initialize_agent, AgentType, Tool
    from langchain.chains import RetrievalQA
    import yfinance as yf
    from googlesearch import search as google_search
    
except ImportError as e:
    st.error(f"❌ 系統啟動失敗！原因: {e}")
    st.stop()

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ================= 4. API Key =================
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    GOOGLE_API_KEY = "請填入Key"

# ================= 5. 定義工具 (Tools) =================

def get_stock_price_func(symbol: str):
    """查詢股票價格"""
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        currency = info.get('currency', 'USD')
        price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('ask') or 'N/A'
        return f"【{symbol}】現價: {price} {currency}"
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
            with st.spinner("🧠 正在讀取財報數據..."):
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
                        st.toast(f"✅ 資料庫建立完成！", icon="💎")
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
    st.markdown("- 查新聞：`Google 搜尋 NVDA`")
    
    st.markdown("") 
    if st.button("🔄 重置系統", type="primary", use_container_width=True, on_click=nuke_reset):
        pass

# ================= 聊天介面 =================

if not st.session_state.messages:
    st.info("👋 我是 Gemini Pro 投資助手，請下達指令。")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("請輸入問題..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("💎 Gemini 正在思考...")
        
        try:
            # 🌟 核心修改：改用最穩定的 'gemini-pro'
            llm = ChatGoogleGenerativeAI(
                google_api_key=GOOGLE_API_KEY,
                model="gemini-pro",  # <--- 這裡改了
                temperature=0.1,
                convert_system_message_to_human=True
            )
            
            tools = [
                Tool(
                    name="Stock_Price",
                    func=get_stock_price_func,
                    description="輸入股票代碼(如 2330.TW)，回傳即時股價。"
                ),
                Tool(
                    name="Google_Search",
                    func=get_google_news_func,
                    description="輸入搜尋關鍵字，回傳網路新聞。"
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
                        description="用於查詢使用者上傳的財報內容。"
                    )
                )

            agent = initialize_agent(
                tools, 
                llm, 
                agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
                verbose=False,
                handle_parsing_errors=True
            )
            
            response = agent.run(prompt)
            
            message_placeholder.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
            
        except Exception as e:
            st.error(f"❌ 錯誤: {e}")
            if "API_KEY" in str(e):
                st.warning("⚠️ 請檢查 Google API Key 設定！")