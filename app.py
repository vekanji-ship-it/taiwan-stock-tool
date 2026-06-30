import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="台股分析儀表板", page_icon="📊", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
.stApp{background:#0d1117;color:#e6edf3}
[data-testid="stSidebar"]{background:#161b22;border-right:1px solid #30363d}
.stTabs [data-baseweb="tab-list"]{background:#161b22;border-bottom:1px solid #30363d;gap:0}
.stTabs [data-baseweb="tab"]{color:#8b949e;padding:10px 20px;font-size:13px;font-weight:600}
.stTabs [aria-selected="true"]{color:#e6edf3;border-bottom:2px solid #58a6ff}
.metric-card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px 18px;margin-bottom:10px}
.metric-card .lbl{font-size:11px;color:#8b949e;text-transform:uppercase;letter-spacing:.08em;margin-bottom:3px}
.metric-card .val{font-size:20px;font-weight:700;font-family:'Courier New',monospace}
.metric-card .dlt{font-size:12px;margin-top:2px}
.up{color:#3fb950}.down{color:#f85149}.neutral{color:#8b949e}.warn{color:#e3b341}
.sig-row{display:flex;align-items:flex-start;gap:10px;padding:11px 0;border-bottom:1px solid #21262d}
.sig-badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;white-space:nowrap;flex-shrink:0}
.sig-buy{background:#1a4731;color:#3fb950;border:1px solid #2d6a4f}
.sig-sell{background:#3d1f1f;color:#f85149;border:1px solid #6b2222}
.sig-hold{background:#272e3b;color:#e3b341;border:1px solid #4a3b1a}
.sig-neutral{background:#21262d;color:#8b949e;border:1px solid #30363d}
.sig-detail{font-size:12px;color:#c9d1d9;line-height:1.5}
.verdict-box{border-radius:8px;padding:12px 16px;margin-bottom:14px;font-weight:700;font-size:14px}
.verdict-bull{background:#1a4731;border:1px solid #2d6a4f;color:#3fb950}
.verdict-bear{background:#3d1f1f;border:1px solid #6b2222;color:#f85149}
.verdict-mid{background:#272e3b;border:1px solid #4a3b1a;color:#e3b341}
.section-hdr{font-size:12px;font-weight:600;color:#8b949e;text-transform:uppercase;letter-spacing:.1em;border-bottom:1px solid #30363d;padding-bottom:7px;margin-bottom:14px}
.error-box{background:#3d1f1f;border:1px solid #6b2222;border-radius:8px;padding:12px 16px;color:#f85149;font-size:13px}
.warn-box{background:#272e3b;border:1px solid #4a3b1a;border-radius:8px;padding:12px 16px;color:#e3b341;font-size:13px}
.rank-row{display:flex;align-items:center;gap:12px;padding:10px 14px;background:#161b22;border:1px solid #30363d;border-radius:8px;margin-bottom:7px}
.rank-num{font-size:18px;font-weight:800;color:#8b949e;width:28px;flex-shrink:0}
.rank-name{font-size:14px;font-weight:700;flex:1}
.rank-score{font-size:12px;color:#8b949e}
#MainMenu,footer{visibility:hidden}
.stTextInput input,.stSelectbox>div>div{background:#21262d;border:1px solid #30363d;color:#e6edf3;border-radius:6px}
.stButton button{background:#238636;color:#fff;border:1px solid #2ea043;border-radius:6px;font-weight:600;width:100%}
.stButton button:hover{background:#2ea043}
.stMultiSelect>div>div{background:#21262d;border:1px solid #30363d}
</style>
""", unsafe_allow_html=True)

# ── Secrets ───────────────────────────────────────────────────────────────────
try:
    FINMIND_TOKEN = st.secrets.get("FINMIND_TOKEN", "")
except Exception:
    FINMIND_TOKEN = ""

FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"
TWSE_BASE    = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
CHART_BG     = "#0d1117"

# ── 預設股票列表（排行榜用）────────────────────────────────────────────────────
WATCHLIST_STOCKS = [
    "2330","2317","2454","2382","3711","2308","2303","2357","2379","2395",
    "2886","2891","2884","2881","2882","1301","1303","2002","2412","3008"
]
MONTHLY_ETF_LIST = [
    ("00878","國泰永續高股息"),("00929","復華台灣科技優息"),("00919","群益台灣精選高息"),
    ("00934","中信成長高股息"),("00713","元大台灣高息低波"),("00930","永豐ESG低碳高息"),
    ("00936","台新臺灣永續高息"),("00940","元大台灣價值高息"),("00915","凱基優選高股息30"),
    ("00943","兆豐台灣核心高息"),("00944","群益半導體收益"),("00945","玉山臺灣創新高息"),
]

# ══════════════════════════════════════════════════════════════════════════════
# API 資料抓取
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def fetch_ohlcv(stock_id, start_date, end_date):
    try:
        r = requests.get(FINMIND_BASE, params={
            "dataset":"TaiwanStockPrice","data_id":stock_id,
            "start_date":start_date,"end_date":end_date,"token":FINMIND_TOKEN
        }, timeout=15)
        data = r.json()
        if data.get("status") != 200 or not data.get("data"): return pd.DataFrame()
        df = pd.DataFrame(data["data"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df.rename(columns={"open":"Open","max":"High","min":"Low","close":"Close",
                            "Trading_Volume":"Volume"}, inplace=True)
        for c in ["Open","High","Low","Close","Volume"]:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_institutional(stock_id, start_date, end_date):
    try:
        r = requests.get(FINMIND_BASE, params={
            "dataset":"TaiwanStockInstitutionalInvestorsBuySell","data_id":stock_id,
            "start_date":start_date,"end_date":end_date,"token":FINMIND_TOKEN
        }, timeout=15)
        data = r.json()
        if data.get("status") != 200 or not data.get("data"): return pd.DataFrame()
        df = pd.DataFrame(data["data"])
        df["date"] = pd.to_datetime(df["date"])
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def fetch_realtime_price(stock_id):
    headers = {"Referer":"https://mis.twse.com.tw"}
    for market in ["tse","otc"]:
        try:
            r = requests.get(TWSE_BASE,
                params={"ex_ch":f"{market}_{stock_id}.tw","json":1,"delay":0},
                headers=headers, timeout=10)
            data = r.json()
            if data.get("rtmessage")=="OK" and data.get("msgArray"):
                item = data["msgArray"][0]
                name = item.get("n","").strip()
                if name:
                    return {"name":name,
                            "price":float(item.get("z",0) or 0),
                            "open": float(item.get("o",0) or 0),
                            "high": float(item.get("h",0) or 0),
                            "low":  float(item.get("l",0) or 0),
                            "prev": float(item.get("y",0) or 0),
                            "volume":int(item.get("v",0) or 0),
                            "time": item.get("t",""), "market":market, "ok":True}
        except Exception:
            pass
    return {"ok":False}

@st.cache_data(ttl=86400)
def fetch_stock_name(stock_id):
    for url, code_key, name_key in [
        ("https://openapi.twse.com.tw/v1/opendata/t187ap03_L","公司代號","公司簡稱"),
        ("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O","SecuritiesCompanyCode","CompanyAbbreviation"),
    ]:
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                for item in r.json():
                    if str(item.get(code_key,"")).strip() == str(stock_id):
                        return str(item.get(name_key, stock_id)).strip()
        except Exception:
            pass
    return stock_id

@st.cache_data(ttl=3600)
def fetch_fundamental(stock_id, start_date):
    """抓 P/E、殖利率、P/B（TaiwanStockPER）"""
    try:
        r = requests.get(FINMIND_BASE, params={
            "dataset":"TaiwanStockPER","data_id":stock_id,
            "start_date":start_date,"token":FINMIND_TOKEN
        }, timeout=15)
        data = r.json()
        if data.get("status") != 200 or not data.get("data"): return pd.DataFrame()
        df = pd.DataFrame(data["data"])
        df["date"] = pd.to_datetime(df["date"])
        for c in ["PER","PBR","DividendYield"]:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
        return df.sort_values("date")
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_monthly_revenue(stock_id):
    """抓月營收（近13個月），自行計算年增率"""
    start = (datetime.today() - timedelta(days=760)).strftime("%Y-%m-%d")  # 抓兩年份才能算YoY
    try:
        r = requests.get(FINMIND_BASE, params={
            "dataset":"TaiwanStockMonthRevenue","data_id":stock_id,
            "start_date":start,"token":FINMIND_TOKEN
        }, timeout=15)
        data = r.json()
        if data.get("status") != 200 or not data.get("data"): return pd.DataFrame()
        df = pd.DataFrame(data["data"])
        df["date"] = pd.to_datetime(df["date"])
        df["revenue"] = pd.to_numeric(df.get("revenue", 0), errors="coerce")
        df = df.sort_values("date").reset_index(drop=True)
        # 自行計算年增率：本月營收 vs 去年同月營收
        df["YoY"] = (df["revenue"] / df["revenue"].shift(12) - 1) * 100
        df["YoY"] = df["YoY"].round(1)
        return df.tail(13)
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_eps(stock_id):
    """抓近8季 EPS"""
    start = (datetime.today() - timedelta(days=800)).strftime("%Y-%m-%d")
    try:
        r = requests.get(FINMIND_BASE, params={
            "dataset":"TaiwanStockFinancialStatements","data_id":stock_id,
            "start_date":start,"token":FINMIND_TOKEN
        }, timeout=15)
        data = r.json()
        if data.get("status") != 200 or not data.get("data"): return pd.DataFrame()
        df = pd.DataFrame(data["data"])
        df["date"] = pd.to_datetime(df["date"])
        if "type" in df.columns:
            df = df[df["type"].str.contains("EPS|每股", na=False)]
        df["value"] = pd.to_numeric(df.get("value", 0), errors="coerce")
        return df.sort_values("date").tail(8)
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_etf_dividend(etf_id):
    """抓 ETF 配息歷史"""
    start = (datetime.today() - timedelta(days=400)).strftime("%Y-%m-%d")
    try:
        r = requests.get(FINMIND_BASE, params={
            "dataset":"TaiwanETFDividend","data_id":etf_id,
            "start_date":start,"token":FINMIND_TOKEN
        }, timeout=15)
        data = r.json()
        if data.get("status") != 200 or not data.get("data"): return pd.DataFrame()
        df = pd.DataFrame(data["data"])
        df["date"] = pd.to_datetime(df["date"])
        for c in ["CashEarningsDistribution","StockEarningsDistribution"]:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
        return df.sort_values("date")
    except Exception:
        return pd.DataFrame()

# ══════════════════════════════════════════════════════════════════════════════
# 計算函數
# ══════════════════════════════════════════════════════════════════════════════

def resample_ohlcv(df, freq="W"):
    """日線轉週線/月線"""
    if df.empty: return df
    df2 = df.set_index("date").resample(freq).agg({
        "Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"
    }).dropna(subset=["Close"]).reset_index()
    return df2

def calc_indicators(df):
    if df.empty or "Close" not in df.columns: return df
    close = df["Close"]
    for p in [5,10,20,60]:
        df[f"MA{p}"] = close.rolling(p).mean().round(2)
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    df["RSI"] = (100 - 100/(1 + gain/loss.replace(0,np.nan))).round(2)
    ema12 = close.ewm(span=12,adjust=False).mean()
    ema26 = close.ewm(span=26,adjust=False).mean()
    df["MACD"]        = (ema12-ema26).round(3)
    df["MACD_signal"] = df["MACD"].ewm(span=9,adjust=False).mean().round(3)
    df["MACD_hist"]   = (df["MACD"]-df["MACD_signal"]).round(3)
    # 布林通道
    df["BB_mid"]   = close.rolling(20).mean().round(2)
    df["BB_std"]   = close.rolling(20).std()
    df["BB_upper"] = (df["BB_mid"] + 2*df["BB_std"]).round(2)
    df["BB_lower"] = (df["BB_mid"] - 2*df["BB_std"]).round(2)
    df["BB_%B"]    = ((close - df["BB_lower"]) / (df["BB_upper"]-df["BB_lower"])*100).round(1)
    # 成交量均量
    df["Vol_MA20"] = df["Volume"].rolling(20).mean()
    return df

def process_institutional(chip_df):
    if chip_df.empty: return pd.DataFrame()
    try:
        df = chip_df.copy()
        df["buy"]  = pd.to_numeric(df["buy"], errors="coerce").fillna(0)
        df["sell"] = pd.to_numeric(df["sell"],errors="coerce").fillna(0)
        df["net"]  = df["buy"] - df["sell"]
        name_map = {"Foreign_Investor":"外資","Foreign_Dealer_Self":"外資",
                    "Investment_Trust":"投信","Dealer":"自營商",
                    "Dealer_Self":"自營商","Dealer_Hedging":"自營商"}
        df["group"] = df["name"].map(name_map)
        df = df.dropna(subset=["group"])
        pivot = df.groupby(["date","group"])["net"].sum().unstack(fill_value=0)
        pivot.columns.name = None
        pivot = pivot.reset_index()
        for col in ["外資","投信","自營商"]:
            if col not in pivot.columns: pivot[col] = 0
        pivot["合計"] = pivot[["外資","投信","自營商"]].sum(axis=1)
        return pivot.sort_values("date")
    except Exception:
        return pd.DataFrame()

def calc_tech_score(df):
    """計算技術分析分數 0-100，供排行榜使用"""
    if df.empty or len(df) < 30: return 0
    score = 50
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df)>1 else last
    try:
        ma5,ma20,ma60 = last.get("MA5"),last.get("MA20"),last.get("MA60")
        if pd.notna(ma5) and pd.notna(ma20) and pd.notna(ma60):
            if ma5>ma20>ma60: score += 15
            elif ma5<ma20<ma60: score -= 15
    except: pass
    try:
        rsi = last.get("RSI")
        if pd.notna(rsi):
            if rsi < 35: score += 10
            elif rsi > 65: score -= 10
    except: pass
    try:
        macd,sig = last.get("MACD"),last.get("MACD_signal")
        pm,ps    = prev.get("MACD"),prev.get("MACD_signal")
        if all(pd.notna(x) for x in [macd,sig,pm,ps]):
            if pm<ps and macd>sig: score += 15  # 黃金交叉
            elif pm>ps and macd<sig: score -= 15  # 死亡交叉
            elif macd>sig: score += 5
            else: score -= 5
    except: pass
    try:
        bb = last.get("BB_%B")
        if pd.notna(bb):
            if bb<20: score += 10
            elif bb>80: score -= 10
    except: pass
    try:
        vol = last.get("Volume"); vol_ma = last.get("Vol_MA20")
        close = last.get("Close"); prev_close = prev.get("Close")
        if all(pd.notna(x) for x in [vol,vol_ma,close,prev_close]):
            if close>prev_close and vol>vol_ma*1.2: score += 5  # 放量上漲
            elif close<prev_close and vol>vol_ma*1.2: score -= 5  # 放量下跌
    except: pass
    return max(0, min(100, score))

def generate_signals(df, chip_df):
    signals = []
    if df.empty or len(df)<2: return signals
    last = df.iloc[-1]; prev = df.iloc[-2]

    # 1. 均線排列
    try:
        ma5,ma20,ma60 = last.get("MA5"),last.get("MA20"),last.get("MA60")
        cl = last.get("Close",0)
        if pd.notna(ma5) and pd.notna(ma20) and pd.notna(ma60):
            above5  = "✓" if cl>ma5  else "✗"
            above20 = "✓" if cl>ma20 else "✗"
            above60 = "✓" if cl>ma60 else "✗"
            if ma5>ma20>ma60:
                signals.append(("均線多頭排列","buy",
                    f"MA5 {ma5:.1f} > MA20 {ma20:.1f} > MA60 {ma60:.1f}｜股價站上MA5 {above5}、MA20 {above20}、MA60 {above60}"))
            elif ma5<ma20<ma60:
                signals.append(("均線空頭排列","sell",
                    f"MA5 {ma5:.1f} < MA20 {ma20:.1f} < MA60 {ma60:.1f}｜股價站上MA5 {above5}、MA20 {above20}、MA60 {above60}"))
            else:
                signals.append(("均線糾結整理","hold",
                    f"MA5 {ma5:.1f} / MA20 {ma20:.1f} / MA60 {ma60:.1f}｜多空尚未明確分化"))
    except: pass

    # 2. RSI
    try:
        rsi = last.get("RSI")
        if pd.notna(rsi):
            if rsi < 30:
                signals.append(("RSI 深度超賣","buy",
                    f"RSI={rsi:.1f}（低於30）｜歷史上此區間反彈機率偏高，留意量能配合"))
            elif rsi < 40:
                signals.append(("RSI 偏弱待確認","hold",
                    f"RSI={rsi:.1f}（30-40）｜偏弱但尚未深超賣，觀察是否止跌"))
            elif rsi > 80:
                signals.append(("RSI 嚴重超買","sell",
                    f"RSI={rsi:.1f}（高於80）｜短期過熱，注意拉回修正風險"))
            elif rsi > 70:
                signals.append(("RSI 超買警示","hold",
                    f"RSI={rsi:.1f}（70-80）｜偏強但接近超買，持股需設好停利"))
            else:
                signals.append(("RSI 健康中性","neutral",
                    f"RSI={rsi:.1f}（40-70）｜動能中性，無明顯過熱或超賣訊號"))
    except: pass

    # 3. MACD
    try:
        macd,sig  = last.get("MACD"),last.get("MACD_signal")
        pm,ps     = prev.get("MACD"),prev.get("MACD_signal")
        hist      = last.get("MACD_hist",0)
        if all(pd.notna(x) for x in [macd,sig,pm,ps]):
            # 計算連續紅/綠柱
            hist_series = df["MACD_hist"].dropna()
            if hist > 0:
                streak = (hist_series > 0)[::-1].cumprod().sum()
            else:
                streak = (hist_series < 0)[::-1].cumprod().sum()
            if pm<ps and macd>sig:
                signals.append(("MACD 黃金交叉","buy",
                    f"MACD線由下往上穿越訊號線｜MACD={macd:.2f} / Signal={sig:.2f}，為中線偏多訊號"))
            elif pm>ps and macd<sig:
                signals.append(("MACD 死亡交叉","sell",
                    f"MACD線由上往下穿越訊號線｜MACD={macd:.2f} / Signal={sig:.2f}，為中線偏空訊號"))
            elif macd>sig:
                signals.append(("MACD 多頭持續","buy" if hist>0 else "hold",
                    f"MACD={macd:.2f} > 訊號線={sig:.2f}｜柱狀圖連續{'縮短' if hist<prev.get('MACD_hist',hist) else '放大'} {int(streak)} 根"))
            else:
                signals.append(("MACD 空頭持續","sell" if hist<0 else "hold",
                    f"MACD={macd:.2f} < 訊號線={sig:.2f}｜柱狀圖連續空頭 {int(streak)} 根"))
    except: pass

    # 4. 布林通道
    try:
        bb_pct = last.get("BB_%B")
        bb_upper = last.get("BB_upper"); bb_lower = last.get("BB_lower")
        close = last.get("Close")
        if pd.notna(bb_pct):
            if bb_pct < 10:
                signals.append(("觸及布林下軌","buy",
                    f"股價 {close:.2f} 逼近下軌 {bb_lower:.2f}｜%B={bb_pct:.0f}%，歷史上常見反彈支撐位"))
            elif bb_pct > 90:
                signals.append(("觸及布林上軌","sell",
                    f"股價 {close:.2f} 逼近上軌 {bb_upper:.2f}｜%B={bb_pct:.0f}%，短期壓力明顯"))
            elif 40 < bb_pct < 60:
                signals.append(("布林帶中軌整理","neutral",
                    f"股價位於布林帶中軌附近｜上軌={bb_upper:.2f} / 下軌={bb_lower:.2f}，方向待定"))
    except: pass

    # 5. 成交量分析
    try:
        vol    = last.get("Volume",0)
        vol_ma = last.get("Vol_MA20",0)
        close  = last.get("Close",0)
        prev_c = prev.get("Close",0)
        if pd.notna(vol) and pd.notna(vol_ma) and vol_ma > 0:
            ratio = vol / vol_ma
            up    = close > prev_c
            if ratio > 1.5 and up:
                signals.append(("放量上漲","buy",
                    f"成交量 {vol/1000:.0f}K（均量 {ratio:.1f}x）｜價量齊揚，多方強勢訊號"))
            elif ratio > 1.5 and not up:
                signals.append(("放量下跌","sell",
                    f"成交量 {vol/1000:.0f}K（均量 {ratio:.1f}x）｜量增價跌，空方主導，需警惕"))
            elif ratio < 0.5:
                signals.append(("量能萎縮","neutral",
                    f"成交量 {vol/1000:.0f}K（僅均量 {ratio:.1f}x）｜市場觀望，突破有效性待確認"))
            else:
                signals.append(("量能正常","neutral",
                    f"成交量 {vol/1000:.0f}K（均量 {ratio:.1f}x）｜無明顯異常放量或縮量"))
    except: pass

    # 6. 三大法人（近5日）
    if not chip_df.empty:
        try:
            last5 = chip_df.tail(5)
            foreign = last5["外資"].sum()
            trust   = last5["投信"].sum()
            total   = last5["合計"].sum()
            consec_buy = 0
            for v in chip_df["合計"].iloc[::-1]:
                if v > 0: consec_buy += 1
                else: break
            if total > 0:
                signals.append(("法人近5日買超","buy",
                    f"合計買超 {total/1000:.0f}K 張｜外資 {foreign/1000:+.0f}K / 投信 {trust/1000:+.0f}K｜連續買超 {consec_buy} 日"))
            elif total < 0:
                signals.append(("法人近5日賣超","sell",
                    f"合計賣超 {abs(total)/1000:.0f}K 張｜外資 {foreign/1000:+.0f}K / 投信 {trust/1000:+.0f}K"))
        except: pass

    return signals

def get_verdict(signals):
    buy  = sum(1 for _,k,_ in signals if k=="buy")
    sell = sum(1 for _,k,_ in signals if k=="sell")
    if buy > sell+1:   return "bull", f"⬆ 整體偏多（{buy} 個多方訊號 / {sell} 個空方訊號）"
    elif sell > buy+1: return "bear", f"⬇ 整體偏空（{sell} 個空方訊號 / {buy} 個多方訊號）"
    else:              return "mid",  f"◆ 多空分歧（{buy} 多 / {sell} 空），方向尚未明確"

# ══════════════════════════════════════════════════════════════════════════════
# 圖表函數
# ══════════════════════════════════════════════════════════════════════════════

def chart_layout(height=620):
    return dict(height=height, paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
                font=dict(color="#e6edf3",size=11),
                legend=dict(bgcolor="#161b22",bordercolor="#30363d",borderwidth=1,
                            x=0.01,y=0.99,font=dict(size=10)),
                margin=dict(l=10,r=10,t=10,b=10),
                hovermode="x unified",
                hoverlabel=dict(bgcolor="#161b22",bordercolor="#30363d",font_size=11))

def draw_main_chart(df, show_ma, show_bb):
    fig = make_subplots(rows=4, cols=1, row_heights=[0.50,0.15,0.20,0.15],
                        shared_xaxes=True, vertical_spacing=0.015)
    up,dn = "#3fb950","#f85149"

    # K線
    fig.add_trace(go.Candlestick(
        x=df["date"],open=df["Open"],high=df["High"],low=df["Low"],close=df["Close"],
        increasing_line_color=up,decreasing_line_color=dn,
        increasing_fillcolor=up,decreasing_fillcolor=dn,
        name="K線",showlegend=False), row=1,col=1)

    # 布林通道
    if show_bb and "BB_upper" in df.columns:
        fig.add_trace(go.Scatter(x=df["date"],y=df["BB_upper"],mode="lines",
            line=dict(color="#58a6ff",width=1,dash="dot"),name="BB上軌"),row=1,col=1)
        fig.add_trace(go.Scatter(x=df["date"],y=df["BB_lower"],mode="lines",
            line=dict(color="#58a6ff",width=1,dash="dot"),name="BB下軌",
            fill="tonexty",fillcolor="rgba(88,166,255,0.06)"),row=1,col=1)
        fig.add_trace(go.Scatter(x=df["date"],y=df["BB_mid"],mode="lines",
            line=dict(color="#58a6ff",width=0.8),name="BB中軌"),row=1,col=1)

    # 均線
    ma_colors = {"MA5":"#58a6ff","MA10":"#d2a8ff","MA20":"#ffa657","MA60":"#f78166"}
    for ma in show_ma:
        if ma in df.columns:
            fig.add_trace(go.Scatter(x=df["date"],y=df[ma],mode="lines",
                line=dict(color=ma_colors.get(ma,"#fff"),width=1.3),name=ma),row=1,col=1)

    # 成交量
    if "Volume" in df.columns:
        vol_colors = [up if row["Close"]>=row["Open"] else dn for _,row in df.iterrows()]
        fig.add_trace(go.Bar(x=df["date"],y=df["Volume"]/1000,marker_color=vol_colors,
            name="量(K)",showlegend=False,opacity=0.7),row=2,col=1)
        if "Vol_MA20" in df.columns:
            fig.add_trace(go.Scatter(x=df["date"],y=df["Vol_MA20"]/1000,mode="lines",
                line=dict(color="#ffa657",width=1.2),name="量均線",showlegend=False),row=2,col=1)

    # RSI
    if "RSI" in df.columns:
        fig.add_trace(go.Scatter(x=df["date"],y=df["RSI"],mode="lines",
            line=dict(color="#d2a8ff",width=1.5),name="RSI(14)",showlegend=False),row=3,col=1)
        for lvl,col in [(70,dn),(50,"#8b949e"),(30,up)]:
            fig.add_hline(y=lvl,line_dash="dash",line_color=col,line_width=0.8,opacity=0.5,row=3,col=1)

    # MACD
    if "MACD" in df.columns:
        hist_col = [up if v>=0 else dn for v in df["MACD_hist"].fillna(0)]
        fig.add_trace(go.Bar(x=df["date"],y=df["MACD_hist"],marker_color=hist_col,
            name="柱",showlegend=False,opacity=0.75),row=4,col=1)
        fig.add_trace(go.Scatter(x=df["date"],y=df["MACD"],
            line=dict(color="#58a6ff",width=1.2),name="MACD",showlegend=False),row=4,col=1)
        fig.add_trace(go.Scatter(x=df["date"],y=df["MACD_signal"],
            line=dict(color="#ffa657",width=1.2),name="Signal",showlegend=False),row=4,col=1)

    fig.update_layout(**chart_layout(660), xaxis_rangeslider_visible=False)
    for i in range(1,5):
        fig.update_yaxes(row=i,col=1,gridcolor="#21262d",zerolinecolor="#30363d",tickfont=dict(size=10))
        fig.update_xaxes(row=i,col=1,gridcolor="#21262d",showgrid=(i==4))
    fig.update_yaxes(title_text="價格",row=1,col=1,title_font=dict(size=10))
    fig.update_yaxes(title_text="量K",row=2,col=1,title_font=dict(size=10))
    fig.update_yaxes(title_text="RSI",row=3,col=1,title_font=dict(size=10),range=[0,100])
    fig.update_yaxes(title_text="MACD",row=4,col=1,title_font=dict(size=10))
    return fig

def draw_chip_chart(chip_df):
    fig = go.Figure()
    for col,color in [("外資","#58a6ff"),("投信","#3fb950"),("自營商","#ffa657")]:
        if col in chip_df.columns:
            vals = chip_df[col]/1000
            fig.add_trace(go.Bar(x=chip_df["date"],y=vals,name=col,
                marker_color=[color if v>=0 else "#f85149" for v in vals],opacity=0.8))
    fig.update_layout(**chart_layout(260),barmode="group",
        xaxis=dict(gridcolor="#21262d"),
        yaxis=dict(gridcolor="#21262d",title="千張"))
    return fig

def draw_fundamental_charts(per_df, rev_df, eps_df):
    charts = []
    if not per_df.empty:
        fig = make_subplots(rows=1,cols=3,subplot_titles=["本益比(PER)","股價淨值比(PBR)","殖利率(%)"])
        for i,(col,color) in enumerate([("PER","#58a6ff"),("PBR","#3fb950"),("DividendYield","#ffa657")],1):
            if col in per_df.columns:
                fig.add_trace(go.Scatter(x=per_df["date"],y=per_df[col],mode="lines",
                    line=dict(color=color,width=1.5),showlegend=False),row=1,col=i)
        fig.update_layout(**chart_layout(240))
        for i in range(1,4):
            fig.update_xaxes(row=1,col=i,gridcolor="#21262d")
            fig.update_yaxes(row=1,col=i,gridcolor="#21262d")
        charts.append(fig)
    if not rev_df.empty and "revenue" in rev_df.columns:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=rev_df["date"],y=rev_df["revenue"]/1e8,
            name="月營收(億)",marker_color="#58a6ff",opacity=0.8))
        if "YoY" in rev_df.columns:
            fig.add_trace(go.Scatter(x=rev_df["date"],y=rev_df["YoY"],mode="lines+markers",
                name="年增率%",line=dict(color="#ffa657",width=2),yaxis="y2"))
        layout = chart_layout(260)
        layout["legend"] = dict(x=0.01, y=0.99, bgcolor="#161b22", bordercolor="#30363d", borderwidth=1)
        fig.update_layout(**layout,
            yaxis=dict(title="億元",gridcolor="#21262d"),
            yaxis2=dict(title="年增率%",overlaying="y",side="right",gridcolor="#21262d"))
        charts.append(fig)
    return charts

def draw_comparison_chart(stock_data):
    fig = go.Figure()
    colors = ["#58a6ff","#3fb950","#ffa657","#d2a8ff","#f78166","#e3b341"]
    for i,(sid,df) in enumerate(stock_data.items()):
        if df.empty: continue
        base = df["Close"].iloc[0]
        norm = (df["Close"]/base - 1)*100
        fig.add_trace(go.Scatter(x=df["date"],y=norm,mode="lines",
            name=sid,line=dict(color=colors[i%len(colors)],width=2)))
    fig.update_layout(**chart_layout(400),
        yaxis=dict(title="漲跌幅 %",gridcolor="#21262d",zeroline=True,zerolinecolor="#30363d"),
        xaxis=dict(gridcolor="#21262d"))
    fig.add_hline(y=0,line_dash="dash",line_color="#8b949e",line_width=0.8)
    return fig

# ══════════════════════════════════════════════════════════════════════════════
# 輔助 HTML
# ══════════════════════════════════════════════════════════════════════════════

def sig_html(label, kind, detail):
    css = {"buy":"sig-buy","sell":"sig-sell","hold":"sig-hold","neutral":"sig-neutral"}
    ico = {"buy":"▲","sell":"▼","hold":"◆","neutral":"●"}
    return f"""<div class="sig-row">
        <span class="sig-badge {css.get(kind,'sig-neutral')}">{ico.get(kind,'●')} {label}</span>
        <span class="sig-detail">{detail}</span></div>"""

def metric_card(label, value, delta="", cls="neutral"):
    return f"""<div class="metric-card">
        <div class="lbl">{label}</div>
        <div class="val {cls}">{value}</div>
        <div class="dlt {cls}">{delta}</div></div>"""

# ══════════════════════════════════════════════════════════════════════════════
# 主程式
# ══════════════════════════════════════════════════════════════════════════════

def main():
    with st.sidebar:
        st.markdown("## 📊 台股分析儀表板")
        st.markdown("---")
        stock_input = st.text_input("股票代號", placeholder="例：2330", max_chars=6)
        period_map  = {"1個月":30,"3個月":90,"6個月":180,"1年":365,"2年":730}
        period_lbl  = st.selectbox("分析區間", list(period_map.keys()), index=2)
        days        = period_map[period_lbl]
        freq_map    = {"日線":"D","週線":"W","月線":"ME"}
        freq_lbl    = st.selectbox("K線週期", list(freq_map.keys()), index=0)
        freq        = freq_map[freq_lbl]
        ma_opts     = st.multiselect("均線顯示", ["MA5","MA10","MA20","MA60"],
                                     default=["MA5","MA20","MA60"])
        show_bb     = st.toggle("布林通道", value=True)
        if st.button("🔍 開始分析"):
            if stock_input.strip():
                st.session_state["analyzed"] = True
                st.session_state["active_stock_id"] = stock_input.strip()
            else:
                st.session_state["analyzed"] = False
        st.markdown("---")
        st.markdown("""<div style='font-size:11px;color:#8b949e;line-height:1.8'>
        <b>資料來源</b><br>K線 · 籌碼 · 基本面：FinMind<br>即時報價：TWSE OpenAPI<br>
        <b>快取</b><br>歷史/基本面：1hr｜即時：5min｜股名：24hr</div>""",unsafe_allow_html=True)

    analyzed = st.session_state.get("analyzed", False)

    if not analyzed:
        st.markdown("""<div style='display:flex;flex-direction:column;align-items:center;
            justify-content:center;height:65vh;gap:16px;'>
            <div style='font-size:52px;'>📊</div>
            <div style='font-size:24px;font-weight:700;color:#e6edf3;'>台股分析儀表板</div>
            <div style='font-size:14px;color:#8b949e;text-align:center;max-width:400px;line-height:1.8;'>
            技術分析・布林通道・籌碼・基本面・多股比較・排行榜<br>
            輸入股票代號 → 點選分頁查看各項分析</div>
            <div style='font-size:12px;color:#30363d;margin-top:4px;'>← 左側輸入代號後點「開始分析」</div></div>
        """, unsafe_allow_html=True)

        # 排行榜分頁可在未輸入股票時獨立顯示
        tab_rank, = st.tabs(["🏆 排行榜"])
        with tab_rank:
            render_ranking()
        return

    stock_input = st.session_state.get("active_stock_id", stock_input)

    stock_id   = stock_input.strip()
    end_date   = datetime.today().strftime("%Y-%m-%d")
    start_date = (datetime.today()-timedelta(days=days)).strftime("%Y-%m-%d")

    with st.spinner(f"抓取 {stock_id} 資料中..."):
        rt      = fetch_realtime_price(stock_id)
        df_raw  = fetch_ohlcv(stock_id, start_date, end_date)
        chip_raw= fetch_institutional(stock_id, start_date, end_date)

    if df_raw.empty:
        st.markdown(f"<div class='error-box'>⚠️ 無法取得 <b>{stock_id}</b> 資料，請確認代號是否正確，或 FinMind Token 是否設定正確。</div>",
                    unsafe_allow_html=True)
        return

    df_day  = calc_indicators(df_raw.copy())
    df      = resample_ohlcv(df_raw, freq) if freq != "D" else df_day
    if freq != "D": df = calc_indicators(df)
    chip    = process_institutional(chip_raw)
    signals = generate_signals(df_day, chip)   # 訊號永遠用日線計算

    rt_name    = rt.get("name","") if rt.get("ok") else ""
    stock_name = rt_name if (rt_name and rt_name!=stock_id) else fetch_stock_name(stock_id)
    last_close = df_day["Close"].iloc[-1]
    prev_close = df_day["Close"].iloc[-2] if len(df_day)>1 else last_close
    chg        = last_close - prev_close
    chg_pct    = chg/prev_close*100 if prev_close else 0
    price_show = rt.get("price") if rt.get("ok") and rt.get("price") else last_close
    chg_cls    = "up" if chg>=0 else "down"
    chg_icon   = "▲" if chg>=0 else "▼"

    # 頁頭
    hc1,hc2 = st.columns([4,1])
    with hc1:
        market_badge = {"tse":"上市","otc":"上櫃"}.get(rt.get("market",""),"")
        badge_html   = f"<span style='background:#21262d;border:1px solid #30363d;border-radius:4px;padding:2px 8px;font-size:11px;color:#8b949e;margin-left:8px;'>{market_badge}</span>" if market_badge else ""
        st.markdown(f"<div style='display:flex;align-items:baseline;gap:10px;'>"
                    f"<span style='font-size:30px;font-weight:800;'>{stock_name}</span>"
                    f"<span style='font-size:16px;color:#8b949e;'>{stock_id}</span>"
                    f"{badge_html}</div>", unsafe_allow_html=True)
    with hc2:
        ts = rt.get("time","") if rt.get("ok") else "歷史收盤"
        st.markdown(f"<div style='text-align:right;color:#8b949e;font-size:12px;padding-top:16px;'>{freq_lbl} · {ts}</div>",unsafe_allow_html=True)

    # 指標卡片
    last = df_day.iloc[-1]
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    with c1:
        st.markdown(metric_card("現價",f"{price_show:.2f}",
            f"{chg_icon} {abs(chg):.2f} ({abs(chg_pct):.2f}%)",chg_cls),unsafe_allow_html=True)
    with c2:
        ma20 = last.get("MA20",np.nan)
        diff = last_close-ma20 if pd.notna(ma20) else 0
        st.markdown(metric_card("MA20",f"{ma20:.1f}" if pd.notna(ma20) else "—",
            f"{'高' if diff>=0 else '低'} {abs(diff):.1f}"),unsafe_allow_html=True)
    with c3:
        rsi = last.get("RSI",np.nan)
        rc  = "up" if pd.notna(rsi) and rsi<30 else ("down" if pd.notna(rsi) and rsi>70 else "neutral")
        rd  = "超賣" if pd.notna(rsi) and rsi<30 else ("超買" if pd.notna(rsi) and rsi>70 else "中性")
        st.markdown(metric_card("RSI(14)",f"{rsi:.1f}" if pd.notna(rsi) else "—",rd,rc),unsafe_allow_html=True)
    with c4:
        macd = last.get("MACD",np.nan)
        mc   = "up" if pd.notna(macd) and macd>0 else "down"
        st.markdown(metric_card("MACD",f"{macd:.2f}" if pd.notna(macd) else "—",
            "多頭" if pd.notna(macd) and macd>0 else "空頭",mc),unsafe_allow_html=True)
    with c5:
        bb_pct = last.get("BB_%B",np.nan)
        bb_c   = "up" if pd.notna(bb_pct) and bb_pct<20 else ("down" if pd.notna(bb_pct) and bb_pct>80 else "neutral")
        st.markdown(metric_card("布林%B",f"{bb_pct:.0f}%" if pd.notna(bb_pct) else "—",
            "接近下軌" if pd.notna(bb_pct) and bb_pct<20 else ("接近上軌" if pd.notna(bb_pct) and bb_pct>80 else "帶中"),bb_c),unsafe_allow_html=True)
    with c6:
        vol = df_day["Volume"].iloc[-1] if "Volume" in df_day.columns else 0
        vol_ma = last.get("Vol_MA20",0)
        ratio  = vol/vol_ma if vol_ma else 0
        vc = "up" if ratio>1.2 else ("down" if ratio<0.8 else "neutral")
        st.markdown(metric_card("成交量",f"{vol/1000:.0f}K",f"均量 {ratio:.1f}x",vc),unsafe_allow_html=True)

    # 分頁
    t1,t2,t3,t4,t5 = st.tabs(["📈 技術分析","📊 基本面","🔀 多股比較","🏆 排行榜","💰 ETF分析"])

    # ── Tab 1：技術分析 ────────────────────────────────────────────────────────
    with t1:
        st.plotly_chart(draw_main_chart(df, ma_opts, show_bb),
                        use_container_width=True, config={"displayModeBar":False})
        col_sig, col_chip = st.columns([1,1])
        with col_sig:
            st.markdown("<div class='section-hdr'>綜合訊號分析</div>", unsafe_allow_html=True)
            if signals:
                vtype, vtxt = get_verdict(signals)
                css_map = {"bull":"verdict-bull","bear":"verdict-bear","mid":"verdict-mid"}
                st.markdown(f"<div class='verdict-box {css_map[vtype]}'>{vtxt}</div>",unsafe_allow_html=True)
                for label,kind,detail in signals:
                    st.markdown(sig_html(label,kind,detail),unsafe_allow_html=True)
        with col_chip:
            st.markdown("<div class='section-hdr'>三大法人籌碼（近30日）</div>",unsafe_allow_html=True)
            if not chip.empty:
                st.plotly_chart(draw_chip_chart(chip.tail(30)),
                                use_container_width=True,config={"displayModeBar":False})
                last5 = chip.tail(5)
                ccols = st.columns(4)
                for i,(cn,lbl) in enumerate([("外資","外資"),("投信","投信"),("自營商","自營商"),("合計","合計")]):
                    if cn in last5.columns:
                        tot = last5[cn].sum()/1000
                        clr = "#3fb950" if tot>=0 else "#f85149"
                        sg  = "+" if tot>=0 else ""
                        ccols[i].markdown(f"""<div style='text-align:center;padding:10px;background:#161b22;
                            border-radius:6px;border:1px solid #30363d;'>
                            <div style='font-size:10px;color:#8b949e;'>{lbl} 近5日</div>
                            <div style='font-size:16px;font-weight:700;color:{clr};'>{sg}{tot:.0f}K</div></div>""",
                            unsafe_allow_html=True)
            else:
                st.markdown("<div class='warn-box'>籌碼資料暫無（FinMind 免費版每小時600次，請稍後再試）</div>",unsafe_allow_html=True)
        with st.expander("📋 原始 K 線資料",expanded=False):
            cols = [c for c in ["date","Open","High","Low","Close","Volume","MA5","MA20","MA60","RSI","MACD","BB_upper","BB_lower","BB_%B"] if c in df_day.columns]
            st.dataframe(df_day[cols].tail(30).iloc[::-1].reset_index(drop=True),use_container_width=True,height=300)

    # ── Tab 2：基本面 ──────────────────────────────────────────────────────────
    with t2:
        fd_start = (datetime.today()-timedelta(days=365)).strftime("%Y-%m-%d")
        with st.spinner("載入基本面資料..."):
            per_df = fetch_fundamental(stock_id, fd_start)
            rev_df = fetch_monthly_revenue(stock_id)
            eps_df = fetch_eps(stock_id)

        if not per_df.empty:
            latest = per_df.iloc[-1]
            pc1,pc2,pc3 = st.columns(3)
            def fd_card(col,label,unit=""):
                v = latest.get(col,np.nan)
                return metric_card(label, f"{v:.2f}{unit}" if pd.notna(v) else "—", "最新值")
            pc1.markdown(fd_card("PER","本益比(PER)","x"),unsafe_allow_html=True)
            pc2.markdown(fd_card("PBR","股價淨值比(PBR)","x"),unsafe_allow_html=True)
            pc3.markdown(fd_card("DividendYield","殖利率","%"),unsafe_allow_html=True)
            charts = draw_fundamental_charts(per_df, rev_df, eps_df)
            for c in charts:
                st.plotly_chart(c, use_container_width=True, config={"displayModeBar":False})
        else:
            st.markdown("<div class='warn-box'>基本面資料暫無（FinMind 免費版可能需稍等配額恢復）</div>",unsafe_allow_html=True)
        if not rev_df.empty and "revenue" in rev_df.columns:
            st.markdown("<div class='section-hdr'>月營收明細</div>",unsafe_allow_html=True)
            disp = rev_df[["date","revenue"]].copy()
            disp["revenue"] = (disp["revenue"]/1e8).round(2)
            disp.columns = ["日期","月營收(億元)"]
            st.dataframe(disp.iloc[::-1].reset_index(drop=True),use_container_width=True,height=280)

    # ── Tab 3：多股比較 ────────────────────────────────────────────────────────
    with t3:
        st.markdown("<div class='section-hdr'>輸入要比較的股票代號（最多5支，逗號或空格分隔）</div>",unsafe_allow_html=True)
        compare_input = st.text_input("",placeholder=f"例：{stock_id}, 2317, 2454",
                                      value=stock_id, key="compare_input")
        if st.button("🔀 開始比較", key="run_compare"):
            ids = [x.strip() for x in compare_input.replace(","," ").split() if x.strip()][:5]
            if len(ids) < 2:
                st.markdown("<div class='warn-box'>至少輸入2支股票</div>",unsafe_allow_html=True)
            else:
                with st.spinner("抓取比較資料..."):
                    stock_data = {}
                    for sid in ids:
                        d = fetch_ohlcv(sid, start_date, end_date)
                        if not d.empty: stock_data[fetch_stock_name(sid)+f"({sid})"] = d
                if len(stock_data) >= 2:
                    st.plotly_chart(draw_comparison_chart(stock_data),
                                   use_container_width=True,config={"displayModeBar":False})
                    st.caption("以各股起始日收盤價為基準，顯示相對漲跌幅（%）")
                else:
                    st.markdown("<div class='warn-box'>部分股票資料無法取得，請確認代號</div>",unsafe_allow_html=True)

    # ── Tab 4：排行榜 ──────────────────────────────────────────────────────────
    with t4:
        render_ranking()

    # ── Tab 5：ETF分析 ─────────────────────────────────────────────────────────
    with t5:
        render_etf_analysis(stock_id)


def calc_etf_single_return(etf_id, buy_date, cost_price, shares):
    """計算單檔ETF：資本利得 + 累積配息 的完整總報酬"""
    result = {"ok": False}
    try:
        end_date = datetime.today().strftime("%Y-%m-%d")
        buy_date_str = buy_date.strftime("%Y-%m-%d")
        price_df = fetch_ohlcv(etf_id, buy_date_str, end_date)
        if price_df.empty:
            result["error"] = "查無此ETF代號的價格資料"
            return result
        rt = fetch_realtime_price(etf_id)
        current_price = rt.get("price") if rt.get("ok") and rt.get("price") else price_df["Close"].iloc[-1]

        div_df = fetch_etf_dividend(etf_id)
        if not div_df.empty:
            div_df = div_df[div_df["date"] >= pd.Timestamp(buy_date)]
        cash_col = "CashEarningsDistribution" if (not div_df.empty and "CashEarningsDistribution" in div_df.columns) else None
        total_dividend_per_share = div_df[cash_col].sum() if cash_col else 0
        dividend_count = len(div_df) if cash_col else 0

        cost_total      = cost_price * shares
        market_value    = current_price * shares
        capital_gain    = market_value - cost_total
        capital_gain_pct= capital_gain / cost_total * 100 if cost_total else 0
        dividend_total  = total_dividend_per_share * shares
        dividend_pct    = dividend_total / cost_total * 100 if cost_total else 0
        total_return     = capital_gain + dividend_total
        total_return_pct = total_return / cost_total * 100 if cost_total else 0

        holding_days = (datetime.today().date() - buy_date).days
        holding_years = max(holding_days/365, 0.01)
        annualized_pct = ((1 + total_return_pct/100) ** (1/holding_years) - 1) * 100

        result.update({
            "ok": True, "current_price": current_price, "cost_price": cost_price,
            "shares": shares, "cost_total": cost_total, "market_value": market_value,
            "capital_gain": capital_gain, "capital_gain_pct": capital_gain_pct,
            "dividend_total": dividend_total, "dividend_pct": dividend_pct,
            "dividend_count": dividend_count, "total_dividend_per_share": total_dividend_per_share,
            "total_return": total_return, "total_return_pct": total_return_pct,
            "annualized_pct": annualized_pct, "holding_days": holding_days,
            "price_df": price_df, "div_df": div_df,
        })
    except Exception as e:
        result["error"] = str(e)
    return result


def calc_etf_comparison_return(etf_ids, start_date, invest_amount):
    """多檔ETF比較：假設同一天投入同樣金額，比較資本利得%與配息%"""
    results = []
    end_date = datetime.today().strftime("%Y-%m-%d")
    start_date_str = start_date.strftime("%Y-%m-%d")
    for eid in etf_ids:
        try:
            price_df = fetch_ohlcv(eid, start_date_str, end_date)
            if price_df.empty:
                results.append({"etf_id": eid, "ok": False, "error": "查無價格資料"})
                continue
            start_price = price_df["Close"].iloc[0]
            rt = fetch_realtime_price(eid)
            current_price = rt.get("price") if rt.get("ok") and rt.get("price") else price_df["Close"].iloc[-1]
            shares = invest_amount / start_price if start_price else 0

            div_df = fetch_etf_dividend(eid)
            if not div_df.empty:
                div_df = div_df[div_df["date"] >= pd.Timestamp(start_date)]
            cash_col = "CashEarningsDistribution" if (not div_df.empty and "CashEarningsDistribution" in div_df.columns) else None
            div_per_share = div_df[cash_col].sum() if cash_col else 0

            capital_gain_pct = (current_price - start_price) / start_price * 100 if start_price else 0
            dividend_total   = div_per_share * shares
            dividend_pct     = dividend_total / invest_amount * 100 if invest_amount else 0
            total_pct        = capital_gain_pct + dividend_pct
            name = fetch_stock_name(eid)

            results.append({
                "etf_id": eid, "ok": True, "name": name,
                "start_price": start_price, "current_price": current_price,
                "capital_gain_pct": capital_gain_pct, "dividend_pct": dividend_pct,
                "total_pct": total_pct, "dividend_count": len(div_df) if cash_col else 0,
            })
        except Exception as e:
            results.append({"etf_id": eid, "ok": False, "error": str(e)})
    return results


def draw_etf_comparison_chart(results):
    ok_results = [r for r in results if r.get("ok")]
    if not ok_results: return None
    ok_results.sort(key=lambda r: r["total_pct"], reverse=True)
    labels = [f"{r['name']}({r['etf_id']})" for r in ok_results]
    cap    = [r["capital_gain_pct"] for r in ok_results]
    div    = [r["dividend_pct"] for r in ok_results]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=cap, name="價差報酬%",
                         marker_color="#58a6ff", opacity=0.85))
    fig.add_trace(go.Bar(x=labels, y=div, name="配息報酬%",
                         marker_color="#3fb950", opacity=0.85))
    fig.update_layout(**chart_layout(360), barmode="stack",
        xaxis=dict(gridcolor="#21262d"),
        yaxis=dict(gridcolor="#21262d", title="報酬率 %"))
    fig.add_hline(y=0, line_dash="dash", line_color="#8b949e", line_width=0.8)
    return fig


def draw_etf_value_chart(price_df, cost_price, shares):
    """畫出持有市值隨時間變化，跟成本線比較"""
    fig = go.Figure()
    market_val = price_df["Close"] * shares
    cost_val   = cost_price * shares
    fig.add_trace(go.Scatter(x=price_df["date"], y=market_val, mode="lines",
        line=dict(color="#58a6ff", width=2), name="市值", fill="tozeroy",
        fillcolor="rgba(88,166,255,0.08)"))
    fig.add_hline(y=cost_val, line_dash="dash", line_color="#e3b341",
                 annotation_text=f"成本 {cost_val:,.0f}", annotation_font_color="#e3b341")
    fig.update_layout(**chart_layout(280),
        xaxis=dict(gridcolor="#21262d"),
        yaxis=dict(gridcolor="#21262d", title="市值(元)"))
    return fig


def render_etf_analysis(default_etf_id):
    et1, et2 = st.tabs(["📍 單檔分析", "🔀 多檔比較"])

    # ── 單檔深入分析 ──────────────────────────────────────────────────────────
    with et1:
        st.markdown("<div class='section-hdr'>輸入你的實際持有資訊，計算真實總報酬（價差＋配息）</div>",unsafe_allow_html=True)
        sc1,sc2,sc3 = st.columns(3)
        with sc1:
            etf_id_input = st.text_input("ETF代號", value=default_etf_id if default_etf_id else "00878", key="etf_single_id")
        with sc2:
            cost_price = st.number_input("每股成本(元)", min_value=0.0, value=20.0, step=0.01, key="etf_cost")
        with sc3:
            shares = st.number_input("持有股數", min_value=0, value=1000, step=100, key="etf_shares")
        buy_date = st.date_input("買入日期", value=datetime.today()-timedelta(days=365),
                                 max_value=datetime.today(), key="etf_buy_date")

        if st.button("📊 計算總報酬", key="calc_etf_single"):
            with st.spinner("計算中..."):
                r = calc_etf_single_return(etf_id_input.strip(), buy_date, cost_price, shares)
            if not r.get("ok"):
                st.markdown(f"<div class='error-box'>⚠️ {r.get('error','資料取得失敗，請確認代號是否正確')}</div>",unsafe_allow_html=True)
            else:
                name = fetch_stock_name(etf_id_input.strip())
                st.markdown(f"### {name} ({etf_id_input.strip()})")

                rc1,rc2,rc3,rc4 = st.columns(4)
                rc1.markdown(metric_card("總投入成本", f"{r['cost_total']:,.0f} 元", f"{r['shares']:.0f}股 × {r['cost_price']:.2f}"),unsafe_allow_html=True)
                rc2.markdown(metric_card("目前市值", f"{r['market_value']:,.0f} 元", f"現價 {r['current_price']:.2f}"),unsafe_allow_html=True)
                gain_cls = "up" if r['capital_gain']>=0 else "down"
                rc3.markdown(metric_card("資本利得(價差)", f"{r['capital_gain']:+,.0f} 元",
                    f"{r['capital_gain_pct']:+.2f}%", gain_cls),unsafe_allow_html=True)
                rc4.markdown(metric_card("累積配息", f"{r['dividend_total']:+,.0f} 元",
                    f"{r['dividend_pct']:.2f}%｜配息{r['dividend_count']}次", "up"),unsafe_allow_html=True)

                total_cls = "up" if r['total_return']>=0 else "down"
                verdict_css = "verdict-bull" if r['total_return_pct']>=0 else "verdict-bear"
                holding_label = f"{r['holding_days']}天（約{r['holding_days']/365:.1f}年）"
                st.markdown(f"""<div class='verdict-box {verdict_css}' style='margin-top:14px;'>
                    💰 總報酬：{r['total_return']:+,.0f} 元（{r['total_return_pct']:+.2f}%）
                    ｜年化報酬率約 {r['annualized_pct']:+.2f}%　｜持有 {holding_label}</div>""",
                    unsafe_allow_html=True)

                # 報酬拆解說明
                if r['capital_gain'] < 0 and r['dividend_total'] > abs(r['capital_gain']):
                    st.markdown("<div class='warn-box'>📌 股價是虧損的，但配息把虧損補回來了——這就是「賺股息賠價差」的典型情況，總報酬仍為正。</div>",unsafe_allow_html=True)
                elif r['capital_gain'] < 0 and r['total_return'] < 0:
                    st.markdown("<div class='error-box'>📌 股價虧損且配息不足以打平，目前總報酬為負，屬於「賺股息賠價差」的虧損情境。</div>",unsafe_allow_html=True)
                elif r['capital_gain'] > 0:
                    st.markdown("<div class='warn-box' style='color:#3fb950;border-color:#2d6a4f;background:#1a4731;'>📌 股價上漲加上配息，價差跟配息都有正貢獻。</div>",unsafe_allow_html=True)

                st.markdown("<div class='section-hdr' style='margin-top:20px;'>持有期間市值變化</div>",unsafe_allow_html=True)
                st.plotly_chart(draw_etf_value_chart(r["price_df"], r["cost_price"], r["shares"]),
                                use_container_width=True, config={"displayModeBar":False})

                if not r["div_df"].empty:
                    with st.expander("📋 配息明細", expanded=False):
                        cash_col = "CashEarningsDistribution"
                        disp = r["div_df"][["date",cash_col]].copy()
                        disp.columns = ["除息日","每股配息(元)"]
                        disp["持股配息(元)"] = (disp["每股配息(元)"] * shares).round(0)
                        st.dataframe(disp.iloc[::-1].reset_index(drop=True), use_container_width=True, height=250)

    # ── 多檔比較 ──────────────────────────────────────────────────────────────
    with et2:
        st.markdown("<div class='section-hdr'>假設同一天投入相同金額，比較不同ETF的「價差報酬」vs「配息報酬」</div>",unsafe_allow_html=True)
        mc1,mc2 = st.columns(2)
        with mc1:
            compare_etfs = st.text_input("ETF代號（逗號分隔，最多6檔）",
                value="00878, 00929, 00919, 00713", key="etf_compare_ids")
        with mc2:
            invest_amount = st.number_input("假設投入金額(元/檔)", min_value=1000, value=100000, step=10000, key="etf_invest_amt")
        compare_start = st.date_input("假設投入日期", value=datetime.today()-timedelta(days=365),
                                      max_value=datetime.today(), key="etf_compare_date")

        if st.button("🔀 開始比較", key="run_etf_compare"):
            ids = [x.strip() for x in compare_etfs.replace("，",",").split(",") if x.strip()][:6]
            if len(ids) < 2:
                st.markdown("<div class='warn-box'>請至少輸入2檔ETF代號</div>",unsafe_allow_html=True)
            else:
                with st.spinner("計算各檔ETF報酬中..."):
                    results = calc_etf_comparison_return(ids, compare_start, invest_amount)

                ok_results = [r for r in results if r.get("ok")]
                fail_results = [r for r in results if not r.get("ok")]

                if ok_results:
                    chart = draw_etf_comparison_chart(results)
                    if chart:
                        st.plotly_chart(chart, use_container_width=True, config={"displayModeBar":False})
                    st.caption(f"假設 {compare_start.strftime('%Y-%m-%d')} 投入 {invest_amount:,} 元，統計至今的累積報酬拆解")

                    st.markdown("<div class='section-hdr' style='margin-top:10px;'>詳細數據</div>",unsafe_allow_html=True)
                    sorted_results = sorted(ok_results, key=lambda r: r["total_pct"], reverse=True)
                    hdr = st.columns([0.5,2,1.2,1.2,1.2,1.2])
                    for col,txt in zip(hdr,["#","ETF","價差%","配息%","配息次數","總報酬%"]):
                        col.markdown(f"<div style='font-size:11px;color:#8b949e;font-weight:600;'>{txt}</div>",unsafe_allow_html=True)
                    st.markdown("<hr style='border-color:#30363d;margin:4px 0 10px 0;'>",unsafe_allow_html=True)
                    for rank,r in enumerate(sorted_results,1):
                        row = st.columns([0.5,2,1.2,1.2,1.2,1.2])
                        row[0].markdown(f"<b>#{rank}</b>",unsafe_allow_html=True)
                        row[1].markdown(f"{r['name']} ({r['etf_id']})",unsafe_allow_html=True)
                        cap_clr = "#3fb950" if r['capital_gain_pct']>=0 else "#f85149"
                        row[2].markdown(f"<span style='color:{cap_clr};'>{r['capital_gain_pct']:+.2f}%</span>",unsafe_allow_html=True)
                        row[3].markdown(f"<span style='color:#3fb950;'>{r['dividend_pct']:+.2f}%</span>",unsafe_allow_html=True)
                        row[4].markdown(f"{r['dividend_count']}次",unsafe_allow_html=True)
                        tot_clr = "#3fb950" if r['total_pct']>=0 else "#f85149"
                        row[5].markdown(f"<b style='color:{tot_clr};'>{r['total_pct']:+.2f}%</b>",unsafe_allow_html=True)

                if fail_results:
                    fail_ids = ", ".join(r["etf_id"] for r in fail_results)
                    st.markdown(f"<div class='warn-box' style='margin-top:10px;'>⚠️ 以下代號查詢失敗，請確認是否正確：{fail_ids}</div>",unsafe_allow_html=True)


def render_ranking():
    rt1, rt2 = st.tabs(["📈 技術訊號排行", "💰 月配息 ETF 排行"])

    with rt1:
        st.markdown("<div class='section-hdr'>主要大型股技術強弱評分（每小時更新）</div>",unsafe_allow_html=True)
        st.markdown("<div class='warn-box' style='margin-bottom:16px;'>此功能會對20支股票各發送1次API請求，建議每小時查詢1次以節省配額。</div>",unsafe_allow_html=True)
        if st.button("🔄 掃描排行", key="scan_ranking"):
            end   = datetime.today().strftime("%Y-%m-%d")
            start = (datetime.today()-timedelta(days=120)).strftime("%Y-%m-%d")
            results = []
            prog = st.progress(0)
            for i,sid in enumerate(WATCHLIST_STOCKS):
                prog.progress((i+1)/len(WATCHLIST_STOCKS), text=f"掃描 {sid}...")
                df_s = fetch_ohlcv(sid, start, end)
                if df_s.empty: continue
                df_s = calc_indicators(df_s)
                score = calc_tech_score(df_s)
                name  = fetch_stock_name(sid)
                last  = df_s.iloc[-1]
                close = last.get("Close",0)
                rsi   = last.get("RSI",np.nan)
                macd  = last.get("MACD",np.nan)
                results.append((score, sid, name, close, rsi, macd))
            prog.empty()
            results.sort(reverse=True)
            st.markdown("### 🔼 技術偏多 Top 10")
            for rank,(score,sid,name,close,rsi,macd) in enumerate(results[:10],1):
                score_color = "#3fb950" if score>=60 else ("#e3b341" if score>=45 else "#f85149")
                rsi_str  = f"{rsi:.0f}" if pd.notna(rsi) else "—"
                macd_str = f"{macd:.2f}" if pd.notna(macd) else "—"
                st.markdown(f"""<div class='rank-row'>
                    <div class='rank-num'>#{rank}</div>
                    <div class='rank-name'>{name} <span style='font-size:12px;color:#8b949e;'>({sid})</span></div>
                    <div style='font-family:monospace;font-size:14px;'>{close:.2f}</div>
                    <div class='rank-score'>RSI {rsi_str}｜MACD {macd_str}</div>
                    <div style='font-weight:700;color:{score_color};font-size:15px;margin-left:auto;'>{score}分</div>
                </div>""", unsafe_allow_html=True)
            if len(results) > 10:
                st.markdown("### 🔽 技術偏空 Bottom")
                for rank,(score,sid,name,close,rsi,macd) in enumerate(reversed(results[-5:]),1):
                    score_color = "#f85149"
                    rsi_str  = f"{rsi:.0f}" if pd.notna(rsi) else "—"
                    st.markdown(f"""<div class='rank-row'>
                        <div class='rank-name'>{name} <span style='font-size:12px;color:#8b949e;'>({sid})</span></div>
                        <div style='font-family:monospace;font-size:14px;'>{close:.2f}</div>
                        <div class='rank-score'>RSI {rsi_str}</div>
                        <div style='font-weight:700;color:{score_color};font-size:15px;margin-left:auto;'>{score}分</div>
                    </div>""", unsafe_allow_html=True)

    with rt2:
        st.markdown("<div class='section-hdr'>月配息高股息 ETF 殖利率排行（近12個月配息統計）</div>",unsafe_allow_html=True)
        if st.button("💰 載入 ETF 排行", key="load_etf"):
            etf_results = []
            prog2 = st.progress(0)
            end = datetime.today().strftime("%Y-%m-%d")
            for i,(eid,ename) in enumerate(MONTHLY_ETF_LIST):
                prog2.progress((i+1)/len(MONTHLY_ETF_LIST), text=f"載入 {eid} {ename}...")
                div_df = fetch_etf_dividend(eid)
                rt_e   = fetch_realtime_price(eid)
                price  = rt_e.get("price",0) if rt_e.get("ok") else 0
                if div_df.empty or price == 0:
                    etf_results.append((0,eid,ename,price,"—","—"))
                    continue
                cash_col = "CashEarningsDistribution" if "CashEarningsDistribution" in div_df.columns else None
                if cash_col:
                    annual = div_df[cash_col].sum()
                    yield_pct = annual/price*100 if price else 0
                    count  = len(div_df)
                    last_d = div_df.iloc[-1][cash_col]
                    etf_results.append((yield_pct,eid,ename,price,f"{annual:.2f}",f"{count}次"))
                else:
                    etf_results.append((0,eid,ename,price,"—","—"))
            prog2.empty()
            etf_results.sort(reverse=True)
            hdr = st.columns([0.5,1.5,2.5,1,1,1,1])
            for col,txt in zip(hdr,["#","代號","名稱","現價","年配息","次數","殖利率"]):
                col.markdown(f"<div style='font-size:11px;color:#8b949e;font-weight:600;'>{txt}</div>",unsafe_allow_html=True)
            st.markdown("<hr style='border-color:#30363d;margin:4px 0 10px 0;'>",unsafe_allow_html=True)
            for rank,(yld,eid,ename,price,annual,count) in enumerate(etf_results,1):
                yld_color = "#3fb950" if yld>=6 else ("#e3b341" if yld>=4 else "#8b949e")
                row = st.columns([0.5,1.5,2.5,1,1,1,1])
                row[0].markdown(f"<div style='color:#8b949e;font-size:14px;font-weight:700;'>#{rank}</div>",unsafe_allow_html=True)
                row[1].markdown(f"<div style='font-size:13px;'>{eid}</div>",unsafe_allow_html=True)
                row[2].markdown(f"<div style='font-size:13px;font-weight:600;'>{ename}</div>",unsafe_allow_html=True)
                row[3].markdown(f"<div style='font-family:monospace;'>{price:.2f}</div>",unsafe_allow_html=True)
                row[4].markdown(f"<div style='font-family:monospace;'>{annual}</div>",unsafe_allow_html=True)
                row[5].markdown(f"<div style='color:#8b949e;'>{count}</div>",unsafe_allow_html=True)
                row[6].markdown(f"<div style='font-weight:700;color:{yld_color};font-size:15px;'>{yld:.2f}%</div>",unsafe_allow_html=True)


if __name__ == "__main__" or True:
    main()
