import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, time
import pytz
import google.generativeai as genai
import ta # 補回這行，避免 data/fetch.py 報錯

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

# 初始化 Gemini AI
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.warning("⚠️ 請在 .streamlit/secrets.toml 設定 GEMINI_API_KEY 才能使用 AI 深度分析功能")

# --- 技術分析計算模組 (純 Pandas 實作) ---
def generate_technical_context(df):
    if len(df) < 60: return "數據不足，略過技術分析。"
    df_calc = df.copy()
    close = df_calc['Close']

    # 手動計算指標
    sma20_series = close.rolling(window=20).mean()
    sma60_series = close.rolling(window=60).mean()
    
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss
    rsi_series = 100 - (100 / (1 + rs))

    exp12 = close.ewm(span=12, adjust=False).mean()
    exp26 = close.ewm(span=26, adjust=False).mean()
    macd_line = exp12 - exp26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - signal_line

    price = close.iloc[-1]
    sma20 = sma20_series.iloc[-1]
    sma60 = sma60_series.iloc[-1]
    rsi = rsi_series.iloc[-1]
    
    cur_hist = macd_hist.iloc[-1]
    prev_hist = macd_hist.iloc[-2]

    report = []
    if price > sma20:
        report.append(f"股價 ({price:.2f}) 站上月線 (20MA: {sma20:.2f})，短線轉強。")
    else:
        report.append(f"股價 ({price:.2f}) 跌破月線 (20MA: {sma20:.2f})，短線示弱。")
        
    if sma20 > sma60:
        report.append("月線大於季線，中長期均線呈現多頭排列。")
    else:
        report.append("月線小於季線，中長期均線呈現空頭或整理格局。")

    if rsi > 70:
        report.append(f"RSI 指標 ({rsi:.2f}) 進入超買區，需留意高檔鈍化或回調風險。")
    elif rsi < 30:
        report.append(f"RSI 指標 ({rsi:.2f}) 進入超賣區，短線隨時可能反彈。")
    else:
        report.append(f"RSI 指標 ({rsi:.2f}) 處於中性區間。")

    if cur_hist > 0 and cur_hist > prev_hist:
        report.append("MACD 紅柱持續放大，多頭動能強勁。")
    elif cur_hist > 0 and cur_hist < prev_hist:
        report.append("MACD 紅柱縮短，多頭動能減弱 (背離警戒)。")
    elif cur_hist < 0 and cur_hist < prev_hist:
        report.append("MACD 綠柱放大，空頭動能增強。")
    else:
        report.append("MACD 綠柱縮短，空頭動能減弱 (可能準備黃金交叉)。")

    return " | ".join(report)

# --- 2. 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 參數設定")
    ticker_input = st.text_input("股票代號", "TSLA", key="sidebar_ticker").upper()
    if st.button("🔄 更新報價 (Refresh)"):
        if 'stored_ticker' in st.session_state: del st.session_state['stored_ticker']
        st.rerun()
    st.markdown("---")
    st.subheader("🧠 策略邏輯")
    strategy_mode = st.radio("判讀模式", ["🤖 自動判別 (Auto)", "🛠️ 手動設定 (Manual)"], key="sidebar_strat_mode")
    strat_fast, strat_slow, strat_desc = 5, 20, "預設"
    if strategy_mode == "🛠️ 手動設定 (Manual)":
        strat_fast = st.number_input("策略快線 (Fast)", value=5, key="sidebar_fast")
        strat_slow = st.number_input("策略慢線 (Slow)", value=20, key="sidebar_slow")
        strat_desc = "自訂策略"

