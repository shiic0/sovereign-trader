import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from anthropic import Anthropic
from datetime import datetime, timedelta
import requests
import time
import warnings
warnings.filterwarnings('ignore')

# ─── DATA SOURCE ROUTER ────────────────────────────────────────────────────────
# Priority:
#   Crypto  → Binance API (free, real-time, institutional grade)
#   Global  → Alpha Vantage (free tier, reliable OHLCV)
#   Saudi   → Yahoo Finance (only free option for .SR)

CRYPTO_SYMBOLS = {
    "BTC-USD": "BTCUSDT", "ETH-USD": "ETHUSDT", "SOL-USD": "SOLUSDT",
    "BNB-USD": "BNBUSDT", "XRP-USD": "XRPUSDT", "AVAX-USD": "AVAXUSDT",
    "DOGE-USD": "DOGEUSDT", "MATIC-USD": "MATICUSDT", "ADA-USD": "ADAUSDT",
    "DOT-USD": "DOTUSDT", "LINK-USD": "LINKUSDT", "LTC-USD": "LTCUSDT",
}

BINANCE_INTERVAL_MAP = {
    "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d", "1wk": "1w"
}

BINANCE_PERIOD_LIMIT = {
    "15m": 500, "1h": 500, "4h": 500, "1d": 365, "1w": 200
}

def fetch_binance(symbol_usdt, interval, limit=500):
    """
    Binance Public API — zero auth, real-time, tick-level accurate.
    Returns standardised OHLCV DataFrame.
    """
    b_interval = BINANCE_INTERVAL_MAP.get(interval, "1d")
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol_usdt, "interval": b_interval, "limit": limit}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        raw = r.json()
        df = pd.DataFrame(raw, columns=[
            "OpenTime","Open","High","Low","Close","Volume",
            "CloseTime","QuoteVol","Trades","TakerBase","TakerQuote","Ignore"
        ])
        df["OpenTime"] = pd.to_datetime(df["OpenTime"], unit="ms")
        df.set_index("OpenTime", inplace=True)
        for col in ["Open","High","Low","Close","Volume"]:
            df[col] = df[col].astype(float)
        df.index.name = "Datetime"
        return df[["Open","High","Low","Close","Volume"]]
    except Exception:
        return None

def fetch_alpha_vantage(ticker, interval, api_key):
    """
    Alpha Vantage free tier — daily/weekly/intraday OHLCV.
    Best for global equities (AAPL, NVDA, ^GSPC proxies, etc.)
    Free key: 25 req/day, no credit card.
    """
    base = "https://www.alphavantage.co/query"
    if interval == "1d":
        params = {"function": "TIME_SERIES_DAILY_ADJUSTED",
                  "symbol": ticker, "outputsize": "full", "apikey": api_key}
        ts_key = "Time Series (Daily)"
    elif interval == "1wk":
        params = {"function": "TIME_SERIES_WEEKLY_ADJUSTED",
                  "symbol": ticker, "apikey": api_key}
        ts_key = "Weekly Adjusted Time Series"
    else:  # intraday
        av_int = {"15m":"15min","1h":"60min","4h":"60min"}.get(interval,"60min")
        params = {"function": "TIME_SERIES_INTRADAY",
                  "symbol": ticker, "interval": av_int,
                  "outputsize": "full", "apikey": api_key}
        ts_key = f"Time Series ({av_int})"

    try:
        r = requests.get(base, params=params, timeout=15)
        data = r.json()
        if ts_key not in data:
            return None
        ts = data[ts_key]
        rows = []
        for date_str, vals in ts.items():
            o = float(vals.get("1. open", vals.get("1. Open", 0)))
            h = float(vals.get("2. high", vals.get("2. High", 0)))
            l = float(vals.get("3. low",  vals.get("3. Low",  0)))
            c = float(vals.get("4. close", vals.get("5. adjusted close",
                      vals.get("4. close", vals.get("4. Close", 0)))))
            v = float(vals.get("5. volume", vals.get("6. volume",
                      vals.get("5. Volume", 0))))
            rows.append({"Datetime": pd.to_datetime(date_str),
                         "Open":o,"High":h,"Low":l,"Close":c,"Volume":v})
        if not rows:
            return None
        df = pd.DataFrame(rows).set_index("Datetime").sort_index()
        return df
    except Exception:
        return None

def fetch_yahoo_robust(ticker, period, interval):
    """
    Yahoo Finance with hardened error handling — fallback for .SR and commodities.
    """
    try:
        df = yf.download(ticker, period=period, interval=interval,
                         progress=False, auto_adjust=True, timeout=15)
        if df.empty:
            # retry once with longer period
            time.sleep(1)
            df = yf.download(ticker, period="2y", interval="1d",
                             progress=False, auto_adjust=True, timeout=15)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        df.index.name = "Datetime"
        return df
    except Exception:
        return None

# ─── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="المستشار السيادي | SOVEREIGN TRADER",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── INJECT CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;900&family=Orbitron:wght@400;700;900&display=swap');

:root {
    --gold: #D4AF37;
    --gold-light: #F5D05E;
    --gold-dark: #8B6914;
    --red: #FF3B3B;
    --green: #00FF88;
    --blue: #00BFFF;
    --bg-dark: #050810;
    --bg-card: #0A0F1E;
    --bg-card2: #0D1526;
    --border: rgba(212,175,55,0.25);
    --text: #E8E8E8;
    --text-dim: #8899AA;
}

* { font-family: 'Tajawal', sans-serif; }
body, .stApp { background: var(--bg-dark) !important; color: var(--text) !important; }

/* Hide streamlit branding */
#MainMenu, footer, header { visibility: hidden; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #050810 0%, #080D1A 100%) !important;
    border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { color: var(--text) !important; }

