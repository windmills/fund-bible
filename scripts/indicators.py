#!/usr/bin/env python3
"""
基金买卖圣经法典 - 全量技术指标计算工具
用法:
  1. 直接粘贴净值数据: python3 indicators.py
  2. 从API获取: python3 indicators.py --code 002112
  3. 传入净值列表: python3 indicators.py --navs 6.0,6.1,6.05,5.9,6.2
"""
import sys
import json
import math
import urllib.request
import re
from datetime import datetime

def fetch_nav_data(code, total=250):
    all_records = []
    pages_needed = (total + 19) // 20
    for page in range(1, pages_needed + 1):
        url = f"https://fund.eastmoney.com/f10/F10DataApi.aspx?type=lsjz&code={code}&per=20&page={page}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            resp = urllib.request.urlopen(req, timeout=15)
            text = resp.read().decode('utf-8')
        except Exception:
            break
        rows = re.findall(r'<tr>(.*?)</tr>', text, re.S)
        page_count = 0
        for row in rows:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
            cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            if len(cells) >= 3 and re.match(r'\d{4}-\d{2}-\d{2}', cells[0]):
                try:
                    chg = 0.0
                    if len(cells) > 3 and cells[3] and cells[3] != '--':
                        chg = float(cells[3].replace('%', ''))
                    all_records.append({
                        'date': cells[0],
                        'nav': float(cells[1]),
                        'acc_nav': float(cells[2]),
                        'chg': chg
                    })
                    page_count += 1
                except (ValueError, IndexError):
                    continue
        if page_count == 0:
            break
    return all_records

def ma(data, period):
    if len(data) < period:
        return None
    return round(sum(data[-period:]) / period, 4)

def ema(data, period):
    if len(data) < period:
        return None
    k = 2 / (period + 1)
    e = sum(data[:period]) / period
    for v in data[period:]:
        e = v * k + e * (1 - k)
    return round(e, 4)

def ema_series(data, period):
    if len(data) < period:
        return []
    k = 2 / (period + 1)
    e = sum(data[:period]) / period
    result = [e]
    for v in data[period:]:
        e = v * k + e * (1 - k)
        result.append(e)
    return result

def calc_macd(closes, fast=12, slow=26, signal=9):
    if len(closes) < slow + signal:
        return None, None, None
    ema_fast = ema_series(closes, fast)
    ema_slow = ema_series(closes, slow)
    min_len = min(len(ema_fast), len(ema_slow))
    dif_series = [ema_fast[-(min_len - i)] - ema_slow[-(min_len - i)] for i in range(min_len)]
    dea_series = ema_series(dif_series, signal)
    dif = round(dif_series[-1], 4)
    dea = round(dea_series[-1], 4)
    hist = round(2 * (dif - dea), 4)
    return dif, dea, hist

def calc_kdj(closes, n=9):
    if len(closes) < n:
        return None, None, None
    k, d = 50.0, 50.0
    for i in range(n - 1, len(closes)):
        window = closes[i - n + 1: i + 1]
        hn = max(window)
        ln = min(window)
        if hn == ln:
            rsv = 50.0
        else:
            rsv = (closes[i] - ln) / (hn - ln) * 100
        k = 2 / 3 * k + 1 / 3 * rsv
        d = 2 / 3 * d + 1 / 3 * k
    j = 3 * k - 2 * d
    return round(k, 2), round(d, 2), round(j, 2)

def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = 0.0, 0.0
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        if diff > 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    for i in range(period + 1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gain = diff if diff > 0 else 0.0
        loss = -diff if diff < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 2)

def calc_boll(closes, n=20, multiplier=1.5):
    if len(closes) < n:
        return None, None, None, None
    window = closes[-n:]
    mb = sum(window) / n
    variance = sum((x - mb) ** 2 for x in window) / n
    std = math.sqrt(variance)
    up = mb + multiplier * std
    dn = mb - multiplier * std
    bandwidth = round((up - dn) / mb * 100, 2) if mb != 0 else 0
    return round(up, 4), round(mb, 4), round(dn, 4), bandwidth

def calc_wr(closes, n=14):
    if len(closes) < n:
        return None
    window = closes[-n:]
    hn = max(window)
    ln = min(window)
    if hn == ln:
        return 50.0
    return round((hn - closes[-1]) / (hn - ln) * 100, 2)

def calc_cci(closes, n=14):
    if len(closes) < n:
        return None
    window = closes[-n:]
    tp = closes[-1]
    ma_n = sum(window) / n
    md = sum(abs(x - ma_n) for x in window) / n
    if md == 0:
        return 0.0
    return round((tp - ma_n) / (0.015 * md), 2)

def calc_bias(closes, period):
    if len(closes) < period:
        return None
    ma_p = sum(closes[-period:]) / period
    if ma_p == 0:
        return None
    return round((closes[-1] - ma_p) / ma_p * 100, 2)

