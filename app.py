import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, time
import pytz
import google.generativeai as genai
import ta
import yfinance as yf 
from plotly.subplots import make_subplots
import plotly.express as px

# 匯入模組
from ui.styles import apply_css, COLOR_UP, COLOR_DOWN, COLOR_NEUTRAL, VOL_EXPLODE, VOL_NORMAL, VOL_SHRINK, VOL_MA_LINE, COLOR_VWAP, MACD_BULL_GROW, MACD_BULL_SHRINK, MACD_BEAR_GROW, MACD_BEAR_SHRINK
from ui.cards import get_price_card_html, get_timeline_html, get_metric_card_html
from data.fetch import fetch_stock_data_now, fetch_exchange_rate_now
from logic.indicators import calculate_ma, get_strategy_values, calculate_bollinger, calculate_vwap
from logic.strategies import generate_ai_summary
from logic.fees import get_fees

# --- 1. 網頁設定 & AI 初始化 ---
st.set_page_config(page_title="AI 智能操盤戰情室 (VIP 終極版)", layout="wide", initial_sidebar_state="collapsed")
apply_css()

# ─────────────────────────────────────────────────────────────
#  [手機優化] 統一的 Plotly 設定輔助函式
# ─────────────────────────────────────────────────────────────

def get_mobile_chart_config(allow_zoom: bool = True) -> dict:
    """
    統一管理 Plotly 圖表在手機/桌機的互動設定。

    allow_zoom=True  → 主K線圖：允許縮放 & 拖拉，顯示工具列
    allow_zoom=False → 走勢迷你圖：靜態不可互動
    """
    if allow_zoom:
        return {
            'scrollZoom': True,           # ✅ 手機雙指縮放 / 桌機滾輪縮放
            'displayModeBar': True,        # ✅ 顯示工具列 (縮放/復位按鈕)
            'displaylogo': False,
            'modeBarButtonsToRemove': [    # 移除不常用按鈕，精簡工具列
                'lasso2d', 'select2d', 'autoScale2d', 'hoverClosestCartesian',
                'hoverCompareCartesian', 'toggleSpikelines'
            ],
            'toImageButtonOptions': {
                'format': 'png', 'filename': 'stock_chart', 'scale': 2
            },
            'responsive': True,            # ✅ 容器寬度自適應 (防破版關鍵)
        }
    else:
        return {
            'displayModeBar': False,
            'staticPlot': True,            # 走勢圖靜態，不攔截觸控事件
            'responsive': True,
        }


def get_responsive_height(desktop: int, mobile: int = None) -> int:
    """根據設備回傳適合的圖表高度 (Streamlit 無法動態偵測，用保守值)"""
    # Streamlit 無法在 Python 端偵測螢幕寬度，
    # 使用保守值確保手機不會過高。
    # 若需要真正響應式，可透過 JS 注入 (進階用法)。
    if mobile is None:
        mobile = max(300, desktop // 2)
    # 回傳桌機高度，CSS 會在手機端限制最大高度
    return desktop


@st.cache_data(ttl=300)
def get_macro_data():
    """抓取宏觀數據 (VIX, 黃金, 原油, BTC)"""
    tickers = {"VIX": "^VIX", "Gold": "GC=F", "Oil": "CL=F", "BTC": "BTC-USD"}
    try:
        raw = yf.download(list(tickers.values()), period="5d", progress=False)
        # [修正] 安全取得 Close 資料 (處理 MultiIndex)
        if isinstance(raw.columns, pd.MultiIndex):
            data = raw['Close']
        else:
            data = raw
        result = {}
        for name, ticker in tickers.items():
            try:
                col = data[ticker]
                col_clean = col.dropna()
                if len(col_clean) >= 2:
                    curr, prev = col_clean.iloc[-1], col_clean.iloc[-2]
                    chg = ((curr - prev) / prev) * 100
                    result[name] = (float(curr), float(chg))
                else:
                    result[name] = (0.0, 0.0)
            except:
                result[name] = (0.0, 0.0)
        return result
    except:
        return {}


# ─────────────────────────────────────────────────────────────
#  [全面修正] 互動式主圖表 — 手機友善版
# ─────────────────────────────────────────────────────────────
def plot_interactive_chart(df, ticker):
    """
    繪製互動式圖表 (K線 + 量 + MACD + RSI)
    手機優化：
      - 工具列強制顯示 (縮放 / 復位)
      - scrollZoom=True 支援雙指縮放
      - 移除週末空白
      - 圖表高度手機版自適應
    """
    df = df.copy()

    # --- 計算指標 (以 Pandas 手算，最穩) ---
    exp12 = df['Close'].ewm(span=12, adjust=False).mean()
    exp26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD']        = exp12 - exp26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist']   = df['MACD'] - df['MACD_Signal']

    if 'RSI' not in df.columns:
        delta = df['Close'].diff()
        gain  = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss  = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = (100 - (100 / (1 + rs))).fillna(50)

    # --- 子圖配置 ---
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.50, 0.16, 0.17, 0.17],
        subplot_titles=(f'{ticker} K線', '成交量', 'MACD', 'RSI')
    )

    # Row 1：K線
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
        name='K線',
        increasing_line_color='#00C853',
        decreasing_line_color='#FF3D00',
        # 手機上蠟燭較窄，調粗邊線
        increasing=dict(line=dict(width=1)),
        decreasing=dict(line=dict(width=1)),
    ), row=1, col=1)

    # Row 1：均線
    ma_colors = {'MA_5': '#D500F9', 'MA_10': '#2962FF', 'MA_20': '#FF6D00', 'MA_60': '#00C853'}
    for ma_name, color in ma_colors.items():
        if ma_name in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[ma_name],
                line=dict(color=color, width=1.2),
                name=ma_name, opacity=0.85
            ), row=1, col=1)

    # Row 2：成交量
    vol_colors = ['#00C853' if c >= o else '#FF3D00'
                  for c, o in zip(df['Close'], df['Open'])]
    fig.add_trace(go.Bar(
        x=df.index, y=df['Volume'],
        marker_color=vol_colors,
        name='Volume', showlegend=False
    ), row=2, col=1)

    # Row 3：MACD
    hist_colors = ['#00C853' if h >= 0 else '#FF3D00' for h in df['MACD_Hist']]
    fig.add_trace(go.Bar(
        x=df.index, y=df['MACD_Hist'],
        marker_color=hist_colors, name='MACD Hist', showlegend=False
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['MACD'],
        line=dict(color='#2962FF', width=1.2), name='MACD'
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['MACD_Signal'],
        line=dict(color='#FF6D00', width=1.2), name='Signal'
    ), row=3, col=1)

    # Row 4：RSI
    fig.add_trace(go.Scatter(
        x=df.index, y=df['RSI'],
        line=dict(color='#9C27B0', width=1.5), name='RSI'
    ), row=4, col=1)
    fig.add_hrect(y0=30, y1=70, row=4, col=1, fillcolor='gray', opacity=0.08, line_width=0)
    fig.add_hline(y=70, row=4, col=1, line_dash='dot', line_color='red',   line_width=1)
    fig.add_hline(y=30, row=4, col=1, line_dash='dot', line_color='green', line_width=1)

    # --- 版面設定 ---
    fig.update_layout(
        height=780,                     # 桌機高度；手機 CSS 限制
        xaxis_rangeslider_visible=False,
        template='plotly_white',
        margin=dict(l=5, r=5, t=28, b=8),
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom', y=1.02,
            xanchor='right',  x=1,
            font=dict(size=11),
        ),
        # [手機優化] 預設拖拉模式改為 pan，更符合手機操作習慣
        dragmode='pan',
        # [手機優化] Hover 模式：最近點
        hovermode='x unified',
    )

    # [手機優化] Y 軸刻度在小螢幕減少
    fig.update_yaxes(
        tickfont=dict(size=10),
        title_font=dict(size=10),
        nticks=5,
    )
    fig.update_xaxes(
        tickfont=dict(size=10),
        # 移除週末空白
        rangebreaks=[dict(bounds=['sat', 'mon'])],
    )

    return fig