/* Main header */
.sovereign-header {
    background: linear-gradient(135deg, #050810 0%, #0A0F1E 50%, #050810 100%);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 30px 40px;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
    text-align: center;
}
.sovereign-header::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    background: radial-gradient(ellipse at 50% 0%, rgba(212,175,55,0.12) 0%, transparent 70%);
    pointer-events: none;
}
.sovereign-title {
    font-family: 'Orbitron', monospace;
    font-size: 2.2rem;
    font-weight: 900;
    background: linear-gradient(135deg, var(--gold) 0%, var(--gold-light) 50%, var(--gold) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: 4px;
    margin: 0;
}
.sovereign-subtitle {
    font-family: 'Tajawal', sans-serif;
    font-size: 1.1rem;
    color: var(--text-dim);
    margin-top: 6px;
    letter-spacing: 2px;
}

/* Metric cards */
.metric-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px 20px;
    text-align: center;
    transition: all 0.3s ease;
}
.metric-card:hover { border-color: var(--gold); box-shadow: 0 0 20px rgba(212,175,55,0.15); }
.metric-label { font-size: 0.75rem; color: var(--text-dim); letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 8px; }
.metric-value { font-family: 'Orbitron', monospace; font-size: 1.4rem; font-weight: 700; }
.metric-value.positive { color: var(--green); }
.metric-value.negative { color: var(--red); }
.metric-value.gold { color: var(--gold); }
.metric-value.blue { color: var(--blue); }

/* Section headers */
.section-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 28px 0 16px 0;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border);
}
.section-title {
    font-family: 'Orbitron', monospace;
    font-size: 0.9rem;
    letter-spacing: 3px;
    color: var(--gold);
    text-transform: uppercase;
}

/* AI Analysis box */
.ai-analysis-box {
    background: linear-gradient(135deg, #0A0F1E 0%, #0D1526 100%);
    border: 1px solid var(--gold-dark);
    border-left: 4px solid var(--gold);
    border-radius: 12px;
    padding: 28px 32px;
    margin-top: 16px;
    direction: rtl;
    line-height: 1.9;
    font-size: 1.05rem;
    color: var(--text);
    position: relative;
}
.ai-analysis-box::before {
    content: '⚔️ AI';
    position: absolute;
    top: -12px;
    right: 20px;
    background: var(--bg-dark);
    padding: 2px 12px;
    font-family: 'Orbitron', monospace;
    font-size: 0.7rem;
    color: var(--gold);
    border: 1px solid var(--gold-dark);
    border-radius: 20px;
}

/* Signal badges */
.signal-buy {
    display: inline-block;
    background: rgba(0,255,136,0.12);
    border: 1px solid var(--green);
    color: var(--green);
    padding: 8px 24px;
    border-radius: 30px;
    font-family: 'Orbitron', monospace;
    font-weight: 700;
    font-size: 1.1rem;
    letter-spacing: 2px;
}
.signal-sell {
    display: inline-block;
    background: rgba(255,59,59,0.12);
    border: 1px solid var(--red);
    color: var(--red);
    padding: 8px 24px;
    border-radius: 30px;
    font-family: 'Orbitron', monospace;
    font-weight: 700;
    font-size: 1.1rem;
    letter-spacing: 2px;
}
.signal-watch {
    display: inline-block;
    background: rgba(212,175,55,0.12);
    border: 1px solid var(--gold);
    color: var(--gold);
    padding: 8px 24px;
    border-radius: 30px;
    font-family: 'Orbitron', monospace;
    font-weight: 700;
    font-size: 1.1rem;
    letter-spacing: 2px;
}

/* Price levels table */
.levels-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 12px;
    direction: rtl;
}
.levels-table th {
    background: rgba(212,175,55,0.08);
    color: var(--gold);
    padding: 12px 16px;
    text-align: right;
    font-size: 0.85rem;
    letter-spacing: 1px;
    border-bottom: 1px solid var(--border);
}
.levels-table td {
    padding: 12px 16px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
    font-family: 'Orbitron', monospace;
    font-size: 0.9rem;
}
.levels-table tr:hover td { background: rgba(212,175,55,0.04); }

/* Streamlit widget overrides */
.stSelectbox > div > div, .stTextInput > div > div {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    color: var(--text) !important;
}
.stButton > button {
    background: linear-gradient(135deg, var(--gold-dark) 0%, var(--gold) 100%) !important;
    color: #000 !important;
    font-family: 'Tajawal', sans-serif !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 12px 32px !important;
    width: 100% !important;
    letter-spacing: 1px !important;
    transition: all 0.3s !important;
}
.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(212,175,55,0.4) !important;
}

/* Chat messages */
.chat-user {
    background: rgba(212,175,55,0.08);
    border: 1px solid var(--border);
    border-radius: 12px 12px 4px 12px;
    padding: 14px 18px;
    margin: 8px 0;
    direction: rtl;
    text-align: right;
}
.chat-ai {
    background: var(--bg-card);
    border: 1px solid rgba(0,191,255,0.2);
    border-left: 3px solid var(--blue);
    border-radius: 12px 12px 12px 4px;
    padding: 14px 18px;
    margin: 8px 0;
    direction: rtl;
    text-align: right;
    line-height: 1.8;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg-dark); }
::-webkit-scrollbar-thumb { background: var(--gold-dark); border-radius: 3px; }

/* Divider */
.golden-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--gold-dark), var(--gold), var(--gold-dark), transparent);
    margin: 24px 0;
}

/* Info box */
.info-box {
    background: rgba(0,191,255,0.06);
    border: 1px solid rgba(0,191,255,0.2);
    border-radius: 10px;
    padding: 14px 18px;
    font-size: 0.9rem;
    color: var(--text-dim);
    direction: rtl;
    margin: 10px 0;
}
</style>
""", unsafe_allow_html=True)

# ─── HEADER ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="sovereign-header">
    <div class="sovereign-title">⚔️ SOVEREIGN TRADER ⚔️</div>
    <div class="sovereign-subtitle">المستشار التداولي السيادي | الأسهم السعودية & العملات الرقمية</div>
</div>
""", unsafe_allow_html=True)