def calc_dmi(closes, n=14):
    if len(closes) < n * 2 + 1:
        if len(closes) < n + 1:
            return None, None, None
    plus_dm_list, minus_dm_list, tr_list = [], [], []
    for i in range(1, len(closes)):
        up = closes[i] - closes[i - 1]
        down = closes[i - 1] - closes[i]
        pdm = up if (up > down and up > 0) else 0.0
        mdm = down if (down > up and down > 0) else 0.0
        tr = abs(closes[i] - closes[i - 1])
        if tr == 0:
            tr = 0.0001
        plus_dm_list.append(pdm)
        minus_dm_list.append(mdm)
        tr_list.append(tr)
    if len(tr_list) < n:
        return None, None, None
    atr = sum(tr_list[:n]) / n
    pdm_sum = sum(plus_dm_list[:n])
    mdm_sum = sum(minus_dm_list[:n])
    pdi_series = []
    mdi_series = []
    dx_series = []
    for i in range(n, len(tr_list)):
        atr = (atr * (n - 1) + tr_list[i]) / n
        pdm_sum = (pdm_sum * (n - 1) + plus_dm_list[i]) / n
        mdm_sum = (mdm_sum * (n - 1) + minus_dm_list[i]) / n
        pdi = pdm_sum / atr * 100 if atr > 0 else 0
        mdi = mdm_sum / atr * 100 if atr > 0 else 0
        pdi_series.append(pdi)
        mdi_series.append(mdi)
        total = pdi + mdi
        dx = abs(pdi - mdi) / total * 100 if total > 0 else 0
        dx_series.append(dx)
    if not dx_series:
        return None, None, None
    if len(dx_series) < n:
        adx = sum(dx_series) / len(dx_series)
    else:
        adx_val = sum(dx_series[:n]) / n
        for i in range(n, len(dx_series)):
            adx_val = (adx_val * (n - 1) + dx_series[i]) / n
        adx = adx_val
    plus_di = round(pdi_series[-1], 2) if pdi_series else 0
    minus_di = round(mdi_series[-1], 2) if mdi_series else 0
    adx_prev = None
    if len(dx_series) >= n + 1:
        adx_prev = sum(dx_series[-(n+1):-1]) / n
    adx_rising = adx > adx_prev if adx_prev else True
    return plus_di, minus_di, round(adx, 2)

def calc_obv(closes):
    if len(closes) < 2:
        return None
    obv = 0
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            obv += 1
        elif closes[i] < closes[i - 1]:
            obv -= 1
    return obv

def calc_sar(closes, af_step=0.02, af_max=0.2):
    if len(closes) < 5:
        return None, None
    if len(closes) < 10:
        closes = closes[-10:] if len(closes) >= 10 else [closes[0]] * (10 - len(closes)) + closes
    is_long = closes[1] >= closes[0]
    if is_long:
        sar = closes[0]
        ep = closes[1]
    else:
        sar = closes[0]
        ep = closes[1]
    af = af_step
    for i in range(1, len(closes)):
        prev_sar = sar
        sar = prev_sar + af * (ep - prev_sar)
        if is_long:
            if i > 1:
                sar = min(sar, closes[i - 1], closes[i - 2] if i >= 2 else closes[i - 1])
            if closes[i] < sar:
                is_long = False
                sar = ep
                ep = closes[i]
                af = af_step
            else:
                if closes[i] > ep:
                    ep = closes[i]
                    af = min(af + af_step, af_max)
        else:
            if i > 1:
                sar = max(sar, closes[i - 1], closes[i - 2] if i >= 2 else closes[i - 1])
            if closes[i] > sar:
                is_long = True
                sar = ep
                ep = closes[i]
                af = af_step
            else:
                if closes[i] < ep:
                    ep = closes[i]
                    af = min(af + af_step, af_max)
    return round(sar, 4), "red" if is_long else "green"

def calc_max_drawdown(closes, lookback=None):
    data = closes[-lookback:] if lookback and len(closes) > lookback else closes
    if not data:
        return 0.0
    peak = data[0]
    max_dd = 0.0
    for v in data:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    return round(max_dd * 100, 2)

def calc_annualized_volatility(closes, trading_days=252):
    if len(closes) < 2:
        return None
    returns = []
    for i in range(1, len(closes)):
        r = (closes[i] - closes[i - 1]) / closes[i - 1]
        returns.append(r)
    mean_r = sum(returns) / len(returns)
    variance = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1) if len(returns) > 1 else 0
    daily_std = math.sqrt(variance)
    return round(daily_std * math.sqrt(trading_days) * 100, 2)

def calc_annualized_return(closes, trading_days=252):
    if len(closes) < 2 or closes[0] == 0:
        return None
    total_return = (closes[-1] - closes[0]) / closes[0]
    n_years = len(closes) / trading_days
    if n_years <= 0:
        return None
    ann_ret = (1 + total_return) ** (1 / n_years) - 1
    return round(ann_ret * 100, 2)

def calc_sharpe(closes, risk_free=0.025):
    ann_ret = calc_annualized_return(closes)
    ann_vol = calc_annualized_volatility(closes)
    if ann_ret is None or ann_vol is None or ann_vol == 0:
        return None
    return round((ann_ret / 100 - risk_free) / (ann_vol / 100), 2)

def calc_sortino(closes, risk_free=0.025):
    if len(closes) < 2:
        return None
    ann_ret = calc_annualized_return(closes)
    returns = []
    for i in range(1, len(closes)):
        r = (closes[i] - closes[i - 1]) / closes[i - 1] if closes[i - 1] != 0 else 0
        returns.append(r)
    target = risk_free / 252
    downside = [(r - target) for r in returns if r < target]
    if not downside:
        return None
    downside_var = sum(d ** 2 for d in downside) / len(returns)
    downside_std = math.sqrt(downside_var) * math.sqrt(252)
    if downside_std == 0:
        return None
    return round((ann_ret / 100 - risk_free) / downside_std, 2)

def calc_calmar(closes):
    ann_ret = calc_annualized_return(closes)
    max_dd = calc_max_drawdown(closes, lookback=252)
    if ann_ret is None or max_dd == 0:
        return None
    return round(ann_ret / max_dd, 2)

