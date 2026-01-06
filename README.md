ShopAI Enterprise | 智慧零售中台 🏪

2024 人工智慧期末專題

ShopAI 是一個專為零售業設計的垂直領域 AI 代理 (Vertical AI Agent)。它結合了 Text-to-SQL 技術與 RAG (檢索增強生成) 概念，讓非技術背景的店長能透過自然語言，即時查詢庫存、分析銷售數據並獲得營運建議。

✨ 核心功能 (Key Features)

📊 企業級戰情儀表板：即時監控總庫存價值 (Total Value)、SKU 數量、以及低水位警示。

💬 自然語言查詢：支援模糊搜尋、多條件篩選（例如：「找出庫存價值最高的酒類」）。

🤖 具備自癒能力的 AI Agent：內建 Self-Correction 機制，當生成的 SQL 執行失敗時，AI 會自動分析錯誤並修正語法，大幅提升穩定性。

🧠 人性化數據解讀：AI 不僅回傳表格，還會扮演「數據分析師」角色，對數據進行商業解讀與建議。

🛠️ SQL 稽核日誌 (Audit Log)：側邊欄即時顯示 AI 的推論邏輯與生成的 SQL 代碼，落實「可解釋性 AI (XAI)」。

🚀 技術架構 (Tech Stack)

Frontend: Streamlit (Python Web Framework)

LLM Inference: Groq API (Ultra-fast inference speed)

Model: Llama-3.3-70b-versatile

Database: SQLite (In-Memory Simulation with 60+ SKUs)

Data Processing: Pandas

📂 專案結構

├── streamlit_app.py # 主程式入口
├── requirements.txt # 套件依賴清單
└── README.md # 專案說明文件

💡 如何使用 (Usage)

快速提問：點擊輸入框上方的「🏆 庫存最多」或「🚨 缺貨清單」膠囊按鈕。

自定義查詢：輸入如「幫我列出所有價格超過 100 元的日用品」。

數據同步：點擊側邊欄的「🔄 同步 ERP」模擬數據更新。

匯出報表：點擊「📊 匯出報表」下載 CSV 檔案。

Created by [1102B0009 簡愷勳]