# ─── TECHNICAL INDICATORS ──────────────────────────────────────────────────────
def calc_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def calc_macd(series, fast=12, slow=26, signal=9):
    ema_fast = calc_ema(series, fast)
    ema_slow = calc_ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calc_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calc_bollinger(series, period=20, std_dev=2):
    sma = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    return upper, sma, lower

def calc_stochastic(high, low, close, k_period=14, d_period=3):
    lowest_low = low.rolling(k_period).min()
    highest_high = high.rolling(k_period).max()
    k = 100 * (close - lowest_low) / (highest_high - lowest_low).replace(0, np.nan)
    d = k.rolling(d_period).mean()
    return k, d

def calc_atr(high, low, close, period=14):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def calc_support_resistance(df, window=20):
    """Calculate dynamic support and resistance levels"""
    highs = df['High'].rolling(window, center=True).max()
    lows = df['Low'].rolling(window, center=True).min()
    
    resistance_levels = []
    support_levels = []
    
    for i in range(window, len(df) - window):
        if df['High'].iloc[i] == highs.iloc[i]:
            resistance_levels.append(df['High'].iloc[i])
        if df['Low'].iloc[i] == lows.iloc[i]:
            support_levels.append(df['Low'].iloc[i])
    
    def cluster_levels(levels, tolerance=0.02):
        if not levels: return []
        levels = sorted(set(levels))
        clustered = []
        group = [levels[0]]
        for level in levels[1:]:
            if (level - group[-1]) / group[-1] < tolerance:
                group.append(level)
            else:
                clustered.append(np.mean(group))
                group = [level]
        clustered.append(np.mean(group))
        return clustered
    
    return cluster_levels(resistance_levels), cluster_levels(support_levels)

def identify_trend(df):
    """Identify market trend using EMA alignment"""
    close = df['Close']
    ema20 = calc_ema(close, 20).iloc[-1]
    ema50 = calc_ema(close, 50).iloc[-1]
    ema200 = calc_ema(close, 200).iloc[-1] if len(close) >= 200 else None
    price = close.iloc[-1]
    
    if ema200:
        if price > ema20 > ema50 > ema200:
            return "صاعد قوي 🟢", "bullish_strong"
        elif price > ema20 > ema50:
            return "صاعد معتدل 🟡", "bullish_moderate"
        elif price < ema20 < ema50 < (ema200 or float('inf')):
            return "هابط قوي 🔴", "bearish_strong"
        elif price < ema20 < ema50:
            return "هابط معتدل 🟠", "bearish_moderate"
        else:
            return "عرضي محايد ⚪", "sideways"
    else:
        if price > ema20 > ema50:
            return "صاعد 🟢", "bullish_moderate"
        elif price < ema20 < ema50:
            return "هابط 🔴", "bearish_moderate"
        else:
            return "عرضي ⚪", "sideways"

# ─── SMART DATA ROUTER ─────────────────────────────────────────────────────────
@st.cache_data(ttl=180)
def fetch_data(ticker, period, interval, av_key="demo"):
    """
    Intelligent multi-source router:
      1. Crypto  → Binance (real-time, no key)
      2. Global  → Alpha Vantage (free key)
      3. Saudi / commodities / forex → Yahoo Finance (hardened)
    """
    # Route 1: Binance for Crypto
    if ticker in CRYPTO_SYMBOLS:
        b_sym  = CRYPTO_SYMBOLS[ticker]
        limit  = BINANCE_PERIOD_LIMIT.get(interval, 500)
        df     = fetch_binance(b_sym, interval, limit)
        if df is not None and len(df) >= 50:
            st.session_state["data_source"] = f"🟢 Binance (Real-Time) — {b_sym}"
            return df
        st.session_state["data_source"] = "🟡 Yahoo Finance (Crypto fallback)"
        return fetch_yahoo_robust(ticker, period, interval)

    # Route 2: Alpha Vantage for Global Equities
    is_global = (
        not ticker.endswith(".SR") and
        "=F" not in ticker and
        "=X" not in ticker and
        ticker not in CRYPTO_SYMBOLS
    )
    if is_global and av_key and av_key != "demo":
        df = fetch_alpha_vantage(ticker, interval, av_key)
        if df is not None and len(df) >= 50:
            st.session_state["data_source"] = f"🔵 Alpha Vantage — {ticker}"
            return df
        st.session_state["data_source"] = "🟡 Yahoo Finance (AV fallback)"
        return fetch_yahoo_robust(ticker, period, interval)

    # Route 3: Yahoo Finance for Saudi / commodities / forex
    for key, label in {
        ".SR": "🟡 Yahoo Finance (Saudi — تداول)",
        "=F":  "🟡 Yahoo Finance (Commodities)",
        "=X":  "🟡 Yahoo Finance (Forex)"
    }.items():
        if key in ticker:
            st.session_state["data_source"] = label
            break
    else:
        st.session_state["data_source"] = "🟡 Yahoo Finance"

    return fetch_yahoo_robust(ticker, period, interval)

