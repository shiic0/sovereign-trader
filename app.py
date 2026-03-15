import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from anthropic import Anthropic
from datetime import datetime, date
import requests
import time
import concurrent.futures
from threading import Lock

# yfinance — بيانات الأسهم
try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    _YF_AVAILABLE = False

_TV_AVAILABLE = False  # tvDatafeed غير مستخدم على Cloud

st.set_page_config(
    page_title="SOVEREIGN TRADER v2",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ══════════════════════════════════════════════════
# ASSET UNIVERSE
# ══════════════════════════════════════════════════

CRYPTO_SYMBOLS = {
    "BTC-USD":"BTCUSDT","ETH-USD":"ETHUSDT","BNB-USD":"BNBUSDT",
    "SOL-USD":"SOLUSDT","ADA-USD":"ADAUSDT","AVAX-USD":"AVAXUSDT",
    "DOT-USD":"DOTUSDT","ATOM-USD":"ATOMUSDT","NEAR-USD":"NEARUSDT",
    "FTM-USD":"FTMUSDT","ALGO-USD":"ALGOUSDT","XTZ-USD":"XTZUSDT",
    "HBAR-USD":"HBARUSDT","UNI-USD":"UNIUSDT","LINK-USD":"LINKUSDT",
    "AAVE-USD":"AAVEUSDT","CRV-USD":"CRVUSDT","MATIC-USD":"MATICUSDT",
    "OP-USD":"OPUSDT","ARB-USD":"ARBUSDT","DOGE-USD":"DOGEUSDT",
    "SHIB-USD":"SHIBUSDT","PEPE-USD":"PEPEUSDT","XRP-USD":"XRPUSDT",
    "XLM-USD":"XLMUSDT","LTC-USD":"LTCUSDT","FIL-USD":"FILUSDT",
    "FET-USD":"FETUSDT","RNDR-USD":"RNDRUSDT","AXS-USD":"AXSUSDT",
    "SAND-USD":"SANDUSDT","MANA-USD":"MANAUSDT","CRO-USD":"CROUSDT",
}

SAUDI_SECTORS = {
    "⛽ الطاقة":{
        "أرامكو":"2222.SR","سابك":"2010.SR",
        "رابغ":"2030.SR","يانسيف":"2370.SR",
    },
    "🏦 البنوك":{
        "الراجحي":"1120.SR","الأهلي":"1180.SR",
        "الإنماء":"1050.SR","الرياض":"1010.SR",
        "البلاد":"1060.SR","العربي":"1040.SR",
        "الفرنسي":"1080.SR","سامبا":"1090.SR",
    },
    "📡 الاتصالات":{
        "stc":"7010.SR","زين":"7030.SR","مدار":"4002.SR",
    },
    "⚙️ الصناعة":{
        "معادن":"1211.SR","المراعي":"2280.SR","الكابلات":"2110.SR",
    },
    "💡 الطاقة المتجددة":{
        "أكوا باور":"4082.SR","الكهرباء":"5110.SR",
    },
    "🛒 التجزئة":{
        "العثيم":"4012.SR","جرير":"4190.SR","بن داود":"4160.SR",
    },
    "🏥 الصحة":{
        "الدواء":"2070.SR","سعود الطبية":"6163.SR",
    },
}

CRYPTO_SECTORS = {
    "🔵 Layer 1":{
        "بيتكوين BTC":"BTC-USD","إيثيريوم ETH":"ETH-USD",
        "سولانا SOL":"SOL-USD","BNB":"BNB-USD",
        "كاردانو ADA":"ADA-USD","أفالانش AVAX":"AVAX-USD",
        "بوليكادوت DOT":"DOT-USD","كوزموس ATOM":"ATOM-USD",
        "نير NEAR":"NEAR-USD","فانتوم FTM":"FTM-USD",
    },
    "🟣 DeFi":{
        "يوني UNI":"UNI-USD","لينك LINK":"LINK-USD",
        "ايف AAVE":"AAVE-USD","كيرف CRV":"CRV-USD",
    },
    "🟡 Layer 2":{
        "بوليجون MATIC":"MATIC-USD","أوبتيميزم OP":"OP-USD",
        "أربيتروم ARB":"ARB-USD",
    },
    "🐕 Meme":{
        "دوجكوين DOGE":"DOGE-USD","شيبا SHIB":"SHIB-USD","بيبي PEPE":"PEPE-USD",
    },
    "💳 المدفوعات":{
        "ريبل XRP":"XRP-USD","ستيلار XLM":"XLM-USD","ليتكوين LTC":"LTC-USD",
    },
    "🤖 AI & Gaming":{
        "فيتش FET":"FET-USD","رندر RNDR":"RNDR-USD",
        "أكسي AXS":"AXS-USD","ساند SAND":"SAND-USD",
    },
}

COMMODITIES = {"ذهب":"GC=F","نفط WTI":"CL=F","فضة":"SI=F","نحاس":"HG=F"}
FOREX = {"EUR/USD":"EURUSD=X","GBP/USD":"GBPUSD=X","USD/JPY":"USDJPY=X","USD/SAR":"USDSAR=X"}
GLOBAL_INDICES = {"S&P 500":"^GSPC","Nasdaq":"^IXIC","NVDA":"NVDA","AAPL":"AAPL","TSLA":"TSLA","MSFT":"MSFT"}

ALL_SAUDI = {k:v for s in SAUDI_SECTORS.values() for k,v in s.items()}
ALL_CRYPTO = {k:v for s in CRYPTO_SECTORS.values() for k,v in s.items()}

# ══════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;700&family=JetBrains+Mono:wght@400;500;700&family=Tajawal:wght@300;400;500;700;900&display=swap');
:root{
  --bg:#070B12;--surface:#0C1220;--surface2:#111927;
  --border:rgba(99,130,190,0.12);--border2:rgba(99,130,190,0.22);
  --gold:#E8B84B;--gold2:#F5CF7A;--golddim:#7A6025;
  --green:#00D68F;--red:#FF4560;--blue:#3B82F6;
  --cyan:#06B6D4;--text:#E2E8F0;--muted:#64748B;--dim:#94A3B8;
}
*{font-family:'Tajawal',sans-serif!important;box-sizing:border-box;}
body,.stApp{background:var(--bg)!important;color:var(--text)!important;}
#MainMenu,footer,header{visibility:hidden;}
[data-testid="stSidebar"]{background:var(--surface)!important;border-left:1px solid var(--border)!important;}
::-webkit-scrollbar{width:4px;height:4px;}
::-webkit-scrollbar-track{background:var(--bg);}
::-webkit-scrollbar-thumb{background:var(--golddim);border-radius:2px;}
.stButton>button{background:linear-gradient(135deg,var(--golddim),var(--gold))!important;color:#000!important;font-weight:700!important;border:none!important;border-radius:8px!important;transition:all .2s!important;}
.stButton>button:hover{transform:translateY(-1px)!important;box-shadow:0 6px 24px rgba(232,184,75,.3)!important;}
.stTextInput>div>div,.stSelectbox>div>div,.stNumberInput>div>div>input{background:var(--surface2)!important;border:1px solid var(--border2)!important;border-radius:8px!important;color:var(--text)!important;}
.stTabs [data-baseweb="tab-list"]{background:var(--surface)!important;border-radius:10px!important;padding:4px!important;gap:2px!important;border:1px solid var(--border)!important;}
.stTabs [data-baseweb="tab"]{background:transparent!important;color:var(--muted)!important;border-radius:8px!important;font-weight:500!important;padding:8px 16px!important;font-size:.85rem!important;}
.stTabs [aria-selected="true"]{background:var(--surface2)!important;color:var(--gold)!important;border-bottom:2px solid var(--gold)!important;}
[data-testid="stMetric"]{background:var(--surface)!important;border:1px solid var(--border)!important;border-radius:12px!important;padding:16px!important;}
@keyframes pulse{0%,100%{opacity:1;}50%{opacity:.3;}}
.kpi-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px;text-align:center;transition:all .2s;position:relative;overflow:hidden;}
.kpi-card:hover{border-color:var(--border2);}
.kpi-label{font-family:'JetBrains Mono',monospace;font-size:.62rem;letter-spacing:2px;color:var(--muted);text-transform:uppercase;margin-bottom:6px;}
.kpi-value{font-family:'JetBrains Mono',monospace;font-size:1.2rem;font-weight:700;line-height:1;}
.kpi-change{font-family:'JetBrains Mono',monospace;font-size:.72rem;margin-top:4px;}
.page-header{background:linear-gradient(135deg,var(--surface) 0%,rgba(11,18,32,.8) 100%);border:1px solid var(--border);border-radius:16px;padding:22px 28px;margin-bottom:18px;position:relative;overflow:hidden;}
.page-header::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,var(--gold),transparent);}
.page-header-title{font-family:'JetBrains Mono',monospace!important;font-size:.72rem;letter-spacing:4px;color:var(--gold);text-transform:uppercase;margin-bottom:5px;}
.page-header-desc{font-size:.85rem;color:var(--dim);line-height:1.6;}
.opp-card{background:var(--surface);border-radius:12px;padding:14px 18px;margin:6px 0;border-right:3px solid var(--green);direction:rtl;transition:all .2s;}
.opp-card:hover{background:var(--surface2);}
.opp-card.sell{border-right-color:var(--red);}
.opp-card.watch{border-right-color:var(--gold);}
.badge{display:inline-block;padding:2px 10px;border-radius:20px;font-size:.68rem;font-weight:700;font-family:'JetBrains Mono',monospace;letter-spacing:.5px;}
.badge-buy{background:rgba(0,214,143,.12);color:var(--green);border:1px solid rgba(0,214,143,.3);}
.badge-sell{background:rgba(255,69,96,.12);color:var(--red);border:1px solid rgba(255,69,96,.3);}
.badge-watch{background:rgba(232,184,75,.12);color:var(--gold);border:1px solid rgba(232,184,75,.3);}
.badge-scalp{background:rgba(255,69,96,.08);color:#FF8C9E;border:1px solid rgba(255,69,96,.2);}
.badge-swing{background:rgba(59,130,246,.08);color:#93C5FD;border:1px solid rgba(59,130,246,.2);}
.badge-invest{background:rgba(0,214,143,.08);color:var(--green);border:1px solid rgba(0,214,143,.2);}
.divider{height:1px;background:linear-gradient(90deg,transparent,var(--border2),transparent);margin:16px 0;}
.section-title{font-family:'JetBrains Mono',monospace;font-size:.68rem;letter-spacing:3px;color:var(--gold);text-transform:uppercase;border-bottom:1px solid var(--border);padding-bottom:10px;margin:18px 0 14px;}
.ai-box{background:linear-gradient(135deg,var(--surface),var(--surface2));border:1px solid var(--border2);border-right:3px solid var(--gold);border-radius:12px;padding:22px 26px;direction:rtl;line-height:2;font-size:.92rem;color:var(--text);min-height:80px;}
.alert-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 18px;margin:5px 0;direction:rtl;display:flex;justify-content:space-between;align-items:center;}
.alert-card.triggered{border-color:var(--green);background:rgba(0,214,143,.04);}
.portfolio-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px 18px;margin:5px 0;direction:rtl;transition:all .2s;}
.portfolio-card:hover{border-color:var(--border2);}
.portfolio-card.danger{border-color:var(--red)!important;background:rgba(255,69,96,.04);}
.trade-row{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 18px;margin:5px 0;direction:rtl;transition:all .15s;}
.trade-row:hover{border-color:var(--border2);}
.trade-row.win{border-right:3px solid var(--green);}
.trade-row.loss{border-right:3px solid var(--red);}
.trade-row.open-trade{border-right:3px solid var(--blue);}
.stat-box{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px;text-align:center;}
.stat-number{font-family:'JetBrains Mono',monospace;font-size:1.8rem;font-weight:700;margin-bottom:4px;}
.stat-label{font-size:.78rem;color:var(--muted);letter-spacing:1px;}
.info-box{background:rgba(59,130,246,.06);border:1px solid rgba(59,130,246,.18);border-radius:10px;padding:12px 16px;font-size:.85rem;color:var(--dim);direction:rtl;margin:8px 0;line-height:1.7;}
.levels-table{width:100%;border-collapse:collapse;direction:rtl;}
.levels-table th{background:rgba(232,184,75,.06);color:var(--gold);padding:10px 14px;text-align:right;font-size:.75rem;border-bottom:1px solid var(--border);font-family:'JetBrains Mono',monospace;letter-spacing:1px;}
.levels-table td{padding:10px 14px;border-bottom:1px solid rgba(255,255,255,.03);font-family:'JetBrains Mono',monospace;font-size:.83rem;}
.scan-progress{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 18px;direction:rtl;font-family:'JetBrains Mono',monospace;font-size:.78rem;color:var(--dim);}
.wl-row{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 16px;margin:4px 0;direction:rtl;transition:all .15s;}
.wl-row:hover{border-color:var(--gold);background:var(--surface2);}
</style>
"""

# ══════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════

_defaults = {
    "page":"home","watchlist":["2222.SR","1120.SR","7010.SR","BTC-USD","ETH-USD","SOL-USD","GC=F"],
    "portfolio":[],"alerts":[],"trades":[],"analysis_done":False,
    "ai_text":"","current_ticker":"","chat_history":[],"opp_cache":[],
}
for k,v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

st.markdown(CSS, unsafe_allow_html=True)

# ══════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════

st.markdown("""
<div style="background:linear-gradient(90deg,#070B12,#0C1220,#070B12);
  border-bottom:1px solid rgba(99,130,190,0.12);
  padding:13px 28px;margin-bottom:14px;
  display:flex;align-items:center;justify-content:space-between;">
  <div style="display:flex;align-items:center;gap:12px;">
    <div style="width:36px;height:36px;background:linear-gradient(135deg,#7A6025,#E8B84B);
      border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:1.1rem;">⚔️</div>
    <div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:.92rem;font-weight:700;color:#E8B84B;letter-spacing:2px;">SOVEREIGN TRADER</div>
      <div style="font-family:'JetBrains Mono',monospace;font-size:.56rem;color:#64748B;letter-spacing:3px;">v2.0 — LIVE MARKET INTELLIGENCE</div>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:7px;
    font-family:'JetBrains Mono',monospace;font-size:.63rem;color:#00D68F;
    background:rgba(0,214,143,.06);border:1px solid rgba(0,214,143,.2);
    padding:5px 13px;border-radius:20px;">
    <div style="width:5px;height:5px;background:#00D68F;border-radius:50%;animation:pulse 2s infinite;"></div>
    BINANCE · YAHOO · LIVE
  </div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════
