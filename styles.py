"""
힐링레터 — 디자인 시스템 (원본 03.html <style> 블록을 그대로 포팅)
색상 변수, 카드/칩/버튼/탭바/모달 등 클래스명과 값 모두 원본 유지.
끝부분에 Streamlit 컨테이너용 보정 CSS만 추가했습니다.
"""

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Noto+Sans+KR:wght@400;500;600;700&family=Noto+Serif+KR:wght@400;500;600;700&display=swap');

:root{
  --font-offset: 0px;
  --ink:#2A2118;
  --ink-2:#3D3125;
  --ink-3:#EFE5CE;
  --ink-4:#E5DBC2;
  --paper:#FBF3E3;
  --paper-dim:#EFE5CE;
  --paper-line:rgba(42,33,24,.14);
  --honey:#C2842A;
  --honey-dark:#A0681A;
  --sage:#4E7D5C;
  --sage-dark:#3B6145;
  --coral:#C95343;
  --coral-dark:#A53D2F;
  --text-ink:#2A2118;
  --text-ink-dim:rgba(42,33,24,.65);
  --text-ink-faint:rgba(42,33,24,.45);
  --text-paper:#2A2118;
  --text-paper-dim:rgba(42,33,24,.62);
  --r-lg:28px;
  --r-md:18px;
  --r-sm:12px;
  --shadow:0 12px 32px rgba(42,33,24,.12);
  --font-serif:'Noto Serif KR', serif;
  --font-sans:'Noto Sans KR', sans-serif;
  --font-mono:'JetBrains Mono', monospace;
}