def calc_alpha_beta(fund_closes, benchmark_closes, risk_free=0.025):
    min_len = min(len(fund_closes), len(benchmark_closes))
    if min_len < 2:
        return None, None
    f = fund_closes[-min_len:]
    b = benchmark_closes[-min_len:]
    f_ret = [(f[i] - f[i-1]) / f[i-1] for i in range(1, len(f))]
    b_ret = [(b[i] - b[i-1]) / b[i-1] for i in range(1, len(b))]
    mean_f = sum(f_ret) / len(f_ret)
    mean_b = sum(b_ret) / len(b_ret)
    cov = sum((f_ret[i] - mean_f) * (b_ret[i] - mean_b) for i in range(len(f_ret))) / (len(f_ret) - 1)
    var_b = sum((r - mean_b) ** 2 for r in b_ret) / (len(b_ret) - 1)
    beta = round(cov / var_b, 2) if var_b > 0 else 1.0
    rf_daily = risk_free / 252
    alpha = round((mean_f - rf_daily) - beta * (mean_b - rf_daily), 4)
    annualized_alpha = round(((1 + alpha) ** 252 - 1) * 100, 2)
    return annualized_alpha, beta

def calc_all(closes, benchmark_closes=None):
    results = {}
    nav = closes[-1]
    results['nav'] = nav
    results['ma5'] = ma(closes, 5)
    results['ma10'] = ma(closes, 10)
    results['ma20'] = ma(closes, 20)
    results['ma60'] = ma(closes, 60)
    results['ma120'] = ma(closes, 120)
    results['ma250'] = ma(closes, 250)
    ma5, ma10, ma20, ma60 = results['ma5'], results['ma10'], results['ma20'], results['ma60']
    if all(x is not None for x in [ma5, ma10, ma20, ma60]):
        if ma5 > ma10 > ma20 > ma60:
            results['ma_align'] = "multi_long"
        elif ma5 < ma10 < ma20 < ma60:
            results['ma_align'] = "multi_short"
        else:
            results['ma_align'] = "mixed"
    else:
        results['ma_align'] = "insufficient_data"
    results['dif'], results['dea'], results['macd_hist'] = calc_macd(closes)
    if len(closes) >= 36:
        closes_prev = closes[:-1]
        dif_prev, dea_prev, _ = calc_macd(closes_prev)
        dif_now, dea_now = results['dif'], results['dea']
        if dif_prev is not None and dea_prev is not None:
            if dif_prev <= dea_prev and dif_now > dea_now:
                results['macd_cross'] = "golden"
            elif dif_prev >= dea_prev and dif_now < dea_now:
                results['macd_cross'] = "death"
            else:
                results['macd_cross'] = "none"
        else:
            results['macd_cross'] = "none"
    else:
        results['macd_cross'] = "none"
    results['kdj_k'], results['kdj_d'], results['kdj_j'] = calc_kdj(closes)
    results['rsi6'] = calc_rsi(closes, 6)
    results['rsi12'] = calc_rsi(closes, 12)
    results['rsi14'] = calc_rsi(closes, 14)
    results['boll_up'], results['boll_mb'], results['boll_dn'], results['boll_bw'] = calc_boll(closes)
    results['wr14'] = calc_wr(closes, 14)
    results['wr6'] = calc_wr(closes, 6)
    results['cci'] = calc_cci(closes, 14)
    results['bias6'] = calc_bias(closes, 6)
    results['bias12'] = calc_bias(closes, 12)
    results['bias24'] = calc_bias(closes, 24)
    results['plus_di'], results['minus_di'], results['adx'] = calc_dmi(closes)
    results['obv'] = calc_obv(closes)
    results['sar'], results['sar_dir'] = calc_sar(closes)
    results['max_drawdown'] = calc_max_drawdown(closes)
    results['max_drawdown_60d'] = calc_max_drawdown(closes, lookback=60)
    results['ann_volatility'] = calc_annualized_volatility(closes)
    results['ann_return'] = calc_annualized_return(closes)
    results['sharpe'] = calc_sharpe(closes)
    results['sortino'] = calc_sortino(closes)
    results['calmar'] = calc_calmar(closes)
    if benchmark_closes:
        results['alpha'], results['beta'] = calc_alpha_beta(closes, benchmark_closes)
    else:
        results['alpha'] = None
        results['beta'] = None
    return results