# NAVIGATION
# ══════════════════════════════════════════════════

nav_items = [
    ("🏠","home","الرئيسية"),("📊","analysis","التحليل"),("⚡","opportunities","الفرص"),
    ("🔔","alerts","المنبهات"),("💼","portfolio","المحفظة"),("📔","journal","السجل"),
    ("📈","watchlist","المراقبة"),("📚","reference","المرجع"),("🐙","github","GitHub"),
]
nav_cols = st.columns(len(nav_items))
for col,(icon,key,label) in zip(nav_cols,nav_items):
    with col:
        active = st.session_state.page == key
        if st.button(f"{icon} {label}", key=f"nav_{key}", use_container_width=True,
                     type="primary" if active else "secondary"):
            st.session_state.page = key
            st.rerun()
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════
# DATA
# ══════════════════════════════════════════════════

# ══════════════════════════════════════════════════
# DATA FUNCTIONS — Binance RT + Yahoo Finance
# ══════════════════════════════════════════════════

@st.cache_data(ttl=20, show_spinner=False)
def _binance_quote(sym):
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/24hr",
                         params={"symbol": sym}, timeout=5)
        d = r.json()
        if "lastPrice" not in d: return None
        return {"price":float(d["lastPrice"]),"change":float(d["priceChangePercent"]),
                "vol":float(d["quoteVolume"]),"high":float(d["highPrice"]),
                "low":float(d["lowPrice"]),"source":"BINANCE RT"}
    except: return None

@st.cache_data(ttl=60, show_spinner=False)
def _yahoo_quote(ticker):
    if not _YF_AVAILABLE: return None
    try:
        import yfinance as yf
        df = yf.download(ticker, period="5d", interval="1d",
                         progress=False, auto_adjust=True, timeout=8)
        if df is None or df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        if len(df) < 2: return None
        p = float(df["Close"].iloc[-1]); pp = float(df["Close"].iloc[-2])
        return {"price":p,"change":(p-pp)/pp*100,"vol":float(df["Volume"].iloc[-1]),
                "high":float(df["High"].iloc[-1]),"low":float(df["Low"].iloc[-1]),
                "source":"YAHOO FINANCE"}
    except: return None

def get_quote(ticker):
    if ticker in CRYPTO_SYMBOLS:
        q = _binance_quote(CRYPTO_SYMBOLS[ticker])
        if q: return q
    return _yahoo_quote(ticker)

@st.cache_data(ttl=120, show_spinner=False)
def _binance_ohlcv(sym, interval, limit):
    bi = {"15m":"15m","1h":"1h","4h":"4h","1d":"1d","1wk":"1w"}.get(interval,"1d")
    try:
        r = requests.get("https://api.binance.com/api/v3/klines",
                         params={"symbol":sym,"interval":bi,"limit":limit}, timeout=10)
        raw = r.json()
        if not raw or isinstance(raw, dict): return None
        df = pd.DataFrame(raw, columns=["T","Open","High","Low","Close","Volume",
                                         "t","q","n","tb","tq","ig"])
        df["T"] = pd.to_datetime(df["T"], unit="ms"); df.set_index("T", inplace=True)
        for c in ["Open","High","Low","Close","Volume"]: df[c] = df[c].astype(float)
        df.index.name = "Datetime"
        return df[["Open","High","Low","Close","Volume"]]
    except: return None

@st.cache_data(ttl=120, show_spinner=False)
def _yahoo_ohlcv(ticker, period, interval):
    if not _YF_AVAILABLE: return None
    try:
        import yfinance as yf
        df = yf.download(ticker, period=period, interval=interval,
                         progress=False, auto_adjust=True, timeout=12)
        if df is None or df.empty:
            time.sleep(0.6)
            df = yf.download(ticker, period="1y", interval="1d",
                             progress=False, auto_adjust=True, timeout=12)
        if df is None or df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df.dropna(); df.index.name = "Datetime"
        return df[["Open","High","Low","Close","Volume"]]
    except: return None

def get_data(ticker, period="3mo", interval="1d"):
    if ticker in CRYPTO_SYMBOLS:
        lim = {"15m":500,"1h":500,"4h":400,"1d":300,"1wk":200}.get(interval, 300)
        df = _binance_ohlcv(CRYPTO_SYMBOLS[ticker], interval, lim)
        if df is not None and len(df) >= 50: return df
    return _yahoo_ohlcv(ticker, period, interval)

# ══════════════════════════════════════════════════
# INDICATORS
# ══════════════════════════════════════════════════

def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def rsi(s, n=14):
    d = s.diff(); g = d.clip(lower=0).rolling(n).mean()
    l = (-d.clip(upper=0)).rolling(n).mean()
    return 100 - (100/(1+g/l.replace(0, np.nan)))
def macd(s):
    m = ema(s,12)-ema(s,26); sig = ema(m,9); return m, sig, m-sig
def bb(s, n=20, k=2):
    sma = s.rolling(n).mean(); std = s.rolling(n).std()
    return sma+k*std, sma, sma-k*std
def atr(h, l, c, n=14):
    tr = pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    return tr.rolling(n).mean()
def stoch(h, l, c, k=14, d=3):
    ll = l.rolling(k).min(); hh = h.rolling(k).max()
    K = 100*(c-ll)/(hh-ll).replace(0, np.nan)
    return K, K.rolling(d).mean()
def fib_levels(hi, lo):
    d = hi-lo
    return {"0%":hi,"23.6%":hi-.236*d,"38.2%":hi-.382*d,
            "50%":hi-.5*d,"61.8%":hi-.618*d,"78.6%":hi-.786*d,"100%":lo}
def calc_sr(df, w=20):
    H = df["High"].rolling(w,center=True).max()
    L = df["Low"].rolling(w,center=True).min()
    res, sup = [], []
    for i in range(w, len(df)-w):
        if df["High"].iloc[i] == H.iloc[i]: res.append(df["High"].iloc[i])
        if df["Low"].iloc[i] == L.iloc[i]: sup.append(df["Low"].iloc[i])
    def cluster(lvls, tol=.02):
        if not lvls: return []
        lvls = sorted(set(lvls)); out, g = [], [lvls[0]]
        for x in lvls[1:]:
            if (x-g[-1])/g[-1] < tol: g.append(x)
            else: out.append(np.mean(g)); g=[x]
        out.append(np.mean(g)); return out
    return cluster(res), cluster(sup)
def get_trend(df):
    c = df["Close"]
    e20 = float(ema(c,20).iloc[-1]); e50 = float(ema(c,50).iloc[-1]); p = float(c.iloc[-1])
    if p > e20 > e50: return "صاعد 🟢","bull"
    if p < e20 < e50: return "هابط 🔴","bear"
    return "عرضي ⚪","side"

# ══════════════════════════════════════════════════
# PARALLEL SCANNER
# ══════════════════════════════════════════════════

@st.cache_data(ttl=300, show_spinner=False)
def score_asset(ticker):
    df = get_data(ticker, "3mo", "1d")
    if df is None or len(df) < 50: return None
    c = df["Close"]; p = float(c.iloc[-1])
    r = float(rsi(c).iloc[-1])
    m, sig, h = macd(c)
    e20v = float(ema(c,20).iloc[-1]); e50v = float(ema(c,50).iloc[-1])
    vavg = float(df["Volume"].tail(20).mean())
    vr = float(df["Volume"].iloc[-1])/vavg if vavg>0 else 1
    hr = float(h.iloc[-1]) > float(h.iloc[-2]) if len(h)>1 else False
    chg = (p-float(c.iloc[-2]))/float(c.iloc[-2])*100 if len(c)>1 else 0
    chg5 = (p-float(c.iloc[-6]))/float(c.iloc[-6])*100 if len(c)>5 else 0
    sc = sum([e20v>e50v, float(m.iloc[-1])>float(sig.iloc[-1]), 35<r<65, hr, vr>1.2])
    res_lvl, sup_lvl = calc_sr(df)
    atr_v = float(atr(df["High"],df["Low"],c).iloc[-1])
    near_sup = any(abs(p-s)/p<.025 for s in sup_lvl) if sup_lvl else False
    near_res = any(abs(p-rv)/p<.025 for rv in res_lvl) if res_lvl else False
    vp = atr_v/p*100
    return {
        "ticker":ticker,"price":p,"change":chg,"change5":chg5,"rsi":r,"score":sc,
        "near_sup":near_sup,"near_res":near_res,"atr":atr_v,"vol_ratio":vr,
        "vol_spike":vr>1.5,"scalp":vp>1.5 and vr>1.2,
        "swing":35<r<65 and (e20v>e50v or near_sup),"invest":e20v>e50v and chg5>0,
        "res":res_lvl,"sup":sup_lvl,
        "signal":"شراء" if sc>=4 else "بيع" if sc<=1 else "مراقبة",
    }

def parallel_scan(universe, prog_ph):
    results = []; total = len(universe); completed = [0]; lock = Lock()
    def scan_one(tkr):
        s = score_asset(tkr)
        with lock:
            completed[0] += 1; pct = completed[0]/total
            prog_ph.markdown(
                f'<div class="scan-progress">'
                f'<div style="display:flex;justify-content:space-between;margin-bottom:6px;">'
                f'<span>⚡ مسح متوازي...</span>'
                f'<span style="color:var(--gold);font-family:JetBrains Mono">{completed[0]}/{total}</span></div>'
                f'<div style="background:rgba(255,255,255,.06);border-radius:3px;height:3px;">'
                f'<div style="width:{pct*100:.0f}%;height:100%;background:var(--gold);border-radius:3px;"></div>'
                f'</div></div>', unsafe_allow_html=True)
        return s
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(scan_one, t): t for t in universe}
        for f in concurrent.futures.as_completed(futs):
            s = f.result()
            if s: results.append(s)
    return results

# ══════════════════════════════════════════════════
# CHART
# ══════════════════════════════════════════════════

