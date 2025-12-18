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
st.caption("🚀 整合即時股價 (Yahoo Finance) + 網路新聞 + 財報深度分析 (RAG)")

# ================= 3. 匯入必要套件 =================
try:
    import langchain
    from langchain_groq import ChatGroq
    from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    # 🌟 使用 FastEmbed 避免雲端當機
    from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
    from langchain_chroma import Chroma
    from langchain_core.prompts import ChatPromptTemplate
    # 🌟 這些是新版 LangChain 的功能，requirements.txt 必須 >=0.2.0
    from langchain.agents import create_tool_calling_agent, AgentExecutor
    from langchain_core.tools import tool
    from langchain.tools.retriever import create_retriever_tool
    from langchain_community.tools import DuckDuckGoSearchRun
    import yfinance as yf
    
except ImportError as e:
    st.error(f"❌ 系統啟動失敗！原因: {e}")
    st.stop()

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ================= 4. API Key =================
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    GROQ_API_KEY = "請填入Key"

# ================= 5. 定義工具 (Tools) =================

@tool
def get_stock_price(symbol: str):
    """
    獲取股票的即時股價資訊。
    輸入參數 symbol 必須是股票代碼。
    台股請加上 .TW (例如 2330.TW)，美股直接輸入代碼 (例如 NVDA, AAPL)。
    """
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        current_price = info.get('currentPrice', 'N/A')
        currency = info.get('currency', 'USD')
        pe_ratio = info.get('trailingPE', 'N/A')
        market_cap = info.get('marketCap', 'N/A')
        return f"【{symbol} 即時數據】\n現價: {current_price} {currency}\n本益比(P/E): {pe_ratio}\n市值: {market_cap}"
    except Exception as e:
        return f"查詢失敗: {e}"

@tool
def get_company_news(query: str):
    """
    搜尋關於該公司的最新網路新聞或市場消息。
    """
    search = DuckDuckGoSearchRun()
    return search.run(query)

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
                        # Agent 模式下，切分可以稍微小一點，讓檢索更精準
                        text_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100)
                        splits = text_splitter.split_documents(docs)
                        all_splits.extend(splits)
                        os.remove(tmp_path)

                    if all_splits:
                        # 🌟 使用 FastEmbed (輕量、CPU專用)
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
            tools = [get_stock_price, get_company_news]
            
            # 如果有 RAG 資料庫，加入檢索工具
            if st.session_state.vector_db:
                retriever = st.session_state.vector_db.as_retriever(search_kwargs={"k": 5})
                retriever_tool = create_retriever_tool(
                    retriever,
                    "search_financial_report",
                    "搜尋使用者上傳的財報內容。當問題涉及公司內部數據、財報細節時使用。"
                )
                tools.append(retriever_tool)

            # 建立 Agent
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", "你是一個專業的投資分析師。結合『即時數據』(股價、新聞) 與 『內部文件』(若有) 來回答。請用繁體中文。"),
                ("placeholder", "{chat_history}"),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ])
            
            agent = create_tool_calling_agent(llm, tools, prompt_template)
            agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
            
            response = agent_executor.invoke({"input": prompt})
            answer = response['output']
            
            message_placeholder.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})
            
        except Exception as e:
            st.error(f"❌ 錯誤: {e}")