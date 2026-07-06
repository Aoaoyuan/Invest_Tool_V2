# -*- coding: utf-8 -*-
import sys, os, json, math, traceback, time, uuid
from datetime import datetime
import requests, pandas as pd, numpy as np
from flask import Flask, request, jsonify, send_from_directory, abort

app = Flask(__name__)
TMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_charts")
os.makedirs(TMP_DIR, exist_ok=True)
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com"}

# ── 股票代码与市场转换 ──
def tc(code):
    if code.startswith("6"): return "sh" + code
    return "sz" + code

def f10_code(code):
    if code.startswith("6"): return "SH" + code
    return "SZ" + code

# ── 获取公司名称 ──
def get_name(code):
    try:
        r = requests.get("https://searchadapter.eastmoney.com/api/suggest/get",
            params={"input": code, "type": 14, "token": "D43BF722C8E33BDC906FB84D85E326E8"},
            headers=HEADERS, timeout=10)
        for item in r.json().get("QuotationCodeTable", {}).get("Data", []):
            if item.get("Code") == code:
                return item.get("Name", "?")
    except: pass
    return "?"

# ── 获取K线数据 ──
def get_kline(code):
    """获取K线数据 - 腾讯API 精细分段 + 去重"""
    tc_code = tc(code)
    all_days = []
    # 每段最多返回约640条，用5年窗口精细分段
    years = list(range(1990, 2030, 5))
    segments = [(f"{y}-01-01", f"{y+4}-12-31") for y in years]
    
    for ss, se in segments:
        try:
            r = requests.get(f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tc_code},day,{ss},{se},2000,qfq",
                             headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            days = r.json().get("data", {}).get(tc_code, {}).get("qfqday", [])
            if days: all_days.extend(days)
        except: pass
        time.sleep(0.2)
    
    if not all_days:
        try:
            r = requests.get(f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tc_code},day,,,3000,qfq",
                             headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            all_days = r.json().get("data", {}).get(tc_code, {}).get("qfqday", [])
        except: pass

    # 去重（按日期）
    seen = set()
    unique = []
    for day in all_days:
        if day[0] not in seen:
            seen.add(day[0])
            unique.append(day)
    unique.sort(key=lambda x: x[0])
    
    if not unique: return None
    
    dates = [d[0] for d in unique]
    opens = [float(d[1]) for d in unique]
    closes = [float(d[2]) for d in unique]
    highs = [float(d[3]) for d in unique]
    lows = [float(d[4]) for d in unique]
    volumes = [float(d[5]) for d in unique]
    
    return {"dates": dates, "opens": opens, "highs": highs, "lows": lows,
            "closes": closes, "volumes": volumes, "n": len(unique)}
# ── 获取公司详细信息 (F10) ──
def get_company_info(code):
    try:
        url = "https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/CompanySurveyAjax?code=" + f10_code(code)
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.encoding = "utf-8"
        if "gsmc" not in r.text: return {}
        d = json.loads(r.text).get("jbzl", {})
        info = {}
        info["gsmc"] = d.get("gsmc", "")
        info["sshy"] = d.get("sshy", "")
        info["zjl"] = d.get("zjl", "")
        info["gsjj"] = d.get("gsjj", "").strip()[:300]
        info["qy"] = d.get("qy", "")
        info["zczb"] = d.get("zczb", "")
        info["gyrs"] = d.get("gyrs", "")
        return info
    except: return {}


