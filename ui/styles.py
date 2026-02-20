import streamlit as st

# --- 全域配色常數 ---
COLOR_UP = "#059a81"      # 上漲 (松石綠)
COLOR_DOWN = "#f23645"    # 下跌 (法拉利紅)
COLOR_NEUTRAL = "#adb5bd" # 中性灰

# MACD 配色
MACD_BULL_GROW = "#2db09c"
MACD_BULL_SHRINK = "#a8e0d1"
MACD_BEAR_GROW = "#ff6666"
MACD_BEAR_SHRINK = "#ffcccc"

# 成交量與 VWAP
VOL_EXPLODE = "#C70039"
VOL_NORMAL = "#FF5733"
VOL_SHRINK = "#FFC300"
VOL_MA_LINE = "#000000"
COLOR_VWAP = "#FF9800"

def apply_css():
    st.markdown(f"""
    <style>
    /* =============================================
       全域變數 & 基礎重置
    ============================================= */
    :root {{
        --primary-color: #ff4b4b;
        --background-color: #f8f9fa;
        --secondary-background-color: #ffffff;
        --text-color: #000000;
        --font: sans-serif;
        --color-up: {COLOR_UP};
        --color-down: {COLOR_DOWN};
        --color-neutral: {COLOR_NEUTRAL};
        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 16px;
        --shadow-sm: 0 2px 8px rgba(0,0,0,0.06);
        --shadow-md: 0 4px 16px rgba(0,0,0,0.08);
    }}

    .stApp {{ background-color: #f8f9fa; }}
    h1, h2, h3, h4, h5, h6, p, div, label, li {{ color: #000000 !important; }}
    .stTextInput > label, .stNumberInput > label, .stRadio > label {{ color: #000000 !important; }}

    /* =============================================
       手機優先：核心響應式修正
    ============================================= */

    /* 手機：Streamlit 側邊欄觸控優化 */
    @media (max-width: 768px) {{
        /* 讓主要內容區更好地利用空間 */
        .main .block-container {{
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-top: 1rem !important;
            max-width: 100% !important;
        }}

        /* 側邊欄按鈕放大 (手指觸控) */
        section[data-testid="stSidebar"] {{
            min-width: 85vw !important;
        }}

        /* 防止橫向溢出 */
        .stApp, .main, .block-container {{
            overflow-x: hidden !important;
        }}

        /* 標題字體縮小 */
        h3 {{ font-size: 1.1rem !important; }}
        h4 {{ font-size: 1rem !important; }}
    }}

    /* =============================================
       Plotly 圖表：手機觸控修正 (核心問題)
    ============================================= */

    /* 讓 Plotly 圖表容器可以正常觸控縮放 */
    .js-plotly-plot {{
        touch-action: pan-y !important;  /* 允許縱向滾動頁面 */
    }}

    /* 手機上讓圖表高度自適應 */
    @media (max-width: 768px) {{
        /* 主K線圖高度手機版縮小 */
        .main-chart-wrapper .js-plotly-plot {{
            min-height: 420px !important;
        }}

        /* 模式列在手機上強制顯示 (否則無法縮放) */
        .js-plotly-plot .plotly .modebar {{
            display: flex !important;
            opacity: 1 !important;
            top: 2px !important;
            right: 2px !important;
        }}

        .modebar-btn svg {{
            width: 18px !important;
            height: 18px !important;
        }}

        /* 小型走勢圖 (spark) 容器高度 */
        .spark-chart-wrapper .js-plotly-plot {{
            max-height: 100px !important;
        }}
    }}

    /* 桌機版隱藏 modebar (原本設定) */
    @media (min-width: 769px) {{
        .js-plotly-plot .plotly .modebar {{
            display: none !important;
        }}
    }}

    /* =============================================
       4 欄 → 手機 2 欄 自動折疊
    ============================================= */
    @media (max-width: 768px) {{
        /* Streamlit columns 在手機自動折成兩欄 */
        [data-testid="column"] {{
            min-width: calc(50% - 0.5rem) !important;
            flex: 0 0 calc(50% - 0.5rem) !important;
        }}

        /* 計算機的兩欄在手機改全寬 */
        .calc-full-mobile [data-testid="column"] {{
            min-width: 100% !important;
            flex: 0 0 100% !important;
        }}
    }}

    /* =============================================
       指標卡片 (Metric Cards)
    ============================================= */
    .metric-card {{
        background-color: #ffffff;
        padding: 16px 14px;
        border-radius: var(--radius-lg);
        box-shadow: var(--shadow-sm);
        margin-bottom: 10px;
        border: 1px solid #f0f0f0;
        position: relative;
        transition: box-shadow 0.2s ease;
        /* 防止破版 */
        min-width: 0;
        overflow: hidden;
    }}

    .metric-card:hover {{
        box-shadow: var(--shadow-md);
    }}

    .metric-title {{
        color: #6c757d !important;
        font-size: 0.82rem;
        font-weight: 700;
        margin-bottom: 4px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}

    .metric-value {{
        font-size: 1.6rem;
        font-weight: 800;
        color: #212529 !important;
        line-height: 1.2;
        /* 防止長數字破版 */
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }}

    .metric-sub {{
        font-size: 0.85rem;
        margin-top: 4px;
    }}

    /* 手機上 metric-value 字體縮小 */
    @media (max-width: 768px) {{
        .metric-value {{ font-size: 1.25rem; }}
        .metric-title {{ font-size: 0.75rem; }}
        .metric-sub {{ font-size: 0.75rem; }}
        .metric-card {{ padding: 12px 10px; }}
    }}

    /* =============================================
       盤前/盤後價格卡片
    ============================================= */
    .ext-price-box {{
        background-color: #f1f3f5;
        padding: 3px 7px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
        color: #666 !important;
        margin-top: 6px;
        display: inline-block;
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
    }}

    .ext-label {{
        font-size: 0.7rem;
        color: #999 !important;
        margin-right: 4px;
    }}

    /* H/L 比例尺 */
    .spark-scale {{
        position: absolute;
        right: 10px;
        top: 55%;
        transform: translateY(-50%);
        text-align: right;
        font-size: 0.65rem;
        line-height: 1.4;
        font-weight: 600;
    }}

    @media (max-width: 480px) {{
        .spark-scale {{ display: none; }} /* 極小螢幕隱藏 */
    }}

    /* =============================================
       AI 摘要卡片
    ============================================= */
    .ai-summary-card {{
        background: linear-gradient(135deg, #e3f2fd 0%, #f0f4ff 100%);
        padding: 18px 20px;
        border-radius: var(--radius-lg);
        border-left: 5px solid #2196f3;
        margin: 16px 0;
        box-shadow: var(--shadow-sm);
    }}

    .ai-title {{
        font-weight: bold;
        font-size: 1.1rem;
        color: #0d47a1 !important;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 6px;
    }}

    .ai-content {{
        font-size: 0.95rem;
        color: #333 !important;
        line-height: 1.7;
    }}

    @media (max-width: 768px) {{
        .ai-content {{ font-size: 0.88rem; }}
        .ai-summary-card {{ padding: 14px 15px; }}
    }}

    /* =============================================
       均線監控盒子
    ============================================= */
    .ma-container {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        background-color: #ffffff;
        padding: 16px;
        border-radius: var(--radius-lg);
        box-shadow: var(--shadow-sm);
        border: 1px solid #f0f0f0;
        margin-bottom: 16px;
    }}

    .ma-box {{
        flex: 1 1 80px;
        text-align: center;
        padding: 10px 6px;
        background-color: #f8f9fa;
        border-radius: var(--radius-sm);
        border: 1px solid #dee2e6;
        min-width: 70px;
        /* 防破版 */
        overflow: hidden;
    }}

    .ma-label {{
        font-size: 0.72rem;
        font-weight: bold;
        color: #666 !important;
        margin-bottom: 4px;
    }}

    .ma-val {{
        font-size: 0.95rem;
        font-weight: 800;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }}

    @media (max-width: 768px) {{
        .ma-box {{ flex: 1 1 60px; min-width: 60px; padding: 8px 4px; }}
        .ma-val {{ font-size: 0.8rem; }}
        .ma-label {{ font-size: 0.65rem; }}
    }}

    /* =============================================
       狀態標籤 (Status Badges)
    ============================================= */
    .status-badge {{
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.78rem;
        font-weight: bold;
        color: white !important;
        display: inline-block;
        margin-top: 6px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 100%;
    }}

    .bg-up    {{ background-color: var(--color-up); }}
    .bg-down  {{ background-color: var(--color-down); }}
    .bg-gray  {{ background-color: var(--color-neutral); }}
    .bg-blue  {{ background-color: #0d6efd; }}

    /* VIP 顏色 */
    .txt-up-vip   {{ color: var(--color-up) !important; font-weight: bold; }}
    .txt-down-vip {{ color: var(--color-down) !important; font-weight: bold; }}
    .txt-gray-vip {{ color: var(--color-neutral) !important; }}

    /* =============================================
       圖表標題
    ============================================= */
    .chart-title {{
        font-size: 1rem;
        font-weight: 700;
        color: #000000 !important;
        margin-top: 8px;
        margin-bottom: 2px;
        padding-left: 5px;
    }}

    /* =============================================
       交易計算機
    ============================================= */
    .calc-box {{
        background-color: #ffffff;
        padding: 14px;
        border-radius: var(--radius-md);
        border: 1px solid #eee;
        margin-bottom: 14px;
    }}

    .calc-header {{
        font-size: 0.95rem;
        font-weight: bold;
        color: #444 !important;
        margin-bottom: 10px;
        border-left: 4px solid var(--color-up);
        padding-left: 8px;
    }}

    .calc-result {{
        background-color: #f8f9fa;
        padding: 12px;
        border-radius: var(--radius-sm);
        text-align: center;
        margin-top: 10px;
    }}

    .calc-res-title {{
        font-size: 0.78rem;
        color: #888 !important;
    }}

    .calc-res-val {{
        font-size: 1.3rem;
        font-weight: bold;
        /* 防長數字破版 */
        word-break: break-all;
    }}

    .fee-badge {{
        background-color: #fff3cd;
        color: #856404 !important;
        padding: 5px 10px;
        border-radius: 5px;
        font-size: 0.8rem;
        border: 1px solid #ffeeba;
        margin-bottom: 14px;
        display: flex;
        align-items: center;
        gap: 5px;
        flex-wrap: wrap;
    }}

    /* =============================================
       Streamlit 原生元件手機優化
    ============================================= */

    /* 數字輸入框在手機變大 */
    @media (max-width: 768px) {{
        input[type="number"], input[type="text"] {{
            font-size: 16px !important; /* 防止 iOS 自動縮放 */
            min-height: 44px !important;
        }}

        /* Radio 按鈕觸控區放大 */
        .stRadio label {{
            padding: 8px 0 !important;
            min-height: 44px !important;
            display: flex !important;
            align-items: center !important;
        }}

        /* Tab 標籤手機加大 */
        .stTabs [data-baseweb="tab"] {{
            font-size: 0.8rem !important;
            padding: 8px 10px !important;
        }}

        /* 按鈕觸控區放大 */
        .stButton > button {{
            min-height: 44px !important;
            width: 100% !important;
            font-size: 0.95rem !important;
        }}

        /* Slider 拖拉軌道加粗 */
        .stSlider [data-testid="stSlider"] div {{
            height: 6px !important;
        }}
        .stSlider [role="slider"] {{
            width: 24px !important;
            height: 24px !important;
        }}

        /* Expander 手機優化 */
        .streamlit-expanderHeader {{
            font-size: 0.9rem !important;
            padding: 12px !important;
        }}

        /* Metric 元件手機縮小 */
        [data-testid="stMetricValue"] {{
            font-size: 1.1rem !important;
        }}
        [data-testid="stMetricDelta"] {{
            font-size: 0.75rem !important;
        }}
    }}

    /* =============================================
       滾動條美化 (全平台)
    ============================================= */
    ::-webkit-scrollbar {{
        width: 6px;
        height: 6px;
    }}
    ::-webkit-scrollbar-track {{ background: #f1f1f1; border-radius: 3px; }}
    ::-webkit-scrollbar-thumb {{ background: #ccc; border-radius: 3px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: #aaa; }}

    /* =============================================
       Radio 按鈕群組
    ============================================= */
    div[role="radiogroup"] {{
        background-color: transparent;
        border: none;
    }}

    /* =============================================
       宏觀指標跑馬燈區塊
    ============================================= */
    @media (max-width: 768px) {{
        /* 宏觀4欄在手機改2欄 */
        [data-testid="stMetric"] {{
            min-width: 0 !important;
        }}
    }}

    /* =============================================
       防止頁面橫向滾動 (根治破圖)
    ============================================= */
    html, body {{
        overflow-x: hidden !important;
        max-width: 100vw !important;
    }}

    /* iframe 內 Plotly 圖自適應寬度 */
    iframe {{
        max-width: 100% !important;
    }}

    /* =============================================
       手機版觸控提示 (新增)
    ============================================= */
    .mobile-chart-hint {{
        display: none;
        text-align: center;
        font-size: 0.72rem;
        color: #999;
        padding: 4px 0 2px;
        margin-bottom: -4px;
    }}

    @media (max-width: 768px) {{
        .mobile-chart-hint {{ display: block; }}
    }}

    </style>
    """, unsafe_allow_html=True)