def get_price_card_html(regular_price, reg_change, reg_pct, is_extended, ext_price, ext_pct, ext_label, day_high_pct, day_low_pct):
    # 決定顏色 class
    reg_class = "txt-up-vip" if reg_change > 0 else "txt-down-vip"
    
    # [修正] 移除多餘縮排，確保 HTML 能被正確渲染
    html = f"""<div class="metric-card">
    <div class="metric-title">最新股價</div>
    <div class="metric-value {reg_class}">{regular_price:.2f}</div>
    <div class="metric-sub {reg_class}">{('+' if reg_change > 0 else '')}{reg_change:.2f} ({reg_pct:.2f}%)</div>"""
    
    if is_extended:
        ext_class = "txt-up-vip" if (ext_price - regular_price) > 0 else "txt-down-vip"
        html += f"""<div class="ext-price-box">
        <span class="ext-label">{ext_label}</span>
        <span class="{ext_class}">{ext_price:.2f} ({('+' if ext_pct > 0 else '')}{ext_pct:.2f}%)</span>
        </div>"""
        
    # H/L Scale
    h_class = "txt-up-vip" if day_high_pct >= 0 else "txt-down-vip"
    l_class = "txt-up-vip" if day_low_pct >= 0 else "txt-down-vip"
    
    html += f"""<div class="spark-scale">
    <div class="{h_class}">H: {day_high_pct:+.1f}%</div>
    <div style="margin-top:25px;" class="{l_class}">L: {day_low_pct:+.1f}%</div>
    </div>
    </div>"""
    return html

def get_timeline_html(ticker):
    # 僅針對美股顯示時間軸 (冬令時間鎖定)
    if ".TW" not in ticker:
        return f"""<div style="position: relative; height: 35px; margin-top: 5px; border-top: 1px dashed #eee; font-size: 0.65rem; color: #999; width: 100%;">
        <div style="position: absolute; left: 0%; transform: translateX(0%); text-align: left;">
        <span>盤前</span><br><b style="color:#555">17:00</b>
        </div>
        <div style="position: absolute; left: 34.375%; transform: translateX(-50%); text-align: center;">
        <span>🔔 開盤</span><br><b style="color:#000">22:30</b>
        </div>
        <div style="position: absolute; left: 75%; transform: translateX(-50%); text-align: center;">
        <span>🌙 收盤</span><br><b style="color:#000">05:00</b>
        </div>
        <div style="position: absolute; right: 0%; transform: translateX(0%); text-align: right;">
        <span>結算</span><br><b style="color:#555">09:00</b>
        </div>
        </div>"""
    return ""

def get_metric_card_html(title, value, sub):
    return f"""<div class="metric-card"><div class="metric-title">{title}</div><div class="metric-value">{value}</div><div class="metric-sub">{sub}</div></div>"""