# ── 增强的大事记生成器 ──
def gen_events(code, kd, info):
    """为任意股票自动生成完善的大事记"""
    # 同仁堂手工精编
    if code == "600085":
        return [
            ("1997-06-25","A股上市","同仁堂A股上交所上市，发行价7.08元","corporate",5),
            ("2000-03-18","同仁堂科技分拆","科技(01666.HK)在香港创业板上市","corporate",5),
            ("2003-04","非典抗疫","加班生产抗非典中药日均200万瓶，承诺不涨价","positive",4),
            ("2007-10","A股6124见顶","上证6124见顶，随大盘大幅回落","negative",4),
            ("2008-01","全球金融危机","次贷危机蔓延至A股，大幅回调","negative",4),
            ("2010-07-08","同仁堂国药上市","国药(03613.HK)在香港联交所上市","corporate",4),
            ("2014-11","沪港通开通","沪港通正式开通，A+H双市场受益","market",3),
            ("2015-06-12","A股5178见顶","大盘创5178点后崩盘千股跌停","negative",5),
            ("2016-01","熔断机制","A股熔断引发暴跌，单月跌超20%","negative",4),
            ("2016-12","中医药法通过","中医药法正式通过，里程碑","policy",4),
            ("2017-01","中医药法实施","首部中医药法实施，行业迎政策红利","positive",4),
            ("2018-12-15","过期蜂蜜门爆发","子公司被曝使用过期蜂蜜生产产品，舆论哗然","scandal",5),
            ("2019-02-11","蜂蜜门处罚落地","被罚款1400万，撤销中国质量奖称号","scandal",5),
            ("2020-01-20","新冠疫情爆发","新冠疫情全面爆发，中药治疗方案受关注","positive",5),
            ("2021-01","中医药政策密集","国务院印发加快中医药特色发展若干措施","policy",4),
            ("2021-07","股价创历史新高","股价突破50元（前复权），创上市以来新高","positive",5),
            ("2021-12","全年涨幅超130%","2021年涨幅超130%，上市以来最佳年份","positive",4),
            ("2022-04","营收突破150亿","2021年度营收突破150亿元大关","positive",3),
            ("2022-10","二十大促中医药","二十大报告强调促进中医药传承创新发展","policy",3),
            ("2025-01","中医药振兴政策","国家进一步出台中医药振兴发展支持政策","policy",3),
        ]

    evts = []
    dates = kd["dates"]
    closes = [float(c) for c in kd["closes"]]
    if not dates: return evts

    # 1. 上市
    evts.append((dates[0], "A股上市", f"股票{code}在A股上市交易","corporate",5))

    # 2. 历史最高价
    if len(closes) > 60:
        mi = max(range(len(closes)), key=lambda i: closes[i])
        evts.append((dates[mi], "股价创历史最高", f"前复权收盘价达{closes[mi]:.2f}元创新高","positive",4))

    # 3. 寻找暴跌日与暴涨日（top/bottom 3）
    if len(closes) > 60:
        changes = [(i, (closes[i]/closes[i-1]-1)*100) for i in range(1, len(closes)) if closes[i-1] != 0]
        # 暴跌
        drops = sorted(changes, key=lambda x: x[1])
        seen_d = set()
        for idx, pct in drops:
            if len([e for e in evts if e[0] == dates[idx]]) > 0: continue
            if pct < -9.5: evts.append((dates[idx], f"暴跌{pct:.1f}%", f"单日暴跌{pct:.1f}%，市场恐慌性抛售","negative",5)); seen_d.add(idx)
            elif pct < -7: evts.append((dates[idx], f"大跌{pct:.1f}%", f"单日大跌{pct:.1f}%","negative",4))
            elif pct < -5: evts.append((dates[idx], f"下挫{pct:.1f}%", f"单日下跌{pct:.1f}%","negative",3))
            if len([e for e in evts[3:] if e[3]=="negative"]) >= 5: break
        # 暴涨
        gains = sorted(changes, key=lambda x: x[1], reverse=True)
        for idx, pct in gains:
            if len([e for e in evts if e[0] == dates[idx]]) > 0: continue
            if pct > 9.5: evts.append((dates[idx], f"暴涨+{pct:.1f}%", f"单日暴涨+{pct:.1f}%，资金抢筹","positive",5)); seen_d.add(idx)
            elif pct > 7: evts.append((dates[idx], f"大涨+{pct:.1f}%", f"单日大涨+{pct:.1f}%","positive",4))
            elif pct > 5: evts.append((dates[idx], f"拉升+{pct:.1f}%", f"单日拉升+{pct:.1f}%","positive",3))
            if len([e for e in evts[3:] if e[3]=="positive"]) >= 5: break

    # 4. 重大市场事件
    first_y = int(dates[0][:4])
    last_y = int(dates[-1][:4])
    major = [
        ("2005-06","股权分置改革","A股启动股权分置改革，市场制度性变革","policy",4),
        ("2007-10","A股6124见顶","上证指数6124点历史大顶后回落","negative",4),
        ("2008-01","全球金融危机","次贷危机引发全球金融海啸","negative",4),
        ("2009-03","四万亿刺激","国家出台四万亿经济刺激计划","policy",3),
        ("2014-11","沪港通开通","沪港通正式开闸","market",3),
        ("2015-06-12","A股5178见顶","杠杆牛市崩盘千股跌停","negative",5),
        ("2016-01","熔断机制","A股熔断机制引发连锁暴跌","negative",4),
        ("2019-06","科创板开板","科创板正式开板注册制启航","market",3),
        ("2020-01-20","新冠疫情爆发","新冠疫情全面冲击全球经济","positive",3),
        ("2020-03","全球股市熔断","疫情引发全球主要股市熔断潮","negative",3),
        ("2024-02","新国九条","国务院新国九条推动资本市场高质量发展","policy",3),
    ]
    for md, mt, mdet, mtyp, mlv in major:
        my = int(md[:4])
        if first_y <= my <= last_y and not any(e[1] == mt for e in evts):
            evts.append((md, mt, mdet, mtyp, mlv))

    # 5. 年度涨跌幅极端年份
    if len(closes) > 250:
        yearly = {}
        for i, d in enumerate(dates):
            y = d[:4]
            if y not in yearly: yearly[y] = {"first": closes[i], "last": closes[i]}
            yearly[y]["last"] = closes[i]
        yrets = [(y, (v["last"]/v["first"]-1)*100) for y, v in yearly.items() if v["first"] > 0 and y != dates[0][:4]]
        yrets.sort(key=lambda x: x[1])
        if yrets and yrets[0][1] < -30:
            evts.append((yrets[0][0], f"年度暴跌{yrets[0][1]:.0f}%", f"全年暴跌{yrets[0][1]:.0f}%，市场极度悲观","negative",4))
        yrets.sort(key=lambda x: x[1], reverse=True)
        if yrets and yrets[0][1] > 50:
            evts.append((yrets[0][0], f"年度暴涨+{yrets[0][1]:.0f}%", f"全年暴涨+{yrets[0][1]:.0f}%，超级大年","positive",4))

    # 6. 公司创始人/董事长信息
    if info and info.get("zjl"):
        name = info["zjl"]
        evts.append(("2000-01", f"董事长{name}", f"公司由{name}领导","corporate",2))

    # 去重+排序
    seen = set()
    unique = []
    for e in evts:
        key = (e[0][:7], e[1][:6])  # 用年月+标题前缀去重
        if key not in seen: seen.add(key); unique.append(e)
    unique.sort(key=lambda x: x[0])
    return unique[-35:]