# ─────────────────────────────────────────────────────────────
#  板塊清單 (不變)
# ─────────────────────────────────────────────────────────────
SECTOR_TICKERS = {
    "Technology": [
        "NVDA", "AAPL", "MSFT", "AMD", "INTC", "TSM", "AVGO", "QCOM", "ORCL", "ADBE",
        "CRM", "CSCO", "TXN", "IBM", "NOW", "MU", "LRCX", "AMAT", "ADI", "PANW"
    ],
    "Communication": [
        "GOOGL", "META", "NFLX", "DIS", "TMUS", "VZ", "CMCSA", "T", "CHTR", "DASH"
    ],
    "Consumer Cyclical": [
        "AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW", "BKNG", "TJX", "F",
        "GM", "LULU", "MAR", "HLT", "CMG"
    ],
    "Financial": [
        "JPM", "BAC", "V", "MA", "WFC", "MS", "GS", "BLK", "C", "AXP",
        "SPGI", "PGR", "CB", "MMC", "UBS", "SCHW"
    ],
    "Healthcare": [
        "LLY", "UNH", "JNJ", "MRK", "PFE", "ABBV", "TMO", "ABT", "DHR", "BMY",
        "AMGN", "CVS", "ELV", "GILD", "ISRG", "SYK"
    ],
    "Energy": [
        "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "KMI", "WMB"
    ],
    "Industrials": [
        "CAT", "GE", "LMT", "RTX", "BA", "HON", "UNP", "UPS", "DE", "ADP",
        "ETN", "WM", "GD", "NOC", "ITW", "EMR"
    ],
    "Consumer Defensive": [
        "WMT", "PG", "COST", "KO", "PEP", "PM", "MO", "EL", "CL", "KMB",
        "GIS", "SYY", "STZ", "TGT"
    ],
    "Utilities": [
        "NEE", "DUK", "SO", "AEP", "SRE", "D", "PEG", "PCG", "EXC", "XEL"
    ],
    "Real Estate": [
        "PLD", "AMT", "CCI", "EQIX", "PSA", "O", "SPG", "WELL", "DLR", "VICI"
    ]
}