# ─── CHART BUILDER ─────────────────────────────────────────────────────────────
def build_chart(df, ticker_name, show_bb=True, show_macd=True):
    close = df['Close']
    high = df['High']
    low = df['Low']
    volume = df['Volume']
    
    ema20 = calc_ema(close, 20)
    ema50 = calc_ema(close, 50)
    ema200 = calc_ema(close, 200)
    rsi = calc_rsi(close)
    macd_line, signal_line, histogram = calc_macd(close)
    bb_upper, bb_mid, bb_lower = calc_bollinger(close)
    k_stoch, d_stoch = calc_stochastic(high, low, close)
    atr = calc_atr(high, low, close)
    
    rows = 4 if show_macd else 3
    row_heights = [0.52, 0.18, 0.15, 0.15] if show_macd else [0.55, 0.22, 0.23]
    subplot_titles = [
        f'📊 {ticker_name} — الشموع اليابانية',
        '📉 RSI — مؤشر القوة النسبية',
        '📊 MACD — التقارب والتباعد' if show_macd else '📊 Stochastic',
        '💧 Volume — حجم التداول'
    ][:rows]
    
    fig = make_subplots(
        rows=rows, cols=1,
        shared_xaxes=True,
        row_heights=row_heights,
        subplot_titles=subplot_titles,
        vertical_spacing=0.04
    )
    
    # ── Candlesticks
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=high, low=low, close=close,
        name='السعر',
        increasing_line_color='#00FF88', increasing_fillcolor='rgba(0,255,136,0.8)',
        decreasing_line_color='#FF3B3B', decreasing_fillcolor='rgba(255,59,59,0.8)',
        line=dict(width=1)
    ), row=1, col=1)
    
    # ── EMAs
    fig.add_trace(go.Scatter(x=df.index, y=ema20, name='EMA 20', line=dict(color='#00BFFF', width=1.5), opacity=0.9), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=ema50, name='EMA 50', line=dict(color='#FFB800', width=1.5), opacity=0.9), row=1, col=1)
    if len(close) >= 200:
        fig.add_trace(go.Scatter(x=df.index, y=ema200, name='EMA 200', line=dict(color='#FF6B6B', width=1.5, dash='dot'), opacity=0.8), row=1, col=1)
    
    # ── Bollinger Bands
    if show_bb:
        fig.add_trace(go.Scatter(x=df.index, y=bb_upper, name='BB Upper', line=dict(color='rgba(212,175,55,0.4)', width=1, dash='dash')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=bb_lower, name='BB Lower', line=dict(color='rgba(212,175,55,0.4)', width=1, dash='dash'),
                                  fill='tonexty', fillcolor='rgba(212,175,55,0.03)'), row=1, col=1)
    
    # ── RSI
    fig.add_trace(go.Scatter(x=df.index, y=rsi, name='RSI', line=dict(color='#9B59B6', width=2)), row=2, col=1)
    fig.add_hline(y=70, line=dict(color='#FF3B3B', width=1, dash='dash'), row=2, col=1)
    fig.add_hline(y=30, line=dict(color='#00FF88', width=1, dash='dash'), row=2, col=1)
    fig.add_hline(y=50, line=dict(color='rgba(255,255,255,0.2)', width=1), row=2, col=1)
    
    fig.add_shape(type="rect", x0=df.index[0], x1=df.index[-1], y0=70, y1=100,
                  fillcolor="rgba(255,59,59,0.06)", line_width=0, row=2, col=1)
    fig.add_shape(type="rect", x0=df.index[0], x1=df.index[-1], y0=0, y1=30,
                  fillcolor="rgba(0,255,136,0.06)", line_width=0, row=2, col=1)
    
    # ── MACD
    if show_macd:
        colors = ['#00FF88' if v >= 0 else '#FF3B3B' for v in histogram]
        fig.add_trace(go.Bar(x=df.index, y=histogram, name='MACD Histogram', marker_color=colors, opacity=0.7), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=macd_line, name='MACD', line=dict(color='#00BFFF', width=1.5)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=signal_line, name='Signal', line=dict(color='#FFB800', width=1.5)), row=3, col=1)
    else:
        fig.add_trace(go.Scatter(x=df.index, y=k_stoch, name='%K', line=dict(color='#00BFFF', width=2)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=d_stoch, name='%D', line=dict(color='#FFB800', width=2)), row=3, col=1)
        fig.add_hline(y=80, line=dict(color='#FF3B3B', width=1, dash='dash'), row=3, col=1)
        fig.add_hline(y=20, line=dict(color='#00FF88', width=1, dash='dash'), row=3, col=1)
    
    # ── Volume
    vol_row = 4 if show_macd else 3
    vol_colors = ['#00FF88' if c >= o else '#FF3B3B' for c, o in zip(close, df['Open'])]
    fig.add_trace(go.Bar(x=df.index, y=volume, name='Volume', marker_color=vol_colors, opacity=0.7), row=vol_row, col=1)
    vol_ma = volume.rolling(20).mean()
    fig.add_trace(go.Scatter(x=df.index, y=vol_ma, name='Vol MA20', line=dict(color='#D4AF37', width=1.5)), row=vol_row, col=1)
    
    # ── Layout
    fig.update_layout(
        template='plotly_dark',
        plot_bgcolor='#050810',
        paper_bgcolor='#050810',
        font=dict(family='Tajawal', color='#E8E8E8', size=12),
        height=820,
        showlegend=True,
        legend=dict(
            orientation='h', yanchor='bottom', y=1.01, xanchor='right', x=1,
            bgcolor='rgba(10,15,30,0.8)', bordercolor='rgba(212,175,55,0.3)', borderwidth=1,
            font=dict(size=10)
        ),
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=0, t=40, b=0),
        hovermode='x unified',
        hoverlabel=dict(bgcolor='#0A0F1E', bordercolor='#D4AF37', font=dict(family='Tajawal', size=12))
    )
    
    for i in range(1, rows+1):
        fig.update_xaxes(
            gridcolor='rgba(212,175,55,0.06)',
            zerolinecolor='rgba(212,175,55,0.15)',
            showgrid=True, row=i, col=1
        )
        fig.update_yaxes(
            gridcolor='rgba(212,175,55,0.06)',
            zerolinecolor='rgba(212,175,55,0.15)',
            showgrid=True, row=i, col=1
        )
    
    return fig, rsi, macd_line, signal_line, histogram, ema20, ema50, atr, k_stoch, d_stoch, bb_upper, bb_lower

