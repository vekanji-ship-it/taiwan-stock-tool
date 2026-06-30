import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ─── 頁面設定 ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="台股技術分析",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── CSS 樣式 ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* 主背景 */
    .stApp { background-color: #0d1117; color: #e6edf3; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    
    /* 指標卡片 */
    .metric-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 12px;
    }
    .metric-card .label { font-size: 11px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px; }
    .metric-card .value { font-size: 22px; font-weight: 700; font-family: 'Courier New', monospace; }
    .metric-card .delta { font-size: 13px; margin-top: 2px; }
    .up { color: #3fb950; }
    .down { color: #f85149; }
    .neutral { color: #8b949e; }
    
    /* 訊號徽章 */
    .signal-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 0.05em;
    }
    .signal-buy { background: #1a4731; color: #3fb950; border: 1px solid #2d6a4f; }
    .signal-sell { background: #3d1f1f; color: #f85149; border: 1px solid #6b2222; }
    .signal-hold { background: #272e3b; color: #e3b341; border: 1px solid #4a3b1a; }
    .signal-neutral { background: #21262d; color: #8b949e; border: 1px solid #30363d; }
    
    /* 區塊標題 */
    .section-header {
        font-size: 13px;
        font-weight: 600;
        color: #8b949e;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        border-bottom: 1px solid #30363d;
        padding-bottom: 8px;
        margin-bottom: 16px;
    }
    
    /* 錯誤與警告 */
    .error-box {
        background: #3d1f1f;
        border: 1px solid #6b2222;
        border-radius: 8px;
        padding: 12px 16px;
        color: #f85149;
        font-size: 13px;
    }
    .warn-box {
        background: #272e3b;
        border: 1px solid #4a3b1a;
        border-radius: 8px;
        padding: 12px 16px;
        color: #e3b341;
        font-size: 13px;
    }
    
    /* 籌碼表格 */
    .chip-table { font-size: 13px; }
    
    /* Plotly 圖表背景 */
    .js-plotly-plot .plotly .bg { fill: #0d1117 !important; }

    div[data-testid="stMetricValue"] { color: #e6edf3; }
    div[data-testid="stMetricDelta"] svg { display: none; }
    
    /* 隱藏 Streamlit watermark */
    #MainMenu, footer { visibility: hidden; }
    
    /* 輸入框 */
    .stTextInput input {
        background: #21262d;
        border: 1px solid #30363d;
        color: #e6edf3;
        border-radius: 6px;
        font-size: 15px;
    }
    .stButton button {
        background: #238636;
        color: white;
        border: 1px solid #2ea043;
        border-radius: 6px;
        font-weight: 600;
        width: 100%;
    }
    .stButton button:hover { background: #2ea043; }
    
    .stSelectbox > div > div {
        background: #21262d;
        border: 1px solid #30363d;
        color: #e6edf3;
    }
</style>
""", unsafe_allow_html=True)

# ─── API 設定 ────────────────────────────────────────────────────────────────
try:
    FINMIND_TOKEN = st.secrets.get("FINMIND_TOKEN", "")
except Exception:
    FINMIND_TOKEN = ""

FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"
TWSE_BASE    = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"

# ─── 資料抓取函數（每個都有 try/except） ────────────────────────────────────

@st.cache_data(ttl=3600)
def fetch_ohlcv(stock_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """從 FinMind 抓取 K 線資料（快取 1 小時）"""
    try:
        params = {
            "dataset": "TaiwanStockPrice",
            "data_id": stock_id,
            "start_date": start_date,
            "end_date": end_date,
            "token": FINMIND_TOKEN,
        }
        r = requests.get(FINMIND_BASE, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get("status") != 200 or not data.get("data"):
            return pd.DataFrame()
        df = pd.DataFrame(data["data"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df.rename(columns={
            "open": "Open", "max": "High", "min": "Low",
            "close": "Close", "Trading_Volume": "Volume"
        }, inplace=True)
        numeric_cols = ["Open", "High", "Low", "Close", "Volume"]
        for c in numeric_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        return df
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_institutional(stock_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """從 FinMind 抓取三大法人籌碼"""
    try:
        params = {
            "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
            "data_id": stock_id,
            "start_date": start_date,
            "end_date": end_date,
            "token": FINMIND_TOKEN,
        }
        r = requests.get(FINMIND_BASE, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get("status") != 200 or not data.get("data"):
            return pd.DataFrame()
        df = pd.DataFrame(data["data"])
        df["date"] = pd.to_datetime(df["date"])
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def fetch_realtime_price(stock_id: str) -> dict:
    """從 TWSE 抓即時報價（快取 5 分鐘）"""
    try:
        params = {"ex_ch": f"tse_{stock_id}.tw", "json": 1, "delay": 0}
        headers = {"Referer": "https://mis.twse.com.tw"}
        r = requests.get(TWSE_BASE, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("rtmessage") == "OK" and data.get("msgArray"):
            item = data["msgArray"][0]
            return {
                "name":   item.get("n", stock_id),
                "price":  float(item.get("z", 0) or 0),
                "open":   float(item.get("o", 0) or 0),
                "high":   float(item.get("h", 0) or 0),
                "low":    float(item.get("l", 0) or 0),
                "prev":   float(item.get("y", 0) or 0),
                "volume": int(item.get("v", 0) or 0),
                "time":   item.get("t", ""),
                "ok":     True
            }
    except Exception:
        pass
    return {"ok": False}

# ─── 技術指標計算 ────────────────────────────────────────────────────────────

def calc_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """計算 MA / RSI / MACD，不依賴外部套件"""
    if df.empty or "Close" not in df.columns:
        return df
    
    close = df["Close"]
    
    # MA
    for period in [5, 10, 20, 60]:
        df[f"MA{period}"] = close.rolling(period).mean().round(2)
    
    # RSI (14)
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss.replace(0, np.nan)
    df["RSI"] = (100 - 100 / (1 + rs)).round(2)
    
    # MACD (12, 26, 9)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["MACD"]        = (ema12 - ema26).round(3)
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean().round(3)
    df["MACD_hist"]   = (df["MACD"] - df["MACD_signal"]).round(3)
    
    return df

def process_institutional(chip_df: pd.DataFrame) -> pd.DataFrame:
    """整理三大法人淨買賣"""
    if chip_df.empty:
        return pd.DataFrame()
    try:
        df = chip_df.copy()
        df["net"] = pd.to_numeric(df["buy"], errors="coerce") - pd.to_numeric(df["sell"], errors="coerce")
        pivot = df.pivot_table(index="date", columns="name", values="net", aggfunc="sum")
        pivot.columns.name = None
        pivot = pivot.reset_index()
        # 標準化欄位名稱
        rename = {}
        for c in pivot.columns:
            if "外資" in str(c):   rename[c] = "外資"
            elif "投信" in str(c): rename[c] = "投信"
            elif "自營" in str(c): rename[c] = "自營商"
        pivot.rename(columns=rename, inplace=True)
        for col in ["外資", "投信", "自營商"]:
            if col not in pivot.columns:
                pivot[col] = 0
        pivot["合計"] = pivot[["外資", "投信", "自營商"]].sum(axis=1)
        return pivot.sort_values("date")
    except Exception:
        return pd.DataFrame()

# ─── 訊號判斷 ────────────────────────────────────────────────────────────────

def generate_signals(df: pd.DataFrame, chip_df: pd.DataFrame) -> list:
    """根據指標產出訊號清單"""
    signals = []
    if df.empty or len(df) < 2:
        return signals
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # MA 均線多空排列
    try:
        ma5, ma20, ma60 = last.get("MA5"), last.get("MA20"), last.get("MA60")
        if pd.notna(ma5) and pd.notna(ma20) and pd.notna(ma60):
            if ma5 > ma20 > ma60:
                signals.append(("均線多頭排列", "buy", f"MA5 {ma5:.1f} > MA20 {ma20:.1f} > MA60 {ma60:.1f}"))
            elif ma5 < ma20 < ma60:
                signals.append(("均線空頭排列", "sell", f"MA5 {ma5:.1f} < MA20 {ma20:.1f} < MA60 {ma60:.1f}"))
            else:
                signals.append(("均線糾結整理", "hold", f"MA5 {ma5:.1f} / MA20 {ma20:.1f} / MA60 {ma60:.1f}"))
    except Exception:
        pass
    
    # RSI
    try:
        rsi = last.get("RSI")
        if pd.notna(rsi):
            if rsi < 30:
                signals.append(("RSI 超賣", "buy", f"RSI = {rsi:.1f}，接近反彈區"))
            elif rsi > 70:
                signals.append(("RSI 超買", "sell", f"RSI = {rsi:.1f}，注意拉回風險"))
            else:
                signals.append(("RSI 中性", "neutral", f"RSI = {rsi:.1f}"))
    except Exception:
        pass
    
    # MACD 黃金/死亡交叉
    try:
        macd, sig = last.get("MACD"), last.get("MACD_signal")
        prev_macd, prev_sig = prev.get("MACD"), prev.get("MACD_signal")
        if all(pd.notna(x) for x in [macd, sig, prev_macd, prev_sig]):
            if prev_macd < prev_sig and macd > sig:
                signals.append(("MACD 黃金交叉", "buy", f"MACD 由下往上穿越訊號線"))
            elif prev_macd > prev_sig and macd < sig:
                signals.append(("MACD 死亡交叉", "sell", f"MACD 由上往下穿越訊號線"))
            elif macd > sig:
                signals.append(("MACD 多頭", "hold", f"MACD {macd:.2f} > 訊號線 {sig:.2f}"))
            else:
                signals.append(("MACD 空頭", "hold", f"MACD {macd:.2f} < 訊號線 {sig:.2f}"))
    except Exception:
        pass
    
    # 三大法人
    if not chip_df.empty:
        try:
            last_chip = chip_df.iloc[-1]
            foreign = last_chip.get("外資", 0)
            trust   = last_chip.get("投信", 0)
            total   = last_chip.get("合計", 0)
            if total > 0:
                signals.append(("法人合計買超", "buy", f"合計買超 {total/1000:.0f} 張（外資 {foreign/1000:.0f} / 投信 {trust/1000:.0f}）"))
            elif total < 0:
                signals.append(("法人合計賣超", "sell", f"合計賣超 {abs(total)/1000:.0f} 張（外資 {foreign/1000:.0f} / 投信 {trust/1000:.0f}）"))
        except Exception:
            pass
    
    return signals

def signal_html(label: str, kind: str, detail: str) -> str:
    css_map = {"buy": "signal-buy", "sell": "signal-sell", "hold": "signal-hold", "neutral": "signal-neutral"}
    icon_map = {"buy": "▲", "sell": "▼", "hold": "◆", "neutral": "●"}
    cls  = css_map.get(kind, "signal-neutral")
    icon = icon_map.get(kind, "●")
    return f"""
    <div style="display:flex; align-items:center; gap:10px; padding:10px 0; border-bottom:1px solid #21262d;">
        <span class="signal-badge {cls}">{icon} {label}</span>
        <span style="font-size:13px; color:#8b949e;">{detail}</span>
    </div>
    """

# ─── 圖表繪製 ────────────────────────────────────────────────────────────────

CHART_THEME = dict(
    paper_bgcolor="#0d1117",
    plot_bgcolor="#0d1117",
    font_color="#e6edf3",
    gridcolor="#21262d",
    zerolinecolor="#30363d",
)

def draw_main_chart(df: pd.DataFrame, show_ma: list, stock_name: str) -> go.Figure:
    fig = make_subplots(
        rows=3, cols=1,
        row_heights=[0.55, 0.25, 0.20],
        shared_xaxes=True,
        vertical_spacing=0.02,
    )
    
    # K 線
    up_color   = "#3fb950"
    down_color = "#f85149"
    colors = [up_color if row["Close"] >= row["Open"] else down_color for _, row in df.iterrows()]
    
    fig.add_trace(go.Candlestick(
        x=df["date"], open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        increasing_line_color=up_color, decreasing_line_color=down_color,
        increasing_fillcolor=up_color, decreasing_fillcolor=down_color,
        name="K線", showlegend=False,
    ), row=1, col=1)
    
    # 均線
    ma_colors = {"MA5": "#58a6ff", "MA10": "#d2a8ff", "MA20": "#ffa657", "MA60": "#f78166"}
    for ma in show_ma:
        if ma in df.columns:
            fig.add_trace(go.Scatter(
                x=df["date"], y=df[ma], mode="lines",
                line=dict(color=ma_colors.get(ma, "#fff"), width=1.2),
                name=ma,
            ), row=1, col=1)
    
    # RSI
    if "RSI" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["RSI"], mode="lines",
            line=dict(color="#d2a8ff", width=1.5),
            name="RSI(14)", showlegend=False,
        ), row=2, col=1)
        for lvl, color in [(70, "#f85149"), (50, "#8b949e"), (30, "#3fb950")]:
            fig.add_hline(y=lvl, line_dash="dash", line_color=color, line_width=0.8, opacity=0.6, row=2, col=1)
    
    # MACD
    if "MACD" in df.columns:
        hist_colors = [up_color if v >= 0 else down_color for v in df["MACD_hist"].fillna(0)]
        fig.add_trace(go.Bar(
            x=df["date"], y=df["MACD_hist"],
            marker_color=hist_colors, name="MACD柱", showlegend=False, opacity=0.8,
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["MACD"],
            line=dict(color="#58a6ff", width=1.2), name="MACD", showlegend=False,
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["MACD_signal"],
            line=dict(color="#ffa657", width=1.2), name="Signal", showlegend=False,
        ), row=3, col=1)
    
    fig.update_layout(
        height=620,
        paper_bgcolor=CHART_THEME["paper_bgcolor"],
        plot_bgcolor=CHART_THEME["plot_bgcolor"],
        font=dict(color=CHART_THEME["font_color"], size=11),
        legend=dict(bgcolor="#161b22", bordercolor="#30363d", borderwidth=1,
                    x=0.01, y=0.99, font=dict(size=10)),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#161b22", bordercolor="#30363d", font_size=11),
    )
    for i in range(1, 4):
        fig.update_yaxes(
            row=i, col=1,
            gridcolor=CHART_THEME["gridcolor"],
            zerolinecolor=CHART_THEME["zerolinecolor"],
            tickfont=dict(size=10),
        )
    for i in range(1, 4):
        fig.update_xaxes(
            row=i, col=1,
            gridcolor=CHART_THEME["gridcolor"],
            showgrid=(i == 3),
        )
    
    # Y 軸標籤
    fig.update_yaxes(title_text="價格", row=1, col=1, title_font=dict(size=10))
    fig.update_yaxes(title_text="RSI", row=2, col=1, title_font=dict(size=10), range=[0, 100])
    fig.update_yaxes(title_text="MACD", row=3, col=1, title_font=dict(size=10))
    
    return fig

def draw_chip_chart(chip_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    color_map = {"外資": "#58a6ff", "投信": "#3fb950", "自營商": "#ffa657"}
    for col, color in color_map.items():
        if col in chip_df.columns:
            vals = chip_df[col] / 1000  # 換算成千張
            bar_colors = [color if v >= 0 else "#f85149" for v in vals]
            fig.add_trace(go.Bar(
                x=chip_df["date"], y=vals,
                name=col, marker_color=bar_colors, opacity=0.8,
            ))
    fig.update_layout(
        height=280,
        paper_bgcolor=CHART_THEME["paper_bgcolor"],
        plot_bgcolor=CHART_THEME["plot_bgcolor"],
        font=dict(color=CHART_THEME["font_color"], size=11),
        legend=dict(bgcolor="#161b22", bordercolor="#30363d", borderwidth=1,
                    orientation="h", y=1.05),
        margin=dict(l=10, r=10, t=30, b=10),
        barmode="group",
        xaxis=dict(gridcolor=CHART_THEME["gridcolor"]),
        yaxis=dict(gridcolor=CHART_THEME["gridcolor"], title="千張"),
        hovermode="x unified",
    )
    return fig

# ─── 主程式 ──────────────────────────────────────────────────────────────────

def main():
    # Sidebar
    with st.sidebar:
        st.markdown("## 📈 台股技術分析")
        st.markdown("---")
        
        stock_input = st.text_input("股票代號", placeholder="例：2330", max_chars=6)
        
        period_map = {"1個月": 30, "3個月": 90, "6個月": 180, "1年": 365, "2年": 730}
        period_label = st.selectbox("分析區間", list(period_map.keys()), index=2)
        days = period_map[period_label]
        
        ma_options = st.multiselect("均線顯示", ["MA5", "MA10", "MA20", "MA60"],
                                    default=["MA5", "MA20", "MA60"])
        
        run = st.button("🔍 開始分析")
        
        st.markdown("---")
        st.markdown("""
        <div style='font-size:11px; color:#8b949e; line-height:1.8;'>
        <b>資料來源</b><br>
        K線 · 籌碼：FinMind API<br>
        即時報價：TWSE OpenAPI<br><br>
        <b>快取說明</b><br>
        歷史資料：1 小時更新<br>
        即時報價：5 分鐘更新
        </div>
        """, unsafe_allow_html=True)
    
    # 主畫面歡迎頁
    if not run or not stock_input.strip():
        st.markdown("""
        <div style='display:flex; flex-direction:column; align-items:center; justify-content:center; height:60vh; gap:16px;'>
            <div style='font-size:52px;'>📊</div>
            <div style='font-size:24px; font-weight:700; color:#e6edf3;'>台股技術分析工具</div>
            <div style='font-size:15px; color:#8b949e; text-align:center; max-width:360px; line-height:1.7;'>
                輸入股票代號，取得 K 線圖、均線、RSI、MACD<br>三大法人籌碼與綜合訊號分析
            </div>
            <div style='font-size:13px; color:#30363d; margin-top:8px;'>← 在左側輸入代號後點擊「開始分析」</div>
        </div>
        """, unsafe_allow_html=True)
        return
    
    stock_id = stock_input.strip()
    end_date   = datetime.today().strftime("%Y-%m-%d")
    start_date = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    # ── 抓資料 ──
    with st.spinner(f"正在抓取 {stock_id} 資料..."):
        rt    = fetch_realtime_price(stock_id)
        df    = fetch_ohlcv(stock_id, start_date, end_date)
        chip  = fetch_institutional(stock_id, start_date, end_date)
    
    if df.empty:
        st.markdown(f"""
        <div class='error-box'>
        ⚠️ 無法取得 <b>{stock_id}</b> 的歷史資料。<br>
        請確認：①代號是否正確（上市用4碼，如 2330）②FinMind Token 是否設定在 Secrets
        </div>
        """, unsafe_allow_html=True)
        return
    
    df        = calc_indicators(df)
    chip_proc = process_institutional(chip)
    signals   = generate_signals(df, chip_proc)
    
    # ── 股名與即時報價 ──
    stock_name = rt.get("name", stock_id) if rt.get("ok") else stock_id
    last_close = df["Close"].iloc[-1]
    prev_close = df["Close"].iloc[-2] if len(df) > 1 else last_close
    chg        = last_close - prev_close
    chg_pct    = chg / prev_close * 100 if prev_close else 0
    
    price_to_show = rt.get("price") if rt.get("ok") and rt.get("price") else last_close
    chg_color     = "up" if chg >= 0 else "down"
    chg_icon      = "▲" if chg >= 0 else "▼"
    
    # ── 頁頭 ──
    col_title, col_time = st.columns([3, 1])
    with col_title:
        st.markdown(f"""
        <div style='display:flex; align-items:baseline; gap:12px;'>
            <span style='font-size:28px; font-weight:800; color:#e6edf3;'>{stock_name}</span>
            <span style='font-size:16px; color:#8b949e;'>{stock_id}</span>
        </div>
        """, unsafe_allow_html=True)
    with col_time:
        ts = rt.get("time", "") if rt.get("ok") else "收盤價"
        st.markdown(f"<div style='text-align:right; color:#8b949e; font-size:12px; padding-top:14px;'>{ts if ts else '歷史收盤'}</div>", unsafe_allow_html=True)
    
    # ── 指標卡片列 ──
    c1, c2, c3, c4, c5 = st.columns(5)
    
    last = df.iloc[-1]
    rsi_val  = last.get("RSI", float("nan"))
    macd_val = last.get("MACD", float("nan"))
    vol      = df["Volume"].iloc[-1] if "Volume" in df.columns else 0
    
    def metric_card(label, value, delta_str="", delta_class="neutral"):
        return f"""
        <div class='metric-card'>
            <div class='label'>{label}</div>
            <div class='value {delta_class}'>{value}</div>
            <div class='delta {delta_class}'>{delta_str}</div>
        </div>
        """
    
    with c1:
        st.markdown(metric_card("現價", f"{price_to_show:.2f}",
                                f"{chg_icon} {abs(chg):.2f} ({abs(chg_pct):.2f}%)", chg_color),
                    unsafe_allow_html=True)
    with c2:
        ma20 = last.get("MA20", float("nan"))
        vs_ma20 = f"較MA20 {'高' if last_close >= ma20 else '低'} {abs(last_close - ma20):.1f}" if pd.notna(ma20) else ""
        st.markdown(metric_card("MA20", f"{ma20:.1f}" if pd.notna(ma20) else "—", vs_ma20), unsafe_allow_html=True)
    with c3:
        rsi_cls = "up" if pd.notna(rsi_val) and rsi_val < 30 else ("down" if pd.notna(rsi_val) and rsi_val > 70 else "neutral")
        rsi_desc = "超賣" if pd.notna(rsi_val) and rsi_val < 30 else ("超買" if pd.notna(rsi_val) and rsi_val > 70 else "中性")
        st.markdown(metric_card("RSI(14)", f"{rsi_val:.1f}" if pd.notna(rsi_val) else "—", rsi_desc, rsi_cls), unsafe_allow_html=True)
    with c4:
        macd_cls = "up" if pd.notna(macd_val) and macd_val > 0 else "down"
        st.markdown(metric_card("MACD", f"{macd_val:.2f}" if pd.notna(macd_val) else "—", "多頭" if pd.notna(macd_val) and macd_val > 0 else "空頭", macd_cls), unsafe_allow_html=True)
    with c5:
        vol_k = vol / 1000
        st.markdown(metric_card("成交量", f"{vol_k:.0f}K" if vol else "—", "千股"), unsafe_allow_html=True)
    
    # ── 圖表 ──
    st.markdown("---")
    fig = draw_main_chart(df, ma_options, stock_name)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    
    # ── 訊號 + 籌碼 ──
    col_sig, col_chip = st.columns([1, 1])
    
    with col_sig:
        st.markdown("<div class='section-header'>綜合訊號分析</div>", unsafe_allow_html=True)
        if signals:
            for label, kind, detail in signals:
                st.markdown(signal_html(label, kind, detail), unsafe_allow_html=True)
        else:
            st.markdown("<div class='warn-box'>指標資料不足，請選擇較長的分析區間</div>", unsafe_allow_html=True)
    
    with col_chip:
        st.markdown("<div class='section-header'>三大法人籌碼（近期）</div>", unsafe_allow_html=True)
        if not chip_proc.empty:
            recent = chip_proc.tail(30)
            chip_fig = draw_chip_chart(recent)
            st.plotly_chart(chip_fig, use_container_width=True, config={"displayModeBar": False})
            
            # 近5日合計
            last5 = chip_proc.tail(5)
            st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)
            ccols = st.columns(4)
            for i, (col_name, label) in enumerate([("外資", "外資"), ("投信", "投信"), ("自營商", "自營商"), ("合計", "合計")]):
                if col_name in last5.columns:
                    total = last5[col_name].sum() / 1000
                    color = "#3fb950" if total >= 0 else "#f85149"
                    sign  = "+" if total >= 0 else ""
                    ccols[i].markdown(f"""
                    <div style='text-align:center; padding:10px; background:#161b22; border-radius:6px; border:1px solid #30363d;'>
                        <div style='font-size:10px; color:#8b949e;'>{label} 近5日</div>
                        <div style='font-size:16px; font-weight:700; color:{color};'>{sign}{total:.0f}K</div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.markdown("<div class='warn-box'>三大法人資料暫無法取得<br>（FinMind 免費版每小時 600 次，請稍後再試）</div>", unsafe_allow_html=True)
    
    # ── 原始資料（可折疊） ──
    with st.expander("📋 查看原始 K 線資料", expanded=False):
        display_cols = ["date", "Open", "High", "Low", "Close", "Volume",
                        "MA5", "MA20", "MA60", "RSI", "MACD"]
        available = [c for c in display_cols if c in df.columns]
        st.dataframe(
            df[available].tail(30).iloc[::-1].reset_index(drop=True),
            use_container_width=True,
            height=300,
        )

# ─── 入口 ────────────────────────────────────────────────────────────────────

if __name__ == "__main__" or True:
    main()