def format_output(r, date_str="", fund_name=""):
    lines = []
    lines.append("=" * 55)
    lines.append(f"  {fund_name} 技术指标计算结果" + (f"  {date_str}" if date_str else ""))
    lines.append("=" * 55)
    lines.append("")
    lines.append("【均线系】")
    lines.append(f"  MA5:{r.get('ma5','N/A')} MA10:{r.get('ma10','N/A')} MA20:{r.get('ma20','N/A')} MA60:{r.get('ma60','N/A')}")
    lines.append(f"  MA120:{r.get('ma120','N/A')} MA250:{r.get('ma250','N/A')}")
    align_map = {'multi_long': '多头排列(看多)', 'multi_short': '空头排列(看空)', 'mixed': '交叉/粘合', 'insufficient_data': '数据不足'}
    lines.append(f"  排列: {align_map.get(r.get('ma_align'), '未知')}")
    lines.append(f"  价>MA5:{r.get('nav',0)>r.get('ma5',0) if r.get('ma5') else 'N/A'} 价>MA20:{r.get('nav',0)>r.get('ma20',0) if r.get('ma20') else 'N/A'} 价>MA60:{r.get('nav',0)>r.get('ma60',0) if r.get('ma60') else 'N/A'}")
    lines.append("")
    lines.append("【趋势系】")
    dif, dea, hist = r.get('dif'), r.get('dea'), r.get('macd_hist')
    if dif is not None:
        bar = "红柱" if hist > 0 else "绿柱"
        cross = ""
        if abs(dif - dea) < 0.001:
            cross = " (金叉/死叉临界!)"
        lines.append(f"  MACD: DIF={dif} DEA={dea} 柱={hist} [{bar}]{cross}")
    else:
        lines.append("  MACD: 数据不足")
    pdi, mdi, adx = r.get('plus_di'), r.get('minus_di'), r.get('adx')
    if pdi is not None:
        lines.append(f"  DMI: +DI={pdi} -DI={mdi} ADX={adx}")
    sar, sar_dir = r.get('sar'), r.get('sar_dir')
    if sar is not None:
        lines.append(f"  SAR: {sar} [{'红(多头)' if sar_dir=='red' else '绿(空头)'}]")
    lines.append("")
    lines.append("【震荡系】")
    k, d, j = r.get('kdj_k'), r.get('kdj_d'), r.get('kdj_j')
    if k is not None:
        zone = "超买(K>80)" if k > 80 else "超卖(K<20)" if k < 20 else "中性"
        lines.append(f"  KDJ: K={k} D={d} J={j} [{zone}]")
    rsi = r.get('rsi14')
    if rsi is not None:
        zone = "超买(>70)" if rsi > 70 else "超卖(<30)" if rsi < 30 else "中性"
        lines.append(f"  RSI(6/12/14): {r.get('rsi6','N/A')} / {r.get('rsi12','N/A')} / {rsi} [{zone}]")
    wr = r.get('wr14')
    if wr is not None:
        zone = "超买(<20)" if wr < 20 else "超卖(>80)" if wr > 80 else "中性"
        lines.append(f"  WR(6/14): {r.get('wr6','N/A')} / {wr} [{zone}]")
    cci = r.get('cci')
    if cci is not None:
        zone = "超买(>100)" if cci > 100 else "超卖(<-100)" if cci < -100 else "中性"
        lines.append(f"  CCI(14): {cci} [{zone}]")
    lines.append("")
    lines.append("【通道系 BOLL (1.5x标准差)】")
    up, mb, dn, bw = r.get('boll_up'), r.get('boll_mb'), r.get('boll_dn'), r.get('boll_bw')
    if up is not None:
        nav = r.get('nav', 0)
        if nav > up:
            pos = "上轨上方(超买)"
        elif nav > mb:
            pos = "中轨-上轨(偏强)"
        elif nav > dn:
            pos = "下轨-中轨(偏弱)"
        else:
            pos = "下轨下方(超卖)"
        bw_status = "收口(变盘在即)" if bw < 5 else "开口" if bw > 15 else "正常"
        lines.append(f"  上轨:{up} 中轨:{mb} 下轨:{dn}")
        lines.append(f"  带宽:{bw}% [{bw_status}]  净值位置:{pos}")
    lines.append("")
    lines.append("【偏离系】")
    lines.append(f"  BIAS6:{r.get('bias6','N/A')}% BIAS12:{r.get('bias12','N/A')}% BIAS24:{r.get('bias24','N/A')}%")
    lines.append("")
    lines.append("【风险系】")
    lines.append(f"  最大回撤: {r.get('max_drawdown','N/A')}%  年化波动率: {r.get('ann_volatility','N/A')}%")
    lines.append(f"  年化收益: {r.get('ann_return','N/A')}%  夏普: {r.get('sharpe','N/A')}  索提诺: {r.get('sortino','N/A')}  卡玛: {r.get('calmar','N/A')}")
    lines.append("")
    lines.append("【专业指标】")
    alpha, beta = r.get('alpha'), r.get('beta')
    if alpha is not None:
        lines.append(f"  Alpha: {alpha}% [{'正=跑赢大盘' if alpha>0 else '负=跑输大盘'}]")
        lines.append(f"  Beta: {beta} [{'高弹性' if beta and beta>1.2 else '抗跌' if beta and beta<0.8 else '中性'}]")
    else:
        lines.append("  Alpha/Beta: 需要大盘基准数据，未计算")
    lines.append("")
    lines.append("=" * 55)
    return '\n'.join(lines)

def fetch_benchmark_data(days=260):
    url = (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get?"
        "secid=1.000001&fields1=f1,f2,f3,f4,f5,f6&"
        "fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&"
        f"klt=101&fqt=1&end=20500101&lmt={days}"
    )
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode('utf-8'))
        klines = data.get('data', {}).get('klines', [])
        closes = []
        for k in klines:
            closes.append(float(k.split(',')[2]))
        return closes
    except Exception:
        return None


def detect_double_top(closes, lookback=20, peak_tolerance=0.03, min_pullback=0.05):
    if len(closes) < lookback:
        return None
    window = closes[-lookback:]
    peak_a_idx = 0
    peak_a = window[0]
    for i in range(len(window)):
        if window[i] > peak_a:
            peak_a = window[i]
            peak_a_idx = i
    valley = min(window[peak_a_idx:])
    valley_idx = peak_a_idx + window[peak_a_idx:].index(valley)
    if valley_idx >= len(window) - 1:
        return None
    peak_b = max(window[valley_idx + 1:])
    peak_b_idx = window.index(peak_b, valley_idx + 1)
    if peak_b_idx == len(window) - 1 or peak_b_idx == len(window) - 2:
        peak_b_current = True
    else:
        peak_b_current = (peak_b_idx >= len(window) - 3)
    if peak_a == 0:
        return None
    pct_diff = abs(peak_a - peak_b) / peak_a * 100
    pullback = (peak_a - valley) / peak_a * 100 if peak_a > 0 else 0
    if pct_diff < peak_tolerance * 100 and pullback > min_pullback * 100:
        if closes[-1] < valley:
            return ("confirmed", peak_a, peak_b, valley, pct_diff)
        else:
            return ("forming", peak_a, peak_b, valley, pct_diff)
    return None


