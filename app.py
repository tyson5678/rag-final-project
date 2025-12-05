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
    page_title="AI 深度知識庫", 
    page_icon="🧠", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("文件深度分析助手")
st.caption("🚀 Powered by Meta Llama 3.3 & Groq Inference Engine | Enterprise-Grade RAG System")

# ================= 3. 安全載入套件 =================
try:
    import langchain
    from langchain_groq import ChatGroq
    from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    # 🌟 關鍵修改：使用 community 的舊版接口，完美相容 sentence-transformers 2.2.2
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_community.vectorstores import Chroma
    
    # 使用舊版 Chain 架構 (最穩定)
    from langchain.chains import RetrievalQA
    from langchain_core.prompts import PromptTemplate
    
except ImportError as e:
    st.error(f"❌ 系統啟動失敗！原因: {e}")
    st.stop()

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ================= 4. API Key =================
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    GROQ_API_KEY = "請填入Key"

# ================= 5. 核心邏輯 =================

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
    st.header("🗂️ 資料上傳")
    
    uploaded_files = st.file_uploader(
        "上傳文件 (PDF / Word)", 
        type=["pdf", "docx"], 
        accept_multiple_files=True,
        key=st.session_state.uploader_id 
    )
    
    current_files_sig = [(f.name, f.size) for f in uploaded_files] if uploaded_files else []
    
    if uploaded_files:
        if current_files_sig != st.session_state.processed_files:
            with st.spinner("🧠 偵測到文件變動，正在重建資料庫 (CPU模式)..."):
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
                        for doc in docs:
                            doc.metadata["source_filename"] = file_name
                        
                        text_splitter = RecursiveCharacterTextSplitter(
                            chunk_size=800, 
                            chunk_overlap=150,
                            separators=["\n\n", "\n", "。", "！", "？", " ", ""]
                        )
                        splits = text_splitter.split_documents(docs)
                        all_splits.extend(splits)
                        os.remove(tmp_path)

                    if all_splits:
                        # 🌟 這裡不需要 device='cpu' 了，因為 2.2.2 版本預設就很乖
                        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
                        
                        # 使用 persist_directory 確保隔離性 (雖然我們用記憶體模式，但這樣寫法相容舊版)
                        unique_collection_name = f"collection_{uuid.uuid4()}"
                        
                        vector_db = Chroma.from_documents(
                            documents=all_splits, 
                            embedding=embeddings,
                            collection_name=unique_collection_name 
                        )
                        
                        st.session_state.vector_db = vector_db
                        st.session_state.processed_files = current_files_sig
                        st.toast(f"✅ 資料庫已重建！", icon="🔄")
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
    st.header("⚙️ 參數")
    
    temperature = st.slider("temperature（模型創意度）", 0.0, 1.0, 0.1, 0.1)
    k_value = st.slider("k值（閱讀廣度）", 2, 20, 8)

    st.markdown("")
    
    if st.button("🗑️ 清空對話", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
        
    st.markdown("") 
    if st.button("🔄 重置文件", type="primary", use_container_width=True, on_click=nuke_reset):
        pass

# ================= 聊天介面 =================

if not st.session_state.messages:
    st.info("👋 請上傳文件開始使用。")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("請輸入問題..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    if st.session_state.vector_db:
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            try:
                llm = ChatGroq(groq_api_key=GROQ_API_KEY, model_name="llama-3.3-70b-versatile", temperature=temperature)
                
                # 使用 PromptTemplate (配合舊版 Chain)
                template = """
                你是一個高階學術研究員。請根據以下【上下文】回答問題。
                1. 若無相關資訊，請誠實回答「文件中未提及」。
                2. 請用台灣繁體中文回答。
                
                【上下文】:
                {context}
                
                【問題】:
                {question}
                """
                QA_CHAIN_PROMPT = PromptTemplate.from_template(template)

                # 使用 RetrievalQA (最穩定的舊版 Chain)
                qa_chain = RetrievalQA.from_chain_type(
                    llm=llm,
                    retriever=st.session_state.vector_db.as_retriever(search_kwargs={"k": k_value}),
                    chain_type_kwargs={"prompt": QA_CHAIN_PROMPT},
                    return_source_documents=True
                )
                
                # 執行
                response = qa_chain.invoke({"query": prompt})
                answer = response['result']
                
                message_placeholder.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                
                # 顯示來源
                sources = response['source_documents']
                if sources:
                    with st.expander("📚 參考來源細節 (Reference Context)"):
                        tabs = st.tabs([f"來源 {i+1}" for i in range(len(sources))])
                        for i, tab in enumerate(tabs):
                            with tab:
                                doc = sources[i]
                                source_name = doc.metadata.get("source_filename", "未知文件")
                                page_num = doc.metadata.get("page", 0) + 1
                                c1, c2 = st.columns([2, 1])
                                with c1: st.markdown(f"**📄 文件：** `{source_name}`")
                                with c2: st.markdown(f"**📌 頁數：** `第 {page_num} 頁`")
                                st.info(doc.page_content)
                
            except Exception as e:
                st.error(f"❌ 錯誤: {e}")
    else:
        with st.chat_message("assistant"):
            st.warning("⚠️ 請先上傳文件，我才能回答問題喔！")