import streamlit as st
import os
import sys

# ================= 1. 雲端資料庫修正 =================
try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

# ================= 2. 設定頁面 =================
st.set_page_config(page_title="AI 知識庫助手", page_icon="📚", layout="wide")
st.title("📚 專屬文件問答助手 (PDF + Word)")

# ================= 3. 安全載入套件 =================
try:
    import langchain
    from langchain_groq import ChatGroq
    from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader # 🌟 新增 Word 讀取器
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_chroma import Chroma
    
    # 嘗試匯入 Chain
    try:
        from langchain.chains import create_retrieval_chain
        from langchain.chains.combine_documents import create_stuff_documents_chain
    except ImportError:
        from langchain.chains.retrieval import create_retrieval_chain
        
    from langchain.retrievers.multi_query import MultiQueryRetriever
    from langchain_core.prompts import ChatPromptTemplate
    
except ImportError as e:
    st.error(f"❌ 系統啟動失敗！錯誤原因: {e}")
    st.stop()

# 消除警告
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ================= 4. API Key 設定 =================
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    GROQ_API_KEY = "請填入Key"

# ================= 5. 主程式邏輯 =================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "vector_db" not in st.session_state:
    st.session_state.vector_db = None

with st.sidebar:
    st.header("📁 資料上傳")
    
    # 🌟 修改點 1：允許 pdf 和 docx 兩種類型
    uploaded_files = st.file_uploader(
        "請上傳文件 (支援 PDF 與 Word)", 
        type=["pdf", "docx"], 
        accept_multiple_files=True
    )
    
    # 🌟 修改點 2：加入切分大小滑桿
    chunk_size = st.slider("切分大小 (Chunk Size)", 200, 1000, 400, 50)
    
    if uploaded_files and st.session_state.vector_db is None:
        with st.spinner("☁️ 正在分析文件 (PDF/Word)..."):
            try:
                import tempfile
                all_splits = []
                for uploaded_file in uploaded_files:
                    # 判斷副檔名
                    file_name = uploaded_file.name
                    file_extension = os.path.splitext(file_name)[1].lower()
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        tmp_path = tmp_file.name

                    # 🌟 修改點 3：智慧判斷使用哪種讀取器
                    if file_extension == ".pdf":
                        loader = PyPDFLoader(tmp_path)
                    elif file_extension == ".docx":
                        loader = Docx2txtLoader(tmp_path)
                    else:
                        continue # 跳過不支援的格式
                        
                    docs = loader.load()
                    
                    for doc in docs:
                        doc.metadata["source_filename"] = file_name
                    
                    text_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=chunk_size, 
                        chunk_overlap=100,
                        separators=["\n\n", "\n", "。", "！", "？", " ", ""]
                    )
                    splits = text_splitter.split_documents(docs)
                    all_splits.extend(splits)
                    os.remove(tmp_path)

                if all_splits:
                    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
                    vector_db = Chroma.from_documents(documents=all_splits, embedding=embeddings)
                    st.session_state.vector_db = vector_db
                    st.success(f"✅ 成功處理 {len(uploaded_files)} 份文件！")
                else:
                    st.warning("⚠️ 檔案內容為空")
            except Exception as e:
                st.error(f"❌ 資料處理錯誤: {e}")

    st.divider()
    st.header("⚙️ 進階設定")
    use_multiquery = st.toggle("啟用多重查詢 (Multi-Query)", value=True)
    temperature = st.slider("創意度 (Temperature)", 0.0, 1.0, 0.1, 0.1)
    k_value = st.slider("檢索數 (Top-K)", 2, 10, 5)

    st.divider()
    if st.button("🗑️ 清除對話"):
        st.session_state.messages = []
        st.rerun()
    if st.button("🔄 重置文件"):
        st.session_state.messages = []
        st.session_state.vector_db = None
        st.rerun()

# ================= 聊天區 =================

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("請輸入問題..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    if st.session_state.vector_db:
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            message_placeholder.markdown("🔍 AI 正在檢索中...")
            try:
                llm = ChatGroq(groq_api_key=GROQ_API_KEY, model_name="llama-3.3-70b-versatile", temperature=temperature)
                
                base_retriever = st.session_state.vector_db.as_retriever(search_kwargs={"k": k_value})
                
                if use_multiquery:
                    retriever = MultiQueryRetriever.from_llm(retriever=base_retriever, llm=llm)
                else:
                    retriever = base_retriever
                
                qa_prompt = ChatPromptTemplate.from_template("""
                你是一個精準的學術助理。請嚴格根據【上下文】回答問題。
                【任務要求】：
                1. 答案必須來自下方提供的上下文，不要加入自己的外部知識。
                2. 如果上下文中包含具體數據、日期或人名，請精確列出。
                3. 如果答案不在上下文中，請直接回答「文件中未提及此資訊」。
                
                【上下文】:{context}
                【問題】:{input}
                請用繁體中文回答：
                """)

                document_chain = create_stuff_documents_chain(llm, qa_prompt)
                retrieval_chain = create_retrieval_chain(retriever, document_chain)
                
                response = retrieval_chain.invoke({"input": prompt})
                answer = response['answer']
                
                message_placeholder.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                
                with st.expander("🔍 檢視參考來源"):
                    for i, doc in enumerate(response['context']):
                        st.markdown(f"**來源 {i+1}: {doc.metadata.get('source_filename')}**")
                        st.info(doc.page_content)
            except Exception as e:
                st.error(f"❌ 錯誤: {e}")
                if "429" in str(e):
                    st.warning("⚠️ 請求過於頻繁，請稍等。")
    else:
        st.warning("⚠️ 請先上傳 PDF 或 Word 檔案")