# ─── AI ANALYSIS ───────────────────────────────────────────────────────────────
def get_ai_analysis(client, ticker, df, rsi, macd_line, signal_line, histogram,
                     ema20, ema50, atr, k_stoch, d_stoch, bb_upper, bb_lower,
                     trend_label, support_levels, resistance_levels, asset_type):
    
    close = df['Close']
    price = close.iloc[-1]
    price_change_1d = ((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100) if len(close) > 1 else 0
    price_change_5d = ((close.iloc[-1] - close.iloc[-6]) / close.iloc[-6] * 100) if len(close) > 5 else 0
    price_change_20d = ((close.iloc[-1] - close.iloc[-21]) / close.iloc[-21] * 100) if len(close) > 20 else 0
    
    high_52w = df['High'].tail(252).max() if len(df) >= 252 else df['High'].max()
    low_52w = df['Low'].tail(252).min() if len(df) >= 252 else df['Low'].min()
    
    volume_avg = df['Volume'].tail(20).mean()
    volume_today = df['Volume'].iloc[-1]
    volume_ratio = volume_today / volume_avg if volume_avg > 0 else 1
    
    rsi_val = rsi.iloc[-1]
    macd_val = macd_line.iloc[-1]
    signal_val = signal_line.iloc[-1]
    hist_val = histogram.iloc[-1]
    hist_prev = histogram.iloc[-2] if len(histogram) > 1 else hist_val
    ema20_val = ema20.iloc[-1]
    ema50_val = ema50.iloc[-1]
    atr_val = atr.iloc[-1]
    k_val = k_stoch.iloc[-1] if not pd.isna(k_stoch.iloc[-1]) else 50
    d_val = d_stoch.iloc[-1] if not pd.isna(d_stoch.iloc[-1]) else 50
    bb_upper_val = bb_upper.iloc[-1]
    bb_lower_val = bb_lower.iloc[-1]
    bb_width = ((bb_upper_val - bb_lower_val) / bb_lower_val * 100) if bb_lower_val > 0 else 0
    
    top_supports = sorted(support_levels)[-3:] if len(support_levels) >= 3 else support_levels
    top_resistances = sorted(resistance_levels)[:3] if len(resistance_levels) >= 3 else resistance_levels

    prompt = f"""أنت خبير تحليل فني وتداول متخصص من أرقى بيوت الخبرة المالية العالمية. مهمتك تقديم تحليل تداولي سيادي شامل ودقيق باللغة العربية الفصحى مع مصطلحات تداولية احترافية.

═══════════════════════════════════════
البيانات التحليلية الكاملة
═══════════════════════════════════════
الأصل: {ticker} | النوع: {asset_type}
السعر الحالي: {price:.4f}
التغير اليومي: {price_change_1d:+.2f}%
التغير 5 أيام: {price_change_5d:+.2f}%
التغير 20 يوم: {price_change_20d:+.2f}%
أعلى 52 أسبوع: {high_52w:.4f}
أدنى 52 أسبوع: {low_52w:.4f}

الاتجاه العام: {trend_label}

── المتوسطات المتحركة الأسية ──
EMA 20: {ema20_val:.4f} | الفرق: {((price-ema20_val)/ema20_val*100):+.2f}%
EMA 50: {ema50_val:.4f} | الفرق: {((price-ema50_val)/ema50_val*100):+.2f}%
EMA Alignment: {'صاعد ✅' if ema20_val > ema50_val else 'هابط ❌'}

── مؤشر القوة النسبية RSI (14) ──
القيمة: {rsi_val:.1f}
الحالة: {'تشبع شراء ⚠️' if rsi_val > 70 else 'تشبع بيع 🎯' if rsi_val < 30 else 'محايد ⚪'}

── مؤشر MACD (12,26,9) ──
MACD Line: {macd_val:.6f}
Signal Line: {signal_val:.6f}
Histogram: {hist_val:.6f}
اتجاه الهيستوغرام: {'تصاعدي 📈' if hist_val > hist_prev else 'تنازلي 📉'}
تقاطع: {'صعودي Golden Cross ✅' if macd_val > signal_val else 'هبوطي Death Cross ❌'}

── Stochastic (14,3) ──
%K: {k_val:.1f} | %D: {d_val:.1f}
الحالة: {'تشبع شراء' if k_val > 80 else 'تشبع بيع' if k_val < 20 else 'محايد'}

── بولينجر باندز (20,2) ──
Upper Band: {bb_upper_val:.4f}
Lower Band: {bb_lower_val:.4f}
عرض النطاق: {bb_width:.1f}% ({'متقلص' if bb_width < 5 else 'موسع'})
موقع السعر: {((price - bb_lower_val) / (bb_upper_val - bb_lower_val) * 100):.1f}% من النطاق

── ATR (متوسط المدى الحقيقي) ──
ATR: {atr_val:.4f} | نسبة التقلب: {(atr_val/price*100):.2f}%

── مستويات الدعم والمقاومة ──
مناطق مقاومة: {[f"{r:.4f}" for r in top_resistances]}
مناطق دعم: {[f"{s:.4f}" for s in top_supports]}

── السيولة ──
حجم اليوم: {volume_today:,.0f}
متوسط 20 يوم: {volume_avg:,.0f}
نسبة السيولة: {volume_ratio:.1f}x {'(سيولة عالية)' if volume_ratio > 1.5 else '(سيولة طبيعية)' if volume_ratio > 0.7 else '(سيولة منخفضة)'}
═══════════════════════════════════════

قدم التحليل بالتنسيق التالي بالضبط:

## 🎯 الحكم السيادي
[جملة واحدة قوية تلخص حالة السوق الآن]
**التوصية النهائية:** [شراء قوي / شراء / مراقبة / بيع / بيع قوي]

---

## 📊 قراءة التحليل الفني

**الاتجاه العام (Trend):**
[تحليل الترند من EMA alignment وموقع السعر، حدد إذا كان الترند الرئيسي صاعد أو هابط أو عرضي]

**زخم السعر (Momentum):**
[تحليل RSI + Stochastic مع توضيح إشارات التشبع]

**قوة الحركة (MACD):**
[قراءة تقاطعات MACD والهيستوغرام وما تعنيه]

**التقلب والنطاق (Bollinger):**
[تحليل موقع السعر من البولينجر وتوقع الحركة]

**السيولة (Volume):**
[تفسير حجم التداول وعلاقته بالحركة السعرية]

---

## ⚔️ خريطة المعارك — المستويات الحاسمة

**🔴 مناطق المقاومة:**
[اذكر مستويات المقاومة مع وصف أهمية كل مستوى]

**🟢 مناطق الدعم:**
[اذكر مستويات الدعم مع وصف أهمية كل مستوى]

---

## 💰 استراتيجية التداول

**نقطة الدخول المثلى:** [السعر أو النطاق]
**الهدف الأول 🎯:** [السعر والنسبة]
**الهدف الثاني 🎯🎯:** [السعر والنسبة]  
**الهدف الثالث 🎯🎯🎯:** [السعر والنسبة — مع ملاحظة إذا كان طموحاً]
**وقف الخسارة الصارم 🛡️:** [السعر والنسبة من الدخول]
**نسبة المخاطرة/العائد:** [R:R ratio]

---

## ⚠️ سيناريوهات التحذير
[اذكر أهم سيناريوهين سلبيين يجب مراقبتهما]

---

## 📡 الخلاصة التنفيذية
[فقرة نهائية موجزة وقوية تلخص القرار التداولي مع التنبيه بأن هذا تحليل فني وليس نصيحة استثمارية مالية]"""

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"خطأ في الاتصال بالـ AI: {str(e)}"

# ─── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 16px 0; border-bottom: 1px solid rgba(212,175,55,0.2); margin-bottom: 20px;">
        <div style="font-family:'Orbitron'; font-size:0.8rem; color:#D4AF37; letter-spacing:3px;">SOVEREIGN TRADER</div>
        <div style="font-size:0.7rem; color:#556677; margin-top:4px;">لوحة التحكم</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 🎯 اختيار الأصل")
    
    asset_category = st.selectbox(
        "فئة الأصل",
        ["الأسهم السعودية 🇸🇦", "العملات الرقمية ₿", "الأسواق العالمية 🌍", "السلع والعملات 💰"],
        key="category"
    )
    
    preset_options = {
        "الأسهم السعودية 🇸🇦": {
            "أرامكو 2222": "2222.SR",
            "سابك 2010": "2010.SR",
            "الراجحي 1120": "1120.SR",
            "الأهلي 1180": "1180.SR",
            "stc 7010": "7010.SR",
            "مدار 4002": "4002.SR",
            "زين السعودية 7030": "7030.SR",
            "أكوا باور 4082": "4082.SR",
        },
        "العملات الرقمية ₿": {
            "بيتكوين BTC": "BTC-USD",
            "إيثيريوم ETH": "ETH-USD",
            "سولانا SOL": "SOL-USD",
            "BNB": "BNB-USD",
            "ريبل XRP": "XRP-USD",
            "أفالانش AVAX": "AVAX-USD",
            "دوجكوين DOGE": "DOGE-USD",
            "بوليغون MATIC": "MATIC-USD",
        },
        "الأسواق العالمية 🌍": {
            "S&P 500": "^GSPC",
            "Nasdaq": "^IXIC",
            "Apple AAPL": "AAPL",
            "NVIDIA NVDA": "NVDA",
            "Tesla TSLA": "TSLA",
            "Microsoft MSFT": "MSFT",
        },
        "السلع والعملات 💰": {
            "ذهب Gold": "GC=F",
            "نفط خام WTI": "CL=F",
            "نفط برنت": "BZ=F",
            "EUR/USD": "EURUSD=X",
            "USD/SAR": "USDSAR=X",
        }
    }
    
    presets = preset_options[asset_category]
    selected_preset = st.selectbox("اختر الأصل", list(presets.keys()))
    default_ticker = presets[selected_preset]
    
    custom_ticker = st.text_input(
        "أو أدخل رمز مخصص",
        placeholder="مثال: 4030.SR أو ETH-USD",
        value=""
    )
    
    ticker = custom_ticker.strip().upper() if custom_ticker.strip() else default_ticker
    
    st.markdown('<div class="golden-divider"></div>', unsafe_allow_html=True)
    st.markdown("### ⚙️ إعدادات التحليل")
    
    timeframe_map = {
        "15 دقيقة (Scalping)": ("5d", "15m"),
        "1 ساعة (Intraday)": ("30d", "1h"),
        "4 ساعات (Swing)": ("60d", "4h"),
        "يومي (Position)": ("1y", "1d"),
        "أسبوعي (Trend)": ("5y", "1wk"),
    }
    selected_tf = st.selectbox("الإطار الزمني", list(timeframe_map.keys()), index=3)
    period, interval = timeframe_map[selected_tf]
    
    show_bb = st.toggle("Bollinger Bands", value=True)
    show_macd = st.toggle("MACD", value=True)

    st.markdown('<div class="golden-divider"></div>', unsafe_allow_html=True)
    st.markdown("### 🔑 Alpha Vantage Key (اختياري)")
    av_key_input = st.text_input(
        "للأسهم العالمية — احصل على مفتاح مجاني من alphavantage.co",
        placeholder="اتركه فارغاً للكريبتو والأسهم السعودية",
        type="password", key="av_key"
    )
    av_key = av_key_input.strip() if av_key_input else "demo"

    st.markdown('<div class="golden-divider"></div>', unsafe_allow_html=True)
    analyze_btn = st.button("⚔️ تحليل سيادي شامل", type="primary")
    
    st.markdown("""
    <div class="info-box" style="margin-top:16px; font-size:0.78rem;">
    ⚠️ التحليل الفني لأغراض تعليمية وإرشادية فقط. لا يُعدّ نصيحة استثمارية. التداول ينطوي على مخاطر مالية عالية.
    </div>
    """, unsafe_allow_html=True)

# ─── MAIN CONTENT ──────────────────────────────────────────────────────────────
if 'analysis_done' not in st.session_state:
    st.session_state.analysis_done = False
if 'ai_text' not in st.session_state:
    st.session_state.ai_text = ""
if 'current_ticker' not in st.session_state:
    st.session_state.current_ticker = ""
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# Determine asset type
if ".SR" in ticker:
    asset_type = "سهم سعودي - تداول"
elif any(c in ticker for c in ["BTC","ETH","SOL","BNB","XRP","DOGE","AVAX","MATIC"]):
    asset_type = "عملة رقمية - Crypto"
elif ticker in ["GC=F","CL=F","BZ=F"]:
    asset_type = "سلعة - Commodity"
elif "USD" in ticker or "EUR" in ticker or "=X" in ticker:
    asset_type = "فوركس - Forex"
else:
    asset_type = "سهم عالمي - Global Equity"

if analyze_btn or (st.session_state.analysis_done and st.session_state.current_ticker == ticker):
    
    with st.spinner(f"⚡ جاري جلب بيانات {ticker}..."):
        _av = st.session_state.get('av_key', '') or 'demo'
        df = fetch_data(ticker, period, interval, _av)
    
    if df is None or len(df) < 50:
        st.error(f"❌ تعذّر جلب بيانات {ticker}. تحقق من الرمز وأعد المحاولة.")
    else:
        _src = st.session_state.get("data_source", "")
        if _src:
            _col = "#00FF88" if "Binance" in _src else "#00BFFF" if "Alpha" in _src else "#D4AF37"
            st.markdown(f'<div style="text-align:right;font-size:0.78rem;color:{_col};margin-bottom:8px;font-family:monospace;">📡 مصدر البيانات: {_src}</div>', unsafe_allow_html=True)
        close = df['Close']
        price = close.iloc[-1]
        prev_price = close.iloc[-2] if len(close) > 1 else price
        price_change = price - prev_price
        price_change_pct = (price_change / prev_price) * 100 if prev_price != 0 else 0
        
        trend_label, trend_key = identify_trend(df)
        resistance_levels, support_levels = calc_support_resistance(df)
        
        high_val = df['High'].iloc[-1]
        low_val = df['Low'].iloc[-1]
        volume_val = df['Volume'].iloc[-1]
        
        # ── Metrics Row
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">السعر الحالي</div>
                <div class="metric-value gold">{price:.4f}</div>
            </div>""", unsafe_allow_html=True)
        with col2:
            chg_class = "positive" if price_change >= 0 else "negative"
            chg_sym = "+" if price_change >= 0 else ""
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">التغير اليومي</div>
                <div class="metric-value {chg_class}">{chg_sym}{price_change_pct:.2f}%</div>
            </div>""", unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">الأعلى</div>
                <div class="metric-value blue">{high_val:.4f}</div>
            </div>""", unsafe_allow_html=True)
        with col4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">الأدنى</div>
                <div class="metric-value">{low_val:.4f}</div>
            </div>""", unsafe_allow_html=True)
        with col5:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">الاتجاه</div>
                <div class="metric-value" style="font-size:0.85rem; font-family:Tajawal;">{trend_label}</div>
            </div>""", unsafe_allow_html=True)
        with col6:
            rsi_temp = calc_rsi(close)
            rsi_now = rsi_temp.iloc[-1]
            rsi_color = "negative" if rsi_now > 70 else "positive" if rsi_now < 30 else "gold"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">RSI (14)</div>
                <div class="metric-value {rsi_color}">{rsi_now:.1f}</div>
            </div>""", unsafe_allow_html=True)
        
        st.markdown('<div class="golden-divider"></div>', unsafe_allow_html=True)
        
        # ── Chart
        st.markdown('<div class="section-header"><div class="section-title">📊 لوحة التحليل الفني</div></div>', unsafe_allow_html=True)
        
        with st.spinner("🎨 بناء الشارت..."):
            fig, rsi, macd_line, signal_line, histogram, ema20, ema50, atr, k_stoch, d_stoch, bb_upper, bb_lower = build_chart(df, f"{ticker} — {asset_type}", show_bb, show_macd)
        
        st.plotly_chart(fig, use_container_width=True, config={
            'displayModeBar': True,
            'modeBarButtonsToRemove': ['pan2d','select2d','lasso2d'],
            'displaylogo': False
        })
        
        # ── Support/Resistance Table
        st.markdown('<div class="section-header"><div class="section-title">⚔️ مستويات الدعم والمقاومة</div></div>', unsafe_allow_html=True)
        
        col_r, col_s = st.columns(2)
        
        with col_r:
            res_above = [r for r in resistance_levels if r > price][:4]
            res_below = [r for r in resistance_levels if r <= price][-2:]
            all_res = sorted(res_below + res_above)[-5:]
            
            table_rows = ""
            for r in sorted(all_res, reverse=True):
                dist = ((r - price) / price * 100)
                color = "#FF3B3B" if r > price else "#FF8C00"
                table_rows += f'<tr><td style="color:{color}; font-weight:700;">{r:.4f}</td><td style="color:#8899AA;">{dist:+.2f}%</td><td style="color:#8899AA;">{"📍 تحليلي"}</td></tr>'
            
            st.markdown(f"""
            <table class="levels-table">
                <thead><tr><th>🔴 المقاومة</th><th>البُعد</th><th>النوع</th></tr></thead>
                <tbody>{table_rows}</tbody>
            </table>""", unsafe_allow_html=True)
        
        with col_s:
            sup_below = [s for s in support_levels if s < price][:4]
            sup_above = [s for s in support_levels if s >= price][-1:]
            all_sup = (sup_above + sup_below)[:5]
            
            table_rows = ""
            for s in sorted(all_sup, reverse=True):
                dist = ((s - price) / price * 100)
                color = "#00FF88" if s < price else "#00CC66"
                table_rows += f'<tr><td style="color:{color}; font-weight:700;">{s:.4f}</td><td style="color:#8899AA;">{dist:+.2f}%</td><td style="color:#8899AA;">{"📍 تحليلي"}</td></tr>'
            
            st.markdown(f"""
            <table class="levels-table">
                <thead><tr><th>🟢 الدعم</th><th>البُعد</th><th>النوع</th></tr></thead>
                <tbody>{table_rows}</tbody>
            </table>""", unsafe_allow_html=True)
        
        st.markdown('<div class="golden-divider"></div>', unsafe_allow_html=True)
        
        # ── AI Analysis
        st.markdown('<div class="section-header"><div class="section-title">🤖 التحليل السيادي بالذكاء الاصطناعي</div></div>', unsafe_allow_html=True)
        
        if analyze_btn or (not st.session_state.analysis_done) or (st.session_state.current_ticker != ticker):
            try:
                client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
                
                with st.spinner("⚔️ المستشار السيادي يحلل المعطيات..."):
                    ai_analysis = get_ai_analysis(
                        client, ticker, df, rsi, macd_line, signal_line, histogram,
                        ema20, ema50, atr, k_stoch, d_stoch, bb_upper, bb_lower,
                        trend_label, support_levels, resistance_levels, asset_type
                    )
                
                st.session_state.ai_text = ai_analysis
                st.session_state.analysis_done = True
                st.session_state.current_ticker = ticker
                st.session_state.chat_history = []
                
            except Exception as e:
                st.error(f"خطأ: {str(e)}")
                ai_analysis = st.session_state.ai_text
        else:
            ai_analysis = st.session_state.ai_text
        
        if ai_analysis:
            st.markdown(f'<div class="ai-analysis-box">{ai_analysis}</div>', unsafe_allow_html=True)
        
        # ── AI CHAT ────────────────────────────────────────────────────────────
        st.markdown('<div class="golden-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-header"><div class="section-title">💬 المحادثة مع المستشار السيادي</div></div>', unsafe_allow_html=True)
        
        st.markdown("""
        <div class="info-box">
        💡 اسأل المستشار أي سؤال تداولي: "ما أفضل نقطة دخول؟" أو "ما رأيك في المخاطرة؟" أو "هل يصلح للمضاربة اليومية؟"
        </div>
        """, unsafe_allow_html=True)
        
        # Display chat history
        for msg in st.session_state.chat_history:
            if msg['role'] == 'user':
                st.markdown(f'<div class="chat-user">👤 {msg["content"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="chat-ai">⚔️ {msg["content"]}</div>', unsafe_allow_html=True)
        
        col_input, col_send = st.columns([5, 1])
        with col_input:
            user_question = st.text_input(
                "سؤالك للمستشار",
                placeholder="مثال: ما هي أفضل استراتيجية لهذا الأصل الآن؟",
                key="chat_input",
                label_visibility="collapsed"
            )
        with col_send:
            send_btn = st.button("إرسال ⚡", key="send")
        
        if send_btn and user_question.strip():
            st.session_state.chat_history.append({"role": "user", "content": user_question})
            
            try:
                client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
                
                messages_for_api = [
                    {"role": "user", "content": f"أنت المستشار التداولي السيادي. لقد قدمت هذا التحليل للأصل {ticker}:\n\n{st.session_state.ai_text}\n\nالآن المتداول يسألك:"}
                ]
                
                for msg in st.session_state.chat_history[:-1]:
                    messages_for_api.append({"role": msg['role'], "content": msg['content']})
                
                messages_for_api.append({"role": "user", "content": user_question})
                
                with st.spinner("المستشار يفكر..."):
                    response = client.messages.create(
                        model="claude-opus-4-5",
                        max_tokens=800,
                        system="أنت مستشار تداولي سيادي خبير. أجب بإيجاز ودقة باللغة العربية مع استخدام المصطلحات التقنية المناسبة.",
                        messages=messages_for_api
                    )
                    ai_reply = response.content[0].text
                
                st.session_state.chat_history.append({"role": "assistant", "content": ai_reply})
                st.rerun()
                
            except Exception as e:
                st.error(f"خطأ: {str(e)}")