def build_chart(df, name, sup=None, res=None, show_bb=True, show_macd=True, show_fib=False):
    c = df["Close"]; h = df["High"]; l = df["Low"]; v = df["Volume"]
    e20 = ema(c,20); e50 = ema(c,50); e200 = ema(c,200)
    r = rsi(c); ml, sl, hist = macd(c)
    bbu, bbm, bbl = bb(c); ks, kd = stoch(h,l,c); at = atr(h,l,c)
    rows = 4 if show_macd else 3
    rh = [.52,.18,.15,.15] if show_macd else [.55,.22,.23]
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True,
                        row_heights=rh, vertical_spacing=.03)
    # Candles
    fig.add_trace(go.Candlestick(x=df.index,open=df["Open"],high=h,low=l,close=c,name="السعر",
        increasing_line_color="#00D68F",increasing_fillcolor="rgba(0,214,143,.8)",
        decreasing_line_color="#FF4560",decreasing_fillcolor="rgba(255,69,96,.8)",
        line=dict(width=1)),row=1,col=1)
    # EMAs
    fig.add_trace(go.Scatter(x=df.index,y=e20,name="EMA20",line=dict(color="#06B6D4",width=1.5)),row=1,col=1)
    fig.add_trace(go.Scatter(x=df.index,y=e50,name="EMA50",line=dict(color="#F59E0B",width=1.5)),row=1,col=1)
    if len(c)>=200:
        fig.add_trace(go.Scatter(x=df.index,y=e200,name="EMA200",line=dict(color="#EF4444",width=1.5,dash="dot")),row=1,col=1)
    # Bollinger
    if show_bb:
        fig.add_trace(go.Scatter(x=df.index,y=bbu,name="BB+",line=dict(color="rgba(232,184,75,.35)",width=1,dash="dash")),row=1,col=1)
        fig.add_trace(go.Scatter(x=df.index,y=bbl,name="BB-",line=dict(color="rgba(232,184,75,.35)",width=1,dash="dash"),
            fill="tonexty",fillcolor="rgba(232,184,75,.03)"),row=1,col=1)
    # S/R
    if res:
        for rv in sorted(res)[:4]:
            if rv>0: fig.add_hline(y=rv,line=dict(color="rgba(255,69,96,.4)",width=1,dash="dot"),
                annotation_text=f"R {rv:.3f}",annotation_font=dict(color="#FF4560",size=9),row=1,col=1)
    if sup:
        for sv in sorted(sup,reverse=True)[:4]:
            if sv>0: fig.add_hline(y=sv,line=dict(color="rgba(0,214,143,.4)",width=1,dash="dot"),
                annotation_text=f"S {sv:.3f}",annotation_font=dict(color="#00D68F",size=9),row=1,col=1)
    # Fibonacci
    if show_fib:
        fhi = float(df["High"].tail(60).max()); flo = float(df["Low"].tail(60).min())
        fcols = {"23.6%":"#FCD34D","38.2%":"#FB923C","50%":"#F97316","61.8%":"#EF4444","78.6%":"#DC2626"}
        for lbl,val in fib_levels(fhi,flo).items():
            if lbl in fcols:
                fig.add_hline(y=val,line=dict(color=fcols[lbl],width=.8,dash="dashdot"),
                    annotation_text=f"Fib {lbl}",annotation_font=dict(color=fcols[lbl],size=8),row=1,col=1)
    # Cross signals
    e20a = e20.values; e50a = e50.values
    for i in range(1,min(len(e20a),len(e50a))):
        pd_ = e20a[i-1]-e50a[i-1]; cd = e20a[i]-e50a[i]
        if pd.isna(pd_) or pd.isna(cd): continue
        if pd_<0 and cd>0:
            fig.add_annotation(x=df.index[i],y=float(e20a[i]),text="⭐ Golden",
                showarrow=True,arrowhead=2,arrowcolor="#FFD700",font=dict(color="#FFD700",size=9),
                bgcolor="rgba(7,11,18,.85)",row=1,col=1)
        elif pd_>0 and cd<0:
            fig.add_annotation(x=df.index[i],y=float(e20a[i]),text="💀 Death",
                showarrow=True,arrowhead=2,arrowcolor="#FF4560",font=dict(color="#FF4560",size=9),
                bgcolor="rgba(7,11,18,.85)",row=1,col=1)
    # RSI
    fig.add_trace(go.Scatter(x=df.index,y=r,name="RSI",line=dict(color="#8B5CF6",width=2)),row=2,col=1)
    fig.add_hline(y=70,line=dict(color="#FF4560",width=1,dash="dash"),row=2,col=1)
    fig.add_hline(y=30,line=dict(color="#00D68F",width=1,dash="dash"),row=2,col=1)
    fig.add_shape(type="rect",x0=df.index[0],x1=df.index[-1],y0=70,y1=100,
        fillcolor="rgba(255,69,96,.04)",line_width=0,row=2,col=1)
    fig.add_shape(type="rect",x0=df.index[0],x1=df.index[-1],y0=0,y1=30,
        fillcolor="rgba(0,214,143,.04)",line_width=0,row=2,col=1)
    # MACD or Stoch
    if show_macd:
        hcols = ["#00D68F" if x>=0 else "#FF4560" for x in hist]
        fig.add_trace(go.Bar(x=df.index,y=hist,name="Hist",marker_color=hcols,opacity=.7),row=3,col=1)
        fig.add_trace(go.Scatter(x=df.index,y=ml,name="MACD",line=dict(color="#06B6D4",width=1.5)),row=3,col=1)
        fig.add_trace(go.Scatter(x=df.index,y=sl,name="Signal",line=dict(color="#F59E0B",width=1.5)),row=3,col=1)
    else:
        fig.add_trace(go.Scatter(x=df.index,y=ks,name="%K",line=dict(color="#06B6D4",width=2)),row=3,col=1)
        fig.add_trace(go.Scatter(x=df.index,y=kd,name="%D",line=dict(color="#F59E0B",width=2)),row=3,col=1)
        fig.add_hline(y=80,line=dict(color="#FF4560",width=1,dash="dash"),row=3,col=1)
        fig.add_hline(y=20,line=dict(color="#00D68F",width=1,dash="dash"),row=3,col=1)
    # Volume
    vr2 = 4 if show_macd else 3
    vc = ["#00D68F" if float(cc)>=float(oo) else "#FF4560" for cc,oo in zip(c,df["Open"])]
    fig.add_trace(go.Bar(x=df.index,y=v,name="Volume",marker_color=vc,opacity=.55),row=vr2,col=1)
    fig.add_trace(go.Scatter(x=df.index,y=v.rolling(20).mean(),name="Vol MA20",line=dict(color="#E8B84B",width=1.5)),row=vr2,col=1)
    # Layout
    fig.update_layout(template="plotly_dark",plot_bgcolor="#070B12",paper_bgcolor="#070B12",
        font=dict(family="JetBrains Mono",color="#94A3B8",size=11),height=820,showlegend=True,
        legend=dict(orientation="h",yanchor="bottom",y=1.01,xanchor="right",x=1,
            bgcolor="rgba(12,18,32,.85)",bordercolor="rgba(99,130,190,.2)",borderwidth=1,font=dict(size=9)),
        xaxis_rangeslider_visible=False,margin=dict(l=0,r=0,t=30,b=0),
        hovermode="x unified",hoverlabel=dict(bgcolor="#0C1220",bordercolor="#E8B84B",font=dict(family="JetBrains Mono",size=11)))
    for i in range(1,rows+1):
        fig.update_xaxes(gridcolor="rgba(99,130,190,.06)",row=i,col=1)
        fig.update_yaxes(gridcolor="rgba(99,130,190,.06)",row=i,col=1)
    return fig, r, ml, sl, hist, e20, e50, at, ks, kd, bbu, bbl

# ══════════════════════════════════════════════════
# AI PROMPT
# ══════════════════════════════════════════════════

def build_ai_prompt(ticker, df, r_s, ml, sl_s, hist, e20, e50, at, ks, kd, bbu, bbl,
                    trend_lbl, res, sup, asset_type):
    c = df["Close"]; p = float(c.iloc[-1])
    chg1 = (p-float(c.iloc[-2]))/float(c.iloc[-2])*100 if len(c)>1 else 0
    chg5 = (p-float(c.iloc[-6]))/float(c.iloc[-6])*100 if len(c)>5 else 0
    hi52 = float(df["High"].tail(252).max()); lo52 = float(df["Low"].tail(252).min())
    vavg = float(df["Volume"].tail(20).mean())
    vr = float(df["Volume"].iloc[-1])/vavg if vavg>0 else 1
    rv = float(r_s.iloc[-1]); mv = float(ml.iloc[-1]); sv_ = float(sl_s.iloc[-1])
    hv = float(hist.iloc[-1]); hpv = float(hist.iloc[-2]) if len(hist)>1 else hv
    e20v = float(e20.iloc[-1]); e50v = float(e50.iloc[-1]); atv = float(at.iloc[-1])
    kv = float(ks.iloc[-1]) if not pd.isna(ks.iloc[-1]) else 50
    bbuw = float(bbu.iloc[-1]); bblw = float(bbl.iloc[-1])
    bbw = (bbuw-bblw)/bblw*100 if bblw>0 else 0
    tr = sorted(res)[:3]; ts = sorted(sup)[-3:]
    return f"""أنت محلل تقني متقدم. قدم تحليلاً احترافياً مختصراً وعملياً باللغة العربية.

الأصل: {ticker} | النوع: {asset_type}
السعر: {p:.4f} | اليوم: {chg1:+.2f}% | 5 أيام: {chg5:+.2f}%
52أسبوع: ▲{hi52:.4f} / ▼{lo52:.4f} | الاتجاه: {trend_lbl}
EMA20: {e20v:.4f} ({(p-e20v)/e20v*100:+.2f}%) | EMA50: {e50v:.4f} ({(p-e50v)/e50v*100:+.2f}%)
RSI: {rv:.1f} | MACD: {mv:.6f} vs {sv_:.6f} | Hist: {"↑" if hv>hpv else "↓"}{abs(hv):.6f}
Stoch %K: {kv:.1f} | BB Width: {bbw:.1f}% | ATR: {atv:.4f} ({atv/p*100:.2f}%)
Volume: {vr:.1f}x | مقاومات: {[f"{x:.3f}" for x in tr]} | دعوم: {[f"{x:.3f}" for x in ts]}

اكتب التحليل بهذا التنسيق:

## 🎯 الحكم
**[شراء قوي / شراء / مراقبة / بيع / بيع قوي]** — جملة حاسمة واحدة

## 📊 المؤشرات
• **الاتجاه:** تحليل EMA
• **RSI {rv:.0f}:** تفسير + خطر أم فرصة؟
• **MACD:** التقاطع + اتجاه الهيستوغرام
• **البولينجر:** موقع السعر + عرض النطاق
• **الحجم:** {vr:.1f}x — تفسير

## ⚔️ المستويات
• **🔴 مقاومات:** {[f"{x:.3f}" for x in tr]}
• **🟢 دعوم:** {[f"{x:.3f}" for x in ts]}

## 💰 خطة التداول
| | السعر |
|--|--|
| **الدخول** | {p:.4f} |
| **الهدف 1** | {p+1.5*atv:.4f} |
| **الهدف 2** | {p+3*atv:.4f} |
| **وقف الخسارة** | {p-1.5*atv:.4f} |

## ⚠️ المخاطر
سيناريو سلبي واحد محدد

---
*للأغراض التعليمية فقط*"""

# ══════════════════════════════════════════════════
# TRADE STATS
# ══════════════════════════════════════════════════

def calc_trade_stats(trades):
    if not trades: return {}
    closed = [t for t in trades if t.get("status")=="مغلقة"]
    open_t = [t for t in trades if t.get("status")=="مفتوحة"]
    if not closed:
        return {"total":len(trades),"open":len(open_t),"closed":0,
                "win_rate":0,"total_pnl":0,"best_trade":0,"worst_trade":0,"profit_factor":0}
    wins = [t for t in closed if t.get("pnl",0)>0]
    losses = [t for t in closed if t.get("pnl",0)<=0]
    pnl_list = [t.get("pnl_pct",0) for t in closed]
    gross_win = sum(t["pnl"] for t in wins) if wins else 0
    gross_loss = abs(sum(t["pnl"] for t in losses)) if losses else 0
    return {
        "total":len(trades),"open":len(open_t),"closed":len(closed),
        "wins":len(wins),"losses":len(losses),
        "win_rate":len(wins)/len(closed)*100 if closed else 0,
        "total_pnl":sum(t.get("pnl",0) for t in closed),
        "best_trade":max(pnl_list) if pnl_list else 0,
        "worst_trade":min(pnl_list) if pnl_list else 0,
        "profit_factor":round(gross_win/gross_loss,2) if gross_loss>0 else float("inf"),
        "avg_pnl_pct":np.mean(pnl_list) if pnl_list else 0,
    }

# ══════════════════════════════════════════════════
# PAGE: HOME
# ══════════════════════════════════════════════════