def scan_signals(r):
    signals = []
    nav = r.get('nav', 0)
    ma5, ma10, ma20, ma60 = r.get('ma5'), r.get('ma10'), r.get('ma20'), r.get('ma60')
    dif, dea, hist = r.get('dif'), r.get('dea'), r.get('macd_hist')
    macd_cross = r.get('macd_cross', 'none')
    k, d, j = r.get('kdj_k'), r.get('kdj_d'), r.get('kdj_j')
    rsi6, rsi12, rsi14 = r.get('rsi6'), r.get('rsi12'), r.get('rsi14')
    wr6, wr14 = r.get('wr6'), r.get('wr14')
    cci = r.get('cci')
    boll_up, boll_mb, boll_dn = r.get('boll_up'), r.get('boll_mb'), r.get('boll_dn')
    bias6, bias12, bias24 = r.get('bias6'), r.get('bias12'), r.get('bias24')
    plus_di, minus_di, adx = r.get('plus_di'), r.get('minus_di'), r.get('adx')
    sar, sar_dir = r.get('sar'), r.get('sar_dir')
    max_dd_60d = r.get('max_drawdown_60d')
    ann_vol = r.get('ann_volatility')
    sharpe = r.get('sharpe')

    if ma5 and ma10 and ma5 < ma10:
        signals.append(("MA-7", "sell", 5, f"MA5({ma5})<MA10({ma10}) 短期均线死叉"))
    if ma5 and ma10 and ma5 > ma10 and ma20 and ma5 > ma20 and ma60 and ma5 > ma60:
        signals.append(("MA-1", "buy", 8, f"净值({nav})>MA20({ma20})>MA60({ma60}) 多头趋势"))
    if macd_cross == "golden":
        signals.append(("TR-1", "buy", 10, "MACD金叉"))
    if macd_cross == "death":
        signals.append(("TR-2", "sell", 10, "MACD死叉"))
    if hist is not None and hist < 0:
        signals.append(("TR-5", "sell", 8, f"MACD绿柱(柱={hist})"))
    if hist is not None and hist > 0:
        signals.append(("TR-4", "buy", 6, f"MACD红柱(柱={hist})"))
    if sar_dir == "red":
        signals.append(("TR-9", "buy", 5, f"SAR红点(多头) SAR={sar}"))
    if sar_dir == "green":
        signals.append(("TR-10", "sell", 5, f"SAR绿点(空头) SAR={sar}"))
    if wr14 is not None and wr14 < 20:
        signals.append(("OS-10", "sell", 6, f"WR超买({wr14}<20)"))
    if wr14 is not None and wr14 > 80:
        signals.append(("OS-9", "buy", 6, f"WR超卖({wr14}>80)"))
    if cci is not None and cci > 100:
        signals.append(("OS-12", "sell", 5, f"CCI超买({cci}>100)"))
    if cci is not None and cci < -100:
        signals.append(("OS-11", "buy", 5, f"CCI超卖({cci}<-100)"))
    if k is not None and k > 80:
        signals.append(("OS-6", "sell", 5, f"KDJ超买(K={k}>80)"))
    if k is not None and k < 20:
        signals.append(("OS-5", "buy", 5, f"KDJ超卖(K={k}<20)"))
    if rsi14 is not None and rsi14 > 80:
        signals.append(("OS-6b", "sell", 5, f"RSI极度超买({rsi14}>80)"))
    if rsi14 is not None and rsi14 < 20:
        signals.append(("OS-5b", "buy", 5, f"RSI极度超卖({rsi14}<20)"))
    if boll_up and nav > boll_up:
        signals.append(("BOLL-4", "sell", 6, f"净值({nav})>BOLL上轨({boll_up}) 超买"))
    if boll_dn and nav < boll_dn:
        signals.append(("BOLL-3", "buy", 6, f"净值({nav})<BOLL下轨({boll_dn}) 超卖"))
    if bias6 is not None and bias6 > 5:
        signals.append(("DV-1", "sell", 4, f"BIAS6超买({bias6}%>5%)"))
    if bias6 is not None and bias6 < -5:
        signals.append(("DV-2", "buy", 4, f"BIAS6超卖({bias6}%<-5%)"))
    if max_dd_60d is not None and max_dd_60d > 15:
        signals.append(("RK-1", "sell", 5, f"近60日最大回撤{max_dd_60d}%>15%"))
    if ann_vol is not None and ann_vol > 30:
        signals.append(("RK-3", "sell", 5, f"年化波动率{ann_vol}%>30% 高波动"))
    if sharpe is not None and sharpe > 1.5:
        signals.append(("RK-6", "buy", 8, f"夏普比率{sharpe}>1.5 优秀"))
    if sharpe is not None and sharpe < 0:
        signals.append(("RK-4", "sell", 6, f"夏普比率{sharpe}<0 风险回报差"))
    if plus_di and minus_di and plus_di > minus_di:
        signals.append(("DMI-1", "buy", 6, f"+DI({plus_di})>-DI({minus_di}) 多头占优"))
    if plus_di and minus_di and plus_di < minus_di:
        signals.append(("DMI-2", "sell", 6, f"+DI({plus_di})<-DI({minus_di}) 空头占优"))
    return signals


