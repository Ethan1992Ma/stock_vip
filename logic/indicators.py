from ta.trend import SMAIndicator
from ta.volatility import BollingerBands

def calculate_ma(df, ma_list=[5, 10, 20, 30, 60, 120, 200]):
    for d in ma_list:
        df[f'MA_{d}'] = SMAIndicator(df['Close'], window=d).sma_indicator()
    return df

def get_strategy_values(df, fast=5, slow=20):
    fast_val = SMAIndicator(df['Close'], window=fast).sma_indicator().iloc[-1]
    slow_val = SMAIndicator(df['Close'], window=slow).sma_indicator().iloc[-1]
    return fast_val, slow_val

def calculate_bollinger(df, window=20, window_dev=2):
    indicator_bb = BollingerBands(close=df["Close"], window=window, window_dev=window_dev)
    df['BB_High'] = indicator_bb.bollinger_hband()
    df['BB_Low'] = indicator_bb.bollinger_lband()
    df['BB_Mid'] = indicator_bb.bollinger_mavg()
    df['BB_Width'] = (df['BB_High'] - df['BB_Low']) / df['BB_Mid']
    return df

# [新增] 計算 VWAP (成交量加權平均價)
def calculate_vwap(df):
    if df.empty: return df
    df = df.copy()
    # 累計成交量
    df['Cum_Vol'] = df['Volume'].cumsum()
    # 累計成交金額 (價格 * 成交量)
    df['Cum_Vol_Price'] = (df['Close'] * df['Volume']).cumsum()
    # VWAP = 累計成交金額 / 累計成交量
    df['VWAP'] = df['Cum_Vol_Price'] / df['Cum_Vol']
    return df