# --- 3. 定義局部刷新 (交易計算機) ---
@st.fragment
def render_calculator_tab(current_close_price, exchange_rate, quote_type):
    st.markdown("#### 🧮 交易前規劃")
    fees = get_fees(quote_type)
    BUY_FIXED_FEE, BUY_RATE_FEE = fees['buy_fixed'], fees['buy_rate']
    SELL_FIXED_FEE, SELL_RATE_FEE = fees['sell_fixed'], fees['sell_rate']
    
    st.markdown(f'<div class="fee-badge">{fees["text"]}</div>', unsafe_allow_html=True)
    st.info(f"💰 目前匯率參考：**1 USD ≈ {exchange_rate:.2f} TWD**")

    with st.container():
        st.markdown('<div class="calc-header">💰 預算試算 (我有多少錢?)</div>', unsafe_allow_html=True)
        bc1, bc2 = st.columns(2)
        with bc1: budget_twd = st.number_input("台幣預算 (TWD)", value=100000, step=1000, key="budget_input")
        with bc2:
            if "buy_price_input" not in st.session_state: st.session_state.buy_price_input = float(current_close_price)
            buy_price_input = st.number_input("預計買入價 (USD)", key="buy_price_input", step=0.1, format="%.2f")

        usd_budget = budget_twd / exchange_rate
        max_shares = (usd_budget - BUY_FIXED_FEE) / (buy_price_input * (1 + BUY_RATE_FEE)) if usd_budget > BUY_FIXED_FEE else 0
        total_buy_cost_usd = (max_shares * buy_price_input * (1 + BUY_RATE_FEE)) + BUY_FIXED_FEE
        total_buy_cost_twd = total_buy_cost_usd * exchange_rate
        
        if max_shares > 0:
            st.markdown(f"""<div class="calc-result"><div class="calc-res-title">可購買股數</div><div class="calc-res-val" style="color:#0d6efd !important;">{max_shares:.2f} 股</div><div style="font-size:0.8rem; margin-top:5px; color:#666 !important;">總成本: ${total_buy_cost_usd:.2f} USD (約 {total_buy_cost_twd:.0f} TWD)</div></div>""", unsafe_allow_html=True)
        else: st.error("預算不足以支付手續費")
    
    st.markdown("---")

    with st.container():
        st.markdown('<div class="calc-header">⚖️ 賣出試算 (獲利預估)</div>', unsafe_allow_html=True)
        c_input1, c_input2 = st.columns(2)
        with c_input1: shares_held = st.number_input("持有股數", value=10.0, step=1.0, key="hold_shares_input")
        with c_input2:
            if "cost_price_input" not in st.session_state: st.session_state.cost_price_input = float(current_close_price)
            cost_price = st.number_input("買入成本 (USD)", key="cost_price_input", step=0.1, format="%.2f")

        real_buy_cost_usd = (cost_price * shares_held * (1 + BUY_RATE_FEE)) + BUY_FIXED_FEE
        breakeven_price = (real_buy_cost_usd + SELL_FIXED_FEE) / (shares_held * (1 - SELL_RATE_FEE))
        st.caption(f"🛡️ 損益兩平價 (含手續費): **${breakeven_price:.2f}**")
        st.divider()

        calc_mode = st.radio("選擇試算目標：", ["🎯 設定【目標獲利】反推股價", "💵 設定【賣出價格】計算獲利"], horizontal=True, key="calc_mode_radio")

        if calc_mode == "🎯 設定【目標獲利】反推股價":
            target_profit_twd = st.number_input("我想賺多少台幣 (TWD)?", value=3000, step=500, key="target_profit_input")
            target_sell_price = ((target_profit_twd / exchange_rate) + real_buy_cost_usd + SELL_FIXED_FEE) / (shares_held * (1 - SELL_RATE_FEE))
            pct_need = ((target_sell_price / cost_price) - 1) * 100 if cost_price > 0 else 0
            st.markdown(f"""<div class="calc-result"><div class="calc-res-title">建議掛單賣出價</div><div class="calc-res-val txt-up-vip">${target_sell_price:.2f}</div><div style="font-size:0.8rem;" class="txt-up-vip">需上漲 {pct_need:.1f}%</div></div>""", unsafe_allow_html=True)
        else:
            if "target_sell_input" not in st.session_state: st.session_state.target_sell_input = float(cost_price) * 1.05
            target_sell_input = st.number_input("預計賣出價格 (USD)", key="target_sell_input", step=0.1, format="%.2f")
            net_profit_twd = ((target_sell_input * shares_held * (1 - SELL_RATE_FEE)) - SELL_FIXED_FEE - real_buy_cost_usd) * exchange_rate
            res_class, res_prefix = ("txt-up-vip", "+") if net_profit_twd >= 0 else ("txt-down-vip", "")
            st.markdown(f"""<div class="calc-result"><div class="calc-res-title">預估淨獲利 (TWD)</div><div class="calc-res-val {res_class}">{res_prefix}{net_profit_twd:.0f} 元</div><div style="font-size:0.8rem; color:#666 !important;">美金損益: {res_prefix}${net_profit_twd/exchange_rate:.2f}</div></div>""", unsafe_allow_html=True)

