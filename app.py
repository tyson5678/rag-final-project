import streamlit as st
import os
import sys
import tempfile

# ================= 1. 雲端資料庫修正 (保持) =================
try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

# ================= 2. 頁面質感設定 =================
st.set_page_config(
    page_title="AI 知識庫助手", 
    page_icon="📑", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 標題設計：簡約有力
st.title("📑 專屬文件問答助手")
st.markdown("##### 支援 PDF 與 Word · 智慧檢索 · 精準回答")

# ================= 3. 安全載入套件 =================
try:
    import langchain
    from langchain_groq import ChatGroq
    from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_chroma import Chroma
    # 嘗試匯入 Chain
    try:
        from langchain.chains import create_retrieval_chain
        from langchain.chains.combine_documents import create_stuff_documents_chain
    except ImportError:
        from langchain.chains.retrieval import create_retrieval_chain
    from langchain_core.prompts import ChatPromptTemplate
    
except ImportError as e:
    st.error(f"❌ 系統啟動失敗！原因: {e}")
    st.stop()

# 消除警告
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ================= 4. API Key =================
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    GROQ_API_KEY = "請填入Key"

# ================= 5. 核心邏輯 =================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "vector_db" not in st.session_state:
    st.session_state.vector_db = None

with st.sidebar:
    st.header("🗂️ 資料上傳")
    
    # 簡約的上傳區，但支援兩種格式
    uploaded_files = st.file_uploader(
        "上傳文件 (PDF / Word)", 
        type=["pdf", "docx"], 
        accept_multiple_files=True
    )
    
    if uploaded_files and st.session_state.vector_db is None:
        with st.spinner("✨ AI 正在分析文件中..."):
            try:
                all_splits = []
                for uploaded_file in uploaded_files:
                    file_name = uploaded_file.name
                    file_ext = os.path.splitext(file_name)[1].lower()
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        tmp_path = tmp_file.name

                    # 智慧判斷讀取器
                    if file_ext == ".pdf":
                        loader = PyPDFLoader(tmp_path)
                    elif file_ext == ".docx":
                        loader = Docx2txtLoader(tmp_path)
                    else:
                        continue
                        
                    docs = loader.load()
                    for doc in docs:
                        doc.metadata["source_filename"] = file_name
                    
                    # 使用固定的最佳參數 (Chunk=500)，讓介面更乾淨
                    text_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=500, 
                        chunk_overlap=50,
                        separators=["\n\n", "\n", "。", "！", "？", " ", ""]
                    )
                    splits = text_splitter.split_documents(docs)
                    all_splits.extend(splits)
                    os.remove(tmp_path)

                if all_splits:
                    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
                    vector_db = Chroma.from_documents(documents=all_splits, embedding=embeddings)
                    st.session_state.vector_db = vector_db
                    st.toast(f"✅ 已處理 {len(uploaded_files)} 份文件", icon="🎉")
                else:
                    st.warning("⚠️ 檔案內容為空")
            except Exception as e:
                st.error(f"❌ 錯誤: {e}")

    st.divider()
    st.header("⚙️ 參數設定")
    
    # 只保留這兩個最重要的滑桿
    temperature = st.slider("模型創意度", 0.0, 1.0, 0.1, 0.1)
    k_value = st.slider("參考段落數", 2, 8, 4)

    st.markdown("") # 加一點留白
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ 清空對話", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
    with col2:
        if st.button("🔄 重置文件", use_container_width=True):
            st.session_state.messages = []
            st.session_state.vector_db = None
            st.rerun()

# ================= 聊天介面 =================

# 顯示歡迎訊息 (如果沒訊息時)
if not st.session_state.messages:
    st.info("👋 嗨！請在左側上傳文件，然後問我任何問題。")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("請輸入問題..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    if st.session_state.vector_db:
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            # message_placeholder.markdown("Thinking...") # 讓畫面更乾淨，不顯示 Thinking 文字
            
            try:
                llm = ChatGroq(groq_api_key=GROQ_API_KEY, model_name="llama-3.3-70b-versatile", temperature=temperature)
                
                # 提示詞優化：更簡潔專業
                qa_prompt = ChatPromptTemplate.from_template("""
                你是一個專業助理。請根據以下【上下文】回答問題。
                1. 答案必須有憑有據。
                2. 若無相關資訊，請誠實回答「文件中未提及」。
                3. 請用台灣繁體中文回答。
                
                【上下文】:
                {context}
                
                【問題】:
                {input}
                """)

                retriever = st.session_state.vector_db.as_retriever(search_kwargs={"k": k_value})
                document_chain = create_stuff_documents_chain(llm, qa_prompt)
                retrieval_chain = create_retrieval_chain(retriever, document_chain)
                
                response = retrieval_chain.invoke({"input": prompt})
                answer = response['answer']
                
                message_placeholder.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                
                # 引用來源改成簡潔的灰色小字
                with st.expander("參考來源 (Source)"):
                    for i, doc in enumerate(response['context']):
                        st.caption(f"📄 **{doc.metadata.get('source_filename')}** (Page {doc.metadata.get('page',0)+1})")
                        st.text(doc.page_content[:100] + "...")
                        st.divider()

            except Exception as e:
                st.error(f"❌ 錯誤: {e}")
                if "401" in str(e):
                    st.warning("API Key 異常，請檢查 Secrets。")
    else:
        st.toast("請先上傳文件喔！", icon="⚠️")