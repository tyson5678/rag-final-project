import streamlit as st
import os
import tempfile
import sys
import logging

# ================= 雲端資料庫修正 =================
try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass
# ===============================================

# 匯入 LangChain 相關套件
try:
    from langchain_groq import ChatGroq
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_chroma import Chroma
    from langchain.chains import create_retrieval_chain
    from langchain.chains.combine_documents import create_stuff_documents_chain
    from langchain_core.prompts import ChatPromptTemplate
    
    # 🌟 新增：多重查詢檢索器 (讓 AI 幫你多問幾次)
    from langchain.retrievers.multi_query import MultiQueryRetriever
    
except ImportError as e:
    st.error(f"❌ 系統啟動失敗！詳細錯誤: {e}")
    st.stop()

# 消除警告
os.environ["TOKENIZERS_PARALLELISM"] = "false"
# 設定 Log 避免 MultiQuery 輸出太多雜訊
logging.getLogger("langchain.retrievers.multi_query").setLevel(logging.INFO)

# ================= API Key 設定 =================
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except:
    GROQ_API_KEY = "請填入你的API_KEY"

# ================= 頁面設定 =================
st.set_page_config(page_title="AI 精準知識庫", page_icon="🎯", layout="wide")
st.title("🎯 AI 精準 PDF 問答助手")
st.caption("🚀 升級版：支援 Multi-Query 多重檢索與精細切分")

# 初始化 Session
if "messages" not in st.session_state:
    st.session_state.messages = []
if "vector_db" not in st.session_state:
    st.session_state.vector_db = None

# ================= 側邊欄 =================
with st.sidebar:
    st.header("📁 資料處理設定")
    
    uploaded_files = st.file_uploader("上傳 PDF", type="pdf", accept_multiple_files=True)
    
    # 🌟 優化點 1：讓使用者決定切分大小 (越小越精準)
    chunk_size = st.slider("切分大小 (Chunk Size)", 200, 1000, 400, 50, help="數值越小，切分越細，對細節問答越精準；數值越大，對摘要型問答越好。")
    
    if uploaded_files and st.session_state.vector_db is None:
        with st.spinner("☁️ 正在進行精細化分析..."):
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
                    
                    # 🌟 使用更細的切分設定
                    text_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=chunk_size,  # 使用滑桿的值
                        chunk_overlap=100,      # 重疊部分保持上下文
                        separators=["\n\n", "\n", "。", "！", "？", " ", ""] # 針對中文優化切割符
                    )
                    splits = text_splitter.split_documents(docs)
                    all_splits.extend(splits)
                    os.remove(tmp_path)

                if all_splits:
                    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
                    vector_db = Chroma.from_documents(documents=all_splits, embedding=embeddings)
                    st.session_state.vector_db = vector_db
                    st.success(f"✅ 精細處理完成！共切分成 {len(all_splits)} 個片段")
            except Exception as e:
                st.error(f"❌ 錯誤: {e}")

    st.divider()
    st.header("⚙️ 檢索增強設定")
    
    # 🌟 優化點 2：開啟 Multi-Query 開關
    use_multiquery = st.toggle("啟用多重查詢 (Multi-Query)", value=True, help="AI 會自動產生 3 個不同版本的問法去搜尋，能大幅提升準確度，但速度會稍慢。")
    
    temperature = st.slider("創意度", 0.0, 1.0, 0.1)
    k_value = st.slider("參考段落數", 2, 10, 5) # 預設提高到 5

    if st.button("🗑️ 清除對話"):
        st.session_state.messages = []
        st.rerun()
    if st.button("🔄 重置文件"):
        st.session_state.messages = []
        st.session_state.vector_db = None
        st.rerun()

# ================= 主畫面 =================

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("請輸入問題..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    if st.session_state.vector_db:
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            message_placeholder.markdown("🔍 AI 正在多角度檢索資料中...")
            
            try:
                llm = ChatGroq(groq_api_key=GROQ_API_KEY, model_name="llama-3.3-70b-versatile", temperature=temperature)
                
                # 1. 設定基礎檢索器
                base_retriever = st.session_state.vector_db.as_retriever(search_kwargs={"k": k_value})
                
                # 🌟 優化點 2 實作：根據開關決定是否使用 Multi-Query
                if use_multiquery:
                    # 這是一個會自動幫你換句話說的檢索器
                    retriever = MultiQueryRetriever.from_llm(
                        retriever=base_retriever,
                        llm=llm
                    )
                else:
                    retriever = base_retriever

                # 🌟 優化點 3：更嚴格的 Prompt (要求引用證據)
                qa_prompt = ChatPromptTemplate.from_template("""
                你是一個精準的學術助理。請嚴格根據【上下文】回答問題。
                
                【任務要求】：
                1. 答案必須來自下方提供的上下文，不要加入自己的外部知識。
                2. 如果上下文中包含具體數據、日期或人名，請精確列出。
                3. 如果答案不在上下文中，請直接回答「文件中未提及此資訊」。
                4. 請條理分明地列點回答。

                【上下文】:
                {context}
                
                【問題】:
                {input}
                
                請用繁體中文回答：
                """)

                document_chain = create_stuff_documents_chain(llm, qa_prompt)
                retrieval_chain = create_retrieval_chain(retriever, document_chain)
                
                # 執行
                response = retrieval_chain.invoke({"input": prompt})
                answer = response['answer']
                
                message_placeholder.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                
                # 顯示來源
                with st.expander("🔍 檢視精準參考來源"):
                    for i, doc in enumerate(response['context']):
                        st.markdown(f"**片段 {i+1} ({doc.metadata.get('source_filename')} p.{doc.metadata.get('page',0)+1})**")
                        st.info(doc.page_content) # 使用 info 框讓文字更明顯
            except Exception as e:
                st.error(f"❌ 錯誤: {e}")
                if "429" in str(e):
                    st.warning("⚠️ 請求過於頻繁 (Rate Limit)，請稍等幾秒再試，或是關閉 Multi-Query 功能。")
    else:
        st.warning("⚠️ 請先上傳 PDF")