/* ---------- Streamlit 컨테이너 보정 (배경/여백/기본 UI 숨김) ---------- */
.stApp{
  background: radial-gradient(ellipse at top, #FDF8ED 0%, var(--paper) 70%, #F5EAD2 100%);
}
#MainMenu, header[data-testid="stHeader"], footer{visibility:hidden; height:0;}
.block-container{
  padding:18px 20px 24px; max-width:460px; margin-top:28px;
  background:var(--paper);
  border-radius:34px;
  border:1px solid rgba(42,33,24,.08);
  box-shadow:var(--shadow);
}
html, body, [class*="css"]{font-family:var(--font-sans); color:var(--text-ink);}

/* ---------- HERO ---------- */
.hl-hero{max-width:620px;text-align:center;position:relative;margin:0 auto 18px;}
.hl-hero .eyebrow{font-family:var(--font-mono);letter-spacing:.16em;text-transform:uppercase;font-size:calc(11.5px + var(--font-offset));color:var(--honey-dark);font-weight:600;}
.hl-hero h1{font-family:var(--font-serif);font-weight:600;font-size:clamp(calc(24px + var(--font-offset)), 6vw, calc(34px + var(--font-offset)));line-height:1.35;margin:12px 0 12px;color:var(--ink);}
.hl-hero h1 em{font-style:normal;color:var(--honey-dark);}
.hl-hero p{color:var(--text-ink-dim);font-size:calc(14px + var(--font-offset));line-height:1.7;margin:0;}
.hero-wave{display:block;width:100%;max-width:480px;height:46px;margin:18px auto 4px;opacity:.75;}

/* ---------- PHONE FRAME ---------- */
.phone-skin{
  background:linear-gradient(180deg,#F5EAD2,#EFE5CE);
  border-radius:42px;padding:12px;
  box-shadow:var(--shadow);
  border:1px solid rgba(42,33,24,.08);
  position:relative;
}
.status-bar{height:28px;display:flex;justify-content:space-between;align-items:center;padding:0 16px;font-family:var(--font-mono);font-size:calc(12px + var(--font-offset));color:var(--text-ink-dim);}
.status-dots{display:flex;gap:4px;align-items:center;}
.status-dots span{width:5px;height:5px;border-radius:50%;background:var(--text-ink-dim);display:inline-block;}
.screen-skin{border-radius:30px;background:var(--paper);padding:22px 18px 14px;}

.screen-title{font-family:var(--font-serif);font-size:calc(19px + var(--font-offset));font-weight:600;margin:0 0 4px;color:var(--ink);}
.screen-sub{font-size:calc(12.5px + var(--font-offset));color:var(--text-ink-dim);margin:0 0 18px;line-height:1.6;}
.back-row{display:flex;align-items:center;gap:8px;margin-bottom:14px;color:var(--text-ink-dim);font-size:calc(13px + var(--font-offset));}
.back-row svg{width:16px;height:16px;}

/* ---------- CARDS / GENERIC ---------- */
.card{background:var(--ink-3);border:1px solid rgba(42,33,24,.06);border-radius:var(--r-md);padding:16px;margin-bottom:14px;}
.card-paper{background:rgba(255,255,255,0.6);color:var(--text-paper);border-radius:var(--r-md);padding:18px;margin-bottom:14px;box-shadow:0 6px 18px rgba(42,33,24,.06);border:1px solid var(--paper-line);}
.row{display:flex;align-items:center;justify-content:space-between;gap:10px;}
.label{font-size:calc(12px + var(--font-offset));color:var(--text-ink-dim);}
.label-paper{font-size:calc(12px + var(--font-offset));color:var(--text-paper-dim);}
.stat-num{font-family:var(--font-mono);font-size:calc(26px + var(--font-offset));font-weight:600;color:var(--ink);}
.stat-num.small{font-size:calc(18px + var(--font-offset));}

.chip{display:inline-flex;align-items:center;gap:5px;font-size:calc(11.5px + var(--font-offset));padding:5px 11px;border-radius:999px;font-weight:600;}
.chip.safe{background:rgba(78,125,92,.12);color:var(--sage-dark);border:1px solid rgba(78,125,92,.35);}
.chip.watch{background:rgba(194,132,42,.12);color:var(--honey-dark);border:1px solid rgba(194,132,42,.35);}
.chip.alert{background:rgba(201,83,67,.12);color:var(--coral-dark);border:1px solid rgba(201,83,67,.35);}
.chip-dot{width:6px;height:6px;border-radius:50%;background:currentColor;}

.disclaimer-foot{display:flex;align-items:flex-start;gap:6px;font-size:calc(10.5px + var(--font-offset));color:var(--text-ink-faint);line-height:1.5;margin-top:10px;}
.disclaimer-foot svg{width:13px;height:13px;flex-shrink:0;margin-top:1px;}

/* ---------- HOME ---------- */
.greeting{font-family:var(--font-serif);font-size:calc(20px + var(--font-offset));font-weight:600;margin:2px 0 2px;color:var(--ink);}
.greeting-sub{font-size:calc(12.5px + var(--font-offset));color:var(--text-ink-dim);margin-bottom:16px;}
.envelope-hero{background:linear-gradient(135deg,#FFF,var(--paper-dim));color:var(--text-paper);border-radius:var(--r-md);padding:20px;margin-bottom:16px;position:relative;overflow:hidden;box-shadow:0 8px 24px rgba(42,33,24,.06);border:1px solid var(--paper-line);}
.envelope-hero .et{font-family:var(--font-serif);font-size:calc(16px + var(--font-offset));font-weight:600;margin-bottom:6px;}
.envelope-hero .es{font-size:calc(12px + var(--font-offset));color:var(--text-paper-dim);line-height:1.6;margin-bottom:14px;}
.quick-card{background:var(--ink-3);border:1px solid rgba(42,33,24,.05);border-radius:var(--r-md);padding:14px;margin-bottom:10px;}
.quick-card svg{width:20px;height:20px;color:var(--honey-dark);margin-bottom:8px;}
.quick-card .qc-title{font-size:calc(13px + var(--font-offset));font-weight:600;margin-bottom:2px;color:var(--ink);}
.quick-card .qc-sub{font-size:calc(11px + var(--font-offset));color:var(--text-ink-dim);}

/* ---------- LETTER ---------- */
.letter-from{font-size:calc(11px + var(--font-offset));color:var(--text-paper-dim);font-family:var(--font-mono);margin-bottom:10px;}
.letter-msg{font-family:var(--font-serif);font-style:italic;font-size:calc(15px + var(--font-offset));line-height:1.8;margin:14px 0 16px;color:var(--ink-2);}
.privacy-note{display:flex;gap:6px;align-items:flex-start;font-size:calc(11px + var(--font-offset));color:var(--text-paper-dim);background:rgba(78,125,92,.08);border:1px solid rgba(78,125,92,.2);border-radius:10px;padding:9px 11px;margin-bottom:14px;line-height:1.5;}
.privacy-note svg{width:13px;height:13px;flex-shrink:0;margin-top:1px;color:var(--sage-dark);}
.privacy-note, .privacy-note *{
  word-break: keep-all !important;
  overflow-wrap: normal !important;
  word-wrap: normal !important;
  -webkit-hyphens: none !important;
  hyphens: none !important;
  line-break: strict !important;
  white-space: normal !important;
}
.privacy-note span, .privacy-note div{
  min-width: 0;
  flex: 1;
}
.waveform-label{font-size:calc(10.5px + var(--font-offset));color:var(--text-paper-dim);font-family:var(--font-mono);margin-bottom:4px;}

.breakdown-row{display:flex;justify-content:space-between;font-size:calc(12px + var(--font-offset));padding:7px 0;border-bottom:1px solid var(--paper-line);color:var(--text-ink);}
.breakdown-row:last-child{border-bottom:none;}
.result-score-row{display:flex;align-items:baseline;gap:8px;margin:10px 0 4px;}
.result-score{font-family:var(--font-mono);font-size:calc(40px + var(--font-offset));font-weight:600;}
.result-caution{font-size:calc(11px + var(--font-offset));color:var(--text-paper-dim);line-height:1.6;background:rgba(42,33,24,.05);border-radius:10px;padding:10px;margin:14px 0;}

/* ---------- REPORT ---------- */
.chart-card{background:var(--ink-3);border:1px solid rgba(42,33,24,.06);border-radius:var(--r-md);padding:16px;margin-bottom:14px;}
.chart-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;}
.chart-head .ct{font-size:calc(13px + var(--font-offset));font-weight:600;color:var(--ink);}
.stat-mini{background:var(--ink-3);border:1px solid rgba(42,33,24,.06);border-radius:var(--r-md);padding:12px 8px;text-align:center;}
.stat-mini .label{margin-bottom:4px;}

/* ---------- MY PAGE ---------- */
.profile-row{display:flex;align-items:center;gap:12px;margin-bottom:18px;}
.avatar{width:50px;height:50px;border-radius:50%;background:var(--ink-4);display:flex;align-items:center;justify-content:center;}
.avatar svg{width:24px;height:24px;color:var(--text-ink-dim);}
.toggle-row{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--paper-line);}
.toggle-row:last-child{border-bottom:none;}
.toggle-row .tt{font-size:calc(13px + var(--font-offset));font-weight:500;}
.toggle-row .ts{font-size:calc(11px + var(--font-offset));color:var(--text-ink-dim);}

/* ---------- TOAST 대용 안내 ---------- */
.credit{font-size:calc(11px + var(--font-offset));color:var(--text-ink-faint);text-align:center;line-height:1.7;margin-top:16px;}

/* ---------- Streamlit 위젯 톤 맞추기 ---------- */
.stButton > button{
  border-radius:999px;font-weight:600;border:1px solid rgba(42,33,24,.18);
  background:var(--ink-3);color:var(--text-ink);transition:transform .12s, background .15s;
}
.stButton > button:hover{transform:translateY(-1px);border-color:var(--honey);color:var(--ink);background:var(--ink-4);}
.stButton > button[kind="primary"]{
  background:var(--honey);color:#FFF;border:none;
  box-shadow:0 6px 16px rgba(194,132,42,.25);
}
.stButton > button[kind="primary"]:hover{background:var(--honey-dark);color:#FFF;}
.stTextArea textarea, .stTextInput input{
  background:var(--paper);border:1px solid var(--paper-line);border-radius:14px;color:var(--ink);
}
.stTextArea textarea:focus, .stTextInput input:focus{border-color:var(--honey-dark);}
div[data-baseweb="tab-list"]{background:var(--ink-3);border-radius:14px;padding:4px;gap:6px;}
button[data-baseweb="tab"]{border-radius:11px;}

/* ---------- 보관함 달력 커스텀 ---------- */
.calendar-container {
    background-color: #FCF9F2; /* 연베이지보다 조금 더 연하고 화사한 색 */
    border-radius: var(--r-md);
    padding: 16px 12px;
    margin-top: 10px;
    border: 1px solid rgba(42,33,24,.05);
}
.calendar-container div[data-testid="column"] .stButton > button {
    border: none !important;
    background: transparent !important;
    color: var(--text-ink) !important;
    padding: 0;
    width: 36px;
    height: 36px;
    border-radius: 50% !important;
    margin: 0 auto;
    font-weight: 500;
    box-shadow: none !important;
}
.calendar-container div[data-testid="column"] .stButton > button:hover {
    background: rgba(42,33,24,.05) !important;
}

/* 기록이 있는 날 (Primary 상태) -> 연핑크 동그라미 */
.calendar-container div[data-testid="column"] .stButton > button[kind="primary"] {
    background-color: #FFE5E5 !important; /* 연핑크 */
    color: #C95343 !important;           /* 텍스트는 붉은 계열 포인트 */
    font-weight: 700;
}
.calendar-container div[data-testid="column"] .stButton > button[kind="primary"]:hover {
    background-color: #FFD4D4 !important;
}
</style>
"""


def font_offset_css(level: int) -> str:
    """접근성 글자 크기 (원본 setFontSize: 0 / 5 / 10pt)"""
    return f"<style>:root{{--font-offset:{level}px;}}</style>"
