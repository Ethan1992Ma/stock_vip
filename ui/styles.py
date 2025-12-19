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
    :root {{ --primary-color: #ff4b4b; --background-color: #f8f9fa; --secondary-background-color: #ffffff; --text-color: #000000; --font: sans-serif; }}
    .stApp {{ background-color: #f8f9fa; }}
    h1, h2, h3, h4, h5, h6, p, div, label, li {{ color: #000000 !important; }}
    .stTextInput > label, .stNumberInput > label, .stRadio > label {{ color: #000000 !important; }}
    
    /* VIP 顏色類別 */
    .txt-up-vip {{ color: {COLOR_UP} !important; font-weight: bold; }}
    .txt-down-vip {{ color: {COLOR_DOWN} !important; font-weight: bold; }}
    .txt-gray-vip {{ color: {COLOR_NEUTRAL} !important; }}
    
    /* 元件樣式 */
    .metric-card {{ background-color: #ffffff; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 10px; border: 1px solid #f0f0f0; position: relative; }}
    .metric-title {{ color: #6c757d !important; font-size: 0.9rem; font-weight: 700; margin-bottom: 5px; }}
    .metric-value {{ font-size: 1.8rem; font-weight: 800; color: #212529 !important; }}
    .metric-sub {{ font-size: 0.9rem; margin-top: 5px; }}
    .ext-price-box {{ background-color: #f1f3f5; padding: 4px 8px; border-radius: 6px; font-size: 0.85rem; font-weight: 600; color: #666 !important; margin-top: 8px; display: inline-block; }}
    .ext-label {{ font-size: 0.75rem; color: #999 !important; margin-right: 5px; }}
    .spark-scale {{ position: absolute; right: 15px; top: 55%; transform: translateY(-50%); text-align: right; font-size: 0.7rem; line-height: 1.4; font-weight: 600; }}
    
    /* AI 卡片 */
    .ai-summary-card {{ background-color: #e3f2fd; padding: 20px; border-radius: 15px; border-left: 5px solid #2196f3; margin-top: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; }}
    .ai-title {{ font-weight: bold; font-size: 1.2rem; color: #0d47a1 !important; margin-bottom: 10px; display: flex; align-items: center; }}
    .ai-content {{ font-size: 1rem; color: #333 !important; line-height: 1.6; }}

    /* 均線盒子 */
    .ma-container {{ display: flex; flex-wrap: wrap; gap: 10px; background-color: #ffffff; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #f0f0f0; margin-bottom: 20px; }}
    .ma-box {{ flex: 1 1 100px; text-align: center; padding: 10px; background-color: #f8f9fa; border-radius: 10px; border: 1px solid #dee2e6; }}
    .ma-label {{ font-size: 0.8rem; font-weight: bold; color: #666 !important; margin-bottom: 5px; }}
    .ma-val {{ font-size: 1.1rem; font-weight: 800; }}
    
    .status-badge {{ padding: 4px 8px; border-radius: 6px; font-size: 0.85rem; font-weight: bold; color: white !important; display: inline-block; margin-top: 8px; }}
    .bg-up {{ background-color: {COLOR_UP}; }}
    .bg-down {{ background-color: {COLOR_DOWN}; }}
    .bg-gray {{ background-color: {COLOR_NEUTRAL}; }}
    .bg-blue {{ background-color: #0d6efd; }}
    
    .chart-title {{ font-size: 1.1rem; font-weight: 700; color: #000000 !important; margin-top: 10px; margin-bottom: 0px; padding-left: 5px; }}
    .js-plotly-plot .plotly .modebar {{ display: none !important; }}
    
    /* 計算機樣式 */
    .calc-box {{ background-color: #ffffff; padding: 15px; border-radius: 12px; border: 1px solid #eee; margin-bottom: 15px; }}
    .calc-header {{ font-size: 1rem; font-weight: bold; color: #444 !important; margin-bottom: 10px; border-left: 4px solid {COLOR_UP}; padding-left: 8px; }}
    .calc-result {{ background-color: #f8f9fa; padding: 10px; border-radius: 8px; text-align: center; margin-top: 10px; }}
    .calc-res-title {{ font-size: 0.8rem; color: #888 !important; }}
    .calc-res-val {{ font-size: 1.4rem; font-weight: bold; }}
    .fee-badge {{ background-color: #fff3cd; color: #856404 !important; padding: 5px 10px; border-radius: 5px; font-size: 0.8rem; border: 1px solid #ffeeba; margin-bottom: 15px; display: flex; align-items: center; gap: 5px; }}
    div[role="radiogroup"] {{ background-color: transparent; border: none; }}
    </style>
    """, unsafe_allow_html=True)