@st.cache_data(ttl=1800)
def plot_market_map_v2(target_sector=None, use_equal_weight=False):
    """繪製板塊熱力圖 (v5：支援等權重模式)"""
    sectors_to_fetch = {target_sector: SECTOR_TICKERS[target_sector]} if target_sector in SECTOR_TICKERS else SECTOR_TICKERS
    all_tickers = [t for tickers in sectors_to_fetch.values() for t in tickers]
    data_list = []

    try:
        raw = yf.download(all_tickers, period='1d', group_by='ticker', progress=False)

        for sector, tickers in sectors_to_fetch.items():
            for t in tickers:
                try:
                    if isinstance(raw.columns, pd.MultiIndex):
                        if t not in raw.columns.get_level_values(0): continue
                        sub_df = raw[t]
                    else:
                        continue

                    close  = float(sub_df['Close'].iloc[-1])
                    open_p = float(sub_df['Open'].iloc[-1])
                    volume = float(sub_df['Volume'].iloc[-1])
                    change_pct = ((close - open_p) / open_p) * 100
                    turnover   = close * volume if volume > 0 else 1000

                    data_list.append({
                        'Ticker': t, 'Sector': sector,
                        'Change': change_pct, 'Price': close,
                        'Turnover': turnover, 'EqualSize': 1,
                        'DisplayLabel': f'{t}<br>{change_pct:+.2f}%'
                    })
                except:
                    continue

        if not data_list: return None

        df_tree = pd.DataFrame(data_list)
        title      = f'🔥 {target_sector} 板塊熱力圖' if target_sector else '🔥 全市場熱力圖 (S&P 100)'
        value_col  = 'EqualSize' if use_equal_weight else 'Turnover'

        fig = px.treemap(
            df_tree,
            path=[px.Constant(title), 'Sector', 'DisplayLabel'],
            values=value_col,
            color='Change',
            color_continuous_scale=['#d50000', '#1a1a1a', '#00c853'],
            color_continuous_midpoint=0,
            range_color=[-3, 3],
            custom_data=['Change', 'Price', 'Ticker']
        )
        fig.update_traces(
            textinfo='label',
            textfont=dict(color='white', family='Arial Black',
                          size=16 if use_equal_weight else None),
            hovertemplate='<b>%{customdata[2]}</b><br>漲跌幅: %{customdata[0]:+.2f}%<br>現價: $%{customdata[1]:.2f}'
        )
        # [手機優化] 熱力圖在手機縮小高度
        fig.update_layout(
            margin=dict(t=30, l=0, r=0, b=0),
            height=600,
            uniformtext=dict(minsize=9, mode='hide')
        )
        return fig

    except Exception as e:
        st.error(f'熱力圖繪製失敗: {e}')
        return None


# --- Gemini AI 初始化 ---
if 'GEMINI_API_KEY' in st.secrets:
    genai.configure(api_key=st.secrets['GEMINI_API_KEY'])
else:
    st.warning('⚠️ 請在 .streamlit/secrets.toml 設定 GEMINI_API_KEY 才能使用 AI 深度分析功能')


@st.cache_resource
def get_gemini_model():
    """[新增] 快取 Gemini Model，避免每次按按鈕都重新掃描"""
    if 'GEMINI_API_KEY' not in st.secrets:
        return None
    genai.configure(api_key=st.secrets['GEMINI_API_KEY'])
    # 優先用 flash 模型
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods and 'flash' in m.name:
            return genai.GenerativeModel(m.name)
    return genai.GenerativeModel('gemini-1.5-flash')


# --- 技術分析摘要 (for Gemini prompt) ---
def generate_technical_context(df):
    if len(df) < 60: return '數據不足，略過技術分析。'
    df_calc = df.copy()
    close = df_calc['Close']

    sma20_series = close.rolling(window=20).mean()
    sma60_series = close.rolling(window=60).mean()

    delta = close.diff()
    gain  = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    loss  = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss
    rsi_series = 100 - (100 / (1 + rs))

    exp12 = close.ewm(span=12, adjust=False).mean()
    exp26 = close.ewm(span=26, adjust=False).mean()
    macd_line   = exp12 - exp26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist   = macd_line - signal_line

    price  = close.iloc[-1]
    sma20  = sma20_series.iloc[-1]
    sma60  = sma60_series.iloc[-1]
    rsi    = rsi_series.iloc[-1]
    cur_hist  = macd_hist.iloc[-1]
    prev_hist = macd_hist.iloc[-2]

    report = []
    report.append(f'股價 ({price:.2f}) {"站上" if price > sma20 else "跌破"} 月線 (20MA: {sma20:.2f})，短線{"轉強" if price > sma20 else "示弱"}。')
    report.append(f'月線{"大於" if sma20 > sma60 else "小於"}季線，中長期均線呈{"多頭" if sma20 > sma60 else "空頭"}排列。')

    if rsi > 70:
        report.append(f'RSI ({rsi:.2f}) 進入超買區，需留意高檔回調風險。')
    elif rsi < 30:
        report.append(f'RSI ({rsi:.2f}) 進入超賣區，短線隨時可能反彈。')
    else:
        report.append(f'RSI ({rsi:.2f}) 處於中性區間。')

    if cur_hist > 0 and cur_hist > prev_hist:
        report.append('MACD 紅柱持續放大，多頭動能強勁。')
    elif cur_hist > 0 and cur_hist < prev_hist:
        report.append('MACD 紅柱縮短，多頭動能減弱 (背離警戒)。')
    elif cur_hist < 0 and cur_hist < prev_hist:
        report.append('MACD 綠柱放大，空頭動能增強。')
    else:
        report.append('MACD 綠柱縮短，空頭動能減弱 (可能準備黃金交叉)。')

    return ' | '.join(report)


# ─────────────────────────────────────────────────────────────
#  2. 側邊欄
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.header('⚙️ 參數設定')
    ticker_input = st.text_input('股票代號', 'TSLA', key='sidebar_ticker').upper()

    st.markdown('---')
    st.subheader('🤖 AI 分析師風格')
    ai_persona = st.selectbox('選擇分析師',
        ['Buffett (巴菲特 - 價值投資)',
         'Soros (索羅斯 - 反身性)',
         'Simons (西蒙斯 - 量化數據)',
         'General (軍工複合體 - 地緣政治)'], index=0)

    if st.button('🔄 更新報價 (Refresh)'):
        if 'stored_ticker' in st.session_state:
            del st.session_state['stored_ticker']
        st.rerun()

    st.markdown('---')
    st.subheader('🧠 策略邏輯')
    strategy_mode = st.radio('判讀模式',
        ['🤖 自動判別 (Auto)', '🛠️ 手動設定 (Manual)'],
        key='sidebar_strat_mode')
    strat_fast, strat_slow, strat_desc = 5, 20, '預設'
    if strategy_mode == '🛠️ 手動設定 (Manual)':
        strat_fast = st.number_input('策略快線 (Fast)', value=5, key='sidebar_fast')
        strat_slow = st.number_input('策略慢線 (Slow)', value=20, key='sidebar_slow')
        strat_desc = '自訂策略'


