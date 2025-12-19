def generate_ai_summary(ticker, last_row, strat_fast_val, strat_slow_val):
    trend_status = "盤整"
    rsi_status = "中性"
    vol_status = "一般"
    macd_status = "不明"
    bb_status = "正常"

    # 1. 趨勢判斷
    if last_row['Close'] > strat_fast_val > strat_slow_val:
        trend_msg = "🚀 火力全開！(多頭)"
        trend_bg = "bg-up"
        trend_desc = "均線向上，順勢操作"
        trend_status = "多頭"
    elif last_row['Close'] < strat_fast_val < strat_slow_val:
        trend_msg = "🐻 熊出沒注意 (空頭)"
        trend_bg = "bg-down"
        trend_desc = "均線蓋頭，保守為宜"
        trend_status = "空頭"
    else:
        trend_msg = "💤 睡覺行情 (盤整)"
        trend_bg = "bg-gray"
        trend_desc = "多空不明，建議觀望"

    # 2. 量能判斷
    vol_r = last_row['Volume'] / last_row['Vol_MA'] if last_row['Vol_MA'] > 0 else 0
    if vol_r > 2.0:
        v_msg = "🔥 資金派對 (爆量)"
        v_bg = "bg-down"
        vol_status = "爆量"
    elif vol_r > 1.0:
        v_msg = "💧 人氣回溫"
        v_bg = "bg-blue"
        vol_status = "溫和"
    else:
        v_msg = "❄️ 冷冷清清"
        v_bg = "bg-gray"

    # 3. MACD 判斷
    hist_val = last_row.get('Hist', 0)
    if hist_val > 0:
        m_msg = "🐂 牛軍集結"
        m_bg = "bg-up"
        macd_status = "多方"
    else:
        m_msg = "📉 空軍壓境"
        m_bg = "bg-down"
        macd_status = "空方"

    # 4. RSI 判斷
    r_val = last_row['RSI']
    if r_val > 70:
        r_msg = "🔥 太燙了！(過熱)"
        r_bg = "bg-down"
        rsi_status = "過熱"
    elif r_val < 30:
        r_msg = "🧊 跌過頭囉 (超賣)"
        r_bg = "bg-up"
        rsi_status = "超賣"
    else:
        r_msg = "⚖️ 多空拔河"
        r_bg = "bg-gray"
        
    # [新增] 5. 布林通道判讀 (只在 AI 文字中呈現)
    bb_high = last_row.get('BB_High', 0)
    bb_low = last_row.get('BB_Low', 0)
    bb_width = last_row.get('BB_Width', 0)
    close = last_row['Close']
    
    bb_text = ""
    if close > bb_high:
        bb_text = "股價突破布林通道上緣，多頭氣勢極強，但需提防短線乖離過大回檔。"
    elif close < bb_low:
        bb_text = "股價跌破布林通道下緣，短線超賣，隨時可能出現技術性反彈。"
    elif bb_width < 0.10: # 通道壓縮小於 10%
        bb_text = "布林通道目前極度壓縮，顯示變盤在即，請密切注意突破方向！"

    # 6. 生成建議文字
    suggestion = ""
    if trend_status == "多頭":
        suggestion += f"目前 {ticker} 呈現多頭排列，均線向上發散。"
        if rsi_status == "過熱":
            suggestion += "惟 RSI 進入過熱區 (>70)，" + ("且突破布林上緣，" if close > bb_high else "") + "短線可能有獲利了結賣壓，不宜過度追價。"
        else:
            suggestion += "RSI 動能健康，" + bb_text + "可續抱或順勢操作。"
    elif trend_status == "空頭":
        suggestion += f"目前 {ticker} 呈現空頭排列，均線蓋頭反壓。"
        if rsi_status == "超賣":
            suggestion += "但 RSI 已進入超賣區 (<30)，" + ("且觸及布林下緣，" if close < bb_low else "") + "隨時有機會出現反彈，搶短手腳要快。"
        else:
            suggestion += "技術面偏弱，建議多看少做。"
    else:
        suggestion += f"目前 {ticker} 處於盤整階段。"
        if bb_text: suggestion += bb_text
        if vol_status == "爆量":
            suggestion += "但近期出現爆量，顯示多空交戰激烈，變盤在即。"

    return {
        'trend': {'msg': trend_msg, 'bg': trend_bg, 'desc': trend_desc, 'status': trend_status},
        'vol': {'msg': v_msg, 'bg': v_bg, 'val': vol_r, 'status': vol_status},
        'macd': {'msg': m_msg, 'bg': m_bg, 'val': last_row.get('MACD', 0), 'status': macd_status},
        'rsi': {'msg': r_msg, 'bg': r_bg, 'val': r_val, 'status': rsi_status},
        'suggestion': suggestion
    }