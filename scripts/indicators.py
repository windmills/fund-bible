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
    for i in range(-period, 0):
        diff = closes[i] - closes[i - 1]
        if diff > 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
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
    if len(closes) < n + 1:
        return None, None, None
    plus_dm, minus_dm, tr_list = [], [], []
    for i in range(-n, 0):
        up = closes[i] - closes[i - 1]
        down = closes[i - 1] - closes[i]
        if up > down and up > 0:
            plus_dm.append(up)
        else:
            plus_dm.append(0)
        if down > up and down > 0:
            minus_dm.append(down)
        else:
            minus_dm.append(0)
        tr_list.append(abs(closes[i] - closes[i - 1]))
    atr = sum(tr_list) / n if tr_list else 1
    plus_di = round(sum(plus_dm) / n / atr * 100, 2) if atr > 0 else 0
    minus_di = round(sum(minus_dm) / n / atr * 100, 2) if atr > 0 else 0
    dx_list = []
    for i in range(n):
        total = plus_dm[i] + minus_dm[i]
        if total > 0:
            dx_list.append(abs(plus_dm[i] - minus_dm[i]) / total * 100)
    adx = round(sum(dx_list) / len(dx_list), 2) if dx_list else 0
    return plus_di, minus_di, adx

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
    is_long = closes[-1] > closes[-5]
    ep = max(closes[-5:]) if is_long else min(closes[-5:])
    af = af_step
    sar = min(closes[-5:-1]) if is_long else max(closes[-5:-1])
    for i in range(-4, 0):
        sar = sar + af * (ep - sar)
        if is_long:
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

def calc_max_drawdown(closes):
    peak = closes[0]
    max_dd = 0.0
    for v in closes:
        if v > peak:
            peak = v
        dd = (peak - v) / peak
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
    if len(closes) < 2:
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
        r = (closes[i] - closes[i - 1]) / closes[i - 1]
        returns.append(r)
    downside = [r for r in returns if r < 0]
    if not downside:
        return None
    downside_var = sum(r ** 2 for r in downside) / len(downside)
    downside_std = math.sqrt(downside_var) * math.sqrt(252)
    if downside_std == 0:
        return None
    return round((ann_ret / 100 - risk_free) / downside_std, 2)

def calc_calmar(closes):
    ann_ret = calc_annualized_return(closes)
    max_dd = calc_max_drawdown(closes)
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

def main():
    code = None
    navs_raw = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == '--code' and i + 1 < len(sys.argv):
            code = sys.argv[i + 1]
        elif arg == '--navs' and i + 1 < len(sys.argv):
            navs_raw = sys.argv[i + 1]

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
    elif navs_raw:
        closes = [float(x.strip()) for x in navs_raw.split(',')]
        date_str = ""
        fund_name = "自定义数据"
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

    if len(closes) < 30:
        print(f"警告: 仅 {len(closes)} 条数据，部分指标无法计算（建议至少60条）")

    results = calc_all(closes)
    output = format_output(results, date_str if 'date_str' in dir() else "", fund_name if 'fund_name' in dir() else "")
    print(output)

if __name__ == '__main__':
    main()