# ─────────────────────────────────────────────────────────────
#  3. 計算機 Tab (Fragment)
# ─────────────────────────────────────────────────────────────
@st.fragment
def render_calculator_tab(current_close_price, exchange_rate, quote_type):
    st.markdown('#### 🧮 交易前規劃')
    fees = get_fees(quote_type)
    BUY_FIXED_FEE, BUY_RATE_FEE   = fees['buy_fixed'],  fees['buy_rate']
    SELL_FIXED_FEE, SELL_RATE_FEE = fees['sell_fixed'], fees['sell_rate']

    st.markdown(f'<div class="fee-badge">{fees["text"]}</div>', unsafe_allow_html=True)
    st.info(f'💰 目前匯率參考：**1 USD ≈ {exchange_rate:.2f} TWD**')

    # [手機優化] 預算試算
    st.markdown('<div class="calc-header">💰 預算試算 (我有多少錢?)</div>', unsafe_allow_html=True)
    bc1, bc2 = st.columns(2)
    with bc1:
        budget_twd = st.number_input('台幣預算 (TWD)', value=100000, step=1000, key='budget_input')
    with bc2:
        if 'buy_price_input' not in st.session_state:
            st.session_state.buy_price_input = float(current_close_price)
        buy_price_input = st.number_input('預計買入價 (USD)', key='buy_price_input', step=0.1, format='%.2f')

    usd_budget = budget_twd / exchange_rate
    max_shares = (usd_budget - BUY_FIXED_FEE) / (buy_price_input * (1 + BUY_RATE_FEE)) if usd_budget > BUY_FIXED_FEE else 0
    total_buy_cost_usd = (max_shares * buy_price_input * (1 + BUY_RATE_FEE)) + BUY_FIXED_FEE
    total_buy_cost_twd = total_buy_cost_usd * exchange_rate

    if max_shares > 0:
        st.markdown(f"""
        <div class="calc-result">
          <div class="calc-res-title">可購買股數</div>
          <div class="calc-res-val" style="color:#0d6efd !important;">{max_shares:.2f} 股</div>
          <div style="font-size:0.8rem; margin-top:5px; color:#666 !important;">
            總成本: ${total_buy_cost_usd:.2f} USD (約 {total_buy_cost_twd:.0f} TWD)
          </div>
        </div>""", unsafe_allow_html=True)
    else:
        st.error('預算不足以支付手續費')

    st.markdown('---')

    # 賣出試算
    st.markdown('<div class="calc-header">⚖️ 賣出試算 (獲利預估)</div>', unsafe_allow_html=True)
    c_input1, c_input2 = st.columns(2)
    with c_input1:
        shares_held = st.number_input('持有股數', value=10.0, step=1.0, key='hold_shares_input')
    with c_input2:
        if 'cost_price_input' not in st.session_state:
            st.session_state.cost_price_input = float(current_close_price)
        cost_price = st.number_input('買入成本 (USD)', key='cost_price_input', step=0.1, format='%.2f')

    real_buy_cost_usd  = (cost_price * shares_held * (1 + BUY_RATE_FEE)) + BUY_FIXED_FEE
    breakeven_price    = (real_buy_cost_usd + SELL_FIXED_FEE) / (shares_held * (1 - SELL_RATE_FEE))
    st.caption(f'🛡️ 損益兩平價 (含手續費): **${breakeven_price:.2f}**')
    st.divider()

    calc_mode = st.radio(
        '選擇試算目標：',
        ['🎯 設定【目標獲利】反推股價', '💵 設定【賣出價格】計算獲利'],
        horizontal=True, key='calc_mode_radio'
    )

    if calc_mode == '🎯 設定【目標獲利】反推股價':
        target_profit_twd  = st.number_input('我想賺多少台幣 (TWD)?', value=3000, step=500, key='target_profit_input')
        target_sell_price  = ((target_profit_twd / exchange_rate) + real_buy_cost_usd + SELL_FIXED_FEE) / (shares_held * (1 - SELL_RATE_FEE))
        pct_need = ((target_sell_price / cost_price) - 1) * 100 if cost_price > 0 else 0
        st.markdown(f"""
        <div class="calc-result">
          <div class="calc-res-title">建議掛單賣出價</div>
          <div class="calc-res-val txt-up-vip">${target_sell_price:.2f}</div>
          <div style="font-size:0.8rem;" class="txt-up-vip">需上漲 {pct_need:.1f}%</div>
        </div>""", unsafe_allow_html=True)
    else:
        if 'target_sell_input' not in st.session_state:
            st.session_state.target_sell_input = float(cost_price) * 1.05
        target_sell_input = st.number_input('預計賣出價格 (USD)', key='target_sell_input', step=0.1, format='%.2f')
        net_profit_twd    = ((target_sell_input * shares_held * (1 - SELL_RATE_FEE)) - SELL_FIXED_FEE - real_buy_cost_usd) * exchange_rate
        res_class = 'txt-up-vip' if net_profit_twd >= 0 else 'txt-down-vip'
        res_prefix = '+' if net_profit_twd >= 0 else ''
        st.markdown(f"""
        <div class="calc-result">
          <div class="calc-res-title">預估淨獲利 (TWD)</div>
          <div class="calc-res-val {res_class}">{res_prefix}{net_profit_twd:.0f} 元</div>
          <div style="font-size:0.8rem; color:#666 !important;">
            美金損益: {res_prefix}${net_profit_twd/exchange_rate:.2f}
          </div>
        </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
#  4. 庫存管理 Tab (Fragment)
# ─────────────────────────────────────────────────────────────
@st.fragment
def render_inventory_tab(current_close_price, quote_type):
    st.markdown('#### 📦 庫存損益與加碼攤平')
    fees = get_fees(quote_type)
    BUY_FIXED_FEE, BUY_RATE_FEE   = fees['buy_fixed'],  fees['buy_rate']
    SELL_FIXED_FEE, SELL_RATE_FEE = fees['sell_fixed'], fees['sell_rate']
    st.caption(fees['text'])

    ic1, ic2 = st.columns(2)
    with ic1:
        st.caption('📍 目前持倉')
        curr_shares = st.number_input('目前股數', value=100.0, key='inv_curr_shares')
        if 'inv_curr_avg' not in st.session_state:
            st.session_state.inv_curr_avg = float(current_close_price) * 1.1
        curr_avg_price = st.number_input('平均成交價 (USD)', key='inv_curr_avg', step=0.1, format='%.2f')
    with ic2:
        st.caption('➕ 預計加碼')
        new_shares = st.number_input('加碼股數', value=50.0, key='inv_new_shares')
        if 'inv_new_price' not in st.session_state:
            st.session_state.inv_new_price = float(current_close_price)
        new_buy_price = st.number_input('加碼單價 (USD)', key='inv_new_price', step=0.1, format='%.2f')

    st.markdown('---')
    total_shares      = curr_shares + new_shares
    total_cost_real   = (curr_shares * curr_avg_price * (1 + BUY_RATE_FEE) + BUY_FIXED_FEE) + \
                        (new_shares  * new_buy_price  * (1 + BUY_RATE_FEE) + BUY_FIXED_FEE)
    new_avg_price     = (curr_shares * curr_avg_price + new_shares * new_buy_price) / total_shares if total_shares > 0 else 0
    market_val_net    = (total_shares * new_buy_price * (1 - SELL_RATE_FEE)) - SELL_FIXED_FEE
    unrealized_pl     = market_val_net - total_cost_real

    pl_class       = 'txt-up-vip'  if unrealized_pl >= 0   else 'txt-down-vip'
    avg_change_class = 'txt-up-vip' if new_avg_price < curr_avg_price else 'txt-gray-vip'

    st.markdown(f"""
    <div class="metric-card">
      <div class="metric-title">加碼後平均成交價</div>
      <div style="display:flex; justify-content:space-between; align-items:end; flex-wrap:wrap; gap:4px;">
        <div class="metric-value">${new_avg_price:.2f}</div>
        <div class="{avg_change_class}">{f"⬇ 下降 ${curr_avg_price - new_avg_price:.2f}" if new_avg_price < curr_avg_price else "變動不大"}</div>
      </div>
    </div>""", unsafe_allow_html=True)

    c_res1, c_res2 = st.columns(2)
    with c_res1:
        st.markdown(f"""
        <div class="calc-result">
          <div class="calc-res-title">加碼後總股數</div>
          <div class="calc-res-val">{total_shares:.0f} 股</div>
        </div>""", unsafe_allow_html=True)
    with c_res2:
        st.markdown(f"""
        <div class="calc-result">
          <div class="calc-res-title">預估總損益 (含費)</div>
          <div class="calc-res-val {pl_class}">${unrealized_pl:.2f}</div>
        </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
#  5. 主程式邏輯
# ─────────────────────────────────────────────────────────────
if ticker_input:
    try:
        if 'stored_ticker' not in st.session_state or st.session_state.stored_ticker != ticker_input:
            with st.spinner(f'正在抓取 {ticker_input} 數據...'):
                df, df_intra, info, quote_type = fetch_stock_data_now(ticker_input)
                exchange_rate = fetch_exchange_rate_now()
                st.session_state.update(
                    stored_ticker=ticker_input,
                    data_df=df, data_df_intra=df_intra,
                    data_info=info, data_quote_type=quote_type,
                    data_exchange_rate=exchange_rate
                )
                for k in ['buy_price_input', 'cost_price_input', 'target_sell_input', 'inv_curr_avg', 'inv_new_price']:
                    if k in st.session_state: del st.session_state[k]

        df, df_intra, info = st.session_state.data_df, st.session_state.data_df_intra, st.session_state.data_info
        quote_type, exchange_rate = st.session_state.data_quote_type, st.session_state.data_exchange_rate

        if not df.empty and len(df) > 200:
            if strategy_mode == '🤖 自動判別 (Auto)':
                strat_fast, strat_slow = (10, 20) if info.get('marketCap', 0) > 200_000_000_000 else (5, 10)
                strat_desc = '🐘 巨頭穩健' if info.get('marketCap', 0) > 200_000_000_000 else '🚀 小型飆股'

            df = calculate_ma(df)
            if 'MA_10' not in df.columns:
                df['MA_10'] = df['Close'].rolling(window=10).mean()
            df = calculate_bollinger(df)

            last  = df.iloc[-1]
            prev  = df.iloc[-2]
            current_close_price = last['Close']
            strat_fast_val, strat_slow_val = get_strategy_values(df, strat_fast, strat_slow)

            # --- 宏觀數據 ---
            macro_data = get_macro_data()
            if macro_data:
                st.markdown('#### 🌍 全球宏觀指標')
                m1, m2, m3, m4 = st.columns(4)
                vix  = macro_data.get('VIX',  (0, 0))
                gold = macro_data.get('Gold', (0, 0))
                oil  = macro_data.get('Oil',  (0, 0))
                btc  = macro_data.get('BTC',  (0, 0))
                m1.metric('VIX 恐慌指數', f'{vix[0]:.2f}',      f'{vix[1]:.2f}%',  delta_color='inverse')
                m2.metric('黃金 (Gold)',   f'${gold[0]:,.1f}',   f'{gold[1]:.2f}%')
                m3.metric('原油 (WTI)',    f'${oil[0]:.2f}',     f'{oil[1]:.2f}%')
                m4.metric('Bitcoin',       f'${btc[0]:,.0f}',    f'{btc[1]:.2f}%')
            st.divider()

            # --- 熱力圖 ---
            with st.expander('🗺️ 點擊展開：市場板塊熱力圖 (Sector Heatmap)', expanded=False):
                target_sector = info.get('sector', 'Unknown')
                sector_mapping = {
                    'Technology': 'Technology', 'Financial Services': 'Financial',
                    'Communication Services': 'Communication', 'Consumer Cyclical': 'Consumer Cyclical',
                    'Consumer Defensive': 'Consumer Defensive', 'Healthcare': 'Healthcare',
                    'Energy': 'Energy', 'Industrials': 'Industrials',
                    'Utilities': 'Utilities', 'Real Estate': 'Real Estate'
                }
                detected_sector = sector_mapping.get(target_sector, None)
                if detected_sector:
                    st.caption(f'🎯 偵測到 {ticker_input} 屬於 **{detected_sector}** 板塊，已自動聚焦。')

                col_map_ctrl, _ = st.columns([0.4, 0.6])
                with col_map_ctrl:
                    use_equal = st.checkbox('⊞ 切換為「等權重」模式', value=False)

                with st.spinner('正在掃描全市場數據...'):
                    fig_map = plot_market_map_v2(detected_sector, use_equal_weight=use_equal)
                    if fig_map:
                        # [手機優化] 熱力圖允許拖拉
                        st.plotly_chart(
                            fig_map,
                            use_container_width=True,
                            config=get_mobile_chart_config(allow_zoom=True)
                        )
                    else:
                        st.warning('無法取得熱力圖數據')

            st.markdown('---')

            tab_analysis, tab_calc, tab_inv = st.tabs(['📊 技術分析', '🧮 交易計算', '📦 庫存管理'])

            # ── 技術分析 Tab ──────────────────────────────────────
            with tab_analysis:
                if not df_intra.empty:
                    # [修正] VWAP 對分鐘線計算才有意義
                    df_intra = df_intra.copy()
                    df_intra['VWAP'] = (df_intra['Close'] * df_intra['Volume']).cumsum() / df_intra['Volume'].cumsum()

                    df_intra.index = pd.to_datetime(df_intra.index)
                    if '.TW' in ticker_input:
                        tz_str = 'Asia/Taipei'
                        open_time, close_time = time(9, 0), time(13, 30)
                    else:
                        tz_str = 'America/New_York'
                        open_time, close_time = time(9, 30), time(16, 0)
                    try:
                        df_intra_tz = df_intra.tz_convert(tz_str)
                    except:
                        df_intra_tz = df_intra

                    mask_reg_hl = (df_intra_tz.index.time >= open_time) & (df_intra_tz.index.time <= close_time)
                    df_reg_hl = df_intra_tz[mask_reg_hl]
                    day_high = df_reg_hl['High'].max() if not df_reg_hl.empty else df_intra_tz['High'].max()
                    day_low  = df_reg_hl['Low'].min()  if not df_reg_hl.empty else df_intra_tz['Low'].min()

                previous_close = info.get('previousClose', df.iloc[-2]['Close'])
                regular_price  = info.get('currentPrice', info.get('regularMarketPrice', last['Close']))

                is_extended, ext_price, ext_label = False, 0, ''
                live_price = df_intra['Close'].iloc[-1] if not df_intra.empty else 0
                if info.get('preMarketPrice'):
                    ext_price, is_extended, ext_label = info['preMarketPrice'], True, '盤前'
                elif info.get('postMarketPrice'):
                    ext_price, is_extended, ext_label = info['postMarketPrice'], True, '盤後'
                elif not df_intra.empty and abs(live_price - regular_price) / max(regular_price, 0.01) > 0.001:
                    ext_price, is_extended, ext_label = live_price, True, '盤後/試撮'

                reg_change  = regular_price - previous_close
                reg_pct     = (reg_change / previous_close) * 100
                ext_pct     = ((ext_price - regular_price) / regular_price) * 100 if is_extended else 0
                day_high_pct = ((day_high - previous_close) / previous_close) * 100 if not df_intra.empty else 0
                day_low_pct  = ((day_low  - previous_close) / previous_close) * 100 if not df_intra.empty else 0

                st.markdown(f"### 📱 {info.get('longName', ticker_input)} ({ticker_input})")
                st.caption(f'目前策略：{strat_desc}')

                # ── 價格卡片 + 走勢迷你圖 ──
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    fig_spark = go.Figure()

                    if not df_intra.empty:
                        tz_tw = pytz.timezone('Asia/Taipei')
                        if df_intra.index.tz is None:
                            df_plot = df_intra.tz_localize('UTC').tz_convert(tz_tw)
                        else:
                            df_plot = df_intra.tz_convert(tz_tw)

                        last_dt = df_plot.index[-1]
                        if last_dt.hour < 12:
                            session_start = (last_dt - pd.Timedelta(days=1)).replace(hour=17, minute=0, second=0, microsecond=0)
                        else:
                            session_start = last_dt.replace(hour=17, minute=0, second=0, microsecond=0)
                        session_end = session_start + pd.Timedelta(hours=16)
                        reg_start   = session_start.replace(hour=22, minute=30)
                        reg_end     = (session_start + pd.Timedelta(days=1)).replace(hour=5, minute=0, second=0, microsecond=0)

                        df_plot = df_plot[(df_plot.index >= session_start) & (df_plot.index <= session_end)]

                        if not df_plot.empty:
                            df_reg = df_plot[(df_plot.index >= reg_start) & (df_plot.index <= reg_end)]

                            fig_spark.add_trace(go.Scatter(
                                x=df_plot.index, y=df_plot['Close'],
                                mode='lines', line=dict(color='#cfd8dc', width=1.5, dash='dot'),
                                hoverinfo='skip'
                            ))

                            if not df_reg.empty:
                                day_open_val = df_reg['Open'].iloc[0]
                                day_close_val = df_reg['Close'].iloc[-1]
                                line_color  = COLOR_UP if day_close_val >= day_open_val else COLOR_DOWN
                                fill_color  = 'rgba(5, 154, 129, 0.2)' if day_close_val >= day_open_val else 'rgba(242, 54, 69, 0.2)'

                                fig_spark.add_trace(go.Scatter(
                                    x=df_reg.index, y=df_reg['Close'],
                                    mode='lines', line=dict(color=line_color, width=2),
                                    fill='tozeroy', fillcolor=fill_color, hoverinfo='skip'
                                ))
                                if 'VWAP' in df_reg.columns:
                                    fig_spark.add_trace(go.Scatter(
                                        x=df_reg.index, y=df_reg['VWAP'],
                                        mode='lines', line=dict(color=COLOR_VWAP, width=1.5),
                                        name='VWAP', hoverinfo='skip'
                                    ))

                            if '.TW' not in ticker_input:
                                # [修正] 動態判斷夏/冬令時間
                                tz_ny = pytz.timezone('America/New_York')
                                now_ny = datetime.now(tz_ny)
                                is_dst = bool(now_ny.dst())
                                open_str  = '21:30' if is_dst else '22:30'
                                close_str = '04:00' if is_dst else '05:00'

                                tick_vals  = [session_start, reg_start, reg_end, session_end]
                                tick_texts = [
                                    '17:00<br><span style="font-size:9px;color:gray">盤前</span>',
                                    f'🔔{open_str}<br><span style="font-size:9px;color:gray">開盤</span>',
                                    f'🌙{close_str}<br><span style="font-size:9px;color:gray">收盤</span>',
                                    '09:00<br><span style="font-size:9px;color:gray">結算</span>'
                                ]
                                x_range = [session_start, session_end]
                            else:
                                tick_vals = tick_texts = None
                                x_range   = None

                            y_min = df_plot['Low'].min()  * 0.999
                            y_max = df_plot['High'].max() * 1.001

                            fig_spark.update_layout(
                                height=110,
                                margin=dict(l=10, r=10, t=5, b=35),
                                xaxis=dict(
                                    visible=True, range=x_range, fixedrange=True,
                                    showgrid=False, showline=False, zeroline=False,
                                    tickmode='array', tickvals=tick_vals, ticktext=tick_texts,
                                    side='bottom', tickfont=dict(size=11)
                                ),
                                yaxis=dict(visible=False, range=[y_min, y_max], fixedrange=True),
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)',
                                showlegend=False, dragmode=False
                            )

                    st.markdown(get_price_card_html(
                        regular_price, reg_change, reg_pct,
                        is_extended, ext_price, ext_pct, ext_label,
                        day_high_pct, day_low_pct
                    ), unsafe_allow_html=True)

                    if not df_intra.empty:
                        # 走勢迷你圖：靜態，不攔截觸控
                        st.markdown('<div class="spark-chart-wrapper">', unsafe_allow_html=True)
                        st.plotly_chart(fig_spark, use_container_width=True,
                                        config=get_mobile_chart_config(allow_zoom=False))
                        st.markdown('</div>', unsafe_allow_html=True)

                with c2:
                    st.markdown(get_metric_card_html('本益比 (P/E)', f"{info.get('trailingPE', 'N/A')}", '估值參考'), unsafe_allow_html=True)
                with c3:
                    st.markdown(get_metric_card_html('EPS', f"{info.get('trailingEps', 'N/A')}", '獲利能力'), unsafe_allow_html=True)
                with c4:
                    mcap  = info.get('marketCap', 0)
                    m_str = f'{mcap/1_000_000_000:.1f}B' if mcap > 1_000_000_000 else f'{mcap/1_000_000:.1f}M'
                    st.markdown(get_metric_card_html('市值', m_str, info.get('sector', 'N/A')), unsafe_allow_html=True)

                # ── 策略訊號 ──
                st.markdown('#### 🤖 策略訊號解讀 (Rule-Based)')
                ai_data = generate_ai_summary(ticker_input, last, strat_fast_val, strat_slow_val)
                k1, k2, k3, k4 = st.columns(4)
                with k1:
                    st.markdown(f"""
                    <div class="metric-card">
                      <div class="metric-title">趨勢訊號</div>
                      <div class="metric-value" style="font-size:1.2rem;">{ai_data['trend']['msg']}</div>
                      <div><span class="status-badge {ai_data['trend']['bg']}">MA{strat_fast} vs MA{strat_slow}</span></div>
                    </div>""", unsafe_allow_html=True)
                with k2:
                    st.markdown(f"""
                    <div class="metric-card">
                      <div class="metric-title">量能判讀</div>
                      <div class="metric-value" style="font-size:1.2rem;">{ai_data['vol']['msg']}</div>
                      <div><span class="status-badge {ai_data['vol']['bg']}">{ai_data['vol']['val']:.1f} 倍均量</span></div>
                    </div>""", unsafe_allow_html=True)
                with k3:
                    st.markdown(f"""
                    <div class="metric-card">
                      <div class="metric-title">MACD 趨勢</div>
                      <div class="metric-value" style="font-size:1.2rem;">{ai_data['macd']['msg']}</div>
                      <div><span class="status-badge {ai_data['macd']['bg']}">{ai_data['macd']['val']:.2f}</span></div>
                    </div>""", unsafe_allow_html=True)
                with k4:
                    st.markdown(f"""
                    <div class="metric-card">
                      <div class="metric-title">RSI 強弱</div>
                      <div class="metric-value" style="font-size:1.2rem;">{ai_data['rsi']['msg']}</div>
                      <div><span class="status-badge {ai_data['rsi']['bg']}">{ai_data['rsi']['val']:.1f}</span></div>
                    </div>""", unsafe_allow_html=True)

                # ── 均線監控 ──
                st.markdown('#### 📏 關鍵均線監控')
                ma_list = [5, 10, 20, 30, 60, 120, 200]
                ma_html = ''.join([
                    f'<div class="ma-box">'
                    f'<div class="ma-label">MA {d}</div>'
                    f'<div class="ma-val {"txt-up-vip" if last.get(f"MA_{d}", 0) > prev.get(f"MA_{d}", 0) else "txt-down-vip"}">'
                    f'{last.get(f"MA_{d}", 0):.2f} {"▲" if last.get(f"MA_{d}", 0) > prev.get(f"MA_{d}", 0) else "▼"}</div></div>'
                    for d in ma_list
                ])
                st.markdown(f'<div class="ma-container">{ma_html}</div>', unsafe_allow_html=True)

                # ── 互動式主圖表 ──────────────────────────────────
                st.markdown('#### 📉 互動式技術分析 (Plotly)')

                # [手機優化] 在圖表上方顯示操作提示
                st.markdown(
                    '<div class="mobile-chart-hint">👆 雙指縮放 | 單指拖拉 | 右上角工具列可截圖</div>',
                    unsafe_allow_html=True
                )

                chart_days = st.slider('選擇顯示天數 (Days)', min_value=30, max_value=300, value=90, step=5)
                df_chart = df.tail(chart_days) if len(df) > chart_days else df

                fig_interactive = plot_interactive_chart(df_chart, ticker_input)

                st.markdown('<div class="main-chart-wrapper">', unsafe_allow_html=True)
                st.plotly_chart(
                    fig_interactive,
                    use_container_width=True,
                    # [關鍵] 手機啟用雙指縮放 + 工具列
                    config=get_mobile_chart_config(allow_zoom=True)
                )
                st.markdown('</div>', unsafe_allow_html=True)

                st.markdown(f"""
                <div class="ai-summary-card">
                  <div class="ai-title">🔎 綜合指標速覽</div>
                  <div class="ai-content">{ai_data['suggestion']}</div>
                </div>""", unsafe_allow_html=True)

                # ── Gemini 深度分析 ──
                st.markdown('---')
                st.subheader('🤖 Gemini 深度戰略分析')

                with st.expander('✨ 點擊展開：呼叫 AI 進行完整解讀 (消耗 Token)', expanded=False):
                    if st.button('🚀 啟動 Gemini 分析', key='btn_gemini_analyze'):
                        if 'GEMINI_API_KEY' not in st.secrets:
                            st.error('❌ 未設定 API Key，請檢查 secrets.toml')
                        else:
                            with st.spinner('正在連線 AI 大腦...'):
                                try:
                                    # [修正] 使用快取的 model，不重複掃描
                                    model = get_gemini_model()
                                    if not model:
                                        st.error('無法初始化 Gemini 模型')
                                    else:
                                        tech_insight = generate_technical_context(df)
                                        persona_prompts = {
                                            'Buffett': '你是巴菲特。請忽略短期波動，專注於護城河、現金流與長期價值。如果本益比過高，請直言不諱。',
                                            'Soros':   '你是索羅斯。請專注於市場情緒與反身性理論。尋找價格與基本面的背離，這是不是一個泡沫？',
                                            'Simons':  '你是量化大師西蒙斯。不要講故事，只看數據機率。請根據 RSI, MACD, 乖離率進行統計分析。',
                                            'General': '你是軍工複合體戰略家。請從地緣政治、供應鏈安全、國防預算角度分析這家公司的戰略價值。'
                                        }
                                        selected_key    = ai_persona.split(' ')[0]
                                        selected_prompt = persona_prompts.get(selected_key, persona_prompts['General'])

                                        prompt = f"""
{selected_prompt}
分析目標：{ticker_input} ({info.get('longName', '')})
【內部技術監控數據】：{tech_insight}
請給出詳細的操作建議 (進場/止損/目標價)
1. 目前的多空趨勢判定
2. 目前線圖的形態分析
3. 短線支撐與壓力位在哪裡
4. 具體操作策略（該追高、觀望還是停損？）
請用繁體中文，語氣專業但直白。
"""
                                        response = model.generate_content(prompt)
                                        st.markdown(f"""
                                        <div style="background-color:#f0f2f6; padding:15px; border-radius:10px; border-left:5px solid #FF4B4B; line-height:1.7;">
                                        {response.text}
                                        </div>""", unsafe_allow_html=True)

                                except Exception as e:
                                    st.error(f'AI 連線失敗，錯誤原因: {e}')
                                    st.caption('建議：請檢查 API Key 是否正確，或稍後再試。')

            with tab_calc:
                render_calculator_tab(current_close_price, exchange_rate, quote_type)
            with tab_inv:
                render_inventory_tab(current_close_price, quote_type)

        else:
            st.error('資料不足，請確認股票代號是否正確。')
    except Exception as e:
        st.error(f'系統忙碌中: {e}')
        st.exception(e)  # 開發模式下顯示完整錯誤堆疊