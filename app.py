import streamlit as st
import os
import tempfile
import sys

# ================= 雲端資料庫修正 (一定要放在最上面) =================
# 這是為了修復 Streamlit Cloud 上 ChromaDB 會遇到的 SQLite 版本問題
# 如果沒有這段，上線後會報 "sqlite3 version too old" 的錯誤
try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass
# ===============================================================

# 匯入 LangChain 相關套件
from langchain_groq import ChatGroq
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

# 消除 Tokenizers 的平行運算警告
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ================= 設定區：API Key 管理 =================
# 優先嘗試從 Streamlit Secrets 讀取 (雲端模式)
# 如果讀不到 (例如在本機跑)，則使用下方的預設 Key (但建議上傳 GitHub 前把下方真實 Key 刪掉)
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    # ⚠️ 注意：上傳 GitHub 時，建議將引號內的真實 Key 刪除，改為提示文字
    GROQ_API_KEY = "請填入Key"
# ====================================================

# 1. 設定網頁標題、圖示與版面
st.set_page_config(
    page_title="AI 知識庫助手 (Llama 3.3)", 
    page_icon="📚",
    layout="wide"
)

st.title("📚 專屬 PDF 知識問答助手")
st.caption("🚀 Powered by Groq Llama 3 & LangChain | 支援參數調校 (Fine-tuning)")

# 2. 初始化 session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "vector_db" not in st.session_state:
    st.session_state.vector_db = None

# ================= 側邊欄：功能與參數區 =================
with st.sidebar:
    st.header("📁 1. 資料上傳")
    
    # 支援多檔案上傳
    uploaded_files = st.file_uploader(
        "請上傳 PDF 文件", 
        type="pdf", 
        accept_multiple_files=True
    )
    
    # 處理上傳邏輯
    if uploaded_files and st.session_state.vector_db is None:
        with st.spinner("☁️ 正在雲端分析 PDF..."):
            try:
                all_splits = []
                for uploaded_file in uploaded_files:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        tmp_path = tmp_file.name

                    loader = PyPDFLoader(tmp_path)
                    docs = loader.load()
                    
                    for doc in docs:
                        doc.metadata["source_filename"] = uploaded_file.name
                    
                    text_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=1000, 
                        chunk_overlap=100
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
                    st.warning("⚠️ 讀取到的文件內容為空。")

            except Exception as e:
                st.error(f"❌ 發生錯誤: {e}")

    # 🌟 新增功能：模型參數調整區
    st.divider()
    st.header("⚙️ 2. 進階參數設定")
    
    # 參數 1: Temperature
    temperature = st.slider(
        "模型創意度 (Temperature)", 
        min_value=0.0, 
        max_value=1.0, 
        value=0.1, 
        step=0.1,
        help="數值越低 (0.1)，回答越嚴謹、直接引用原文；數值越高 (0.9)，回答越有創意但可能產生幻覺。"
    )
    
    # 參數 2: Top-K
    k_value = st.slider(
        "檢索段落數 (Top-K)", 
        min_value=2, 
        max_value=20, 
        value=4, 
        step=1,
        help="決定 AI 一次參考多少個最相關的段落。設為 4 代表 AI 會閱讀 4 個最相關的片段來回答你。"
    )

    # 重置按鈕
    st.divider()
    if st.button("🗑️ 清除對話紀錄"):
        st.session_state.messages = []
        st.rerun()

    if st.button("🔄 重置所有文件"):
        st.session_state.messages = []
        st.session_state.vector_db = None
        st.rerun()

# ================= 主畫面：聊天區 =================

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("請輸入關於這份文件的問題..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    if st.session_state.vector_db is not None:
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            message_placeholder.markdown("🤖 AI 正在雲端思考中...")
            
            try:
                # 🌟 使用 secrets 或 fallback key
                llm = ChatGroq(
                    groq_api_key=GROQ_API_KEY, 
                    model_name="llama-3.3-70b-versatile",
                    temperature=temperature 
                )
                
                qa_prompt = ChatPromptTemplate.from_template("""
                你是一個專業的學術助理。請根據下方的【上下文】內容來回答使用者的問題。
                如果答案不在上下文中，請誠實說不知道，不要編造答案。
                
                【上下文】:
                {context}
                
                【問題】:
                {input}
                
                請務必使用「台灣繁體中文」回答，並保持語氣專業、條理分明：
                """)

                # 🌟 使用者調整的 k_value 會在這裡生效
                retriever = st.session_state.vector_db.as_retriever(search_kwargs={"k": k_value})
                
                document_chain = create_stuff_documents_chain(llm, qa_prompt)
                retrieval_chain = create_retrieval_chain(retriever, document_chain)
                
                response = retrieval_chain.invoke({"input": prompt})
                answer = response['answer']
                context_docs = response['context']
                
                message_placeholder.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                
                with st.expander(f"🔍 查看參考來源 (共參考 {len(context_docs)} 個片段)"):
                    for i, doc in enumerate(context_docs):
                        source_name = doc.metadata.get("source_filename", "未知文件")
                        page_num = doc.metadata.get("page", 0) + 1
                        
                        st.markdown(f"**📄 來源 {i+1}: {source_name} (第 {page_num} 頁)**")
                        st.text(doc.page_content)
                        st.divider()
                
            except Exception as e:
                message_placeholder.markdown(f"❌ 發生錯誤: {e}")
                st.error("請檢查 API Key 是否正確。")
    else:
        with st.chat_message("assistant"):
            st.warning("⚠️ 請先在左側上傳 PDF 檔案！")