def format_signals(signals):
    if not signals:
        return "  (无信号触发)"
    buy_sigs = [(s[0], s[3], s[2]) for s in signals if s[1] == "buy"]
    sell_sigs = [(s[0], s[3], s[2]) for s in signals if s[1] == "sell"]
    buy_weight = sum(s[2] for s in signals if s[1] == "buy")
    sell_weight = sum(s[2] for s in signals if s[1] == "sell")
    lines = []
    lines.append(f"  买入信号: {len(buy_sigs)}条 (权重合计 {buy_weight})")
    for sid, desc, w in buy_sigs:
        lines.append(f"    +{sid} [权重{w}] {desc}")
    lines.append(f"  卖出信号: {len(sell_sigs)}条 (权重合计 {sell_weight})")
    for sid, desc, w in sell_sigs:
        lines.append(f"    -{sid} [权重{w}] {desc}")
    lines.append(f"  多空力量: 买{buy_weight} vs 卖{sell_weight} → {'偏多' if buy_weight > sell_weight else '偏空' if sell_weight > buy_weight else '均衡'}")
    return '\n'.join(lines)


# ============================================================
# 自适应分析框架（v2.0 新增）
# ============================================================

def detect_regime(closes):
    if len(closes) < 65:
        return {"trend": "unknown", "trend_strength": "weak",
                "volatility": "unknown", "vol_factor": 1.0,
                "adx": 0, "price_vs_ma60": 0, "ma60_slope": 0, "ann_vol": 0}

    r = calc_all(closes)
    ann_vol = r.get('ann_volatility') or 0
    ma60 = r.get('ma60') or 0
    ma20 = r.get('ma20') or 0
    nav = closes[-1]
    adx = r.get('adx') or 0

    if ann_vol > 30:
        vol_regime = "high"
        vol_factor = round(ann_vol / 25, 2)
    elif ann_vol < 20:
        vol_regime = "low"
        vol_factor = 0.8
    else:
        vol_regime = "medium"
        vol_factor = 1.0

    ma60_5d = sum(closes[-65:-5]) / 60
    ma60_slope = (ma60 - ma60_5d) / ma60_5d * 100 if ma60_5d > 0 else 0
    price_vs_ma60 = (nav - ma60) / ma60 * 100 if ma60 > 0 else 0

    if price_vs_ma60 > 5 and ma60_slope > 0:
        trend = "strong_up"
    elif price_vs_ma60 > 0 and ma60_slope >= 0:
        trend = "up"
    elif price_vs_ma60 < -5 and ma60_slope < 0:
        trend = "strong_down"
    elif price_vs_ma60 < 0 and ma60_slope <= 0:
        trend = "down"
    else:
        trend = "sideways"

    if adx > 25:
        trend_strength = "strong"
    elif adx > 20:
        trend_strength = "moderate"
    else:
        trend_strength = "weak"

    return {
        "trend": trend,
        "trend_strength": trend_strength,
        "volatility": vol_regime,
        "vol_factor": vol_factor,
        "adx": round(adx, 1),
        "price_vs_ma60": round(price_vs_ma60, 1),
        "ma60_slope": round(ma60_slope, 2),
        "ann_vol": round(ann_vol, 1),
    }


def backtest_signals(closes, lookback=30, horizon=3):
    if len(closes) < lookback + horizon + 70:
        lookback = max(30, len(closes) - horizon - 70)
    start = max(len(closes) - lookback - horizon, 70)
    end = len(closes) - horizon
    signal_stats = {}

    for i in range(start, end):
        day_closes = closes[:i + 1]
        if len(day_closes) < 70:
            continue
        r = calc_all(day_closes)
        sigs = scan_signals(r)
        dt = detect_double_top(day_closes)
        if dt and dt[0] == "forming":
            sigs.append(("铁律1", "sell", 20, "双顶"))
        elif dt and dt[0] == "confirmed":
            sigs.append(("铁律1", "sell", 30, "双顶确认"))

        fwd_ret = (closes[i + horizon] - day_closes[-1]) / day_closes[-1] * 100

        for sig_id, direction, weight, desc in sigs:
            if sig_id not in signal_stats:
                signal_stats[sig_id] = {
                    "triggered": 0, "correct": 0, "total_return": 0.0,
                    "direction": direction, "descriptions": []
                }
            signal_stats[sig_id]["triggered"] += 1
            signal_stats[sig_id]["total_return"] += fwd_ret
            signal_stats[sig_id]["descriptions"].append(desc)
            is_buy = direction == "buy"
            if (is_buy and fwd_ret > 0) or (not is_buy and fwd_ret < 0):
                signal_stats[sig_id]["correct"] += 1

    results = {}
    for sig_id, stats in signal_stats.items():
        n = stats["triggered"]
        if n < 2:
            wm = 1.0
            acc = None
        else:
            acc = stats["correct"] / n
            avg_ret = stats["total_return"] / n
            if acc >= 0.65:
                wm = 1.5
            elif acc >= 0.55:
                wm = 1.0
            elif acc >= 0.45:
                wm = 0.7
            else:
                wm = 0.3
        results[sig_id] = {
            "accuracy": round(acc * 100, 1) if acc is not None else None,
            "avg_return": round(stats["total_return"] / n, 2) if n > 0 else 0,
            "triggered": n,
            "weight_multiplier": wm,
            "direction": stats["direction"],
        }

    return results