# ── 生成Plotly交互式图表 ──
def gen_chart(secid, name, kd, evts, info):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    do = [datetime.strptime(d, "%Y-%m-%d") for d in kd["dates"]]
    c = kd["closes"]; o = kd["opens"]; v = kd["volumes"]
    df = pd.DataFrame({"close": c})
    for ma in [20, 60, 250]: df[f"MA{ma}"] = df["close"].rolling(ma).mean()
    pct = [0.0]
    for i in range(1, len(c)):
        if c[i-1] != 0: pct.append((c[i]/c[i-1]-1)*100)
        else: pct.append(0.0)
    ydf = pd.DataFrame({"year": [d.year for d in do], "close": c})
    yd = ydf.groupby("year")["close"].agg(["first","last","min","max"])
    yd["ret"] = (yd["last"]/yd["first"]-1)*100

    ed, et, ede, etp, el = [], [], [], [], []
    for e in evts:
        ds = e[0]
        try:
            if len(ds)==10: dt = datetime.strptime(ds, "%Y-%m-%d")
            elif len(ds)==7: dt = datetime.strptime(ds+"-01", "%Y-%m-%d")
            elif len(ds)==4: dt = datetime.strptime(ds+"-07-01", "%Y-%m-%d")
            else: continue
            bi = min(range(len(do)), key=lambda i: abs((do[i]-dt).days))
            ed.append(do[bi]); et.append(e[1]); ede.append(e[2]); etp.append(e[3]); el.append(e[4])
        except: continue

    tc_map = {"positive":"#00e676","negative":"#ff1744","scandal":"#ff6d00","policy":"#00b0ff","corporate":"#ffd740","market":"#e040fb"}
    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.35,0.12,0.1,0.1,0.33])

    fig.add_trace(go.Scatter(x=do, y=c, mode="lines", name="收盘价(前复权)", line=dict(color="#00e5ff",width=1.5), hovertemplate="%{x|%Y-%m-%d}<br>收盘价:¥%{y:.2f}"), row=1, col=1)
    for mc,mn,mn_ in [("#ffd740","MA20",20),("#ff9100","MA60",60),("#ff4081","MA250",250)]:
        fig.add_trace(go.Scatter(x=do, y=[None if pd.isna(v) else v for v in df[f"MA{mn_}"].tolist()], mode="lines", name=mn, line=dict(color=mc,width=1,dash="dot"), connectgaps=False, hovertemplate=f"%{{x|%Y-%m-%d}}<br>{mn}:¥%{{y:.2f}}"), row=1, col=1)
    fig.add_trace(go.Scatter(x=do, y=c, mode="lines", fill="tozeroy", line=dict(width=0), fillcolor="rgba(0,229,255,0.06)", showlegend=False), row=1, col=1)

    mx = max(c)*1.15
    for i in range(len(ed)):
        col = tc_map.get(etp[i], "#9e9e9e"); sz = el[i]+3
        fig.add_trace(go.Scatter(x=[ed[i]], y=[mx], mode="markers+text", text=[et[i]], textposition="top center",
            marker=dict(symbol="triangle-down",size=sz,color=col),
            textfont=dict(size=min(sz+6,16),color=col), showlegend=False,
            hovertemplate=f"<b>{et[i]}</b><br>{ede[i]}<br>%{{x|%Y-%m-%d}}<extra></extra>"), row=1, col=1)
        if el[i] >= 4: fig.add_vline(x=ed[i], line_width=1, line_dash="dash", line_color=col, opacity=0.25)

    # 在价格位置加小注释
    price_range = max(c) - min(c)
    for i in range(len(ed)):
        if el[i] >= 4:
            try:
                idx2 = [j for j,d in enumerate(do) if d==ed[i]][0]
                ep = c[idx2]
                col = tc_map.get(etp[i], "#9e9e9e")
                fig.add_annotation(x=ed[i], y=ep, text=et[i], showarrow=True, arrowhead=1, arrowsize=0.7, arrowwidth=1,
                    arrowcolor=col, font=dict(size=7, color=col), bgcolor="rgba(10,10,26,0.5)",
                    bordercolor=col, borderwidth=0.5, opacity=0.7, ax=0, ay=-22)
            except: pass

    cl = ["#ff1744" if cc<oo else "#00e676" for cc,oo in zip(c,o)]
    fig.add_trace(go.Bar(x=do, y=v, name="成交量", marker_color=cl, marker_line_width=0, opacity=0.6, hovertemplate="%{x|%Y-%m-%d}<br>成交量:%{y:,.0f}手"), row=2, col=1)
    cp = ["#ff1744" if p<0 else "#00e676" for p in pct]
    fig.add_trace(go.Bar(x=do, y=pct, name="涨跌幅", marker_color=cp, marker_line_width=0, opacity=0.5, hovertemplate="%{x|%Y-%m-%d}<br>涨跌幅:%{y:.2f}%"), row=3, col=1)
    yr = yd.reset_index()
    cy = ["#ff1744" if r<0 else "#00e676" for r in yr["ret"]]
    fig.add_trace(go.Bar(x=yr["year"], y=yr["ret"], name="年度涨跌幅", marker_color=cy, marker_line_width=0, opacity=0.7, hovertemplate="%{x}<br>涨跌幅:%{y:.1f}%"), row=4, col=1)
    fig.add_hline(y=0, line_width=1, line_color="rgba(255,255,255,0.3)", row=4, col=1)
    for _,r in yr.iterrows():
        fig.add_trace(go.Scatter(x=[r["year"],r["year"]], y=[r["min"],r["max"]], mode="lines", line=dict(color="#00b0ff",width=4), showlegend=False, hovertemplate="%{x}<br>最低:¥%{y[0]:.2f}<br>最高:¥%{y[1]:.2f}"), row=5, col=1)
    fig.add_trace(go.Scatter(x=yr["year"], y=yr["first"], mode="markers+text", marker=dict(color="#ffd740",size=6),
        text=[f"¥{v_:.1f}" for v_ in yr["first"]], textposition="bottom center", textfont=dict(size=8,color="#ffd740"), showlegend=False), row=5, col=1)
    fig.add_trace(go.Scatter(x=yr["year"], y=yr["last"], mode="markers+text", marker=dict(color="#00e676",size=6),
        text=[f"¥{v_:.1f}" for v_ in yr["last"]], textposition="top center", textfont=dict(size=8,color="#00e676"), showlegend=False), row=5, col=1)

    tt = f"<b>{name}({secid})</b> 全历史走势与大事记" if name else f"<b>{secid}</b> 全历史走势与大事记"
    st = f"{do[0].strftime('%Y.%m.%d')} ~ {do[-1].strftime('%Y.%m.%d')} | 前复权"
    fig.update_layout(title=dict(text=f"{tt}<br><sup>{st}</sup>", font=dict(size=20,color="#e0e0e0"), x=0.5),
        height=1550, template="plotly_dark", paper_bgcolor="#0a0a1a", plot_bgcolor="#0f0f2a",
        font=dict(color="#c0c0c0",family="Microsoft YaHei,SimHei,Arial"), hovermode="x unified",
        legend=dict(orientation="h", y=1.02, x=0.5, xanchor="center", font=dict(size=11), bgcolor="rgba(10,10,26,0.8)"),
        margin=dict(l=60,r=40,t=100,b=40))
    fig.update_xaxes(showgrid=True, gridwidth=0.5, gridcolor="rgba(255,255,255,0.05)", tickfont=dict(size=10))
    for i,ti in enumerate(["股价(¥)","成交量","涨跌幅%","年度涨跌幅%","年度区间¥"], 1):
        fig.update_yaxes(title=ti, tickfont=dict(size=9), showgrid=True, gridcolor="rgba(255,255,255,0.05)", row=i, col=1)
    return fig.to_html(include_plotlyjs="cdn", full_html=True)



