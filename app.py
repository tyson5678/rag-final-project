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

st.title("深度文件分析助手")
st.caption("🚀 Powered by Meta Llama 3.3 & Groq Inference Engine | Enterprise-Grade RAG System")

# ================= 3. 安全載入套件 =================
try:
    import langchain
    from langchain_groq import ChatGroq
    from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_chroma import Chroma
    try:
        from langchain.chains import create_retrieval_chain
        from langchain.chains.combine_documents import create_stuff_documents_chain
    except ImportError:
        from langchain.chains.retrieval import create_retrieval_chain
    from langchain_core.prompts import ChatPromptTemplate
    
except ImportError as e:
    st.error(f"❌ 系統啟動失敗！原因: {e}")
    st.stop()

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ================= 4. API Key =================
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    GROQ_API_KEY = "請填入Key"

# ================= 5. 核心邏輯 (核彈重置機制) =================

if "uploader_id" not in st.session_state:
    st.session_state.uploader_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "vector_db" not in st.session_state:
    st.session_state.vector_db = None

def nuke_reset():
    """核彈級重置：直接換一個新的 ID"""
    st.session_state.messages = []
    st.session_state.vector_db = None
    st.session_state.uploader_id = str(uuid.uuid4()) 

with st.sidebar:
    st.header("🗂️ 資料上傳")
    
    uploaded_files = st.file_uploader(
        "上傳文件 (PDF / Word)", 
        type=["pdf", "docx"], 
        accept_multiple_files=True,
        key=st.session_state.uploader_id 
    )
    
    if uploaded_files and st.session_state.vector_db is None:
        with st.spinner("🧠 AI 正在進行深度分析..."):
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
                    # 強制指定 CPU，修復 Meta Tensor 錯誤
                    embeddings = HuggingFaceEmbeddings(
                        model_name="sentence-transformers/all-MiniLM-L6-v2",
                        model_kwargs={'device': 'cpu'}
                    )
                    vector_db = Chroma.from_documents(documents=all_splits, embedding=embeddings)
                    st.session_state.vector_db = vector_db
                    st.toast(f"✅ 深度處理完成！", icon="🧠")
                else:
                    st.warning("⚠️ 檔案內容為空")
            except Exception as e:
                st.error(f"❌ 錯誤: {e}")

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
                
                qa_prompt = ChatPromptTemplate.from_template("""
                你是一個高階學術研究員。請根據以下【上下文】回答問題。
                1. 若無相關資訊，請誠實回答「文件中未提及」。
                2. 請用台灣繁體中文回答。
                【上下文】:{context}
                【問題】:{input}
                """)

                retriever = st.session_state.vector_db.as_retriever(search_kwargs={"k": k_value})
                document_chain = create_stuff_documents_chain(llm, qa_prompt)
                retrieval_chain = create_retrieval_chain(retriever, document_chain)
                
                response = retrieval_chain.invoke({"input": prompt})
                answer = response['answer']
                
                message_placeholder.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                
                # 🌟 優化點：使用 Tabs 分頁顯示參考來源
                sources = response['context']
                if sources:
                    with st.expander("📚 檢視參考來源細節 (Reference Context)"):
                        # 建立 Tabs
                        tabs = st.tabs([f"來源 {i+1}" for i in range(len(sources))])
                        
                        for i, tab in enumerate(tabs):
                            with tab:
                                doc = sources[i]
                                source_name = doc.metadata.get("source_filename", "未知文件")
                                page_num = doc.metadata.get("page", 0) + 1
                                
                                # 使用 Markdown 排版
                                st.markdown(f"**📄 文件名稱：** `{source_name}`")
                                st.markdown(f"**📌 所在頁數：** `第 {page_num} 頁`")
                                st.markdown("---")
                                # 使用 info 框框顯示內容，質感更好
                                st.info(doc.page_content)
                
            except Exception as e:
                st.error(f"❌ 錯誤: {e}")
    else:
        with st.chat_message("assistant"):
            st.warning("⚠️ 請先上傳文件，我才能回答問題喔！(若已重置，請重新上傳)")