else:
    # Welcome screen
    st.markdown("""
    <div style="text-align:center; padding: 60px 20px; opacity:0.7;">
        <div style="font-family:'Orbitron'; font-size:3rem; color:#D4AF37; margin-bottom:20px;">⚔️</div>
        <div style="font-family:'Orbitron'; font-size:1.2rem; color:#D4AF37; letter-spacing:4px; margin-bottom:16px;">AWAITING ORDERS</div>
        <div style="color:#8899AA; font-size:1rem; direction:rtl; max-width:500px; margin:0 auto; line-height:2;">
            اختر الأصل المراد تحليله من القائمة الجانبية،<br>
            ثم اضغط على <strong style="color:#D4AF37">تحليل سيادي شامل</strong><br>
            للحصول على أكمل تحليل فني مدعوم بالذكاء الاصطناعي
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Quick tips
    st.markdown('<div class="golden-divider"></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown("""
        <div class="metric-card" style="text-align:right; direction:rtl;">
            <div style="font-size:1.5rem; margin-bottom:8px;">📊</div>
            <div style="color:#D4AF37; font-weight:700; margin-bottom:6px;">تحليل متعدد المؤشرات</div>
            <div style="color:#8899AA; font-size:0.85rem;">RSI + MACD + EMA + Bollinger + Stochastic + ATR</div>
        </div>""", unsafe_allow_html=True)
    
    with c2:
        st.markdown("""
        <div class="metric-card" style="text-align:right; direction:rtl;">
            <div style="font-size:1.5rem; margin-bottom:8px;">🤖</div>
            <div style="color:#D4AF37; font-weight:700; margin-bottom:6px;">ذكاء اصطناعي متخصص</div>
            <div style="color:#8899AA; font-size:0.85rem;">توصيات دخول وخروج وأهداف ووقف خسارة بدقة عالية</div>
        </div>""", unsafe_allow_html=True)
    
    with c3:
        st.markdown("""
        <div class="metric-card" style="text-align:right; direction:rtl;">
            <div style="font-size:1.5rem; margin-bottom:8px;">💬</div>
            <div style="color:#D4AF37; font-weight:700; margin-bottom:6px;">محادثة تداولية</div>
            <div style="color:#8899AA; font-size:0.85rem;">اسأل المستشار أي سؤال بعد التحليل وستحصل على إجابة فورية</div>
        </div>""", unsafe_allow_html=True)