def adaptive_scan(results, backtest_stats, regime):
    base_signals = scan_signals(results)
    vol_factor = regime.get("vol_factor", 1.0)
    trend = regime.get("trend", "sideways")
    trend_strength = regime.get("trend_strength", "weak")

    if trend == "strong_up":
        sell_trend_factor, buy_trend_factor = 0.3, 1.0
    elif trend == "up":
        sell_trend_factor, buy_trend_factor = 0.7, 1.0
    elif trend == "strong_down":
        sell_trend_factor, buy_trend_factor = 1.0, 0.3
    elif trend == "down":
        sell_trend_factor, buy_trend_factor = 1.0, 0.7
    else:
        sell_trend_factor, buy_trend_factor = 1.0, 1.0

    nav = results.get("nav", 0)
    bias6 = results.get("bias6")
    wr14 = results.get("wr14")
    cci = results.get("cci")
    kdj_k = results.get("kdj_k")

    adapted = []
    adjustments = []

    for sig_id, direction, weight, desc in base_signals:
        orig_w = weight
        reasons = []

        if direction == "sell":
            weight *= sell_trend_factor
            if sell_trend_factor != 1.0:
                reasons.append(f"趋势{trend}×{sell_trend_factor}")
        else:
            weight *= buy_trend_factor
            if buy_trend_factor != 1.0:
                reasons.append(f"趋势{trend}×{buy_trend_factor}")

        if sig_id in ("TR-9", "TR-10") and trend_strength == "weak":
            weight *= 0.3
            reasons.append("ADX弱趋势SAR×0.3")

        if sig_id in backtest_stats:
            bt = backtest_stats[sig_id]
            wm = bt["weight_multiplier"]
            weight *= wm
            if wm != 1.0:
                acc_str = f"{bt['accuracy']:.0f}%" if bt['accuracy'] else "?"
                reasons.append(f"回测{acc_str}×{wm}")

        weight = round(weight)

        adapted.append((sig_id, direction, weight, desc))
        if reasons:
            adjustments.append((sig_id, orig_w, weight, " | ".join(reasons)))

    return adapted, adjustments


def detect_double_top_adaptive(closes, regime):
    dt = detect_double_top(closes)
    if not dt:
        return None

    status, peak_a, peak_b, neckline, pct_diff = dt

    if regime.get("trend") == "strong_up":
        if regime.get("price_vs_ma60", 0) > 10:
            return ("observation", peak_a, peak_b, neckline, pct_diff,
                    "强上升趋势中双顶降级为观察（价格远超MA60，可能为上涨中继）")

    return (status, peak_a, peak_b, neckline, pct_diff, "")


def format_regime(regime):
    trend_map = {
        "strong_up": "🟢 强上升趋势", "up": "🟢 上升趋势",
        "sideways": "🟡 震荡", "down": "🔴 下降趋势",
        "strong_down": "🔴 强下降趋势", "unknown": "⚪ 未知"
    }
    vol_map = {"high": "🔴 高波动", "medium": "🟡 中波动",
               "low": "🟢 低波动", "unknown": "⚪ 未知"}
    strength_map = {"strong": "强(ADX>25)", "moderate": "中(ADX20-25)",
                    "weak": "弱(ADX<20)"}

    lines = []
    lines.append("【市场状态识别】")
    lines.append(f"  趋势: {trend_map.get(regime['trend'], '?')}")
    lines.append(f"  趋势强度: {strength_map.get(regime['trend_strength'], '?')} (ADX={regime['adx']})")
    lines.append(f"  波动率: {vol_map.get(regime['volatility'], '?')} (年化{regime['ann_vol']}%)")
    lines.append(f"  波动系数: ×{regime['vol_factor']}")
    lines.append(f"  价偏MA60: {regime['price_vs_ma60']}%")
    lines.append(f"  MA60斜率: {regime['ma60_slope']}%/5日")
    if regime['trend'] in ('strong_up', 'strong_down'):
        lines.append(f"  ⚡ 强趋势模式: {'卖出信号×0.3(抑制恐慌), 买入信号正常' if regime['trend']=='strong_up' else '买入信号×0.3(不接飞刀), 卖出信号正常'}")
    if regime['trend_strength'] == 'weak':
        lines.append(f"  ⚡ 弱趋势模式: SAR信号×0.3（ADX<20时SAR不可靠）")
    return '\n'.join(lines)


def format_backtest(bt_stats):
    if not bt_stats:
        return "【回测校准】\n  (数据不足，无法回测)"

    valid = {k: v for k, v in bt_stats.items() if v['accuracy'] is not None}
    if not valid:
        return "【回测校准】\n  (触发次数不足，使用默认权重)"

    sorted_sigs = sorted(valid.items(), key=lambda x: x[1]['accuracy'])

    lines = []
    lines.append("【回测校准】")
    lines.append(f"  回测窗口: 近{max(v['triggered'] for v in valid.values())}次触发, 3日前瞻")

    lines.append("  📊 信号准确率排行:")
    for sig_id, stats in sorted_sigs:
        acc = stats['accuracy']
        avg = stats['avg_return']
        n = stats['triggered']
        wm = stats['weight_multiplier']
        direction = "买" if stats['direction'] == 'buy' else "卖"
        mark = "⚠️" if acc < 45 else "✅" if acc >= 65 else "  "
        lines.append(f"    {mark} {sig_id:<10} {direction} {acc:>5.1f}% 均{avg:>+6.2f}% x{n} → 权重×{wm}")

    dangerous = [(k, v) for k, v in sorted_sigs if v['accuracy'] < 45]
    if dangerous:
        lines.append(f"  ⚠️ 危险信号(准确率<45%): {', '.join(k for k,_ in dangerous)}")

    reliable = [(k, v) for k, v in sorted_sigs if v['accuracy'] >= 65]
    if reliable:
        lines.append(f"  ✅ 可靠信号(准确率≥65%): {', '.join(k for k,_ in reliable)}")

    return '\n'.join(lines)


