import yfinance as yf
import pandas as pd
import streamlit as st  # [新增] 引入 streamlit 以使用快取功能
from ta.trend import SMAIndicator, MACD
from ta.momentum import RSIIndicator

# [新增] ttl=60 代表資料會暫存 60 秒，期間內不再重複下載
# show_spinner=False 代表背景默默執行，不需一直跳出轉圈圈
@st.cache_data(ttl=60, show_spinner=False)
def fetch_stock_data_now(ticker):
    stock = yf.Ticker(ticker)
    df = stock.history(period="2y")
    df_intra = stock.history(period="1d", interval="5m", prepost=True)
    info = stock.info
    quote_type = info.get('quoteType', 'EQUITY')
    
    # 資料清洗與基礎指標計算
    if not df.empty:
        df['RSI'] = RSIIndicator(df['Close'], window=14).rsi()
        macd = MACD(df['Close'])
        df['MACD'] = macd.macd()
        df['Signal'] = macd.macd_signal()
        df['Hist'] = macd.macd_diff()
        
        # 強制填補 NaN
        df['Hist'] = df['Hist'].fillna(0)
        df['MACD'] = df['MACD'].fillna(0)
        df['Signal'] = df['Signal'].fillna(0)
        
        df['Vol_MA'] = SMAIndicator(df['Volume'], window=20).sma_indicator()
    
    return df, df_intra, info, quote_type

# [新增] 匯率也加上快取，設定 1 小時 (3600秒) 更新一次即可，不用一直查
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_exchange_rate_now():
    try:
        fx = yf.Ticker("USDTWD=X")
        hist = fx.history(period="1d")
        if not hist.empty:
            return hist['Close'].iloc[-1]
        return 32.5
    except:
        return 32.5