# --- 4. 定義局部刷新 (庫存管理) ---
@st.fragment
def render_inventory_tab(current_close_price, quote_type):
    st.markdown("#### 📦 庫存損益與加碼攤平")
    fees = get_fees(quote_type)
    BUY_FIXED_FEE, BUY_RATE_FEE = fees['buy_fixed'], fees['buy_rate']
    SELL_FIXED_FEE, SELL_RATE_FEE = fees['sell_fixed'], fees['sell_rate']
    st.caption(f"{fees['text']}")

    with st.container():
        ic1, ic2 = st.columns(2)
        with ic1:
            st.caption("📍 目前持倉")
            curr_shares = st.number_input("目前股數", value=100.0, key="inv_curr_shares")
            if "inv_curr_avg" not in st.session_state: st.session_state.inv_curr_avg = float(current_close_price) * 1.1
            curr_avg_price = st.number_input("平均成交價 (USD)", key="inv_curr_avg", step=0.1, format="%.2f")
        with ic2:
            st.caption("➕ 預計加碼")
            new_shares = st.number_input("加碼股數", value=50.0, key="inv_new_shares")
            if "inv_new_price" not in st.session_state: st.session_state.inv_new_price = float(current_close_price)
            new_buy_price = st.number_input("加碼單價 (USD)", key="inv_new_price", step=0.1, format="%.2f")
    st.markdown("---")

    total_shares = curr_shares + new_shares
    total_cost_real = ((curr_shares * curr_avg_price * (1 + BUY_RATE_FEE)) + (BUY_FIXED_FEE if curr_shares > 0 else 0)) + \
                      ((new_shares * new_buy_price * (1 + BUY_RATE_FEE)) + (BUY_FIXED_FEE if new_shares > 0 else 0))
    new_avg_price = (curr_shares * curr_avg_price + new_shares * new_buy_price) / total_shares if total_shares > 0 else 0
    market_val_net = (total_shares * new_buy_price * (1 - SELL_RATE_FEE)) - (SELL_FIXED_FEE if total_shares > 0 else 0)
    unrealized_pl = market_val_net - total_cost_real
    
    pl_class = "txt-up-vip" if unrealized_pl >= 0 else "txt-down-vip"
    avg_change_class = "txt-up-vip" if new_avg_price < curr_avg_price else "txt-gray-vip"

    st.markdown(f"""<div class="metric-card"><div class="metric-title">加碼後平均成交價</div><div style="display:flex; justify-content:space-between; align-items:end;"><div class="metric-value">${new_avg_price:.2f}</div><div class="{avg_change_class}">{f'⬇ 下降 ${curr_avg_price - new_avg_price:.2f}' if new_avg_price < curr_avg_price else '變動不大'}</div></div></div>""", unsafe_allow_html=True)
    c_res1, c_res2 = st.columns(2)
    with c_res1: st.markdown(f"""<div class="calc-result"><div class="calc-res-title">加碼後總股數</div><div class="calc-res-val">{total_shares:.0f} 股</div></div>""", unsafe_allow_html=True)
    with c_res2: st.markdown(f"""<div class="calc-result"><div class="calc-res-title">預估總損益 (含費)</div><div class="calc-res-val {pl_class}">${unrealized_pl:.2f}</div></div>""", unsafe_allow_html=True)

