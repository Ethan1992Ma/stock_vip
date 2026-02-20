SEC_FEE_RATE = 0.0000278

def get_fees(quote_type):
    if quote_type == 'ETF':
        return {
            'buy_fixed': 3.0, 'buy_rate': 0.0,
            'sell_fixed': 3.0, 'sell_rate': SEC_FEE_RATE,
            'text': "💡 檢測為 **ETF**：套用固定手續費 **$3 USD**"
        }
    else:
        return {
            'buy_fixed': 0.0, 'buy_rate': 0.001,
            'sell_fixed': 0.0, 'sell_rate': 0.001 + SEC_FEE_RATE,
            'text': "💡 檢測為 **一般股票**：套用費率 **0.1%**"
        }