IDX = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>A股全历史走势分析工具</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a1a;color:#e0e0e0;font-family:"Microsoft YaHei","SimHei",sans-serif;min-height:100vh}
.hd{background:linear-gradient(135deg,#1a1a2e,#16213e);padding:25px 20px;text-align:center;border-bottom:1px solid #2a2a5e}
.hd h1{font-size:24px;color:#00e5ff;margin-bottom:4px}
.hd p{color:#888;font-size:13px}
.sb-wrap{max-width:600px;margin:20px auto;padding:0 20px;position:relative}
.sb-wrap .sb{display:flex;gap:10px}
.sb-wrap input{flex:1;padding:14px 20px;border:2px solid #2a2a5e;border-radius:10px;background:#1a1a2e;color:#e0e0e0;font-size:16px;outline:none}
.sb-wrap input:focus{border-color:#00e5ff}
.sb-wrap input::placeholder{color:#555}
.sb-wrap button{padding:14px 24px;border:none;border-radius:10px;background:linear-gradient(135deg,#00e5ff,#00b0ff);color:#0a0a1a;font-size:15px;font-weight:bold;cursor:pointer;white-space:nowrap}
.sb-wrap button:disabled{opacity:.5;cursor:not-allowed}
.suggest{position:absolute;top:100%;left:0;right:80px;z-index:100;background:#1a1a2e;border:1px solid #2a2a5e;border-radius:0 0 10px 10px;max-height:280px;overflow-y:auto;display:none}
.suggest div{padding:10px 16px;cursor:pointer;border-bottom:1px solid #222;font-size:14px}
.suggest div:hover{background:#2a2a5e;color:#00e5ff}
.suggest small{color:#666;margin-left:8px}
.small{text-align:center;margin:5px 0;font-size:12px;color:#555}
.small span{color:#00b0ff;cursor:pointer;margin:0 5px;padding:2px 8px;border-radius:4px;display:inline-block;margin-bottom:3px}
.small span:hover{background:#2a2a5e}
.ld{display:none;text-align:center;padding:40px}
.ld .sp{width:40px;height:40px;border:4px solid #2a2a5e;border-top-color:#00e5ff;border-radius:50%;animation:s .8s linear infinite;margin:0 auto 12px}
@keyframes s{to{transform:rotate(360deg)}}
.ld p{color:#888;font-size:13px}
.err{display:none;max-width:700px;margin:15px auto;padding:12px 18px;background:rgba(255,23,68,.1);border:1px solid #ff1744;border-radius:10px;color:#ff6b6b;font-size:13px}
#result{display:none}
.ib{max-width:1200px;margin:0 auto;padding:8px 20px;display:flex;gap:8px;flex-wrap:wrap;font-size:12px;color:#888}
.ib .it{background:#1a1a2e;padding:6px 12px;border-radius:6px;border:1px solid #2a2a5e;color:#aaa}
.ib .it b{color:#00e5ff}
.ft{text-align:center;padding:20px;color:#444;font-size:11px}
#chart-frame{width:100%;height:1550px;border:none;border-radius:6px}
</style></head><body>
<div class="hd"><h1>A股全历史走势分析工具</h1><p>输入股票代码或名称，自动生成走势图 + 大事记 + 公司简介</p></div>
<div class="sb-wrap">
<div class="sb"><input type="text" id="ci" placeholder="代码或名称 如 600085、同仁堂、002463" autocomplete="off"><button id="sb" onclick="srch()">查询</button></div>
<div class="suggest" id="suggest"></div>
</div>
<div class="small">热门:
<span onclick="q('600085')">同仁堂</span><span onclick="q('600519')">茅台</span><span onclick="q('000001')">平安</span><span onclick="q('000858')">五粮液</span><span onclick="q('002415')">海康</span><span onclick="q('300750')">宁德时代</span><span onclick="q('000568')">泸州老窖</span><span onclick="q('002463')">沪电股份</span><span onclick="q('601318')">中国平安</span><span onclick="q('002594')">比亚迪</span>
</div>
<div class="ld" id="ld"><div class="sp"></div><p>正在获取数据并生成图表...</p></div>
<div class="err" id="err"></div>
<div id="result">
<div class="ib" id="ib"></div>
<iframe id="chart-frame" src="about:blank"></iframe>
</div>
<div class="ft">数据:腾讯证券 + 东方财富F10 | 大事记基于行情自动生成 | 仅供参考</div>
<script>
var st;var nameTimer;
document.getElementById("ci").addEventListener("input", function(){
    clearTimeout(st); var v=this.value.trim();
    if(v.length<2){document.getElementById("suggest").style.display="none";return}
    st=setTimeout(function(){
        fetch("/api/suggest?q="+encodeURIComponent(v)).then(function(r){return r.json()}).then(function(d){
            var bx=document.getElementById("suggest"); bx.innerHTML="";
            if(!d.length){bx.style.display="none";return}
            d.slice(0,8).forEach(function(item){
                var dv=document.createElement("div");
                dv.innerHTML="<b>"+item.n+"</b> <small>"+item.c+" | "+item.hy+"</small>";
                dv.onclick=function(){document.getElementById("ci").value=item.c;bx.style.display="none";srch()};
                bx.appendChild(dv);
            }); bx.style.display="block";
        }).catch(function(){});
    },300);
});
document.addEventListener("click",function(e){if(!e.target.closest(".sb-wrap"))document.getElementById("suggest").style.display="none"});
function srch(c2){var c=c2||document.getElementById("ci").value.trim();if(!c){alert("输入代码或名称");return}
document.getElementById("ld").style.display="block";document.getElementById("err").style.display="none"
document.getElementById("result").style.display="none";document.getElementById("sb").disabled=true
document.getElementById("suggest").style.display="none"
fetch("/api/a?c="+encodeURIComponent(c)).then(function(r){return r.json()}).then(function(d){
document.getElementById("ld").style.display="none";document.getElementById("sb").disabled=false
if(d.e){document.getElementById("err").innerHTML=d.e;document.getElementById("err").style.display="block";return}
var h="<div class=it><b>"+d.n+"</b>("+d.c+")</div>"
h+="<div class=it>K:"+d.k+"条</div><div class=it>"+d.s+"~"+d.e2+"</div>"
h+="<div class=it>最高:"+d.h+"</div><div class=it>最低:"+d.l+"</div><div class=it>大事记:"+d.ev+"条</div>"
if(d.hy){h="<div class=it><b>"+d.n+"</b>("+d.c+")</div><div class=it>行业:"+d.hy+"</div><div class=it>董事长:"+d.zjl+"</div>"+h.substring(h.indexOf('<div class=it>K:'))}
if(d.intro && d.intro.length>5){document.getElementById("ib").innerHTML+="<div class=it style=width:100%>简介:"+d.intro+"</div>"}
document.getElementById("ib").innerHTML=h
document.getElementById("chart-frame").src="/chart/"+d.f
document.getElementById("result").style.display="block"
}).catch(function(e){document.getElementById("ld").style.display="none";document.getElementById("sb").disabled=false
document.getElementById("err").innerHTML="请求失败:"+e.message;document.getElementById("err").style.display="block"})}
function q(c){document.getElementById("ci").value=c;srch(c)}
window.onload=function(){var p=new URLSearchParams(window.location.search);var c=p.get("code");if(c){document.getElementById("ci").value=c;srch(c)}}
</script></body></html>"""

@app.route("/")
def idx_page(): return IDX

@app.route("/api/suggest")
def suggest():
    q = request.args.get("q", "").strip()
    if len(q) < 1: return jsonify([])
    try:
        r = requests.get("https://searchadapter.eastmoney.com/api/suggest/get",
            params={"input": q, "type": 14, "token": "D43BF722C8E33BDC906FB84D85E326E8"},
            headers=HEADERS, timeout=10)
        items = r.json().get("QuotationCodeTable", {}).get("Data", [])
        result = []
        for item in items:
            code = item.get("Code", "")
            name = item.get("Name", "")
            hy = ""
            try:
                info = get_company_info(code)
                hy = info.get("sshy", "")
            except: pass
            result.append({"c": code, "n": name, "hy": hy})
        return jsonify(result)
    except: return jsonify([])

@app.route("/chart/<fname>")
def serve_chart(fname):
    fpath = os.path.join(TMP_DIR, fname)
    if not os.path.exists(fpath): abort(404)
    return send_from_directory(TMP_DIR, fname)

@app.route("/api/a")
def analyze():
    try:
        raw = request.args.get("c", "").strip()
        if not raw: return jsonify({"e": "请输入股票代码或名称"})
        code = raw
        if not code.isdigit():
            r = requests.get("https://searchadapter.eastmoney.com/api/suggest/get",
                params={"input": code, "type": 14, "token": "D43BF722C8E33BDC906FB84D85E326E8"},
                headers=HEADERS, timeout=10)
            items = r.json().get("QuotationCodeTable", {}).get("Data", [])
            if items: code = items[0].get("Code", code)

        info = get_company_info(code)
        name = info.get("gsmc", get_name(code))

        kd = get_kline(code)
        if kd is None:
            return jsonify({"e": f"未找到股票{code}的数据，请检查代码"})

        evt = gen_events(code, kd, info)
        chart_html = gen_chart(code, name, kd, evt, info)

        fname = f"{code}_{uuid.uuid4().hex[:8]}.html"
        with open(os.path.join(TMP_DIR, fname), "w", encoding="utf-8") as f:
            f.write(chart_html)

        hy = info.get("sshy", "")
        zjl = info.get("zjl", "")
        intro = info.get("gsjj", "")[:200]

        return jsonify({"c":code,"n":name,"k":kd["n"],"s":kd["dates"][0],"e2":kd["dates"][-1],
            "h":round(max(kd["highs"]),2),"l":round(min(kd["lows"]),2),"ev":len(evt),"f":fname,
            "hy": hy, "zjl": zjl, "intro": intro})
    except Exception as ex:
        return jsonify({"e": f"错误: {str(ex)}"})

if __name__ == "__main__":
    for old in os.listdir(TMP_DIR):
        try: os.remove(os.path.join(TMP_DIR, old))
        except: pass
    print("="*60)
    print("  A股全历史走势分析工具 v3")
    print("  http://localhost:6789")
    print("  支持: 代码/名称搜索 + 行业/董事长 + 大事记")
    print("="*60)
    app.run(host="0.0.0.0", port=6789, debug=False)