if st.session_state.page == "home":
    st.markdown('<div class="page-header"><div class="page-header-title">🏠 نبض السوق</div>'
                '<div class="page-header-desc">أسعار لحظية · Binance RT + Yahoo Finance · تحديث تلقائي</div></div>',
                unsafe_allow_html=True)

    home_items = {
        "أرامكو":"2222.SR","الراجحي":"1120.SR","stc":"7010.SR","معادن":"1211.SR",
        "BTC":"BTC-USD","ETH":"ETH-USD","SOL":"SOL-USD","XRP":"XRP-USD",
        "ذهب":"GC=F","نفط":"CL=F","EUR/USD":"EURUSD=X","NVDA":"NVDA",
    }
    cols = st.columns(6)
    for idx,(name,tkr) in enumerate(home_items.items()):
        q = get_quote(tkr)
        with cols[idx%6]:
            if q:
                clr = "var(--green)" if q["change"]>=0 else "var(--red)"
                sym = "▲" if q["change"]>=0 else "▼"
                src_dot = ("🟢" if "BINANCE" in q.get("source","")
                           else "🟡" if "TRADINGVIEW" in q.get("source","") else "⚪")
                st.markdown(f'<div class="kpi-card"><div class="kpi-label">{name}</div>'
                            f'<div class="kpi-value" style="color:var(--gold);font-size:.95rem;">{q["price"]:,.3f}</div>'
                            f'<div class="kpi-change" style="color:{clr};">{sym} {q["change"]:+.2f}%</div>'
                            f'<div style="font-family:JetBrains Mono;font-size:.55rem;color:var(--muted);margin-top:3px;">{src_dot} {q.get("source","")}</div>'
                            f'</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="kpi-card"><div class="kpi-label">{name}</div>'
                            f'<div style="color:var(--muted);font-size:.75rem;margin-top:8px;">جاري...</div></div>',
                            unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # Leaderboard
    st.markdown('<div class="section-title">🏆 تصنيف الأسهم السعودية</div>', unsafe_allow_html=True)
    lb_tickers = list(list(SAUDI_SECTORS.values())[0].values()) + list(list(SAUDI_SECTORS.values())[1].values())[:5]
    lb_data = []
    for tkr in lb_tickers[:10]:
        q = get_quote(tkr)
        nm = [k for sec in SAUDI_SECTORS.values() for k,v in sec.items() if v==tkr]
        nm = nm[0] if nm else tkr.replace(".SR","")
        if q: lb_data.append({"name":nm,"price":q["price"],"change":q["change"]})
    if lb_data:
        lb_data.sort(key=lambda x: x["change"], reverse=True)
        lb_cols = st.columns(len(lb_data))
        for i,(col,d) in enumerate(zip(lb_cols,lb_data)):
            clr = "var(--green)" if d["change"]>=0 else "var(--red)"
            medal = "🥇" if i==0 else "🥈" if i==1 else "🥉" if i==2 else f"{i+1}"
            with col:
                st.markdown(f'<div class="kpi-card" style="padding:10px 6px;">'
                            f'<div class="kpi-label" style="font-size:.56rem;">{medal} {d["name"]}</div>'
                            f'<div class="kpi-value" style="color:{clr};font-size:.85rem;">{d["change"]:+.2f}%</div>'
                            f'<div style="color:var(--muted);font-size:.62rem;margin-top:2px;font-family:JetBrains Mono">{d["price"]:.2f}</div>'
                            f'</div>', unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # Hot moves
    st.markdown('<div class="section-title">⚡ تحركات لافتة</div>', unsafe_allow_html=True)
    found = False
    for tkr in ["2222.SR","1120.SR","BTC-USD","ETH-USD","SOL-USD","GC=F","XRP-USD","NVDA"]:
        q = get_quote(tkr)
        if q and abs(q["change"])>1.5:
            found = True
            name = tkr.replace(".SR","").replace("-USD","").replace("=X","")
            clr = "var(--green)" if q["change"]>0 else "var(--red)"
            icon = "🟢" if q["change"]>0 else "🔴"
            st.markdown(f'<div class="opp-card {"sell" if q["change"]<0 else ""}">'
                        f'<span style="font-family:JetBrains Mono;color:var(--gold);font-weight:700;">{icon} {name}</span>'
                        f'<span style="margin-right:12px;font-family:JetBrains Mono;color:{clr};font-weight:700;"> {q["change"]:+.2f}%</span>'
                        f'<span style="color:var(--muted);font-size:.8rem;"> {q["price"]:,.4f}</span></div>',
                        unsafe_allow_html=True)
    if not found:
        st.markdown('<div class="info-box">السوق هادئ — لا تحركات فوق 1.5%</div>', unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">💡 <strong>التحليل 📊</strong> شارت كامل + AI streaming &nbsp;|&nbsp; '
                '<strong>الفرص ⚡</strong> ماسح متوازي 12 خيط &nbsp;|&nbsp; '
                '<strong>السجل 📔</strong> تتبع صفقاتك + إحصائيات</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════
# PAGE: ANALYSIS
# ══════════════════════════════════════════════════

elif st.session_state.page == "analysis":
    with st.sidebar:
        st.markdown('<div style="font-family:JetBrains Mono;font-size:.68rem;color:var(--gold);'
                    'letter-spacing:3px;padding-bottom:10px;border-bottom:1px solid var(--border);'
                    'margin-bottom:14px;">⚔️ ANALYSIS ENGINE</div>', unsafe_allow_html=True)
        cat = st.selectbox("فئة الأصل",["الأسهم السعودية 🇸🇦","العملات الرقمية ₿","السلع 🏅","الفوركس 💱","أسواق عالمية 🌍"])
        if cat == "الأسهم السعودية 🇸🇦":
            sector = st.selectbox("القطاع", list(SAUDI_SECTORS.keys()))
            preset = SAUDI_SECTORS[sector]
        elif cat == "العملات الرقمية ₿":
            sector = st.selectbox("الفئة", list(CRYPTO_SECTORS.keys()))
            preset = CRYPTO_SECTORS[sector]
        elif cat == "السلع 🏅": preset = COMMODITIES
        elif cat == "الفوركس 💱": preset = FOREX
        else: preset = GLOBAL_INDICES
        sel = st.selectbox("الأصل", list(preset.keys()))
        default_tkr = preset[sel]
        custom = st.text_input("أو رمز مخصص", placeholder="4030.SR", value="")
        ticker = custom.strip().upper() if custom.strip() else default_tkr
        tf_map = {"15 دقيقة":("5d","15m"),"1 ساعة":("30d","1h"),"4 ساعات":("60d","4h"),
                  "يومي":("1y","1d"),"أسبوعي":("5y","1wk")}
        tf = st.selectbox("الإطار الزمني", list(tf_map.keys()), index=3)
        period, interval = tf_map[tf]
        show_bb = st.toggle("Bollinger Bands", value=True)
        show_macd = st.toggle("MACD", value=True)
        show_fib = st.toggle("Fibonacci", value=False)
        st.markdown('<div class="info-box" style="font-size:.7rem;">⚠️ للأغراض التعليمية فقط</div>',
                    unsafe_allow_html=True)
        analyze_btn = st.button("⚔️ تحليل شامل", type="primary")

    asset_type = ("سهم سعودي" if ".SR" in ticker else "عملة رقمية" if ticker in CRYPTO_SYMBOLS
                  else "سلعة" if "=F" in ticker else "فوركس" if "=X" in ticker else "سهم عالمي")

    if analyze_btn or (st.session_state.analysis_done and st.session_state.current_ticker==ticker):
        with st.spinner(f"جلب {ticker}..."):
            df = get_data(ticker, period, interval)
        if df is None or len(df)<50:
            st.error(f"تعذّر جلب {ticker}")
        else:
            c = df["Close"]; price = float(c.iloc[-1]); prev = float(c.iloc[-2]) if len(c)>1 else price
            chg = (price-prev)/prev*100; hi = float(df["High"].iloc[-1]); lo = float(df["Low"].iloc[-1])
            trend_lbl, _ = get_trend(df); res_lvl, sup_lvl = calc_sr(df); r_now = float(rsi(c).iloc[-1])
            atr_v = float(atr(df["High"],df["Low"],c).iloc[-1])
            # مصدر البيانات الفعلي
            q_check = get_quote(ticker)
            src = q_check.get("source","TRADINGVIEW") if q_check else "TRADINGVIEW"
            src_clr = ("#00D68F" if "BINANCE" in src
                       else "#E8B84B" if "TRADINGVIEW" in src
                       else "#64748B")
            src_icon = "⚡" if "BINANCE" in src else "📡" if "TRADINGVIEW" in src else "⚠️"
            st.markdown(f'<div style="text-align:right;font-family:JetBrains Mono;font-size:.66rem;'
                        f'color:{src_clr};margin-bottom:8px;">{src_icon} {src} — {ticker}</div>',
                        unsafe_allow_html=True)
            # KPIs
            kpi_cols = st.columns(6)
            kpis = [("السعر",f"{price:.4f}","var(--gold)"),("التغير",f"{chg:+.2f}%","var(--green)" if chg>=0 else "var(--red)"),
                    ("الأعلى",f"{hi:.4f}","var(--cyan)"),("الأدنى",f"{lo:.4f}","var(--text)"),
                    ("الاتجاه",trend_lbl,"var(--text)"),
                    ("RSI",f"{r_now:.1f}","var(--red)" if r_now>70 else "var(--green)" if r_now<30 else "var(--gold)")]
            for col,(lbl,val,clr) in zip(kpi_cols,kpis):
                with col:
                    st.markdown(f'<div class="kpi-card"><div class="kpi-label">{lbl}</div>'
                                f'<div class="kpi-value" style="color:{clr};font-size:.95rem;">{val}</div></div>',
                                unsafe_allow_html=True)
            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

            # Chart
            with st.spinner("بناء الشارت..."):
                fig, r_s, ml, sl_s, hist, e20, e50, at, ks, kd, bbu, bbl = build_chart(
                    df, f"{ticker} — {asset_type}", sup_lvl, res_lvl, show_bb, show_macd, show_fib)
            st.plotly_chart(fig, use_container_width=True,
                            config={"displayModeBar":True,"displaylogo":False,
                                    "modeBarButtonsToRemove":["pan2d","select2d","lasso2d"]})

            # Quick decision card
            sl_p = round(price-1.5*atr_v, 4); t1_p = round(price+1.5*atr_v, 4); t2_p = round(price+3*atr_v, 4)
            rr = round((t1_p-price)/max(price-sl_p,.0001), 2)
            e20v = float(e20.iloc[-1]); e50v = float(e50.iloc[-1])
            mv_ = float(ml.iloc[-1]); sv__ = float(sl_s.iloc[-1])
            hr_ = float(hist.iloc[-1])>float(hist.iloc[-2]) if len(hist)>1 else False
            vr_ = float(df["Volume"].iloc[-1]/df["Volume"].tail(20).mean()) if df["Volume"].tail(20).mean()>0 else 1
            conf = int(sum([e20v>e50v, mv_>sv__, 35<r_now<65, hr_, vr_>1])/5*100)
            cc = "var(--green)" if conf>=60 else "var(--red)" if conf<=40 else "var(--gold)"
            st.markdown('<div class="section-title">⚡ القرار السريع</div>', unsafe_allow_html=True)
            qc = st.columns(5)
            for col,(lbl,val,clr) in zip(qc,[
                ("الدخول",f"{price:.4f}","var(--gold)"),("الهدف 1 🎯",f"{t1_p:.4f}","var(--green)"),
                ("الهدف 2 🎯",f"{t2_p:.4f}","#4ADE80"),("وقف الخسارة 🛡️",f"{sl_p:.4f}","var(--red)"),
                ("R:R",f"1:{rr}","var(--cyan)")]):
                with col:
                    st.markdown(f'<div class="kpi-card"><div class="kpi-label">{lbl}</div>'
                                f'<div class="kpi-value" style="color:{clr};font-size:.9rem;">{val}</div></div>',
                                unsafe_allow_html=True)
            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

            # S/R Levels
            st.markdown('<div class="section-title">⚔️ الدعم والمقاومة</div>', unsafe_allow_html=True)
            col_r, col_conf, col_s = st.columns([5,2,5])
            with col_r:
                rows_h = ""
                for rv in sorted([x for x in res_lvl if x>price])[:5]:
                    d = (rv-price)/price*100
                    st_ = "قريب 🔴" if abs(d)<3 else "متوسط 🟠" if abs(d)<7 else "بعيد"
                    rows_h += f'<tr style="background:rgba(255,69,96,.04)"><td style="color:#FF4560;font-weight:700">{rv:.4f}</td><td style="color:var(--muted)">{d:+.2f}%</td><td style="color:var(--muted);font-size:.76rem">{st_}</td></tr>'
                st.markdown(f'<table class="levels-table"><thead><tr><th>🔴 مقاومة</th><th>البُعد</th><th>القوة</th></tr></thead><tbody>{rows_h}</tbody></table>', unsafe_allow_html=True)
            with col_conf:
                cl = "شراء قوي" if conf>=70 else "بيع قوي" if conf<=30 else "محايد" if conf<=55 else "ميل شراء"
                st.markdown(f'<div class="kpi-card" style="padding:14px 8px;"><div class="kpi-label" style="font-size:.56rem;">CONF</div>'
                            f'<div class="kpi-value" style="color:{cc};font-size:1.4rem;">{conf}%</div>'
                            f'<div style="font-size:.66rem;color:{cc};margin:4px 0;">{cl}</div>'
                            f'<div style="height:3px;background:rgba(255,255,255,.06);border-radius:2px;">'
                            f'<div style="width:{conf}%;height:100%;background:{cc};border-radius:2px;"></div></div></div>',
                            unsafe_allow_html=True)
            with col_s:
                rows_h = ""
                for sv in sorted([x for x in sup_lvl if x<price],reverse=True)[:5]:
                    d = (sv-price)/price*100
                    st_ = "قريب 🟢" if abs(d)<3 else "متوسط 🟡" if abs(d)<7 else "بعيد"
                    rows_h += f'<tr style="background:rgba(0,214,143,.04)"><td style="color:#00D68F;font-weight:700">{sv:.4f}</td><td style="color:var(--muted)">{d:+.2f}%</td><td style="color:var(--muted);font-size:.76rem">{st_}</td></tr>'
                st.markdown(f'<table class="levels-table"><thead><tr><th>🟢 دعم</th><th>البُعد</th><th>القوة</th></tr></thead><tbody>{rows_h}</tbody></table>', unsafe_allow_html=True)
            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

            # AI STREAMING
            st.markdown('<div class="section-title">🤖 التحليل الذكي — Streaming</div>', unsafe_allow_html=True)
            if analyze_btn or not st.session_state.analysis_done or st.session_state.current_ticker!=ticker:
                try:
                    client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
                    prompt = build_ai_prompt(ticker, df, r_s, ml, sl_s, hist, e20, e50, at, ks, kd, bbu, bbl,
                                            trend_lbl, res_lvl, sup_lvl, asset_type)
                    ph = st.empty()
                    ph.markdown('<div class="ai-box">⚔️ يحلل المعطيات...</div>', unsafe_allow_html=True)
                    full_text = ""
                    with client.messages.stream(model="claude-opus-4-5", max_tokens=1800,
                                                messages=[{"role":"user","content":prompt}]) as stream:
                        for chunk in stream.text_stream:
                            full_text += chunk
                            ph.markdown(f'<div class="ai-box">{full_text}▋</div>', unsafe_allow_html=True)
                    ph.markdown(f'<div class="ai-box">{full_text}</div>', unsafe_allow_html=True)
                    st.session_state.ai_text = full_text
                    st.session_state.analysis_done = True
                    st.session_state.current_ticker = ticker
                    st.session_state.chat_history = []
                except Exception as e:
                    st.error(f"خطأ AI: {e}")
            else:
                st.markdown(f'<div class="ai-box">{st.session_state.ai_text}</div>', unsafe_allow_html=True)

            # Chat
            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
            st.markdown('<div class="section-title">💬 سؤال المستشار</div>', unsafe_allow_html=True)
            for msg in st.session_state.chat_history:
                style = ('background:rgba(232,184,75,.06);border:1px solid var(--border);border-radius:10px;'
                         'padding:12px 16px;direction:rtl;margin:4px 0;' if msg["role"]=="user"
                         else "")
                icon = "👤" if msg["role"]=="user" else "⚔️"
                cls = "" if msg["role"]=="user" else 'class="ai-box" style="font-size:.88rem;margin:4px 0;"'
                st.markdown(f'<div style="{style}" {cls}>{icon} {msg["content"]}</div>', unsafe_allow_html=True)
            ci, cs2 = st.columns([5,1])
            with ci: uq = st.text_input("سؤالك", placeholder="اسأل المستشار...", label_visibility="collapsed", key="chat_in")
            with cs2:
                st.markdown("<br>", unsafe_allow_html=True)
                sb = st.button("إرسال ⚡")
            if sb and uq.strip():
                st.session_state.chat_history.append({"role":"user","content":uq})
                try:
                    client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
                    msgs = [{"role":"user","content":f"مستشار تداولي. تحليلك: {st.session_state.ai_text[:600]}"}]
                    for m in st.session_state.chat_history[:-1]: msgs.append({"role":m["role"],"content":m["content"]})
                    msgs.append({"role":"user","content":uq})
                    rph = st.empty(); reply = ""
                    with client.messages.stream(model="claude-opus-4-5", max_tokens=500,
                                                system="مستشار تداولي خبير. أجب بإيجاز بالعربية.",
                                                messages=msgs) as stream:
                        for chunk in stream.text_stream:
                            reply += chunk
                            rph.markdown(f'<div class="ai-box" style="font-size:.88rem;">{reply}▋</div>', unsafe_allow_html=True)
                    rph.markdown(f'<div class="ai-box" style="font-size:.88rem;">{reply}</div>', unsafe_allow_html=True)
                    st.session_state.chat_history.append({"role":"assistant","content":reply})
                    st.rerun()
                except Exception as e: st.error(f"خطأ: {e}")
    else:
        st.markdown('<div style="text-align:center;padding:80px 20px;opacity:.5;">'
                    '<div style="font-size:3rem;margin-bottom:14px;">📊</div>'
                    '<div style="font-family:JetBrains Mono;font-size:.8rem;color:var(--gold);letter-spacing:3px;">'
                    'افتح الشريط الجانبي ← اختر الأصل ← تحليل شامل</div></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════
# PAGE: OPPORTUNITIES
# ══════════════════════════════════════════════════

elif st.session_state.page == "opportunities":
    st.markdown('<div class="page-header"><div class="page-header-title">⚡ ماسح الفرص — موازي سريع</div>'
                '<div class="page-header-desc">فحص 81+ أصل بالتوازي · 12 خيط · أسرع 8x من التسلسلي</div></div>',
                unsafe_allow_html=True)
    f1, f2, f3 = st.columns([2,2,1])
    with f1: scan_cats = st.multiselect("الفئات",["أسهم سعودية","عملات رقمية","سلع"],default=["أسهم سعودية","عملات رقمية"])
    with f2: style_f = st.selectbox("نوع الفرصة",["الكل","مضارب ⚡","سويينج 📊","استثماري 💎"])
    with f3:
        st.markdown("<br>", unsafe_allow_html=True)
        scan_btn = st.button("⚡ فحص متوازي", type="primary")
    if scan_btn:
        universe = []
        if "أسهم سعودية" in scan_cats: universe += list(ALL_SAUDI.values())
        if "عملات رقمية" in scan_cats: universe += list(ALL_CRYPTO.values())
        if "سلع" in scan_cats: universe += list(COMMODITIES.values())
        prog_ph = st.empty(); t0 = time.time()
        results = parallel_scan(universe, prog_ph)
        elapsed = time.time()-t0
        prog_ph.empty()
        results.sort(key=lambda x: x["score"], reverse=True)
        st.session_state.opp_cache = results
        st.success(f"✅ فحص {len(results)} أصل في {elapsed:.1f}ث — الماسح المتوازي أسرع بـ 8x!")
    results = st.session_state.opp_cache
    if results:
        if style_f=="مضارب ⚡": results = [r for r in results if r.get("scalp")]
        elif style_f=="سويينج 📊": results = [r for r in results if r.get("swing")]
        elif style_f=="استثماري 💎": results = [r for r in results if r.get("invest")]
        buys = len([r for r in results if r["signal"]=="شراء"])
        sells = len([r for r in results if r["signal"]=="بيع"])
        sc1, sc2, sc3 = st.columns(3)
        for col,(lbl,val,clr) in zip([sc1,sc2,sc3],[
            ("إشارات شراء",buys,"var(--green)"),("إشارات بيع",sells,"var(--red)"),
            ("مراقبة",len(results)-buys-sells,"var(--gold)")]):
            with col:
                st.markdown(f'<div class="kpi-card"><div class="kpi-label">{lbl}</div>'
                            f'<div class="kpi-value" style="color:{clr};">{val}</div></div>',
                            unsafe_allow_html=True)
        st.markdown(f'<div class="section-title">🏆 أفضل الفرص — {min(20,len(results))} من {len(results)}</div>',
                    unsafe_allow_html=True)
        for r in results[:20]:
            sig_css = "sell" if r["signal"]=="بيع" else "watch" if r["signal"]=="مراقبة" else ""
            bdg_cls = "badge-sell" if r["signal"]=="بيع" else "badge-watch" if r["signal"]=="مراقبة" else "badge-buy"
            styles = ""
            if r.get("scalp"): styles += '<span class="badge badge-scalp">⚡ مضارب</span> '
            if r.get("swing"): styles += '<span class="badge badge-swing">📊 سويينج</span> '
            if r.get("invest"): styles += '<span class="badge badge-invest">💎 استثماري</span> '
            near = "🟢 عند دعم" if r.get("near_sup") else "🔴 عند مقاومة" if r.get("near_res") else ""
            chg_c = "var(--green)" if r["change"]>=0 else "var(--red)"
            name = r["ticker"].replace(".SR","").replace("-USD","")
            stars = "●"*r["score"]+"○"*(5-r["score"])
            st.markdown(f'''<div class="opp-card {sig_css}">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:7px;">
                <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                  <span style="font-family:JetBrains Mono;color:var(--gold);font-weight:700;font-size:.9rem;">{name}</span>
                  <span class="badge {bdg_cls}">{r["signal"]}</span>{styles}
                </div>
                <div style="text-align:left;">
                  <div style="font-family:JetBrains Mono;color:var(--text);font-size:.86rem;">{r["price"]:.4f}</div>
                  <div style="color:{chg_c};font-size:.7rem;font-family:JetBrains Mono;">{r["change"]:+.2f}%</div>
                </div>
              </div>
              <div style="display:flex;gap:14px;font-size:.76rem;color:var(--muted);flex-wrap:wrap;">
                <span>RSI <span style="color:var(--text);font-family:JetBrains Mono;">{r["rsi"]:.0f}</span></span>
                <span style="color:var(--gold);font-family:JetBrains Mono;">{stars}</span>
                {'<span style="color:var(--cyan);">⚡ سيولة</span>' if r.get("vol_spike") else ""}
                <span style="color:var(--dim);">{near}</span>
                <span>5أيام <span style="color:{"var(--green)" if r["change5"]>=0 else "var(--red)"};font-family:JetBrains Mono;">{r["change5"]:+.1f}%</span></span>
              </div></div>''', unsafe_allow_html=True)
    else:
        st.markdown('<div class="info-box" style="text-align:center;">اضغط ⚡ فحص متوازي لبدء المسح</div>',
                    unsafe_allow_html=True)

# ══════════════════════════════════════════════════
# PAGE: ALERTS
# ══════════════════════════════════════════════════

elif st.session_state.page == "alerts":
    st.markdown('<div class="page-header"><div class="page-header-title">🔔 نظام المنبهات</div>'
                '<div class="page-header-desc">حدد سعراً مستهدفاً — سيتفعل عند الوصول</div></div>',
                unsafe_allow_html=True)
    with st.expander("➕ منبه جديد", expanded=True):
        a1,a2,a3,a4 = st.columns([2,2,2,1])
        with a1: at_ = st.text_input("الأصل", placeholder="2222.SR أو BTC-USD")
        with a2: ap_ = st.number_input("السعر المستهدف", min_value=0.0, value=0.0, format="%.4f")
        with a3: atype = st.selectbox("النوع",["يصل أو يتجاوز ▲","ينزل إلى ▼"])
        with a4:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("إضافة 🔔"):
                if at_ and ap_>0:
                    st.session_state.alerts.append({"ticker":at_.upper(),"price":ap_,
                        "type":atype,"triggered":False,"created":datetime.now().strftime("%H:%M")})
                    st.success("تم!"); st.rerun()
    if st.session_state.alerts:
        chk = st.button("🔄 فحص المنبهات"); to_del = []
        for i,al in enumerate(st.session_state.alerts):
            if chk:
                q = get_quote(al["ticker"])
                if q:
                    if "يتجاوز" in al["type"] and q["price"]>=al["price"]: al["triggered"]=True
                    elif "ينزل" in al["type"] and q["price"]<=al["price"]: al["triggered"]=True
            sc = "triggered" if al["triggered"] else ""
            si = "✅ تفعّل!" if al["triggered"] else "⏳ انتظار"
            sclr = "var(--green)" if al["triggered"] else "var(--muted)"
            name = al["ticker"].replace(".SR","").replace("-USD","")
            c1,c2 = st.columns([5,1])
            with c1:
                st.markdown(f'<div class="alert-card {sc}">'
                            f'<div><span style="font-family:JetBrains Mono;color:var(--gold);font-weight:700;">{name}</span> '
                            f'<span style="font-family:JetBrains Mono;color:var(--text);">{al["price"]:.4f}</span> '
                            f'<span style="color:var(--muted);font-size:.78rem;">{al["type"]}</span></div>'
                            f'<div style="color:{sclr};font-size:.76rem;font-family:JetBrains Mono;">{si} | {al["created"]}</div></div>',
                            unsafe_allow_html=True)
            with c2:
                if st.button("🗑️", key=f"da_{i}"): to_del.append(i)
        for i in reversed(to_del): st.session_state.alerts.pop(i)
        if to_del: st.rerun()
    else:
        st.markdown('<div class="info-box" style="text-align:center;">لا توجد منبهات — أضف أعلاه</div>',
                    unsafe_allow_html=True)

# ══════════════════════════════════════════════════
# PAGE: PORTFOLIO
# ══════════════════════════════════════════════════

elif st.session_state.page == "portfolio":
    st.markdown('<div class="page-header"><div class="page-header-title">💼 المحفظة الحية</div>'
                '<div class="page-header-desc">تتبع مراكزك المفتوحة · أسعار لحظية · تحذيرات وقف الخسارة</div></div>',
                unsafe_allow_html=True)
    with st.expander("➕ إضافة مركز", expanded=not bool(st.session_state.portfolio)):
        p1,p2,p3,p4,p5 = st.columns(5)
        with p1: pt = st.text_input("الأصل", placeholder="2222.SR")
        with p2: pq = st.number_input("الكمية", min_value=0.0, value=1.0, format="%.4f")
        with p3: pp = st.number_input("سعر الدخول", min_value=0.0, value=0.0, format="%.4f")
        with p4: psl = st.number_input("وقف الخسارة", min_value=0.0, value=0.0, format="%.4f")
        with p5:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("إضافة 💼"):
                if pt and pp>0:
                    st.session_state.portfolio.append({"ticker":pt.upper(),"qty":pq,
                        "entry":pp,"sl":psl,"date":datetime.now().strftime("%Y-%m-%d")})
                    st.success("تمت الإضافة!"); st.rerun()
    if st.session_state.portfolio:
        total_inv = 0; total_pnl = 0; to_del = []
        for i,pos in enumerate(st.session_state.portfolio):
            q = get_quote(pos["ticker"]); curr = q["price"] if q else pos["entry"]
            pnl = (curr-pos["entry"])*pos["qty"]; pnl_pct = (curr-pos["entry"])/pos["entry"]*100
            value = curr*pos["qty"]; inv = pos["entry"]*pos["qty"]
            total_inv += inv; total_pnl += pnl
            pclr = "var(--green)" if pnl>=0 else "var(--red)"
            danger = pos["sl"]>0 and curr<pos["sl"]
            name = pos["ticker"].replace(".SR","").replace("-USD","")
            c1,c2 = st.columns([5,1])
            with c1:
                st.markdown(f'<div class="portfolio-card {"danger" if danger else ""}">'
                            f'<div style="display:flex;justify-content:space-between;margin-bottom:7px;">'
                            f'<span style="font-family:JetBrains Mono;color:var(--gold);font-weight:700;">{name}</span>'
                            f'{"<span style=\"color:var(--red);font-size:.73rem;\">⚠️ تحت وقف الخسارة</span>" if danger else ""}'
                            f'<span style="font-family:JetBrains Mono;color:{pclr};font-weight:700;">{pnl:+,.2f} ({pnl_pct:+.2f}%)</span></div>'
                            f'<div style="display:flex;gap:18px;font-size:.76rem;color:var(--muted);flex-wrap:wrap;">'
                            f'<span>الدخول <span style="color:var(--text);font-family:JetBrains Mono;">{pos["entry"]:.4f}</span></span>'
                            f'<span>الحالي <span style="color:var(--gold);font-family:JetBrains Mono;">{curr:.4f}</span></span>'
                            f'<span>الكمية <span style="color:var(--text);">{pos["qty"]}</span></span>'
                            f'<span>القيمة <span style="color:var(--text);font-family:JetBrains Mono;">{value:,.2f}</span></span>'
                            f'{"<span>وقف <span style=\"color:var(--red);font-family:JetBrains Mono;\">"+str(pos["sl"])+"</span></span>" if pos["sl"]>0 else ""}'
                            f'</div></div>', unsafe_allow_html=True)
            with c2:
                if st.button("🗑️", key=f"dp_{i}"): to_del.append(i)
        for i in reversed(to_del): st.session_state.portfolio.pop(i)
        if to_del: st.rerun()
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        s1,s2,s3 = st.columns(3)
        for col,(lbl,val,clr) in zip([s1,s2,s3],[
            ("إجمالي الاستثمار",f"{total_inv:,.2f}","var(--gold)"),
            ("الربح / الخسارة",f"{total_pnl:+,.2f}","var(--green)" if total_pnl>=0 else "var(--red)"),
            ("العائد",f"{(total_pnl/total_inv*100) if total_inv>0 else 0:+.2f}%","var(--green)" if total_pnl>=0 else "var(--red)")]):
            with col:
                st.markdown(f'<div class="kpi-card"><div class="kpi-label">{lbl}</div>'
                            f'<div class="kpi-value" style="color:{clr};font-size:1rem;">{val}</div></div>',
                            unsafe_allow_html=True)
    else:
        st.markdown('<div class="info-box" style="text-align:center;">المحفظة فارغة — أضف مراكزك أعلاه</div>',
                    unsafe_allow_html=True)

# ══════════════════════════════════════════════════
# PAGE: JOURNAL ★ NEW ★
# ══════════════════════════════════════════════════

elif st.session_state.page == "journal":
    st.markdown('<div class="page-header"><div class="page-header-title">📔 سجل الصفقات</div>'
                '<div class="page-header-desc">تتبع كل صفقة · إحصائيات الأداء · منحنى رأس المال · تحليل نقاط الضعف</div></div>',
                unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["➕ صفقة جديدة", "📋 السجل الكامل", "📊 إحصائيات الأداء"])

    with tab1:
        st.markdown('<div class="section-title">تسجيل صفقة</div>', unsafe_allow_html=True)
        c1,c2,c3 = st.columns(3)
        with c1:
            j_ticker = st.text_input("الأصل", placeholder="AAPL, BTC-USD, 2222.SR")
            j_type = st.selectbox("نوع الصفقة", ["شراء LONG","بيع SHORT"])
            j_style = st.selectbox("أسلوب التداول", ["مضاربة","سويينج","استثمار"])
        with c2:
            j_entry = st.number_input("سعر الدخول", min_value=0.0, format="%.4f")
            j_exit = st.number_input("سعر الخروج (0 = مفتوحة)", min_value=0.0, format="%.4f")
            j_qty = st.number_input("الكمية", min_value=0.0, value=1.0, format="%.4f")
        with c3:
            j_sl = st.number_input("وقف الخسارة", min_value=0.0, format="%.4f")
            j_tp = st.number_input("هدف الربح", min_value=0.0, format="%.4f")
            j_date = st.date_input("تاريخ الدخول", value=date.today())
        j_notes = st.text_area("ملاحظات الصفقة", placeholder="سبب الدخول، الإعداد الفني، الدروس المستفادة...", height=80)
        j_emotion = st.select_slider("الحالة النفسية عند الدخول",
            options=["خوف شديد","خوف","محايد","ثقة","ثقة زائدة"], value="محايد")
        if st.button("💾 حفظ الصفقة", type="primary"):
            if j_ticker and j_entry>0:
                pnl = 0.0; pnl_pct = 0.0; status = "مفتوحة"
                rr_actual = 0.0
                if j_exit>0:
                    if "LONG" in j_type:
                        pnl = (j_exit-j_entry)*j_qty
                        pnl_pct = (j_exit-j_entry)/j_entry*100
                    else:
                        pnl = (j_entry-j_exit)*j_qty
                        pnl_pct = (j_entry-j_exit)/j_entry*100
                    status = "مغلقة"
                    if j_sl>0:
                        risk = abs(j_entry-j_sl)
                        reward = abs(j_exit-j_entry)
                        rr_actual = round(reward/risk, 2) if risk>0 else 0
                trade = {
                    "id": len(st.session_state.trades)+1,
                    "ticker": j_ticker.upper(), "type": j_type, "style": j_style,
                    "entry": j_entry, "exit": j_exit if j_exit>0 else None,
                    "qty": j_qty, "sl": j_sl, "tp": j_tp,
                    "pnl": round(pnl,4), "pnl_pct": round(pnl_pct,2),
                    "rr": rr_actual, "status": status, "date": str(j_date),
                    "notes": j_notes, "emotion": j_emotion,
                    "created": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
                st.session_state.trades.append(trade)
                st.success(f"✅ صفقة {j_ticker.upper()} تم حفظها! | الحالة: {status} | PnL: {pnl:+.2f}")
                st.rerun()
            else:
                st.error("أدخل الأصل وسعر الدخول")

    with tab2:
        st.markdown('<div class="section-title">📋 سجل الصفقات</div>', unsafe_allow_html=True)
        if not st.session_state.trades:
            st.markdown('<div class="info-box" style="text-align:center;">لا يوجد سجل — أضف صفقاتك في التبويب الأول</div>', unsafe_allow_html=True)
        else:
            # Filters
            ff1,ff2,ff3 = st.columns(3)
            with ff1: fstatus = st.selectbox("الحالة",["الكل","مفتوحة","مغلقة"],key="fstatus")
            with ff2: fstyle = st.selectbox("الأسلوب",["الكل","مضاربة","سويينج","استثمار"],key="fstyle")
            with ff3: fresult = st.selectbox("النتيجة",["الكل","رابحة","خاسرة"],key="fresult")
            trades_to_show = st.session_state.trades.copy()
            if fstatus!="الكل": trades_to_show = [t for t in trades_to_show if t["status"]==fstatus]
            if fstyle!="الكل": trades_to_show = [t for t in trades_to_show if t["style"]==fstyle]
            if fresult=="رابحة": trades_to_show = [t for t in trades_to_show if t.get("pnl",0)>0]
            elif fresult=="خاسرة": trades_to_show = [t for t in trades_to_show if t.get("pnl",0)<=0 and t["status"]=="مغلقة"]
            for idx,t in enumerate(reversed(trades_to_show)):
                status_cls = "open-trade" if t["status"]=="مفتوحة" else ("win" if t.get("pnl",0)>0 else "loss")
                pclr = "var(--green)" if t.get("pnl",0)>0 else "var(--red)" if t.get("pnl",0)<0 else "var(--muted)"
                bdg = ('badge-buy" style="background:rgba(59,130,246,.12);color:#93C5FD;border-color:rgba(59,130,246,.25)' if t["status"]=="مفتوحة"
                       else "badge-buy" if t.get("pnl",0)>0 else "badge-sell")
                pnl_display = f'{t["pnl"]:+.2f} ({t["pnl_pct"]:+.2f}%)' if t["status"]=="مغلقة" else "مفتوحة"
                rr_display = f'R:R {t["rr"]}' if t.get("rr") and t["rr"]>0 else ""
                c1,c2 = st.columns([6,1])
                with c1:
                    st.markdown(f'''<div class="trade-row {status_cls}">
                      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                          <span style="font-family:JetBrains Mono;color:var(--gold);font-weight:700;">{t["ticker"]}</span>
                          <span class="badge badge-swing" style="font-size:.62rem;">{t["style"]}</span>
                          <span style="color:var(--muted);font-size:.75rem;">{t["date"]}</span>
                          <span style="color:var(--muted);font-size:.72rem;">{t["emotion"]}</span>
                        </div>
                        <span style="font-family:JetBrains Mono;color:{pclr};font-weight:700;">{pnl_display}</span>
                      </div>
                      <div style="display:flex;gap:16px;font-size:.75rem;color:var(--muted);flex-wrap:wrap;">
                        <span>دخول <span style="color:var(--text);font-family:JetBrains Mono;">{t["entry"]:.4f}</span></span>
                        {f'<span>خروج <span style="color:var(--text);font-family:JetBrains Mono;">{t["exit"]:.4f}</span></span>' if t["exit"] else ""}
                        <span>ك {t["qty"]}</span>
                        {f'<span style="color:var(--cyan);">{rr_display}</span>' if rr_display else ""}
                        {f'<span style="color:var(--muted);font-size:.72rem;max-width:300px;overflow:hidden;text-overflow:ellipsis;">{t["notes"][:60]}...</span>' if t.get("notes") else ""}
                      </div></div>''', unsafe_allow_html=True)
                with c2:
                    orig_idx = st.session_state.trades.index(t) if t in st.session_state.trades else -1
                    if st.button("🗑️", key=f"del_trade_{orig_idx}_{idx}") and orig_idx>=0:
                        st.session_state.trades.pop(orig_idx); st.rerun()

    with tab3:
        st.markdown('<div class="section-title">📊 إحصائيات الأداء</div>', unsafe_allow_html=True)
        stats = calc_trade_stats(st.session_state.trades)
        if not stats or stats.get("total",0)==0:
            st.markdown('<div class="info-box" style="text-align:center;">لا يوجد بيانات كافية — أضف وأغلق بعض الصفقات</div>', unsafe_allow_html=True)
        else:
            s1,s2,s3,s4 = st.columns(4)
            for col,(lbl,val,clr) in zip([s1,s2,s3,s4],[
                ("إجمالي الصفقات",stats.get("total",0),"var(--gold)"),
                ("معدل الربح",f'{stats.get("win_rate",0):.1f}%',"var(--green)" if stats.get("win_rate",0)>=50 else "var(--red)"),
                ("PnL الكلي",f'{stats.get("total_pnl",0):+.2f}',"var(--green)" if stats.get("total_pnl",0)>=0 else "var(--red)"),
                ("Profit Factor",f'{stats.get("profit_factor",0):.2f}',"var(--green)" if stats.get("profit_factor",0)>=1.5 else "var(--red)"),
            ]):
                with col:
                    st.markdown(f'<div class="stat-box"><div class="stat-number" style="color:{clr};">{val}</div>'
                                f'<div class="stat-label">{lbl}</div></div>', unsafe_allow_html=True)
            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

            s5,s6,s7,s8 = st.columns(4)
            for col,(lbl,val,clr) in zip([s5,s6,s7,s8],[
                ("مغلقة",stats.get("closed",0),"var(--text)"),
                ("رابحة ✅",stats.get("wins",0),"var(--green)"),
                ("خاسرة ❌",stats.get("losses",0),"var(--red)"),
                ("مفتوحة",stats.get("open",0),"var(--blue)"),
            ]):
                with col:
                    st.markdown(f'<div class="stat-box"><div class="stat-number" style="color:{clr};font-size:1.4rem;">{val}</div>'
                                f'<div class="stat-label">{lbl}</div></div>', unsafe_allow_html=True)

            # Equity curve
            closed_trades = [t for t in st.session_state.trades if t.get("status")=="مغلقة"]
            if len(closed_trades)>=2:
                st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
                st.markdown('<div class="section-title">📈 منحنى رأس المال</div>', unsafe_allow_html=True)
                equity = 10000.0; eq_vals = [equity]
                for t in closed_trades:
                    equity += t.get("pnl",0); eq_vals.append(equity)
                eq_fig = go.Figure()
                eq_fig.add_trace(go.Scatter(
                    y=eq_vals, mode="lines+markers",
                    line=dict(color="#E8B84B", width=2.5),
                    marker=dict(color=["#00D68F" if eq_vals[i]>=eq_vals[i-1] else "#FF4560"
                                       for i in range(len(eq_vals))], size=7),
                    fill="tozeroy", fillcolor="rgba(232,184,75,0.05)", name="رأس المال"))
                eq_fig.update_layout(template="plotly_dark", plot_bgcolor="#070B12", paper_bgcolor="#0C1220",
                    height=280, margin=dict(l=0,r=0,t=10,b=0), showlegend=False,
                    font=dict(family="JetBrains Mono", color="#94A3B8", size=10))
                eq_fig.update_xaxes(gridcolor="rgba(99,130,190,.06)")
                eq_fig.update_yaxes(gridcolor="rgba(99,130,190,.06)")
                st.plotly_chart(eq_fig, use_container_width=True, config={"displayModeBar":False})

            # Emotion analysis
            if closed_trades:
                st.markdown('<div class="section-title">🧠 تحليل الحالة النفسية</div>', unsafe_allow_html=True)
                emotions = {}
                for t in closed_trades:
                    em = t.get("emotion","محايد")
                    if em not in emotions: emotions[em] = {"count":0,"total_pnl":0}
                    emotions[em]["count"] += 1; emotions[em]["total_pnl"] += t.get("pnl",0)
                em_cols = st.columns(len(emotions))
                for col,(em,data) in zip(em_cols,emotions.items()):
                    avg = data["total_pnl"]/data["count"] if data["count"]>0 else 0
                    clr = "var(--green)" if avg>0 else "var(--red)"
                    with col:
                        st.markdown(f'<div class="stat-box"><div class="stat-number" style="color:{clr};font-size:1.1rem;">{avg:+.1f}</div>'
                                    f'<div class="stat-label">{em}</div>'
                                    f'<div style="color:var(--muted);font-size:.65rem;margin-top:2px;">{data["count"]} صفقة</div></div>',
                                    unsafe_allow_html=True)
                st.markdown('<div class="info-box">💡 الحالة النفسية التي تنتج أفضل نتائج هي الأساس لتطوير أداءك</div>',
                            unsafe_allow_html=True)

# ══════════════════════════════════════════════════
# PAGE: WATCHLIST
# ══════════════════════════════════════════════════

elif st.session_state.page == "watchlist":
    st.markdown('<div class="page-header"><div class="page-header-title">📈 قائمة المراقبة</div>'
                '<div class="page-header-desc">أسعار لحظية لقائمتك · أضف أي رمز من أي سوق</div></div>',
                unsafe_allow_html=True)
    wa, wb = st.columns([3,1])
    with wa: new_tkr = st.text_input("رمز للإضافة", placeholder="4030.SR أو ETH-USD أو NVDA")
    with wb:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("إضافة ➕") and new_tkr.strip():
            tkr_up = new_tkr.strip().upper()
            if tkr_up not in st.session_state.watchlist:
                st.session_state.watchlist.append(tkr_up)
                st.rerun()
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px;">',
                unsafe_allow_html=True)
    to_del = []
    for i, tkr in enumerate(st.session_state.watchlist):
        q = get_quote(tkr)
        name = tkr.replace(".SR","").replace("-USD","").replace("=X","").replace("=F","").replace("^","")
        if q:
            clr = "var(--green)" if q["change"]>=0 else "var(--red)"
            sym = "▲" if q["change"]>=0 else "▼"
            c1,c2 = st.columns([4,1])
            with c1:
                st.markdown(f'<div class="wl-row">'
                            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                            f'<span style="font-family:JetBrains Mono;color:var(--gold);font-weight:700;">{name}</span>'
                            f'<span style="font-family:JetBrains Mono;color:{clr};font-size:.88rem;">{sym} {q["change"]:+.2f}%</span></div>'
                            f'<div style="display:flex;justify-content:space-between;margin-top:5px;">'
                            f'<span style="font-family:JetBrains Mono;color:var(--text);font-size:.9rem;">{q["price"]:,.4f}</span>'
                            f'<span style="color:var(--muted);font-size:.7rem;">{tkr}</span></div></div>',
                            unsafe_allow_html=True)
            with c2:
                if st.button("✕", key=f"wl_del_{i}"): to_del.append(i)
        else:
            c1,c2 = st.columns([4,1])
            with c1:
                st.markdown(f'<div class="wl-row"><span style="font-family:JetBrains Mono;color:var(--muted);">{name}</span>'
                            f'<span style="color:var(--muted);font-size:.75rem;display:block;">جاري الجلب...</span></div>',
                            unsafe_allow_html=True)
            with c2:
                if st.button("✕", key=f"wl_del_{i}"): to_del.append(i)
    st.markdown('</div>', unsafe_allow_html=True)
    for i in reversed(to_del): st.session_state.watchlist.pop(i)
    if to_del: st.rerun()

# ══════════════════════════════════════════════════
# PAGE: REFERENCE
# ══════════════════════════════════════════════════

elif st.session_state.page == "reference":
    st.markdown('<div class="page-header"><div class="page-header-title">📚 المرجع التقني</div>'
                '<div class="page-header-desc">شرح المؤشرات وقراءتها · استراتيجيات التداول · نسب المخاطرة</div></div>',
                unsafe_allow_html=True)
    ref_items = [
        ("RSI — مؤشر القوة النسبية",
         "يقيس قوة الحركة. فوق 70 = تشبع شراء (احتمال هبوط). تحت 30 = تشبع بيع (احتمال صعود). "
         "أهم من القيمة المطلقة: التباين مع السعر. التباين الصاعد (RSI يصعد والسعر يهبط) = إشارة انعكاس قوية."),
        ("MACD — المتوسط المتحرك المتقارب/المتباعد",
         "فرق بين EMA12 و EMA26. التقاطع الصاعد (MACD يعبر فوق Signal) = إشارة شراء. "
         "الهيستوغرام يُظهر قوة الزخم. إذا كان الهيستوغرام يتقلص = الزخم يضعف."),
        ("Bollinger Bands — نطاقات بولينجر",
         "3 خطوط: الوسط (SMA20) + الحد العلوي والسفلي (±2 انحراف معياري). "
         "انكماش النطاق = طاقة متراكمة = تحرك وشيك. السعر عند الحد السفلي مع RSI منخفض = فرصة شراء محتملة."),
        ("EMA — المتوسطات المتحركة الأسية",
         "EMA20: اتجاه قصير. EMA50: اتجاه متوسط. EMA200: الاتجاه الكبير. "
         "Golden Cross (EMA20 فوق EMA50) = إشارة شراء كبرى. Death Cross = إشارة بيع. "
         "السعر فوق EMA200 = سوق صاعد عموماً."),
        ("نسبة العائد/المخاطرة R:R",
         "الأساس الذهبي: R:R لا تقل عن 1:2 (تخاطر 1 لتربح 2). "
         "مع معدل ربح 50% ونسبة R:R 1:2 ستكون رابحاً دائماً. "
         "الوقف على أقرب دعم/مقاومة. الهدف عند المستوى التالي الطبيعي."),
        ("حجم التداول Volume",
         "الحجم يؤكد الحركة. صعود مع حجم عالٍ = قوي وموثوق. "
         "صعود مع حجم منخفض = ضعيف وغير موثوق. "
         "حجم عالٍ عند الدعم = مشترون حقيقيون. حجم عالٍ عند المقاومة = بائعون حقيقيون."),
    ]
    for title, content in ref_items:
        with st.expander(f"📖 {title}"):
            st.markdown(f'<div class="ai-box" style="font-size:.88rem;line-height:1.9;">{content}</div>',
                        unsafe_allow_html=True)
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🏛️ رموز مرجعية سريعة</div>', unsafe_allow_html=True)
    ref_cats = {
        "🇸🇦 سعودية رئيسية": {"أرامكو":"2222.SR","الراجحي":"1120.SR","معادن":"1211.SR","stc":"7010.SR"},
        "₿ كريبتو رئيسية": {"BTC":"BTC-USD","ETH":"ETH-USD","SOL":"SOL-USD","XRP":"XRP-USD"},
        "🌍 عالمية": {"S&P500":"^GSPC","NVDA":"NVDA","AAPL":"AAPL","TSLA":"TSLA"},
        "🏅 سلع": {"ذهب":"GC=F","نفط":"CL=F","فضة":"SI=F"},
    }
    for cat_name, items in ref_cats.items():
        st.markdown(f'<div style="font-family:JetBrains Mono;font-size:.65rem;color:var(--muted);'
                    f'letter-spacing:2px;margin:12px 0 6px;">{cat_name}</div>', unsafe_allow_html=True)
        rc = st.columns(len(items))
        for col,(name,tkr) in zip(rc,items.items()):
            with col:
                st.markdown(f'<div class="kpi-card" style="padding:10px;cursor:pointer;">'
                            f'<div class="kpi-label" style="font-size:.6rem;">{name}</div>'
                            f'<div style="font-family:JetBrains Mono;color:var(--gold);font-size:.72rem;margin-top:4px;">{tkr}</div>'
                            f'</div>', unsafe_allow_html=True)
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="info-box">⚠️ <strong>تنبيه مهم:</strong> هذا التطبيق للأغراض التعليمية والبحثية فقط. '
                'لا يُعدّ نصيحة مالية أو توصية استثمارية. التداول ينطوي على مخاطر عالية وقد تخسر رأس مالك. '
                'استشر مستشاراً مالياً مرخصاً قبل اتخاذ أي قرار استثماري.</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════
# PAGE: GITHUB — رفع وتحميل مباشر
# ══════════════════════════════════════════════════

elif st.session_state.page == "github":
    st.markdown("""
    <div class="page-header">
      <div class="page-header-title">🐙 GitHub — ربط المستودع</div>
      <div class="page-header-desc">
        رفع الملفات · تحميلها · عرض المحتوى · كل شيء مباشرة من TradingView Sovereign
      </div>
    </div>""", unsafe_allow_html=True)

    # ── إعدادات الاتصال ──
    REPO = "shiic0/sovereign-trader"

    with st.expander("⚙️ إعدادات الاتصال", expanded=True):
        gh_token = st.text_input(
            "GitHub Token",
            value=st.session_state.get("gh_token", ""),
            type="password",
            placeholder="ghp_xxxxxxxxxxxxxxxxxxxx",
            help="Personal Access Token بصلاحيات repo"
        )
        gh_branch = st.text_input("الـ Branch", value="main", placeholder="main")
        if st.button("🔌 اختبار الاتصال", type="primary"):
            if not gh_token:
                st.error("أدخل الـ Token أولاً")
            else:
                with st.spinner("جاري الاتصال بـ GitHub..."):
                    try:
                        r = requests.get(
                            f"https://api.github.com/repos/{REPO}",
                            headers={"Authorization": f"token {gh_token}",
                                     "Accept": "application/vnd.github.v3+json"},
                            timeout=10
                        )
                        if r.status_code == 200:
                            info = r.json()
                            st.session_state["gh_token"] = gh_token
                            st.session_state["gh_branch"] = gh_branch
                            st.success(f"✅ متصل! الـ Repo: **{info['full_name']}** | "
                                       f"⭐ {info.get('stargazers_count',0)} | "
                                       f"🍴 {info.get('forks_count',0)}")
                        elif r.status_code == 401:
                            st.error("❌ Token غير صحيح أو منتهي الصلاحية")
                        elif r.status_code == 404:
                            st.error("❌ الـ Repo غير موجود أو خاص")
                        else:
                            st.error(f"❌ خطأ {r.status_code}: {r.text[:200]}")
                    except requests.exceptions.ConnectionError:
                        st.error("❌ لا يوجد اتصال بالإنترنت — تأكد من تشغيل التطبيق على جهازك")
                    except Exception as e:
                        st.error(f"❌ {e}")

    token = st.session_state.get("gh_token", "")
    branch = st.session_state.get("gh_branch", "main")
    gh_headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    if not token:
        st.markdown('<div class="info-box">🔑 أدخل الـ Token أعلاه لتفعيل جميع الوظائف</div>',
                    unsafe_allow_html=True)
    else:
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        tab_up, tab_down, tab_browse, tab_commits = st.tabs([
            "⬆️ رفع ملف", "⬇️ تحميل ملف", "📁 تصفح الملفات", "📜 سجل التعديلات"
        ])

        # ════════════════════
        # TAB 1 — رفع ملف
        # ════════════════════
        with tab_up:
            st.markdown('<div class="section-title">⬆️ رفع ملف إلى GitHub</div>',
                        unsafe_allow_html=True)

            up_mode = st.radio("اختر مصدر الرفع",
                               ["رفع الـ app.py الحالي", "رفع ملف من جهازك"],
                               horizontal=True)

            if up_mode == "رفع الـ app.py الحالي":
                st.markdown('<div class="info-box">سيتم رفع نسخة app.py الحالية مباشرة إلى المستودع</div>',
                            unsafe_allow_html=True)
                up_path = st.text_input("مسار الملف في الـ Repo", value="app.py")
                up_msg  = st.text_input("رسالة الـ Commit",
                                        value=f"update: app.py via Sovereign Trader — {datetime.now().strftime('%Y-%m-%d %H:%M')}")

                if st.button("🚀 رفع الآن", type="primary", key="push_app"):
                    try:
                        import base64, json as _json

                        # قراءة الملف الحالي
                        with open(__file__, "rb") as f:
                            file_bytes = f.read()
                        file_b64 = base64.b64encode(file_bytes).decode()

                        # هل الملف موجود مسبقاً؟ (نحتاج SHA للتحديث)
                        check = requests.get(
                            f"https://api.github.com/repos/{REPO}/contents/{up_path}",
                            headers=gh_headers, params={"ref": branch}, timeout=10)

                        payload = {
                            "message": up_msg,
                            "content": file_b64,
                            "branch":  branch,
                        }
                        if check.status_code == 200:
                            payload["sha"] = check.json()["sha"]
                            action = "تحديث"
                        else:
                            action = "إنشاء"

                        with st.spinner(f"جاري {action} الملف..."):
                            resp = requests.put(
                                f"https://api.github.com/repos/{REPO}/contents/{up_path}",
                                headers=gh_headers,
                                data=_json.dumps(payload),
                                timeout=30
                            )

                        if resp.status_code in (200, 201):
                            commit_url = resp.json().get("commit",{}).get("html_url","")
                            st.success(f"✅ تم الرفع بنجاح! [{action}]")
                            if commit_url:
                                st.markdown(f'<a href="{commit_url}" target="_blank" '
                                            f'style="color:var(--gold);font-family:JetBrains Mono;font-size:.8rem;">'
                                            f'🔗 عرض الـ Commit</a>', unsafe_allow_html=True)
                        else:
                            st.error(f"❌ فشل الرفع — {resp.status_code}: {resp.text[:300]}")

                    except FileNotFoundError:
                        st.error("❌ تعذّر قراءة الملف الحالي")
                    except requests.exceptions.ConnectionError:
                        st.error("❌ لا يوجد اتصال بالإنترنت")
                    except Exception as e:
                        st.error(f"❌ {e}")

            else:  # رفع من الجهاز
                uploaded = st.file_uploader("اختر ملفاً من جهازك",
                                            type=["py","txt","md","json","csv","toml","yaml","yml"])
                if uploaded:
                    up_path2 = st.text_input("مسار الحفظ في الـ Repo",
                                             value=uploaded.name)
                    up_msg2  = st.text_input("رسالة الـ Commit",
                                             value=f"upload: {uploaded.name} — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                                             key="commit_msg2")

                    col_prev, col_up = st.columns([3,1])
                    with col_prev:
                        with st.expander("👁 معاينة الملف"):
                            try:
                                st.code(uploaded.read().decode("utf-8")[:3000], language="python")
                                uploaded.seek(0)
                            except Exception:
                                st.info("ملف بياني — لا يمكن المعاينة")

                    with col_up:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("🚀 رفع", type="primary", key="push_upload"):
                            try:
                                import base64, json as _json
                                file_b64 = base64.b64encode(uploaded.read()).decode()
                                check = requests.get(
                                    f"https://api.github.com/repos/{REPO}/contents/{up_path2}",
                                    headers=gh_headers, params={"ref": branch}, timeout=10)
                                payload = {"message":up_msg2,"content":file_b64,"branch":branch}
                                if check.status_code == 200:
                                    payload["sha"] = check.json()["sha"]
                                with st.spinner("جاري الرفع..."):
                                    resp = requests.put(
                                        f"https://api.github.com/repos/{REPO}/contents/{up_path2}",
                                        headers=gh_headers, data=_json.dumps(payload), timeout=30)
                                if resp.status_code in (200,201):
                                    st.success("✅ تم الرفع!")
                                else:
                                    st.error(f"❌ {resp.status_code}: {resp.text[:200]}")
                            except Exception as e:
                                st.error(f"❌ {e}")

        # ════════════════════
        # TAB 2 — تحميل ملف
        # ════════════════════
        with tab_down:
            st.markdown('<div class="section-title">⬇️ تحميل ملف من GitHub</div>',
                        unsafe_allow_html=True)

            dl_path = st.text_input("مسار الملف في الـ Repo", value="app.py", key="dl_path")

            if st.button("📥 جلب الملف", type="primary"):
                with st.spinner("جاري الجلب..."):
                    try:
                        import base64
                        r = requests.get(
                            f"https://api.github.com/repos/{REPO}/contents/{dl_path}",
                            headers=gh_headers, params={"ref": branch}, timeout=15)

                        if r.status_code == 200:
                            data = r.json()
                            content_b64 = data.get("content","")
                            content_bytes = base64.b64decode(content_b64)
                            st.session_state["dl_content"] = content_bytes
                            st.session_state["dl_name"]    = data["name"]
                            st.session_state["dl_sha"]     = data["sha"]
                            st.session_state["dl_size"]    = data["size"]
                            st.success(f"✅ تم الجلب! الحجم: {data['size']:,} byte | SHA: {data['sha'][:8]}")
                        elif r.status_code == 404:
                            st.error("❌ الملف غير موجود في الـ Repo")
                        else:
                            st.error(f"❌ {r.status_code}: {r.text[:200]}")
                    except Exception as e:
                        st.error(f"❌ {e}")

            if st.session_state.get("dl_content"):
                content_bytes = st.session_state["dl_content"]
                file_name     = st.session_state.get("dl_name","file")

                # عرض المحتوى
                try:
                    text = content_bytes.decode("utf-8")
                    with st.expander(f"👁 معاينة: {file_name} ({len(text):,} حرف)"):
                        st.code(text[:5000], language="python")
                        if len(text) > 5000:
                            st.info(f"يُعرض أول 5000 حرف من {len(text):,}")
                except Exception:
                    st.info("ملف بياني")

                # زر التحميل
                st.download_button(
                    label=f"💾 حفظ {file_name} على جهازك",
                    data=content_bytes,
                    file_name=file_name,
                    mime="text/plain" if file_name.endswith(".py") else "application/octet-stream",
                    type="primary"
                )

                # استبدال الـ app.py الحالي
                if file_name.endswith(".py"):
                    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
                    if st.button("🔄 استبدال app.py الحالي بهذه النسخة", type="secondary"):
                        try:
                            with open(__file__, "wb") as f:
                                f.write(content_bytes)
                            st.success("✅ تم الاستبدال! أعد تشغيل التطبيق لتفعيل التغييرات.")
                            st.info("شغّل: `streamlit run app.py`")
                        except Exception as e:
                            st.error(f"❌ {e}")

        # ════════════════════
        # TAB 3 — تصفح الملفات
        # ════════════════════
        with tab_browse:
            st.markdown('<div class="section-title">📁 تصفح الـ Repository</div>',
                        unsafe_allow_html=True)

            browse_path = st.text_input("المسار (اتركه فارغاً للجذر)", value="", key="browse_path")

            if st.button("🔍 تصفح", key="browse_btn") or True:
                try:
                    url_path = f"https://api.github.com/repos/{REPO}/contents/{browse_path}"
                    r = requests.get(url_path, headers=gh_headers,
                                     params={"ref": branch}, timeout=10)
                    if r.status_code == 200:
                        items = r.json()
                        if isinstance(items, list):
                            files   = [i for i in items if i["type"]=="file"]
                            folders = [i for i in items if i["type"]=="dir"]

                            # مجلدات
                            if folders:
                                st.markdown('<div style="color:var(--cyan);font-family:JetBrains Mono;'
                                            'font-size:.72rem;letter-spacing:2px;margin-bottom:8px;">📂 مجلدات</div>',
                                            unsafe_allow_html=True)
                                for folder in folders:
                                    st.markdown(f'<div class="wl-row">'
                                                f'<span style="color:var(--cyan);">📂</span> '
                                                f'<span style="font-family:JetBrains Mono;color:var(--text);">'
                                                f'{folder["name"]}</span></div>',
                                                unsafe_allow_html=True)

                            # ملفات
                            if files:
                                st.markdown('<div style="color:var(--gold);font-family:JetBrains Mono;'
                                            'font-size:.72rem;letter-spacing:2px;margin:12px 0 8px;">📄 ملفات</div>',
                                            unsafe_allow_html=True)
                                for file in files:
                                    size_kb = file["size"] / 1024
                                    ext = file["name"].split(".")[-1] if "." in file["name"] else ""
                                    ext_clr = {"py":"#8B5CF6","md":"#06B6D4","json":"#F59E0B",
                                               "txt":"#94A3B8","csv":"#00D68F"}.get(ext,"#64748B")
                                    c1, c2 = st.columns([5,1])
                                    with c1:
                                        st.markdown(
                                            f'<div class="wl-row" style="cursor:pointer;">'
                                            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                                            f'<span><span style="font-family:JetBrains Mono;color:{ext_clr};'
                                            f'font-size:.7rem;border:1px solid {ext_clr};padding:1px 6px;'
                                            f'border-radius:3px;margin-left:8px;">.{ext}</span>'
                                            f'<span style="font-family:JetBrains Mono;color:var(--text);">'
                                            f'{file["name"]}</span></span>'
                                            f'<span style="font-family:JetBrains Mono;color:var(--muted);'
                                            f'font-size:.72rem;">{size_kb:.1f} KB</span>'
                                            f'</div></div>', unsafe_allow_html=True)
                                    with c2:
                                        if st.button("⬇️", key=f"dl_browse_{file['sha'][:8]}",
                                                     help=f"تحميل {file['name']}"):
                                            st.session_state["dl_path_prefill"] = file["path"]
                                            st.rerun()
                        else:
                            # ملف واحد
                            st.json(items)
                    elif r.status_code == 404:
                        st.warning("المسار غير موجود")
                    else:
                        st.error(f"خطأ {r.status_code}")
                except requests.exceptions.ConnectionError:
                    st.error("❌ لا يوجد اتصال بالإنترنت")
                except Exception as e:
                    st.error(f"❌ {e}")

        # ════════════════════
        # TAB 4 — سجل Commits
        # ════════════════════
        with tab_commits:
            st.markdown('<div class="section-title">📜 آخر التعديلات على الـ Repo</div>',
                        unsafe_allow_html=True)

            n_commits = st.slider("عدد الـ Commits", 5, 30, 10)

            if st.button("🔄 تحديث السجل", type="primary"):
                with st.spinner("جاري الجلب..."):
                    try:
                        r = requests.get(
                            f"https://api.github.com/repos/{REPO}/commits",
                            headers=gh_headers,
                            params={"sha": branch, "per_page": n_commits},
                            timeout=10)
                        if r.status_code == 200:
                            commits = r.json()
                            for cm in commits:
                                sha    = cm["sha"][:7]
                                msg    = cm["commit"]["message"].split("\n")[0][:80]
                                author = cm["commit"]["author"]["name"]
                                date_  = cm["commit"]["author"]["date"][:10]
                                url    = cm["html_url"]
                                st.markdown(
                                    f'<div class="trade-row">'
                                    f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                                    f'<div>'
                                    f'<span style="font-family:JetBrains Mono;color:var(--gold);'
                                    f'font-size:.75rem;background:rgba(232,184,75,.08);'
                                    f'padding:2px 8px;border-radius:4px;margin-left:10px;">{sha}</span>'
                                    f'<span style="color:var(--text);font-size:.88rem;">{msg}</span>'
                                    f'</div>'
                                    f'<div style="text-align:left;">'
                                    f'<div style="font-family:JetBrains Mono;color:var(--muted);font-size:.7rem;">{author}</div>'
                                    f'<div style="font-family:JetBrains Mono;color:var(--dim);font-size:.68rem;">{date_}</div>'
                                    f'</div></div>'
                                    f'<div style="margin-top:5px;">'
                                    f'<a href="{url}" target="_blank" '
                                    f'style="font-family:JetBrains Mono;color:var(--blue);font-size:.7rem;">'
                                    f'🔗 عرض على GitHub</a></div>'
                                    f'</div>', unsafe_allow_html=True)
                        else:
                            st.error(f"❌ {r.status_code}")
                    except requests.exceptions.ConnectionError:
                        st.error("❌ لا يوجد اتصال بالإنترنت")
                    except Exception as e:
                        st.error(f"❌ {e}")

        # ── معلومات الـ Repo ──
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        st.markdown(f"""<div class="info-box">
          🐙 <strong>Repository:</strong>
          <a href="https://github.com/{REPO}" target="_blank"
             style="color:var(--gold);font-family:JetBrains Mono;">
            github.com/{REPO}
          </a>
          &nbsp;|&nbsp; Branch: <span style="font-family:JetBrains Mono;color:var(--cyan);">{branch}</span>
          &nbsp;|&nbsp; Token: <span style="font-family:JetBrains Mono;color:var(--green);">✅ متصل</span>
        </div>""", unsafe_allow_html=True)