def format_adaptive_signals(signals, adjustments):
    buy_sigs = [(s[0], s[3], s[2]) for s in signals if s[1] == "buy"]
    sell_sigs = [(s[0], s[3], s[2]) for s in signals if s[1] == "sell"]
    buy_weight = sum(s[2] for s in signals if s[1] == "buy")
    sell_weight = sum(s[2] for s in signals if s[1] == "sell")
    net = buy_weight - sell_weight

    lines = []
    lines.append("【自适应信号扫描】")
    lines.append(f"  买入信号: {len(buy_sigs)}条 (权重合计 {buy_weight})")
    for sid, desc, w in sorted(buy_sigs, key=lambda x: -x[2]):
        adj = next((f" [原{oa}→{na}]" for s, oa, na, r in adjustments if s == sid), "")
        lines.append(f"    +{sid} [权重{w}]{adj} {desc}")
    lines.append(f"  卖出信号: {len(sell_sigs)}条 (权重合计 {sell_weight})")
    for sid, desc, w in sorted(sell_sigs, key=lambda x: -x[2]):
        adj = next((f" [原{oa}→{na}]" for s, oa, na, r in adjustments if s == sid), "")
        lines.append(f"    -{sid} [权重{w}]{adj} {desc}")

    lines.append(f"  多空力量: 买{buy_weight} vs 卖{sell_weight} → 净分{net}")

    if net > 15:
        action = "买入/加仓"
    elif net > 0:
        action = "持有偏多"
    elif net > -15:
        action = "持有偏空"
    elif net > -30:
        action = "减仓"
    else:
        action = "清仓"
    lines.append(f"  操作建议: {action}")

    return '\n'.join(lines)


def main():
    code = None
    navs_raw = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == '--code' and i + 1 < len(sys.argv):
            code = sys.argv[i + 1]
        elif arg == '--navs' and i + 1 < len(sys.argv):
            navs_raw = sys.argv[i + 1]

    date_str = ""
    fund_name = ""

    if code:
        print(f"正在获取基金 {code} 的历史净值数据...")
        records = fetch_nav_data(code)
        if not records:
            print(f"获取基金 {code} 数据失败")
            sys.exit(1)
        records.reverse()
        closes = [r['nav'] for r in records]
        date_str = records[-1]['date']
        fund_name = f"基金{code}"
        print(f"获取到 {len(records)} 条净值数据，日期范围: {records[0]['date']} ~ {records[-1]['date']}")
        benchmark_closes = fetch_benchmark_data(days=len(closes))
    elif navs_raw:
        closes = [float(x.strip()) for x in navs_raw.split(',')]
        benchmark_closes = None
    else:
        print("用法:")
        print("  python3 indicators.py --code 002112        # 从API获取")
        print("  python3 indicators.py --navs 6.0,6.1,5.9   # 传入净值")
        print()
        print("或粘贴净值数据（每行一个净值），按Ctrl+D结束:")
        try:
            lines = sys.stdin.read().strip().split('\n')
            closes = [float(x.strip()) for x in lines if x.strip()]
        except:
            print("输入格式错误")
            sys.exit(1)
        benchmark_closes = None

    if len(closes) < 30:
        print(f"警告: 仅 {len(closes)} 条数据，部分指标无法计算（建议至少60条）")

    results = calc_all(closes, benchmark_closes)
    output = format_output(results, date_str, fund_name)
    print(output)

    # ===== 自适应分析框架 v2.0 =====

    # ① 市场状态识别
    regime = detect_regime(closes)
    print(format_regime(regime))
    print()

    # ② 回测校准
    lookback = 30 if regime.get('volatility') == 'high' else 60
    bt_stats = backtest_signals(closes, lookback=lookback, horizon=3)
    print(format_backtest(bt_stats))
    print()

    # ③ 自适应信号扫描
    adapted_signals, adjustments = adaptive_scan(results, bt_stats, regime)

    # ④ 自适应双顶检测
    dt_adaptive = detect_double_top_adaptive(closes, regime)
    if dt_adaptive:
        status, peak_a, peak_b, neckline, pct_diff, note = dt_adaptive
        if status == "forming":
            adapted_signals.append(("铁律1", "sell", 20,
                f"双顶形成中: A={peak_a:.4f} B={peak_b:.4f} 差{pct_diff:.2f}% 颈线={neckline:.4f}"))
            print(f"⚠️ 铁律1: 双顶形成中  A={peak_a:.4f} B={peak_b:.4f} 颈线={neckline:.4f}")
            if note:
                print(f"   💡 {note}")
        elif status == "observation":
            adapted_signals.append(("铁律1-观察", "sell", 5,
                f"双顶(降级观察): A={peak_a:.4f} B={peak_b:.4f} 颈线={neckline:.4f}"))
            print(f"💡 铁律1(观察): 双顶形态存在但在强上升趋势中降级")
            print(f"   A={peak_a:.4f} B={peak_b:.4f} 颈线={neckline:.4f}")
            print(f"   {note}")
        elif status == "confirmed":
            adapted_signals.append(("铁律1", "sell", 30,
                f"双顶已确认: 颈线{neckline:.4f}已跌破 → 清仓!"))
            print(f"🚨 铁律1: 双顶已确认! 颈线{neckline:.4f}跌破 → 清仓!")

    print()
    print(format_adaptive_signals(adapted_signals, adjustments))

if __name__ == '__main__':
    main()
