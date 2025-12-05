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

# ================= 2. 設定頁面 (放在最前面以免報錯) =================
st.set_page_config(page_title="AI 知識庫助手", page_icon="📚", layout="wide")
st.title("📚 專屬 PDF 知識問答助手")

# ================= 3. 安全載入套件 (偵錯模式) =================
try:
    import langchain
    from langchain_groq import ChatGroq
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_chroma import Chroma
    
    # 嘗試匯入 Chain，如果失敗會顯示版本號
    try:
        from langchain.chains import create_retrieval_chain
        from langchain.chains.combine_documents import create_stuff_documents_chain
    except ImportError:
        # 如果新路徑失敗，嘗試舊路徑 (Fallback)
        from langchain.chains.retrieval import create_retrieval_chain
        
    from langchain_core.prompts import ChatPromptTemplate
    
except ImportError as e:
    st.error(f"❌ 系統啟動失敗！")
    st.error(f"錯誤原因: {e}")
    st.warning(f"目前安裝的 LangChain 版本: {langchain.__version__}")
    st.stop()

# 消除 Tokenizers 的平行運算警告
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
    st.header("📁 1. 資料上傳")
    uploaded_files = st.file_uploader("請上傳 PDF 文件", type="pdf", accept_multiple_files=True)
    
    if uploaded_files and st.session_state.vector_db is None:
        with st.spinner("☁️ 正在雲端分析 PDF..."):
            try:
                import tempfile
                all_splits = []
                for uploaded_file in uploaded_files:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        tmp_path = tmp_file.name

                    loader = PyPDFLoader(tmp_path)
                    docs = loader.load()
                    for doc in docs:
                        doc.metadata["source_filename"] = uploaded_file.name
                    
                    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
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
    st.header("⚙️ 2. 參數設定")
    temperature = st.slider("創意度 (Temperature)", 0.0, 1.0, 0.1, 0.1)
    k_value = st.slider("檢索數 (Top-K)", 2, 10, 4)

    st.divider()
    if st.button("🗑️ 清除對話"):
        st.session_state.messages = []
        st.rerun()
    if st.button("🔄 重置文件"):
        st.session_state.messages = []
        st.session_state.vector_db = None
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("請輸入問題..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    if st.session_state.vector_db:
        with st.chat_message("assistant"):
            try:
                llm = ChatGroq(groq_api_key=GROQ_API_KEY, model_name="llama-3.3-70b-versatile", temperature=temperature)
                
                qa_prompt = ChatPromptTemplate.from_template("""
                你是一個專業助理。請根據【上下文】回答問題。若不知道請說不知道。
                【上下文】:{context}
                【問題】:{input}
                請用繁體中文回答：
                """)

                retriever = st.session_state.vector_db.as_retriever(search_kwargs={"k": k_value})
                document_chain = create_stuff_documents_chain(llm, qa_prompt)
                retrieval_chain = create_retrieval_chain(retriever, document_chain)
                
                response = retrieval_chain.invoke({"input": prompt})
                answer = response['answer']
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                
                with st.expander("🔍 參考來源"):
                    for i, doc in enumerate(response['context']):
                        st.markdown(f"**來源 {i+1}: {doc.metadata.get('source_filename')} (p.{doc.metadata.get('page',0)+1})**")
                        st.text(doc.page_content[:200] + "...")
                        st.divider()
            except Exception as e:
                st.error(f"❌ 生成回答錯誤: {e}")
                if "API_KEY" in str(e) or "401" in str(e):
                    st.warning("請檢查 Secrets 中的 API Key 是否正確。")
    else:
        st.warning("⚠️ 請先上傳 PDF")