# --- 5. 主程式邏輯 ---
if ticker_input:
    try:
        if 'stored_ticker' not in st.session_state or st.session_state.stored_ticker != ticker_input:
            with st.spinner(f"正在抓取 {ticker_input} 數據..."):
                df, df_intra, info, quote_type = fetch_stock_data_now(ticker_input)
                exchange_rate = fetch_exchange_rate_now()
                st.session_state.update(stored_ticker=ticker_input, data_df=df, data_df_intra=df_intra, data_info=info, data_quote_type=quote_type, data_exchange_rate=exchange_rate)
                for k in ["buy_price_input", "cost_price_input", "target_sell_input", "inv_curr_avg", "inv_new_price"]:
                    if k in st.session_state: del st.session_state[k]

        df, df_intra, info = st.session_state.data_df, st.session_state.data_df_intra, st.session_state.data_info
        quote_type, exchange_rate = st.session_state.data_quote_type, st.session_state.data_exchange_rate

        if not df.empty and len(df) > 200:
            if strategy_mode == "🤖 自動判別 (Auto)":
                strat_fast, strat_slow = (10, 20) if info.get('marketCap', 0) > 200_000_000_000 else (5, 10)
                strat_desc = "🐘 巨頭穩健" if info.get('marketCap', 0) > 200_000_000_000 else "🚀 小型飆股"
            
            # [計算指標]
            df = calculate_ma(df)
            
            # 【關鍵新增】手動計算 10MA (以防 logic 模組沒算)
            if 'MA_10' not in df.columns:
                df['MA_10'] = df['Close'].rolling(window=10).mean()

            df = calculate_bollinger(df)
            
            last = df.iloc[-1]
            prev = df.iloc[-2]
            current_close_price = last['Close']
            strat_fast_val, strat_slow_val = get_strategy_values(df, strat_fast, strat_slow)

            tab_analysis, tab_calc, tab_inv = st.tabs(["📊 技術分析", "🧮 交易計算", "📦 庫存管理"])

            with tab_analysis:
                if not df_intra.empty:
                    df_intra = calculate_vwap(df_intra)
                    
                    df_intra.index = pd.to_datetime(df_intra.index)
                    if ".TW" in ticker_input:
                        tz_str = 'Asia/Taipei'
                        open_time, close_time = time(9, 0), time(13, 30)
                    else:
                        tz_str = 'America/New_York'
                        open_time, close_time = time(9, 30), time(16, 0)
                    try: df_intra_tz = df_intra.tz_convert(tz_str)
                    except: df_intra_tz = df_intra
                    
                    mask_reg_hl = (df_intra_tz.index.time >= open_time) & (df_intra_tz.index.time <= close_time)
                    df_reg_hl = df_intra_tz[mask_reg_hl]
                    day_high = df_reg_hl['High'].max() if not df_reg_hl.empty else df_intra_tz['High'].max()
                    day_low = df_reg_hl['Low'].min() if not df_reg_hl.empty else df_intra_tz['Low'].min()
                
                previous_close = info.get('previousClose', df.iloc[-2]['Close'])
                regular_price = info.get('currentPrice', info.get('regularMarketPrice', last['Close']))
                
                is_extended, ext_price, ext_label = False, 0, ""
                live_price = df_intra['Close'].iloc[-1] if not df_intra.empty else 0
                if info.get('preMarketPrice'): ext_price, is_extended, ext_label = info['preMarketPrice'], True, "盤前"
                elif info.get('postMarketPrice'): ext_price, is_extended, ext_label = info['postMarketPrice'], True, "盤後"
                elif abs(live_price - regular_price) / regular_price > 0.001: ext_price, is_extended, ext_label = live_price, True, "盤後/試撮"
                
                reg_change = regular_price - previous_close
                reg_pct = (reg_change / previous_close) * 100
                ext_pct = ((ext_price - regular_price) / regular_price) * 100 if is_extended else 0
                day_high_pct = ((day_high - previous_close) / previous_close) * 100 if not df_intra.empty else 0
                day_low_pct = ((day_low - previous_close) / previous_close) * 100 if not df_intra.empty else 0

                st.markdown(f"### 📱 {info.get('longName', ticker_input)} ({ticker_input})")
                st.caption(f"目前策略：{strat_desc}")
                
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    fig_spark = go.Figure()
                    # 確保有資料
                    if not df_intra.empty:
                        # 1. 設定正規交易時段 (美股 09:30-16:00, 台股 09:00-13:30)
                        is_us = ".TW" not in ticker_input
                        t_start = "09:30" if is_us else "09:00"
                        t_end = "16:00" if is_us else "13:30"
                        
                        # 2. 【關鍵】使用 Pandas 強制過濾，只保留這段時間的數據
                        # 這樣盤前盤後的數據會直接被丟棄，不會畫在圖上
                        df_plot = df_intra_tz.between_time(t_start, t_end).copy()
                        
                        if not df_plot.empty:
                            # 3. 繪製 VWAP (如果有) - 此時數據已經乾淨了，不用擔心畫出去
                            if 'VWAP' in df_plot.columns:
                                fig_spark.add_trace(go.Scatter(
                                    x=df_plot.index, y=df_plot['VWAP'], 
                                    mode='lines', line=dict(color=COLOR_VWAP, width=1.5), 
                                    name='VWAP', hoverinfo='skip'
                                ))
                            
                            # 4. 繪製股價走勢
                            day_open = df_plot['Open'].iloc[0]
                            day_close = df_plot['Close'].iloc[-1]
                            line_color = COLOR_UP if day_close >= day_open else COLOR_DOWN
                            fill_color = "rgba(5, 154, 129, 0.15)" if day_close >= day_open else "rgba(242, 54, 69, 0.15)"
                            
                            fig_spark.add_trace(go.Scatter(
                                x=df_plot.index, y=df_plot['Close'], 
                                mode='lines', line=dict(color=line_color, width=2), 
                                fill='tozeroy', fillcolor=fill_color, hoverinfo='skip'
                            ))
                            
                            # 5. 強制鎖定 X 軸範圍 (確保圖表左右邊緣切齊開收盤時間)
                            # 取得當前數據的日期
                            current_date = df_plot.index[0].date()
                            
                            if is_us:
                                tz_obj = pytz.timezone('America/New_York')
                                dt_start = tz_obj.localize(datetime.combine(current_date, time(9, 30)))
                                dt_end = tz_obj.localize(datetime.combine(current_date, time(16, 0)))
                            else:
                                tz_obj = pytz.timezone('Asia/Taipei')
                                dt_start = tz_obj.localize(datetime.combine(current_date, time(9, 0)))
                                dt_end = tz_obj.localize(datetime.combine(current_date, time(13, 30)))

                            y_min = df_plot['Low'].min() * 0.999
                            y_max = df_plot['High'].max() * 1.001
                            
                            fig_spark.update_layout(
                                height=80, 
                                margin=dict(l=0, r=40, t=5, b=5), 
                                xaxis=dict(visible=False, range=[dt_start, dt_end]), # 鎖定 X 軸
                                yaxis=dict(visible=False, range=[y_min, y_max]), 
                                paper_bgcolor='rgba(0,0,0,0)', 
                                plot_bgcolor='rgba(0,0,0,0)', 
                                showlegend=False, 
                                dragmode=False
                            )

                    # 顯示價格卡片與圖表
                    st.markdown(get_price_card_html(regular_price, reg_change, reg_pct, is_extended, ext_price, ext_pct, ext_label, day_high_pct, day_low_pct), unsafe_allow_html=True)
                    if not df_intra.empty and not df_plot.empty:
                        st.plotly_chart(fig_spark, use_container_width=True, config={'displayModeBar': False, 'staticPlot': True})
                        st.markdown(get_timeline_html(ticker_input), unsafe_allow_html=True)
                
                with c2: st.markdown(get_metric_card_html("本益比 (P/E)", f"{info.get('trailingPE', 'N/A')}", "估值參考"), unsafe_allow_html=True)
                with c3: st.markdown(get_metric_card_html("EPS", f"{info.get('trailingEps', 'N/A')}", "獲利能力"), unsafe_allow_html=True)
                with c4:
                    mcap = info.get('marketCap', 0)
                    m_str = f"{mcap/1000000000:.1f}B" if mcap > 1000000000 else f"{mcap/1000000:.1f}M"
                    st.markdown(get_metric_card_html("市值", m_str, info.get('sector','N/A')), unsafe_allow_html=True)

                st.markdown("#### 🤖 策略訊號解讀 (Rule-Based)")
                ai_data = generate_ai_summary(ticker_input, last, strat_fast_val, strat_slow_val)
                k1, k2, k3, k4 = st.columns(4)
                with k1: st.markdown(f"""<div class="metric-card"><div class="metric-title">趨勢訊號</div><div class="metric-value" style="font-size:1.3rem;">{ai_data['trend']['msg']}</div><div><span class="status-badge {ai_data['trend']['bg']}">MA{strat_fast} vs MA{strat_slow}</span></div></div>""", unsafe_allow_html=True)
                with k2: st.markdown(f"""<div class="metric-card"><div class="metric-title">量能判讀</div><div class="metric-value" style="font-size:1.3rem;">{ai_data['vol']['msg']}</div><div><span class="status-badge {ai_data['vol']['bg']}">{ai_data['vol']['val']:.1f} 倍均量</span></div></div>""", unsafe_allow_html=True)
                with k3: st.markdown(f"""<div class="metric-card"><div class="metric-title">MACD 趨勢</div><div class="metric-value" style="font-size:1.3rem;">{ai_data['macd']['msg']}</div><div><span class="status-badge {ai_data['macd']['bg']}">{ai_data['macd']['val']:.2f}</span></div></div>""", unsafe_allow_html=True)
                with k4: st.markdown(f"""<div class="metric-card"><div class="metric-title">RSI 強弱</div><div class="metric-value" style="font-size:1.3rem;">{ai_data['rsi']['msg']}</div><div><span class="status-badge {ai_data['rsi']['bg']}">{ai_data['rsi']['val']:.1f}</span></div></div>""", unsafe_allow_html=True)

                st.markdown("#### 📏 關鍵均線監控")
                ma_list = [5, 10, 20, 30, 60, 120, 200]
                ma_html = "".join([f'<div class="ma-box"><div class="ma-label">MA {d}</div><div class="ma-val {"txt-up-vip" if last.get(f"MA_{d}", 0) > prev.get(f"MA_{d}", 0) else "txt-down-vip"}">{last.get(f"MA_{d}", 0):.2f} {"▲" if last.get(f"MA_{d}", 0) > prev.get(f"MA_{d}", 0) else "▼"}</div></div>' for d in ma_list])
                st.markdown(f'<div class="ma-container">{ma_html}</div>', unsafe_allow_html=True)

                st.markdown("#### 📉 技術分析")
                st.write("##### 📅 選擇歷史走勢長度 (月)")
                chart_months = st.slider(" ", 1, 12, 6, label_visibility="collapsed")
                cutoff = df.index[-1] - pd.DateOffset(months=chart_months)
                df_chart = df[df.index >= cutoff].copy()
                range_breaks = [dict(values=pd.date_range(start=df_chart.index[0], end=df_chart.index[-1]).difference(df_chart.index).strftime("%Y-%m-%d").tolist())]

                # --- 設定通用的圖表 Config (防手殘設定) ---
                chart_config = {'displayModeBar': False, 'scrollZoom': False}

                # 1. K線圖 + 5, 10, 20, 60, 120 MA
                st.markdown("<div class='chart-title'>📈 股價走勢 </div>", unsafe_allow_html=True)
                fig_price = go.Figure()
                fig_price.add_trace(go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], increasing_line_color=COLOR_UP, decreasing_line_color=COLOR_DOWN, name='K線', showlegend=False))
                
                # 【關鍵修改】加入 10MA (藍色)，並更新列表
                # 顏色順序：5(紫), 10(藍), 20(橘), 60(綠), 120(灰)
                for m, c in zip([5, 10, 20, 60, 120], ['#D500F9', '#2962FF', '#FF6D00', '#00C853', '#78909C']): 
                    if f'MA_{m}' in df_chart.columns:
                        fig_price.add_trace(go.Scatter(x=df_chart.index, y=df_chart[f'MA_{m}'], line=dict(color=c, width=1), name=f'MA{m}'))
                
                fig_price.update_layout(
                    height=400, 
                    margin=dict(l=10,r=10,t=10,b=50), 
                    xaxis_rangeslider_visible=False, 
                    showlegend=True, 
                    template="plotly_white", 
                    legend=dict(orientation="h", yanchor="top", y=-0.1),
                    dragmode=False  # 禁止滑鼠拖曳
                )
                fig_price.update_xaxes(rangebreaks=range_breaks, fixedrange=True) 
                fig_price.update_yaxes(fixedrange=True)
                st.plotly_chart(fig_price, use_container_width=True, config=chart_config)

                # 2. 成交量
                st.markdown("<div class='chart-title'>📊 成交量</div>", unsafe_allow_html=True)
                colors = [VOL_EXPLODE if (r['Volume']/(r['Vol_MA'] if r['Vol_MA']>0 else 1))>=2 else VOL_NORMAL if (r['Volume']/(r['Vol_MA'] if r['Vol_MA']>0 else 1))>=1 else VOL_SHRINK for _, r in df_chart.iterrows()]
                fig_vol = go.Figure(data=[go.Bar(x=df_chart.index, y=df_chart['Volume'], marker_color=colors), go.Scatter(x=df_chart.index, y=df_chart['Vol_MA'], line=dict(color='black', width=1))])
                fig_vol.update_layout(height=200, margin=dict(l=10,r=10,t=10,b=10), showlegend=False, template="plotly_white", dragmode=False)
                fig_vol.update_xaxes(rangebreaks=range_breaks, fixedrange=True)
                fig_vol.update_yaxes(fixedrange=True)
                st.plotly_chart(fig_vol, use_container_width=True, config=chart_config)

                # 3. RSI & MACD
                c_rsi, c_macd = st.columns(2)
                with c_rsi:
                    st.markdown("<div class='chart-title'>⚡ RSI 強弱指標</div>", unsafe_allow_html=True)
                    fig_rsi = go.Figure(go.Scatter(x=df_chart.index, y=df_chart['RSI'], line=dict(color='#9C27B0')))
                    fig_rsi.add_hline(y=70, line_dash="dash", line_color=COLOR_DOWN); fig_rsi.add_hline(y=30, line_dash="dash", line_color=COLOR_UP)
                    fig_rsi.update_layout(height=200, margin=dict(l=10,r=10,t=10,b=10), template="plotly_white", dragmode=False)
                    fig_rsi.update_xaxes(rangebreaks=range_breaks, fixedrange=True)
                    fig_rsi.update_yaxes(fixedrange=True)
                    st.plotly_chart(fig_rsi, use_container_width=True, config=chart_config)
                with c_macd:
                    st.markdown("<div class='chart-title'>🌊 MACD 趨勢指標</div>", unsafe_allow_html=True)
                    hist_data = df_chart['Hist']
                    fig_macd = go.Figure([go.Scatter(x=df_chart.index, y=df_chart['MACD'], line=dict(color='#2196F3')), go.Scatter(x=df_chart.index, y=df_chart['Signal'], line=dict(color='#FF5722')), go.Bar(x=df_chart.index, y=hist_data, marker_color=[(MACD_BULL_GROW if h>0 else MACD_BEAR_GROW) for h in hist_data])])
                    fig_macd.update_layout(height=200, margin=dict(l=10,r=10,t=10,b=10), showlegend=False, template="plotly_white", dragmode=False)
                    fig_macd.update_xaxes(rangebreaks=range_breaks, fixedrange=True)
                    fig_macd.update_yaxes(fixedrange=True)
                    st.plotly_chart(fig_macd, use_container_width=True, config=chart_config)
                
                st.markdown(f"""<div class="ai-summary-card"><div class="ai-title">🔎 綜合指標速覽</div><div class="ai-content">{ai_data['suggestion']}</div></div>""", unsafe_allow_html=True)
                
                # --- Gemini 深度 AI 分析區塊 ---
                st.markdown("---")
                st.subheader("🤖 Gemini 深度戰略分析")
                
                with st.expander("✨ 點擊展開：呼叫 AI 進行完整解讀 (消耗 Token)", expanded=False):
                    if st.button("🚀 啟動 Gemini 分析", key="btn_gemini_analyze"):
                        if "GEMINI_API_KEY" not in st.secrets:
                            st.error("❌ 未設定 API Key，請檢查 secrets.toml")
                        else:
                            with st.spinner("正在連線 AI 大腦..."):
                                try:
                                    # 自動尋找可用的模型
                                    valid_model_name = None
                                    for m in genai.list_models():
                                        if 'generateContent' in m.supported_generation_methods:
                                            if 'flash' in m.name:
                                                valid_model_name = m.name
                                                break
                                    
                                    if not valid_model_name:
                                        for m in genai.list_models():
                                            if 'gemini-pro' in m.name:
                                                valid_model_name = m.name
                                                break
                                    
                                    if not valid_model_name:
                                        valid_model_name = 'models/gemini-pro'

                                    # 執行分析
                                    model = genai.GenerativeModel(valid_model_name)
                                    
                                    tech_insight = generate_technical_context(df)
                                    
                                    prompt = f"""
                                    你是華爾街頂級交易員。請分析股票 {ticker_input} ({info.get('longName', '')})。
                                    
                                    【內部技術監控數據 (請基於此進行解讀，勿直接列出數字)】：
                                    {tech_insight}
                                    
                                    請給出詳細的操作建議，包含：
                                    1. 目前的多空趨勢判定。
                                    2. 短線支撐與壓力位在哪裡？
                                    3. 具體操作策略（該追高、觀望還是停損？）。
                                    請用繁體中文，語氣專業但直白。
                                    """
                                    
                                    response = model.generate_content(prompt)
                                    st.markdown(f"""<div style="background-color:#f0f2f6; padding:15px; border-radius:10px; border-left: 5px solid #FF4B4B;">{response.text}</div>""", unsafe_allow_html=True)
                                
                                except Exception as e:
                                    st.error(f"AI 連線失敗，錯誤原因: {e}")
                                    st.caption("建議：請檢查 API Key 是否正確，或稍後再試。")

            with tab_calc: render_calculator_tab(current_close_price, exchange_rate, quote_type)
            with tab_inv: render_inventory_tab(current_close_price, quote_type)

        else: st.error("資料不足")
    except Exception as e: st.error(f"系統忙碌中: {e}")