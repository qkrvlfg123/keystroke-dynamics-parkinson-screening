"""
힐링레터 — 키보드 리듬 기반 파킨슨 초기 선별 보조 (Streamlit 버전)
원본 03.html 을 Streamlit + Python 으로 포팅. 디자인/색상/화면 구성/점수 로직 유지.

실행:   streamlit run app.py
"""
from __future__ import annotations

import re
import calendar
import random
import time
import os       
import base64 
from datetime import datetime

import streamlit as st
import pandas as pd
import altair as alt
import streamlit.components.v1 as components

from report_pdf import build_report_pdf

# 키 입력 캡처 컴포넌트 (없어도 앱이 죽지 않도록 방어)
try:
    from components.keystroke import keystroke_letter
    KEYSTROKE_AVAILABLE = True
except Exception as _e:  # ModuleNotFoundError 등
    KEYSTROKE_AVAILABLE = False
    _KEYSTROKE_IMPORT_ERROR = _e

    def keystroke_letter(*args, **kwargs):
        return None

# 스타일 로딩 (어떤 경우에도 디자인이 날아가지 않도록 3중 안전장치)
import os as _os


def _load_css():
    # 1) 정상: styles.py 에서 import
    try:
        from styles import CSS as _c
        if _c and _c.strip():
            return _c
    except Exception:
        pass
    # 2) 폴백: app.py 와 같은 폴더의 styles.py 를 직접 읽어 CSS 문자열만 추출
    try:
        import re as _re
        _here = _os.path.dirname(_os.path.abspath(__file__))
        _src = open(_os.path.join(_here, "styles.py"), encoding="utf-8").read()
        _m = _re.search(r'CSS\s*=\s*r?"""(.*?)"""', _src, _re.S)
        if _m:
            return _m.group(1)
    except Exception:
        pass
    return ""


CSS = _load_css()

# 🆕 앱 폴더 기준 경로 (opening.mp4 위치 계산용)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_PATH = os.path.join(BASE_DIR, "opening.mp4")
LOGO_PATH = os.path.join(BASE_DIR, "logo.png")

def _load_logo_b64():
    """logo.png 를 base64 로 미리 읽어둔다. 없으면 빈 문자열(로고 미표시)."""
    try:
        with open(LOGO_PATH, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""

LOGO_B64 = _load_logo_b64()

# 🆕 힐링레터 이미지 폴더 + base64 캐시 로더
LETTER_IMG_DIR = BASE_DIR
_letter_img_cache = {}

def _load_letter_img_b64(filename):
    if not filename:
        return ""
    if filename in _letter_img_cache:
        return _letter_img_cache[filename]
    try:
        with open(os.path.join(LETTER_IMG_DIR, filename), "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
    except Exception:
        b64 = ""
    _letter_img_cache[filename] = b64
    return b64

# 🆕 멍멍우체부 카드 아이콘 (강아지 이미지)
def _load_icon_b64(filename):
    try:
        with open(os.path.join(BASE_DIR, filename), "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""

ICON_DOG_B64 = _load_icon_b64("icon_dog.png")
PAW_PAD_B64 = _load_icon_b64("paw pad.png")

def _find_and_load_banner_b64():
    """BASE_DIR에서 '트라슈'와 '배너'가 들어간 이미지 파일을 자동으로 찾아 로드한다.
    파일명 공백/자소결합 방식 차이와 무관하게 동작하도록 함."""
    try:
        for fname in os.listdir(BASE_DIR):
            if ("트라슈" in fname or "배너" in fname) and fname.lower().endswith((".png", ".jpg", ".jpeg")):
                with open(os.path.join(BASE_DIR, fname), "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                ext = "jpeg" if fname.lower().endswith((".jpg", ".jpeg")) else "png"
                return b64, ext
    except Exception:
        pass
    return "", "png"

GAME_BANNER_B64, GAME_BANNER_EXT = _find_and_load_banner_b64()

# 🆕 점수 상태 이모지(red/yellow/green) 로더
_score_img_cache = {}

def _load_score_img_b64(filename):
    if filename in _score_img_cache:
        return _score_img_cache[filename]
    try:
        with open(os.path.join(BASE_DIR, filename), "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
    except Exception:
        b64 = ""
    _score_img_cache[filename] = b64
    return b64

def score_emoji_html(score, size=36):
    """점수를 우리 3구간 컷오프(logic.ml_thresholds: upper/lower)에 맞춰
    초록(안정)/노랑(관찰 필요)/빨강(상담 권장) 이미지로 반환.
    - score >= upper       : green.png  (안정)
    - lower < score < upper : yellow.png (관찰 필요)
    - score <= lower        : red.png    (상담 권장)"""
    upper, lower = 66.6, 49.9  # 기본값 (json 로드 실패 시)
    try:
        th = getattr(logic, "ml_thresholds", None)
        if th:
            upper = th.get("upper", upper)
            lower = th.get("lower", lower)
    except Exception:
        pass
    if score >= upper:
        fname = "green.png"
    elif score > lower:
        fname = "yellow.png"
    else:
        fname = "red.png"

    b64 = _load_score_img_b64(fname)
    if not b64:
        # 이미지 로드 실패 시 안전한 대체(기존 텍스트)
        return f'<div style="font-size:18px;font-weight:bold;color:#222;">{score}점</div>'

    return (
        f'<img src="data:image/png;base64,{b64}" '
        f'style="width:{size}px;height:{size}px;object-fit:contain;'
        f'display:inline-block;vertical-align:middle;" />'
    )

# 차트/로직 (pandas·joblib·scikit-learn 필요)
try:
    import charts
    import logic
    LOGIC_AVAILABLE = True
except Exception as _le:
    LOGIC_AVAILABLE = False
    _LOGIC_IMPORT_ERROR = _le

    class Dummy:
        def __getattr__(self, name): return lambda *args, **kwargs: ""
    charts = logic = Dummy()

# 🆕 힐링레터 텍스트 + 매칭 이미지 (5개 전부 이미지 있음)
HEAL_LETTERS = [
    {"text": "잠시 멈춰 서서 가장<br> 편안해지는 순간을 떠올려 볼까요?", "image": "image4-잠시 멈춰서서.png"},
    {"text": "오늘 당신을 웃게 했던<br>작은 일 하나가 무엇이었나요?", "image": "image5-웃게 했던.png"},
    {"text": "오늘 마주친 수많은 일들 중에서,<br>가장 빛나게 했던 순간은 언제였나요?", "image": "image3-빛나게.png"},
    {"text": "복잡한 생각은 내려두고 오늘<br> 밤은 편안한 잠만을 생각하면 어떨까요?", "image": "image1-복잡한 생각.png"},
    {"text": "오늘 마음속에 들어온 평온한<br> 풍경 하나가 있다면 무엇인가요?", "image": "image2-평온한 풍경.png"},
    
    {"text": "잠시 멈춰 서서 지금 당신의 마음이<br> 가장 편안해지는 순간을 떠올려 볼까요?", "image": "image4-잠시 멈춰서서.png"},
    {"text": "오늘 당신을 웃게 했던 아주 작은 일 <br>하나가 무엇이었는지 기억나나요?", "image": "image5-웃게 했던.png"},
    {"text": "오늘 당신이 마주친 수많은 일들 중에서,<br> 당신을 가장 빛나게 했던 순간은 언제였나요?", "image": "image3-빛나게.png"},
    {"text": "복잡한 생각은 내려두고<br>오늘 밤은 편안한 잠만을 생각하면 어떨까요?", "image": "image1-복잡한 생각.png"},
    {"text": "오늘 당신의 마음속에 들어온<br> 평온한 풍경 하나가 있다면 무엇인가요?", "image": "image2-평온한 풍경.png"},
]

def font_offset_css(x):
    return f"""
    <style>
    .stMarkdown p, .stMarkdown li, .stMarkdown span,
    .stMarkdown div,
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] div,
    [data-testid="stWidgetLabel"] p,
    [data-testid="stWidgetLabel"] label,
    .stRadio label, .stToggle label,
    .stTextInput input, .stTextArea textarea,
    .stExpander summary,
    div[role="radiogroup"] label
    {{
        font-size: calc(14px + {x}pt) !important;
    }}
    .stButton > button {{
        font-size: 11px !important;
        white-space: nowrap !important;
        height: 36px !important;
        min-height: 36px !important;
        max-height: 36px !important;
        padding: 0 4px !important;
        width: 100% !important;
        box-sizing: border-box !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }}
    </style>
    """

# ============================================================
# 다국어 (한국어 / English)
# ============================================================
LANG_TEXTS = {
    "ko": {
        # 공통 / 메뉴
        "menu_title": "메뉴", "menu_share": "앱 공유하기", "menu_lang": "언어 / Language",
        "lang_ko": "한국어", "lang_en": "English",
        "share_title": "힐링레터 공유하기",
        "share_desc": "아래 주소를 복사해 다른 분께 보내면, 같은 네트워크에서 접속할 수 있어요. "
                      "누구나 접속 가능한 공개 링크가 필요하면 Streamlit Cloud로 배포하세요.",
        "share_url_label": "공유 주소",
        # 온보딩
        "ob0_title": "\"당신의 안부가 우리의 안심이 됩니다.\"",
        "ob0_sub": "힐링레터는 소중한 사람과 주고받는 안부 속에 건강 리듬을 담습니다. "
                   "부담 없는 편지 한 통으로 매일의 상태를 기록하고, "
                   "가족과 함께 서로를 살피는 따뜻한 일상을 만들어보세요.",
        "ob0_btn": "확인하고 시작하기",
        "ob0_privacy_btn": "개인정보 수집·이용 동의",
        "ob0_privacy_done": "✔ 개인정보 수집·이용에 동의했어요",
        "ob1_title": "힐링레터에 오신 것을 환영합니다",
        "ob1_sub": "일상적인 타이핑 리듬을 통해 건강의 흔적을 살펴볼게요. 먼저 사용하실 이름을 입력해 주세요.",
        "ob1_name": "사용자 이름", "ob1_ph": "이름을 입력해 주세요 (예: 보영)",
        "ob2_title": "생년월일을 선택해 주세요",
        "ob2_sub": "선별 보조 분석 시 연령대별 기준 데이터 비교를 위해 활용되며, 정보는 안전하게 보관됩니다.",
        "ob2_y": "년", "ob2_m": "월", "ob2_d": "일",
        "ob3_title": "보호자를 등록하시겠어요?",
        "ob3_sub": "보호자를 등록해 두시면, 이상 신호가 감지되었을 때 결과를 함께 공유할 수 있어요.",
        "common_prev": "이전", "common_next": "다음으로",
        # 홈
        "home_greeting": "안녕하세요, {name}님",
        "home_sub_has": "지금까지 {n}번의 편지를 기록했어요.",
        "home_sub_none": "오늘 첫 편지를 기록해볼까요?",
        "home_env_title": "오늘의 힐링레터가 도착했어요",
        "home_letter_btn": "편지 읽고 답장하기",
        "home_trend": "최근 문자 점수 추이",
        "home_game": "멍멍우체부(반응 속도 측정)\n화면에 나오는 강아지 터치하기",
        "home_report": "변화 리포트\n장기 추세로 살펴보기",
        "home_disc": "힐링레터는 의료기기가 아니며, 의학적 진단을 내리지 않습니다. 결과가 걱정스러우시면 신경과 전문의와 상담해 주세요.",
        # 네비
        "nav_home": "홈", "nav_archive": "보관함", "nav_report": "리포트", "nav_info": "정보", "nav_my": "MY",
        # 마이페이지
        "my_title": "마이페이지", "my_photo_upload": "프로필 사진 올리기", "my_photo_reset": "기본 이미지로",
    },
    "en": {
        "menu_title": "Menu", "menu_share": "Share app", "menu_lang": "언어 / Language",
        "lang_ko": "한국어", "lang_en": "English",
        "share_title": "Share Healing Letter",
        "share_desc": "Copy the address below and send it to others so they can open it on the same network. "
                      "For a public link anyone can open, deploy to Streamlit Cloud.",
        "share_url_label": "Share address",
        "ob0_title": "\"Your wellbeing gives us peace of mind.\"",
        "ob0_sub": "Healing Letter captures your precious health rhythm within the everyday check-ins you share "
                   "with someone you love. With one simple letter, you can naturally record your daily state "
                   "and build a warm routine of checking in on each other with your family.",
        "ob0_btn": "I understand — let's start",
        "ob0_privacy_btn": "Privacy consent",
        "ob0_privacy_done": "✔ You agreed to the privacy policy",
        "ob1_title": "Welcome to Healing Letter",
        "ob1_sub": "We'll look at traces of your health through everyday typing rhythm. First, please enter your name.",
        "ob1_name": "Your name", "ob1_ph": "Please enter your name (e.g., Boyoung)",
        "ob2_title": "Please select your date of birth",
        "ob2_sub": "This is used to compare against age-group reference data during screening support. Your information is kept securely.",
        "ob2_y": "Year", "ob2_m": "Month", "ob2_d": "Day",
        "ob3_title": "Would you like to register a guardian?",
        "ob3_sub": "If you register a guardian, results can be shared together when an unusual signal is detected.",
        "common_prev": "Back", "common_next": "Next",
        "home_greeting": "Hello, {name}",
        "home_sub_has": "You've written {n} letters so far.",
        "home_sub_none": "Shall we write your first letter today?",
        "home_env_title": "Today's Healing Letter has arrived",
        "home_letter_btn": "Read & reply to the letter",
        "home_trend": "Recent letter score trend",
        "home_game": "Woof Postman (reaction speed)\nTap the dog that appears on screen",
        "home_report": "Change Report\nView long-term trends",
        "home_disc": "Healing Letter is not a medical device and does not provide a medical diagnosis. "
                     "If you're worried about your results, please consult a neurologist.",
        "nav_home": "Home", "nav_archive": "Archive", "nav_report": "Report", "nav_info": "Info", "nav_my": "MY",
        "my_title": "My Page", "my_photo_upload": "Upload profile photo", "my_photo_reset": "Reset to default",
    },
}


def L(key, **kwargs):
    lang = st.session_state.get("lang", "ko")
    txt = LANG_TEXTS.get(lang, LANG_TEXTS["ko"]).get(key)
    if txt is None:
        txt = LANG_TEXTS["ko"].get(key, key)
    return txt.format(**kwargs) if kwargs else txt

def render_logo_header():
    """모든 화면 상단(시계 위)에 고정 노출되는 힐링레터 로고 이미지."""
    if LOGO_B64:
        st.markdown(
            f'''
            <div class="hl-logo-header">
                <img src="data:image/png;base64,{LOGO_B64}" class="hl-logo-img" alt="PA트라슈"/>
            </div>
            ''',
            unsafe_allow_html=True
        )
    else:
        # logo.png 를 못 찾았을 때의 안전한 대체 표시 (텍스트만)
        st.markdown(
            '<div class="hl-logo-header"><span class="hl-logo-text">파트라슈</span></div>',
            unsafe_allow_html=True
        )

def clock_span():
    """서버 시각을 초기값으로 하는 시계 span (JS가 매초 갱신)."""
    return f'<span id="hl-clock">{datetime.now():%H:%M}</span>'


def inject_live_clock():
    """브라우저 로컬 시각으로 status-bar 시계를 매초 실시간 갱신."""
    components.html(
        """
        <script>
        function _hlTick(){
          try{
            var d = new Date();
            var s = ('0'+d.getHours()).slice(-2) + ':' + ('0'+d.getMinutes()).slice(-2);
            var el = window.parent.document.getElementById('hl-clock');
            if (el) el.textContent = s;
          } catch(e){}
        }
        _hlTick(); setInterval(_hlTick, 1000);
        </script>
        """,
        height=0,
    )


# ============================================================
# 페이지 설정 + 스타일
# ============================================================
st.set_page_config(page_title="힐링레터", page_icon="✉️", layout="centered")


def init_state():
    ss = st.session_state
    now = datetime.now()
    
    defaults = {
        "logged_in": False,
        "intro_done": False,
        "privacy_agreed": False,
        "onboard_step": 0,
        "lang": "ko",
        "profile_photo": None,
        "guardian_choice": "O",
        "name": "보영",
        "birth": {"year": "1965", "month": "01", "day": "01"},
        "guardian": {"registered": False, "name": "", "age": "", "contactType": "phone", "contact": ""},
        "letters": [],
        "games": [],
        "screen": "home",
        "report_seg": "game",    
        "sample_toggle": False,
        "font_level": 0,
        "last_letter_date": None,
        "daily_letter_msg": None,
        "daily_letter_img": None,
        "daily_letter_date": None,
        "last_info_update": None,
        "letter_nonce": 0,
        "last_submit_id": None,
        "last_game_id": None,
        "notif_weekly": True,
        "notif_monthly": True,
        "_open_photo_dialog": False,
        "_open_info_dialog": False,
        "ob_year": "1965",
        "ob_month": "01",
        "ob_day": "01",
        "fs_radio": "기본",
        "cal_year": now.year,
        "cal_month": now.month,
        "cal_selected": now.strftime("%Y-%m-%d"),
        
        # 🔄 두더지 게임용 상태 변수
        "game_playing": False,
        "game_step": 0,          
        "game_miss_count": 0,    
        "game_sequence": [],     
        "game_start_time": 0.0,  
        "game_grid": [0] * 9,    
        
        # 🆕 공중 비행 시간 측정을 위한 변수
        "game_last_click_time": 0.0,
        "game_flight_times": [],
    }
    
    for k, v in defaults.items():
        if k not in ss:
            ss[k] = v


init_state()
ss = st.session_state

# 🆕 영상(JS)에서 보낸 종료 신호를 받아서 상태 갱신
if st.query_params.get("intro") == "done":
    ss.intro_done = True
    st.query_params.clear()

st.markdown(CSS, unsafe_allow_html=True)

# 다이얼로그/메뉴 배경을 항상 페이퍼 톤으로 고정 (PC별 라이트/다크 차이 방지)
st.markdown("""
<style>
div[data-testid="stDialog"] > div,
div[data-testid="stDialog"] div[role="dialog"],
div[data-baseweb="popover"] div[data-baseweb="menu"]{
    background: #FBF3E3 !important;
    color: #2A2118 !important;
    border: 1px solid rgba(42,33,24,.10) !important;
}
</style>
""", unsafe_allow_html=True)

# 로직/차트 모듈 로드 실패 시 조용히 넘기지 않고 진짜 원인을 보여준다.
if not LOGIC_AVAILABLE:
    st.error(
        "분석 모듈(charts/logic) 로드에 실패했습니다. 필요한 패키지가 설치되지 않았을 수 있어요.\n\n"
        "터미널에서 다음을 실행해 주세요:  `pip install -r requirements.txt`\n\n"
        f"원본 오류: {type(_LOGIC_IMPORT_ERROR).__name__}: {_LOGIC_IMPORT_ERROR}"
    )
st.markdown(font_offset_css(ss.font_level), unsafe_allow_html=True)

# 시안 스타일 맞춤 추가 CSS 디자인 정의
STYLING_HONEY = """
<style>

/* 🆕 페이지 최상단 여백(로고 위 빈 공간) 줄이기 — 여러 후보 컨테이너를 모두 압축 */
[data-testid="stAppViewContainer"] .main .block-container,
[data-testid="stMain"] .block-container,
.block-container {
    padding-top: 0px !important;
}
[data-testid="stVerticalBlock"] {
    gap: 0.4rem !important;
}
.hl-logo-header {
    padding: 4px 0 4px 0 !important;
    margin-top: 0 !important;
}
[data-testid="stAppViewContainer"] > .main {
    padding-top: 0 !important;
}

.report-title-section { font-family: var(--font-serif); font-size: 24px; font-weight: 600; color: #1e1e1e; margin-bottom: 12px; }
.report-sub-section { font-size: 13.5px; color: #767676; margin-bottom: 20px; }
.summary-container { display: flex; gap: 10px; margin-bottom: 16px; justify-content: space-between; }
.summary-card { flex: 1; background: #f3ece2; border-radius: 16px; padding: 8px 6px; text-align: center; }
.summary-card .s-label { font-size: 12px; color: #7d7263; margin-bottom: 6px; font-weight: 500; }
.summary-card .s-value { font-size: 20px; font-weight: bold; color: #222; }
.chart-box { background: #f3ece2; border-radius: 20px; padding: 16px; margin-bottom: 16px; min-height: 200px; }
.chart-title { font-size: 14px; font-weight: bold; color: #222; margin-bottom: 12px; }
.chart-empty { text-align: center; color: #9a9081; font-size: 14px; padding-top: 60px; }
.trend-card { background: #eee7dc; border-radius: 16px; padding: 16px; margin-bottom: 20px; }
.trend-title { font-size: 13px; font-weight: bold; color: #444; margin-bottom: 4px; }
.trend-sub { font-size: 12px; color: #888; }
.share-btn-style { background: #eee7dc; border: 1px solid #dcd3c4; color: #5e5446; text-align: center; border-radius: 24px; padding: 12px; font-size: 14px; font-weight: 600; cursor: pointer; width: 100%; margin-bottom: 10px; }

/* 🖱️ 칸 자체를 버튼으로 쓸 때 투명도 조절 및 예쁜 커서 효과 */
div.stButton > button.grid-pad-btn {
    min-height: 110px !important;
    white-space: pre-wrap !important;
    border-radius: 12px !important;
    font-weight: bold !important;
    font-size: 13px !important;
    border: 1px solid #DDD !important;
    transition: transform 0.1s ease;
}
div.stButton > button.grid-pad-btn:active {
    transform: scale(0.96);
}

/* 👤 마이페이지 프로필 및 섹션 스타일링 추가 */
.my-profile-container { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }
.my-profile-avatar { width: 44px; height: 44px; background: #e3dcd3; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 20px; color: #666; }
.my-profile-name { font-size: 18px; font-weight: bold; color: #222; }
.my-section-title { font-size: 13px; font-weight: bold; color: #333; margin-top: 18px; margin-bottom: 16px; }
.my-info-card { background: #f5efe6; border-radius: 14px; padding: 14px; margin-bottom: 8px; }
.my-info-card-title { font-size: 14px; font-weight: bold; color: #222; margin-bottom: 4px; }
.my-info-card-sub { font-size: 12px; color: #767676; }

/* 🆕 상단 고정 로고 (이미지 로고, 확대 버전) */

.hl-logo-header {
    position: sticky;
    top: 0;
    z-index: 9998;
    display: flex;
    align-items: center;
    padding: 6px 0 4px 0;
    background: transparent;
}
.hl-logo-img {
    height: 44px;      /* 🔧 로고 세로 높이 - 더 크게 하고 싶으면 이 값을 키우세요 */
    width: auto;
    object-fit: contain;
    display: block;
}
.hl-logo-text {
    font-family: var(--font-serif, serif);
    font-size: 13px;
    font-weight: 700;
    color: #3a2b22;
    letter-spacing: 0.3px;   
}

/* 🆕 2단 그리드: 1행(로고-시계) / 2행(빈칸-점) — 시계와 점이 같은 세로선상에 위치 */
.hl-topbar-grid {
    display: grid;
    grid-template-columns: 1fr auto;
    grid-template-rows: auto auto;
    align-items: center;
    row-gap: 4px;
    padding: 4px 0 0 0;
}
.hl-topbar-logo { grid-column: 1; grid-row: 1; }
.hl-topbar-clock {
    grid-column: 2; grid-row: 1;
    font-size: 13px; color: var(--text-ink-dim);
    text-align: right;
}
.hl-topbar-spacer { grid-column: 1; grid-row: 2; }
.hl-topbar-dots, .hl-topbar-dots-slot {
    grid-column: 2; grid-row: 2;
    display: flex; justify-content: flex-end;
}

</style>
"""
st.markdown(STYLING_HONEY, unsafe_allow_html=True)

# ============================================================
# 공통 유틸
# ============================================================
def today_str():
    d = datetime.now()
    return f"{d.year}-{d.month:02d}-{d.day:02d}"

def ensure_daily_letter():
    """그날 하루 동안 유지될 힐링레터를 날짜가 바뀔 때만 랜덤으로 새로 뽑아둔다."""
    if ss.daily_letter_date != today_str():
        try:
            letter = random.choice(HEAL_LETTERS)
            ss.daily_letter_msg = letter["text"]
            ss.daily_letter_img = letter.get("image")
        except:
            ss.daily_letter_msg = "따뜻한 날씨네요. 오늘 하루는 어떻게 보내셨나요? 편하게 적어주세요."
            ss.daily_letter_img = None
        ss.daily_letter_date = today_str()

def validate_guardian(name, age, contact, mode):
    if not name or len(name) < 2:
        return False
    if not age:
        return False
    if mode == "phone":
        if not re.match(r"^\d{2,3}-\d{3,4}-\d{4}$", contact):
            return False
    else:
        if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", contact):
            return False
    return True


def goto(screen):
    ss.screen = screen

# ============================================================
# 🎬 오프닝 영상
# ============================================================
def render_intro_video():
    """opening.mp4 를 전체 화면으로 자동재생하고, 영상이 끝나면(또는 문제가 생기면) 자동으로 온보딩 화면으로 전환한다."""

    if not os.path.exists(VIDEO_PATH):
        ss.intro_done = True
        st.rerun()
        return

    with open(VIDEO_PATH, "rb") as f:
        video_b64 = base64.b64encode(f.read()).decode()

    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"],
    [data-testid="stHeader"],
    .main, .block-container {
        padding: 0 !important;
        margin: 0 !important;
        background: #000 !important;
        max-width: 100% !important;
    }
    .st-key-intro_done_trigger { display:none !important; }
    div[data-testid="stIFrame"], iframe {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        border: none !important;
        z-index: 999999 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    if st.button("intro done", key="intro_done_trigger"):
        ss.intro_done = True
        st.rerun()

    # 🆕 자동재생이 막히거나 영상이 재생되지 않을 때를 대비한 "건너뛰기" 버튼 (항상 화면에 노출)
    st.markdown("""
    <style>
    .st-key-intro_skip_btn {
        position: fixed !important;
        top: 16px !important;
        right: 16px !important;
        z-index: 1000000 !important;
    }
    .st-key-intro_skip_btn button {
        background: rgba(0,0,0,0.45) !important;
        color: #fff !important;
        border: 1px solid rgba(255,255,255,0.4) !important;
        border-radius: 999px !important;
        padding: 6px 14px !important;
        font-size: 13px !important;
    }
    </style>
    """, unsafe_allow_html=True)
    if st.button("건너뛰기 ›", key="intro_skip_btn"):
        ss.intro_done = True
        st.rerun()

    video_html = f"""
    <style>
    html, body {{ margin:0; padding:0; overflow:hidden; background:#000; }}
    #opening-video {{
        width:100vw;
        height:100vh;
        object-fit: contain;   /* 🆕 cover → contain : 영상이 잘리지 않고 전체가 다 보이도록 */
        display:block;
        background:#000;
    }}
    #tap-to-play {{
        position:fixed; inset:0; display:none; align-items:center; justify-content:center;
        background:rgba(0,0,0,0.55); color:#fff; font-size:16px; z-index:2;
        cursor:pointer; text-align:center;
    }}
    </style>
    <video id="opening-video" autoplay muted playsinline webkit-playsinline preload="auto">
        <source src="data:video/mp4;base64,{video_b64}" type="video/mp4">
    </video>
    <div id="tap-to-play">화면을 눌러 시작하기 ▶</div>
    <script>
    var video = document.getElementById('opening-video');
    var tapLayer = document.getElementById('tap-to-play');
    var already = false;

    function finishIntro() {{
        if (already) return;
        already = true;
        var btn = window.parent.document.querySelector('.st-key-intro_done_trigger button');
        if (btn) {{ btn.click(); }}
    }}

    // 🆕 자동재생이 브라우저 정책으로 막힐 경우를 대비해 명시적으로 play() 호출
    function tryPlay() {{
        var p = video.play();
        if (p !== undefined) {{
            p.catch(function(err) {{
                console.warn('autoplay blocked:', err);
                tapLayer.style.display = 'flex';
            }});
        }}
    }}

    tapLayer.addEventListener('click', function() {{
        tapLayer.style.display = 'none';
        video.play();
    }});

    video.addEventListener('ended', finishIntro);

    // 🆕 영상 로딩/재생 자체가 실패하는 경우(코덱 문제, 파일 손상 등) 무한 대기하지 않도록 처리
    video.addEventListener('error', function() {{
        console.error('video error', video.error);
        finishIntro();
    }});

    video.addEventListener('loadedmetadata', function() {{
        var ms = (video.duration ? video.duration * 1000 : 8000) + 1000;
        setTimeout(finishIntro, ms);
    }});

    // 🆕 loadedmetadata 자체가 발생하지 않는 최악의 경우를 대비한 최대 대기 시간(안전장치)
    setTimeout(finishIntro, 15000);

    tryPlay();
    </script>
    """
    components.html(video_html, height=100)

# ============================================================
# 온보딩(로그인) 플로우
# ============================================================
def render_onboarding():
    logo_html = (f'<img src="data:image/png;base64,{LOGO_B64}" class="hl-logo-img" alt="PA트라슈"/>'
                 if LOGO_B64 else '<span class="hl-logo-text">파트라슈</span>')

    st.markdown(
        f'''
        <div class="hl-topbar-grid">
            <div class="hl-topbar-logo">{logo_html}</div>
            <div class="hl-topbar-clock">{clock_span()}</div>
            <div class="hl-topbar-spacer"></div>
            <div class="hl-topbar-dots">
                <span class="status-dots"><span></span><span></span><span></span></span>
            </div>
        </div>
        ''',
        unsafe_allow_html=True
    )
    inject_live_clock()

    step = ss.onboard_step

    if step == 0:
        st.markdown(
            '<div class="screen-title" style="font-family:var(--font-serif); '
            'font-size:calc(23px + var(--font-offset)); font-weight:700; line-height:1.4; '
            'margin:0 0 16px 0; text-indent:0; padding-left:0; color:var(--ink); '
            'text-align:left; width:100%; box-sizing:border-box;">'
            + L("ob0_title") + '</div>'
            '<div class="screen-sub" style="font-size:calc(14.5px + var(--font-offset)); '
            'line-height:1.9; word-break:keep-all !important; overflow-wrap:normal !important; '
            'word-wrap:normal !important; white-space:normal !important; overflow:visible; '
            'text-align:left !important; letter-spacing:normal !important; '
            'word-spacing:normal !important; width:100%; max-width:100%; '
            'box-sizing:border-box; margin:0; text-indent:0; padding-left:0; padding-right:2px; '
            'text-justify:none !important; hyphens:none !important; '
            '-webkit-hyphens:none !important; text-rendering:optimizeLegibility; '
            '-webkit-font-smoothing:antialiased;">'
            + L("ob0_sub") + '</div>',
            unsafe_allow_html=True)
        
        st.markdown('<div style="margin-top:28px;"></div>', unsafe_allow_html=True)

        # 🆕 개인정보 수집·이용 동의 내용을 "확인만" 할 수 있는 접이식 섹션 (동의 버튼 없음)
        with st.expander("개인정보 수집·이용 동의"):
            
            st.markdown('''
            <style>
            #privacy-consent-box, #privacy-consent-box * {
                word-break: keep-all !important;
                overflow-wrap: normal !important;
                word-wrap: normal !important;
                -webkit-hyphens: none !important;
                hyphens: none !important;
                line-break: strict !important;
            }
            </style>
            <div id="privacy-consent-box" style="font-size:13.5px; line-height:1.85; color:var(--ink); max-height:360px;
            overflow-y:auto; overflow-x:hidden; padding-right:6px; padding-left:0;
            width:100%; max-width:100%; box-sizing:border-box;
            white-space:normal !important;
            text-align:left !important; text-align-last:auto !important;
            letter-spacing:normal !important; word-spacing:normal !important;
            text-justify:none !important;
            text-rendering:optimizeLegibility; -webkit-font-smoothing:antialiased;">
            <p style="margin:0 0 14px 0; text-indent:0; padding-left:0;"><strong>1. 수집하는 개인정보 항목</strong><br>
            이름, 생년월일, 보호자 정보(등록 시), 타이핑 리듬 데이터(키 입력 간격, 정지·백스페이스 횟수 등),
            게임 반응 속도 데이터가 수집됩니다.</p>
            <p style="margin:0 0 14px 0; text-indent:0; padding-left:0;"><strong>2. 수집·이용 목적</strong><br>
            파킨슨병 초기 신호 선별 보조를 위한 리듬 분석, 연령대별 기준 비교, 보호자와의 리포트 공유,
            서비스 품질 개선에 활용됩니다.</p>
            <p style="margin:0 0 14px 0; text-indent:0; padding-left:0;"><strong>3. 보유 및 이용 기간</strong><br>
            데모 버전에서는 모든 데이터가 세션 내에서만 유지되며, 새로고침 시 즉시 파기됩니다.
            서버 저장이나 제3자 제공은 없습니다.</p>
            <p style="margin:0; text-indent:0; padding-left:0;"><strong>4. 동의 거부 권리 및 불이익</strong><br>
            동의하지 않을 권리가 있으며, 동의하지 않을 경우 힐링레터 서비스 이용이
            제한될 수 있습니다.</p>
            </div>
            ''', unsafe_allow_html=True)

        st.markdown('<div style="margin-top:-14px;"></div>', unsafe_allow_html=True)

        # 🆕 "확인하고 시작하기" 버튼 — 별도 동의 팝업 없이 바로 다음 단계(이름 입력)로 이동
        if st.button(L("ob0_btn"), use_container_width=True, type="primary", key="ob0_confirm"):
            ss.privacy_agreed = True
            ss.onboard_step = 1
            st.rerun()

    elif step == 1:
        st.markdown(
            '<style>#ob1-sub-box, #ob1-sub-box * { word-break: keep-all !important; '
            'overflow-wrap: normal !important; word-wrap: normal !important; '
            '-webkit-hyphens: none !important; hyphens: none !important; '
            'line-break: strict !important; }</style>'
            '<div class="screen-title" style="font-family:var(--font-serif); '
            'font-size:calc(23px + var(--font-offset)); font-weight:700; line-height:1.4; '
            'margin:0 0 16px 0; color:var(--ink); text-align:left;">' + L("ob1_title") + '</div>'
            '<div id="ob1-sub-box" class="screen-sub" style="white-space:normal !important; '
            'text-align:left !important; letter-spacing:normal !important; '
            'word-spacing:normal !important; text-justify:none !important;">'
            + L("ob1_sub") + '</div>', unsafe_allow_html=True)
        name = st.text_input(L("ob1_name"), value="", max_chars=10,
                             placeholder=L("ob1_ph"), key="ob_name")
        c1, c2 = st.columns([1, 2])
        with c1:
            if st.button(L("common_prev"), use_container_width=True, key="ob1_back"):
                ss.onboard_step = 0
                st.rerun()
        with c2:
            if st.button(L("common_next"), use_container_width=True, type="primary",
                         disabled=not name.strip()):
                ss.name = name.strip()
                ss.onboard_step = 2
                st.rerun()

    elif step == 2:
        st.markdown(
            '<style>#ob2-sub-box, #ob2-sub-box * { word-break: keep-all !important; '
            'overflow-wrap: normal !important; word-wrap: normal !important; '
            '-webkit-hyphens: none !important; hyphens: none !important; '
            'line-break: strict !important; }</style>'
            '<div class="screen-title" style="font-family:var(--font-serif); '
            'font-size:calc(23px + var(--font-offset)); font-weight:700; line-height:1.4; '
            'margin:0 0 16px 0; color:var(--ink); text-align:left;">' + L("ob2_title") + '</div>'
            '<div id="ob2-sub-box" class="screen-sub" style="white-space:normal !important; '
            'text-align:left !important; letter-spacing:normal !important; '
            'word-spacing:normal !important; text-justify:none !important;">'
            + L("ob2_sub") + '</div>', unsafe_allow_html=True)
        years = [str(y) for y in range(datetime.now().year, 1929, -1)]
        months = [f"{m:02d}" for m in range(1, 13)]
        days = [f"{d:02d}" for d in range(1, 32)]
        c1, c2, c3 = st.columns(3)
        y = c1.selectbox(L("ob2_y"), years, key="ob_year")
        m = c2.selectbox(L("ob2_m"), months, key="ob_month")
        d = c3.selectbox(L("ob2_d"), days, key="ob_day")
        b1, b2 = st.columns([1, 2])
        with b1:
            if st.button(L("common_prev"), use_container_width=True, key="ob2_back"):
                ss.onboard_step = 1
                st.rerun()
        with b2:
            if st.button(L("common_next"), use_container_width=True, type="primary", key="ob2_next"):
                ss.birth = {"year": y, "month": m, "day": d}
                ss.onboard_step = 3
                st.rerun()

    elif step == 3:
        st.markdown(
            '<div class="screen-title" style="font-family:var(--font-serif); '
            'font-size:calc(23px + var(--font-offset)); font-weight:700; line-height:1.4; '
            'margin:0 0 16px 0; color:var(--ink); text-align:left;">' + L("ob3_title") + '</div>'
            '<div class="screen-sub">' + L("ob3_sub") + '</div>', unsafe_allow_html=True)
        seg1, seg2 = st.columns(2)
        if seg1.button("O (등록할게요)", use_container_width=True,
                       type="primary" if ss.guardian_choice == "O" else "secondary", key="gc_o"):
            ss.guardian_choice = "O"
            st.rerun()
        if seg2.button("X (혼자 쓸게요)", use_container_width=True,
                       type="primary" if ss.guardian_choice == "X" else "secondary", key="gc_x"):
            ss.guardian_choice = "X"
            st.rerun()

        if ss.guardian_choice == "O":
            gname = st.text_input("보호자 성명", placeholder="최소 2글자 이상 (예: 이보검)", key="ob_gname")
            gage = st.text_input("보호자 나이", placeholder="예: 35", key="ob_gage")
            mode = st.radio("연락처 수단", ["전화번호", "이메일"], horizontal=True, key="ob_gmode")
            mode_key = "phone" if mode == "전화번호" else "email"
            ph = "예: 010-1234-5678" if mode_key == "phone" else "예: healing@example.com"
            gcontact = st.text_input("연락처", placeholder=ph, key="ob_gcontact")
            valid = validate_guardian(gname.strip(), gage.strip(), gcontact.strip(), mode_key)
            b1, b2 = st.columns([1, 2])
            with b1:
                if st.button("이전", use_container_width=True, key="ob3_back"):
                    ss.onboard_step = 2
                    st.rerun()
            with b2:
                if st.button("완료하고 시작하기", use_container_width=True, type="primary",
                             disabled=not valid, key="ob3_done"):
                    ss.guardian = {"registered": True, "name": gname.strip(), "age": gage.strip(),
                                   "contactType": mode_key, "contact": gcontact.strip()}
                    ss.logged_in = True
                    st.toast(f"{ss.name}님, 환영합니다!")
                    st.rerun()
        else:
            st.markdown(
                '<style>#ob3-noguardian-box, #ob3-noguardian-box * { word-break: keep-all !important; '
                'overflow-wrap: normal !important; word-wrap: normal !important; '
                '-webkit-hyphens: none !important; hyphens: none !important; '
                'line-break: strict !important; }</style>'
                '<div class="card" style="background:rgba(194,132,42,.08);border-color:rgba(194,132,42,.2);">'
                '<div id="ob3-noguardian-box" style="font-size:calc(12.5px + var(--font-offset));line-height:1.6;color:var(--ink-2); '
                'white-space:normal !important; text-align:left !important; '
                'letter-spacing:normal !important; word-spacing:normal !important; '
                'text-justify:none !important;">'
                '보호자를 등록하지 않으셔도 괜찮아요.<br><br>매일 작성하시는 기록은 일기 형식으로 안전하게 '
                '축적되며, 추후 <strong>[리포트]</strong> 탭에서 변화를 확인하시거나 '
                '<strong>인쇄하여 병원 진료 시 활용</strong>하실 수 있습니다.</div></div>',
                unsafe_allow_html=True)
            ack = st.checkbox("안내 사항을 확인했습니다.", key="ob_noguardian_ack")
            b1, b2 = st.columns([1, 2])
            with b1:
                if st.button("이전", use_container_width=True, key="ob3x_back"):
                    ss.onboard_step = 2
                    st.rerun()
            with b2:
                if st.button("완료하고 시작하기", use_container_width=True, type="primary",
                             disabled=not ack, key="ob3x_done"):
                    ss.guardian = {"registered": False, "name": "", "age": "",
                                   "contactType": "phone", "contact": ""}
                    ss.logged_in = True
                    st.toast(f"{ss.name}님, 환영합니다!")
                    st.rerun()


# ============================================================
# 모달들 (st.dialog)
# ============================================================
@st.dialog("내 정보 변경")
def dlg_my_info():
    st.markdown('<div class="screen-sub">이름과 생년월일을 수정할 수 있습니다.<br>'
                '<strong style="color:var(--coral-dark);">※ 정보 변경은 월 1회만 가능합니다.</strong></div>',
                unsafe_allow_html=True)
    n = st.text_input("이름", value=ss.name, key="mi_name")
    c1, c2, c3 = st.columns(3)
    y = c1.text_input("년(YYYY)", value=ss.birth["year"], key="mi_year")
    m = c2.text_input("월(MM)", value=ss.birth["month"], key="mi_month")
    d = c3.text_input("일(DD)", value=ss.birth["day"], key="mi_day")
    if st.button("저장하기", type="primary", use_container_width=True, key="mi_save"):
        if not (n.strip() and y.strip() and m.strip() and d.strip()):
            st.toast("이름과 생년월일을 모두 정확히 입력해 주세요.")
            return
        ss.name = n.strip()
        ss.birth = {"year": y.strip(), "month": m.strip(), "day": d.strip()}
        ss.last_info_update = datetime.now()
        st.toast("내 정보가 성공적으로 저장되었습니다.")
        st.rerun()


@st.dialog("보호자 관리")
def dlg_guardian():
    is_reg = ss.guardian["registered"]
    st.markdown(f'<div class="screen-sub">{"보호자 정보를 변경합니다." if is_reg else "보호자 정보를 입력해 주세요. 등록 시 자동 알림 등에 활용됩니다."}</div>',
                unsafe_allow_html=True)
    n = st.text_input("보호자 성명", value=ss.guardian["name"] if is_reg else "",
                      placeholder="최소 2글자 이상 (예: 이보검)", key="gd_name")
    a = st.text_input("보호자 나이", value=ss.guardian["age"] if is_reg else "", placeholder="예: 35",
                      key="gd_age")
    default_mode = 0 if (not is_reg or ss.guardian["contactType"] == "phone") else 1
    mode = st.radio("연락처 수단", ["전화번호", "이메일"], horizontal=True, index=default_mode,
                    key="gd_mode")
    mode_key = "phone" if mode == "전화번호" else "email"
    ph = "예: 010-1234-5678" if mode_key == "phone" else "예: healing@example.com"
    c = st.text_input("연락처", value=ss.guardian["contact"] if is_reg else "", placeholder=ph,
                      key="gd_contact")

    valid = validate_guardian(n.strip(), a.strip(), c.strip(), mode_key)
    if st.button("저장하기", type="primary", use_container_width=True, disabled=not valid,
                 key="gd_save"):
        new = not ss.guardian["registered"]
        ss.guardian = {"registered": True, "name": n.strip(), "age": a.strip(),
                       "contactType": mode_key, "contact": c.strip()}
        st.toast("새로운 보호자가 등록되었습니다." if new else "보호자 정보가 변경되었습니다.")
        st.rerun()

    if is_reg:
        st.divider()
        ack = st.checkbox("안내 사항을 확인했으며, 보호자 정보를 삭제하는 것에 동의합니다.", key="gd_del_ack")
        if st.button("보호자 삭제", use_container_width=True, disabled=not ack, key="gd_del"):
            ss.guardian = {"registered": False, "name": "", "age": "", "contactType": "phone", "contact": ""}
            st.toast("보호자 정보가 삭제되었습니다.")
            st.rerun()


@st.dialog("데이터 초기화 및 개인정보 파기 안내")
def dlg_reset():
    st.markdown(
        '<div class="screen-sub">초기화를 진행할 경우, 지금까지 기록된 <strong>모든 리듬 분석 데이터</strong>와 '
        '설정하신 <strong>개인정보</strong>가 영구적으로 파기됩니다. 복구할 수 없습니다.</div>',
        unsafe_allow_html=True)
    ack = st.checkbox("안내 사항을 모두 확인했으며, 모든 개인정보 및 데이터가 영구히 삭제됨에 동의합니다.", key="rst_ack")
    if st.button("초기화 진행", use_container_width=True, disabled=not ack, key="rst_go"):
        keep_keys = set(st.session_state.keys())
        for k in list(keep_keys):
            del st.session_state[k]
        st.toast("모든 데이터가 파기되었습니다.")
        st.rerun()

@st.dialog("개인정보 수집·이용 동의")
def dlg_privacy_consent():
    st.markdown('''
    <div style="font-size:13.5px; line-height:1.7; color:var(--ink); max-height:360px; overflow-y:auto; padding-right:6px;">
    <p><strong>1. 수집하는 개인정보 항목</strong><br>
    이름, 생년월일, 보호자 성명·나이·연락처(등록 시), 타이핑 리듬 데이터(키 입력 간격, 정지 횟수, 백스페이스 횟수 등),
    게임 반응 속도 데이터가 수집됩니다.</p>
    <p><strong>2. 수집·이용 목적</strong><br>
    파킨슨병 초기 신호 선별 보조를 위한 리듬 분석, 연령대별 기준 데이터 비교, 보호자와의 리포트 공유,
    서비스 이용 통계 및 품질 개선에 활용됩니다.</p>
    <p><strong>3. 보유 및 이용 기간</strong><br>
    본 데모 버전에서는 모든 데이터가 세션 내에서만 유지되며, 새로고침 시 즉시 파기됩니다.
    별도의 서버 저장이나 제3자 제공은 이루어지지 않습니다.</p>
    <p><strong>4. 동의 거부 권리 및 불이익</strong><br>
    개인정보 수집·이용에 동의하지 않을 권리가 있으며, 동의하지 않을 경우 힐링레터 서비스 이용이
    제한될 수 있습니다.</p>
    <p style="color:var(--text-ink-dim); font-size:12px;">
    ※ 본 서비스는 의료기기가 아니며 의학적 진단을 내리지 않습니다. 자세한 사항은 [정보] 탭의
    의료 고지사항을 참고해 주세요.</p>
    </div>
    ''', unsafe_allow_html=True)

    st.divider()
    ack = st.checkbox("위 개인정보 수집·이용 동의 내용을 모두 확인했으며 이에 동의합니다.",
                       key="privacy_dlg_ack")
    if st.button("동의하고 다음으로", type="primary", use_container_width=True,
                 disabled=not ack, key="privacy_dlg_confirm"):
        ss.privacy_agreed = True
        ss.onboard_step = 1          # 🆕 동의 즉시 온보딩 1단계(이름 입력)로 이동
        st.toast("개인정보 수집·이용에 동의하셨습니다.")
        st.rerun()
        
# ============================================================
# ⋯ 메뉴 (앱 공유 / 언어 변경)
# ============================================================
@st.dialog(" ")
def dlg_menu():
    st.markdown(f'<div class="screen-title" style="margin-bottom:12px;">{L("menu_title")}</div>',
                unsafe_allow_html=True)

    # 앱 공유
    if st.button("🔗 " + L("menu_share"), use_container_width=True, key="menu_share_btn"):
        ss._open_share = True
        st.rerun()

    st.markdown('<div style="margin:10px 0 6px; font-size:12px; color:var(--text-ink-dim);">'
                + L("menu_lang") + '</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button(L("lang_ko"), use_container_width=True,
                 type="primary" if ss.lang == "ko" else "secondary", key="menu_lang_ko"):
        ss.lang = "ko"
        st.rerun()
    if c2.button(L("lang_en"), use_container_width=True,
                 type="primary" if ss.lang == "en" else "secondary", key="menu_lang_en"):
        ss.lang = "en"
        st.rerun()


@st.dialog(" ")
def dlg_share():
    st.markdown(f'<div class="screen-title" style="margin-bottom:8px;">{L("share_title")}</div>',
                unsafe_allow_html=True)
    st.markdown(f'<div class="screen-sub">{L("share_desc")}</div>', unsafe_allow_html=True)
    st.text_input(L("share_url_label"), value="http://localhost:8501", key="share_url_field")
    st.caption("Streamlit Cloud: https://share.streamlit.io")


@st.dialog(" ")
def dlg_profile_photo():
    st.markdown(f'<div class="screen-title" style="margin-bottom:10px;">{L("my_photo_upload")}</div>',
                unsafe_allow_html=True)
    if ss.get("profile_photo"):
        st.markdown(
            f'<div style="text-align:center;margin-bottom:12px;">'
            f'<img src="{ss.profile_photo}" style="width:96px;height:96px;object-fit:cover;'
            f'border-radius:50%;border:1px solid rgba(42,33,24,.1);"/></div>',
            unsafe_allow_html=True)
    up = st.file_uploader(L("my_photo_upload"), type=["png", "jpg", "jpeg", "webp"],
                          key="profile_uploader_dlg", label_visibility="collapsed")
    if up is not None:
        import base64
        mime = up.type or "image/png"
        b64 = base64.b64encode(up.getvalue()).decode()
        new_photo = f"data:{mime};base64,{b64}"
        if new_photo != ss.get("profile_photo"):
            ss.profile_photo = new_photo
            st.toast("프로필 사진이 변경되었습니다.")
            st.rerun()
    if ss.get("profile_photo"):
        if st.button(L("my_photo_reset"), key="profile_reset_dlg", use_container_width=True):
            ss.profile_photo = None
            st.rerun()

@st.dialog("내 정보 변경")
def dlg_edit_info_menu():
    st.markdown('<div class="screen-sub">변경하실 항목을 선택해 주세요.</div>',
                unsafe_allow_html=True)
    # 🆕 사진이 한 번도 업로드된 적 없으면 "사진 추가", 이미 있으면 "사진 추가 및 변경"
    photo_btn_label = "📷 사진 추가 및 변경" if ss.get("profile_photo") else "📷 사진 추가"
    if st.button(photo_btn_label, use_container_width=True, key="editmenu_photo"):
        ss._open_photo_dialog = True
        st.rerun()
    if st.button("✏️ 이름·생년월일 변경", use_container_width=True, key="editmenu_info"):
        ss._open_info_dialog = True
        st.rerun()
        
# ============================================================
# 화면들
# ============================================================
def status_bar():
    d = datetime.now()
    logo_html = (f'<img src="data:image/png;base64,{LOGO_B64}" class="hl-logo-img" alt="PA트라슈"/>'
                 if LOGO_B64 else '<span class="hl-logo-text">파트라슈</span>')

    # 1행: 로고(왼쪽) ── 시계(오른쪽) / 2행: (빈 공간) ── 점(...) 은 시계 바로 아래
    st.markdown(
        f'''
        <div class="hl-topbar-grid">
            <div class="hl-topbar-logo">{logo_html}</div>
            <div class="hl-topbar-clock">{clock_span()}</div>
            <div class="hl-topbar-spacer"></div>
            <div class="hl-topbar-dots-slot"></div>
        </div>
        ''',
        unsafe_allow_html=True
    )

    # ⋯ 를 실제 메뉴 버튼으로 (점 자리에 겹쳐 표시)
    st.markdown("""
    <style>
    .st-key-topbar_menu button{
        background:transparent !important; border:none !important; box-shadow:none !important;
        color:var(--text-ink-dim) !important; font-size:20px !important; line-height:1 !important;
        padding:0 !important; min-height:28px !important; height:28px !important;
        margin-top:-30px !important;
    }
    .st-key-topbar_menu button:hover{ color:var(--honey-dark) !important; transform:none !important; }
    div[data-testid="stHorizontalBlock"]:has(.st-key-topbar_menu){
        justify-content:flex-end !important;
    }
    </style>
    """, unsafe_allow_html=True)
    c_spacer, c_menu = st.columns([5, 1])
    with c_menu:
        if st.button("⋯", key="topbar_menu", help="메뉴 / Menu"):
            dlg_menu()

    # 공유 다이얼로그 열기 요청 처리
    if ss.get("_open_share"):
        ss._open_share = False
        dlg_share()
    inject_live_clock()

def screen_home():
    streak = len(ss.letters)
    sub = (L("home_sub_has", n=streak) if streak > 0 else L("home_sub_none"))
    st.markdown(f'<div class="greeting" style="font-family:var(--font-serif); '
                f'font-size:calc(23px + var(--font-offset)); font-weight:700; line-height:1.4; '
                f'margin:0 0 16px 0; color:var(--ink); text-align:left;">'
                f'{L("home_greeting", name=ss.name)}</div>'
                f'<div class="greeting-sub">{sub}</div>', unsafe_allow_html=True)

    img_b64 = _load_letter_img_b64(ss.get("daily_letter_img"))
    img_html = (
        f'<img src="data:image/png;base64,{img_b64}" '
        f'style="width:100%; max-height:180px; object-fit:cover; '
        f'border-radius:14px; display:block; margin:8px 0 12px;" />'
    ) if img_b64 else ""

    st.markdown(
        f'<div class="envelope-hero" style="padding-bottom: 12px;"><div class="et" style="font-size: 30px; font-weight: 800;">{L("home_env_title")}</div>'
        f'{img_html}'
        f'<div class="es" style="position: relative; font-size: 28px; font-weight: 700; line-height: 1.6; '
        f'font-style: italic; margin: 25px 20px 10px 20px; padding: 0 45px; text-align:center; word-break:keep-all !important; '
        f'overflow-wrap:normal !important; white-space:normal !important;">'
        f'<span style="position: absolute; top: -10px; left: -20px; font-size: 900px; color: #C2842A; font-family: serif; line-height: 1;">&ldquo;</span>'
        f'<span style="position: relative; z-index: 2;">{ss.daily_letter_msg}</span>'
        f'<span style="position: absolute; top: -10px; right: -20px; font-size: 900px; color: #C2842A; font-family: serif; line-height: 1;">&rdquo;</span>'
        f'</div></div>', unsafe_allow_html=True)

    if st.button(L("home_letter_btn"), type="primary", use_container_width=True, key="home_letter"):
        goto("letter")
        st.rerun()

    # 최근 문자 점수 추이
    if ss.letters:
        try:
            band = logic.band_for(ss.letters[-1]["score"])
            chip = charts.chip_html(band)
        except:
            chip = '<span class="chip watch">기록 있음</span>'
    else:
        chip = '<span class="chip watch">기록 없음</span>'
    
    scores = [l["score"] for l in ss.letters]
    try:
        spark = charts.sparkline(scores if scores else [70, 70, 70])
    except:
        spark = "<div>추이 데이터 로딩 중</div>"
        
    st.markdown(f'<div class="card"><div class="row" style="margin-bottom:8px;">'
                f'<span class="label">{L("home_trend")}</span>{chip}</div>{spark}</div>',
                unsafe_allow_html=True)

    QUICK_CARD_CSS = f"""
    <style>
    .st-key-qc_game button, .st-key-qc_report button {{
        background: #fbf7ee !important;
        border: none !important;
        border-radius: 16px !important;
        padding: 14px 12px !important;
        min-height: 84px !important;
        height: auto !important;
        max-height: none !important;
        overflow: visible !important;
        text-overflow: unset !important;
        white-space: pre-line !important;
        text-align: left !important;
        line-height: 1.5 !important;
        color: #1e1e1e !important;
        box-shadow: none !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: flex-start !important;
        justify-content: flex-start !important;
    }}
    .st-key-qc_game button::before,
    .st-key-qc_report button::before {{
        content: '' !important;
        display: block !important;
        width: 30px !important;
        height: 30px !important;
        margin-bottom: 8px !important;
        background-size: contain !important;
        background-repeat: no-repeat !important;
        background-position: left center !important;
    }}
    .st-key-qc_game button::before {{
        background-image: url("data:image/png;base64,{ICON_DOG_B64}") !important;
    }}
    .st-key-qc_report button::before {{
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23c2841a' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3 15l4.5-5 3.5 3 6-7'/%3E%3Cpath d='M13 6h4v4'/%3E%3Cpath d='M3 19h18'/%3E%3C/svg%3E") !important;
    }}
    .st-key-qc_game button p, .st-key-qc_report button p {{
        margin: 0 !important;
        font-weight: 400 !important;
        font-size: calc(12.5px + {ss.font_level}pt) !important;
        color: #767676 !important;
    }}
    .st-key-qc_game button p::first-line,
    .st-key-qc_report button p::first-line {{
        font-weight: 700 !important;
        font-size: calc(14.5px + {ss.font_level}pt) !important;
        color: #1e1e1e !important;
    }}
    </style>
    """
    st.markdown(QUICK_CARD_CSS, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button(L("home_game"), use_container_width=True, key="qc_game"):
            goto("game")
            st.rerun()
    with c2:
        if st.button(L("home_report"), use_container_width=True, key="qc_report"):
            goto("report")
            st.rerun()
    
def screen_letter():
    if st.button("← 오늘의 힐링레터", key="letter_back"):
        goto("home")
        st.rerun()

    already = (ss.last_letter_date == today_str())

    msg = ss.daily_letter_msg

    if already:
        msg = "오늘의 편지를 이미 작성하셨어요. 내일 다시 새로운 편지로 만나요!"

    st.markdown(
        f'<div class="letter-msg" style="margin-bottom: 20px; font-size: 19px; '
        f'font-weight: 600; line-height: 1.7;">{msg}</div>',
        unsafe_allow_html=True
    )
    
    if not KEYSTROKE_AVAILABLE:
        st.warning("키 입력 캡처 컴포넌트(components/keystroke)를 찾지 못했어요. "
                   "편지 입력·분석 기능이 비활성화됩니다. 폴더 구성을 확인해 주세요.")

    letter_result = keystroke_letter(
        date_label=today_str(),
        letter_message=msg,
        already_done=already,
        font_offset=ss.font_level,
        reset_nonce=ss.letter_nonce,
        key=f"keystroke_letter_{ss.letter_nonce}"
    )
    if letter_result and letter_result.get("submitId") != ss.get("last_submit_id"):
        ss.last_submit_id = letter_result.get("submitId")

        features = letter_result.get("features")

        # 점수 출처는 ML 하나로 통일한다.
        # rhythmScore(휴리스틱)는 스케일이 다른 별개 지표이므로 절대 'score' 자리에 넣지 않고
        # 참고용 메타데이터로만 저장한다. features 가 없으면 ML 계산 불가 → 중립 50.
        if features:
            ml_score = logic.predict_parkinson(features)
        else:
            ml_score = 50  # 캡처 실패 시 중립값 (리듬점수로 대체하지 않음)

        ss.letters.append({
            "t": datetime.now(),
            "score": ml_score,                                        # ← ML 점수 (유일한 공식 점수)
            "rhythmScore": letter_result.get("rhythmScore", 0),       # 참고용
            "rawRhythmScore": letter_result.get("rawRhythmScore", 0), # 참고용
            "avgFlight": letter_result.get("avgInterval", 0),
            "cv": letter_result.get("cv", 0),
            "pauseCount": letter_result.get("pauseCount", 0),
            "backspaceCount": letter_result.get("backspaceCount", 0),
            "features": features,
            "text": letter_result.get("text", ""),                    # ← 답장 본문 저장 (보관함 표시용)
            "letter_msg": msg,
        })

        ss.last_letter_date = today_str()
        st.toast(f"분석 점수 {ml_score}점이 저장되었어요.")
        st.rerun()

    st.markdown('<div style="margin-top:8px;"></div>', unsafe_allow_html=True)
    st.markdown("""
    <style>
    .st-key-letter_to_report button:disabled {
        background: #e6ddcc !important;
        color: #b3a58f !important;
        opacity: 1 !important;
        border: none !important;
    }
    </style>
    """, unsafe_allow_html=True)
    if st.button("📊 리포트 보러가기", type="primary", use_container_width=True,
                 key="letter_to_report", disabled=not already):
        ss.report_seg = "letter"
        goto("report")
        st.rerun()

def screen_game():
    st.markdown(
        '<div class="screen-title" style="font-family:var(--font-serif); '
        'font-size:calc(23px + var(--font-offset)); font-weight:700; line-height:1.4; '
        'margin:0 0 16px 0; color:var(--ink); text-align:left;">🚪 멍멍 우체부</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="screen-sub">시작 버튼을 누르면 타이머가 작동합니다. '
        '열리는 칸을 정확하게 터치해 주세요!</div>',
        unsafe_allow_html=True
    )
    
    if not ss.game_playing:
        if GAME_BANNER_B64:
            st.markdown(
                f'<div style="border-radius:12px; overflow:hidden; margin-bottom:16px;">'
                f'<img src="data:image/{GAME_BANNER_EXT};base64,{GAME_BANNER_B64}" '
                f'style="width:100%; display:block; object-fit:cover;" /></div>',
                unsafe_allow_html=True
            )
        else:
            st.warning(f"배너 이미지를 찾지 못했습니다. {BASE_DIR} 폴더 파일 목록: {os.listdir(BASE_DIR)}")
            st.markdown('''
            <div style="background:rgba(0,0,0,0.02); padding:24px; border-radius:12px; text-align:center; margin-bottom:16px;">
                <p style="font-size:15px; color:#444; font-weight:bold;">시작 버튼을 누르면 타이머가 작동합니다.<br>열리는 칸을 정확하게 터치해 주세요!</p>
            </div>
            ''', unsafe_allow_html=True)
        
        if st.button("🎮 게임 시작하기 (타이머 시작)", type="primary", use_container_width=True):
            ss.game_playing = True
            ss.game_step = 0
            ss.game_miss_count = 0 
            
            # 비행 시간 측정용 변수 초기화
            ss.game_last_click_time = time.time()
            ss.game_flight_times = []
            
            seq = list(range(9))
            random.shuffle(seq)
            ss.game_sequence = seq
            
            ss.game_grid = [0] * 9
            first_target = ss.game_sequence[0]
            ss.game_grid[first_target] = 1  
            
            ss.game_start_time = time.time()
            st.rerun()
            
    else:
        elapsed_now = time.time() - ss.game_start_time
        
        col_status_1, col_status_2 = st.columns(2)
        col_status_1.metric("진행 상황", f"{ss.game_step} / 9 완료")
        col_status_2.metric("실수(오터치) 횟수", f"{ss.game_miss_count}회")
        
        st.markdown(f"<p style='text-align:right; font-size:13px; color:#666;'>현재 측정 시간: <b>{elapsed_now:.2f}초</b></p>", unsafe_allow_html=True)
        st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
        
        # 🔒/🔓 이미지 URL (닫힘 / 열림)
        DOOR_CLOSED_IMG = "https://i.postimg.cc/LX5tLksL/wanjeon-dadhim.png"
        DOOR_OPEN_IMG   = "https://i.postimg.cc/3wHfXqMj/wanjeon-opeun.png"

        # 각 버튼의 key(grid_direct_btn_0 ~ 8)를 기준으로 배경 이미지를 입혀주는 CSS 주입
        door_css_rules = []
        for i in range(9):
            img = DOOR_OPEN_IMG if ss.game_grid[i] == 1 else DOOR_CLOSED_IMG
            door_css_rules.append(f"""
            .st-key-grid_direct_btn_{i} button,
            .st-key-grid_direct_btn_{i} button:hover,
            .st-key-grid_direct_btn_{i} button:active,
            .st-key-grid_direct_btn_{i} button:focus,
            .st-key-grid_direct_btn_{i} button:focus:not(:active) {{
                background-image: url('{img}') !important;
                background-size: contain !important;
                background-position: center !important;
                background-repeat: no-repeat !important;
                background-color: #f3ece2 !important;
                color: transparent !important;
                text-indent: -9999px;
                width: 100% !important;
                height: 220px !important;
                min-height: unset !important;
                max-height: unset !important;
                border-radius: 12px !important;
                border: none !important;
                box-shadow: none !important;
                transition: transform 0.12s ease !important;
            }}
            .st-key-grid_direct_btn_{i} button:hover {{
                transform: scale(1.05) !important;
            }}
            .st-key-grid_direct_btn_{i} button:active {{
                transform: scale(0.95) !important;
            }}
            """)
            
        st.markdown(f"<style>{''.join(door_css_rules)}</style>", unsafe_allow_html=True)
        
        for row in range(3):
            cols = st.columns(3)
            for col in range(3):
                idx = row * 3 + col
                status = ss.game_grid[idx]
                
                # 텍스트는 CSS로 숨겨지므로 공백 라벨만 전달
                btn_label = " "
                
                if cols[col].button(btn_label, key=f"grid_direct_btn_{idx}", use_container_width=True):
                    if status == 1: 
                        # 정답 클릭 시 비행 시간 기록
                        current_time = time.time()
                        flight_time = current_time - ss.game_last_click_time
                        ss.game_flight_times.append(flight_time)
                        ss.game_last_click_time = current_time

                        ss.game_grid[idx] = 0
                        ss.game_step += 1
                        
                        if ss.game_step >= 9:
                            end_time = time.time()
                            total_duration = round(end_time - ss.game_start_time, 2)
                            ss.game_playing = False
                            
                            # 비행 시간 평균 계산
                            avg_flight_time = sum(ss.game_flight_times) / len(ss.game_flight_times) if ss.game_flight_times else 0.0

                            ss.games.append({
                                "t": datetime.now(),
                                "duration": total_duration,        
                                "miss": ss.game_miss_count,        
                                "score": total_duration,
                                "avg_flight": round(avg_flight_time, 2)
                            })
                            ss.last_game_id = datetime.now().timestamp()
                            st.success(f"🎉 게임 완료! 소요 시간: 총 【 {total_duration}초 】 / 실수: 【 {ss.game_miss_count}회 】")
                            goto("report") 
                            st.rerun()
                        else:
                            next_target = ss.game_sequence[ss.game_step]
                            ss.game_grid[next_target] = 1
                            st.rerun()
                    else: 
                        ss.game_miss_count += 1
                        st.toast("틀렸습니다! 다른 칸(닫힌 문)을 터치하셨어요.", icon="⚠️")
                        st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("⏹️ 게임 중단하기", use_container_width=True):
            ss.game_playing = False
            st.rerun()

    if st.button("홈으로 돌아가기", use_container_width=True, key="game_to_home"):
        goto("home")
        st.rerun()


def screen_report():
    st.markdown('<div class="report-title-section" style="font-family:var(--font-serif); '
                'font-size:calc(23px + var(--font-offset)); font-weight:700; line-height:1.4; '
                'margin:0 0 16px 0; color:var(--ink); text-align:left;">변화 리포트</div>', unsafe_allow_html=True)
    st.markdown('<div class="report-sub-section">기록이 쌓일수록 더 의미 있는 추세를 볼 수 있어요.</div>', unsafe_allow_html=True)
    
    seg_c1, seg_c2 = st.columns(2)
    if seg_c1.button("편지 문자", use_container_width=True, type="secondary" if ss.report_seg == "game" else "primary"):
        ss.report_seg = "letter"
        st.rerun()
    if seg_c2.button("멍멍 우체부", use_container_width=True, type="primary" if ss.report_seg == "game" else "secondary"):
        ss.report_seg = "game"
        st.rerun()
        
    sample_active = st.checkbox("예시 데이터로 추세 미리보기 (실제 기록 아님)", value=ss.sample_toggle, key="sample_chk")
    ss.sample_toggle = sample_active
    
    # 데이터 매핑 및 라벨 설정 분기 처리 (탭 게임 시 항목 변경 적용)
    label_html ="" 
    if ss.report_seg == "game":
        label_1, label_2, label_3 = "게임 소요시간", "동작 소요 시간", "오답 갯수"
        
        if sample_active:
            data_source = [8.5, 7.9, 8.2, 6.8, 5.9, 6.1, 5.3, 4.8]  
            flight_source = [0.9, 0.85, 0.88, 0.72, 0.65, 0.68, 0.58, 0.52]
            all_misses = [1, 2, 0, 1, 0, 0, 1, 0]
            avg_miss_str = f"{all_misses[-1]}회"
        
        else:
            data_source = [g["duration"] for g in ss.games]
            flight_source = [g.get("avg_flight", 0.0) for g in ss.games]
            all_misses = [g["miss"] for g in ss.games]
            avg_miss_str = f"{all_misses[-1]}회" if all_misses else "-"
            
        if data_source:
            val_1 = f"{round(data_source[-1], 2)}초"   # 🆕 평균이 아닌, 직전(최근) 게임 1회 소요 시간
            val_2 = f"{round(sum(flight_source) / len(flight_source), 2)}초"
            val_3 = avg_miss_str
        else:
            val_1, val_2, val_3 = "-", "-", "-"
    else: 
        label_1, label_2, label_3 = "평균 기록", "최고 기록", "기록 일수"
        
        if sample_active:
            data_source = [70, 74, 72, 75, 81, 79, 83]
            days_count = 7
        else:
            data_source = [l["score"] for l in ss.letters]
            days_count = len(set(l["t"].date() for l in ss.letters)) if ss.letters else 0
            
       # [수정된 코드] 점수 라벨 계산 로직 추가 + 점수 → 이모지 이미지로 대체
        if data_source:
            avg_score = round(sum(data_source) / len(data_source))
            val_1 = score_emoji_html(avg_score, size=90)   # 🆕 이모지 크기 확대 (36 → 64)
            label_html = ""   # 🆕 "안정" 등 밴드 라벨 텍스트 제거
            
            val_2 = f"{max(data_source)}점"
            val_3 = f"{days_count}일"
        else:
            val_1, val_2, val_3 = "-", "-", "-"
            label_html = ""
    
    st.markdown(f'''
<div class="summary-container" style="align-items:stretch;">

<div class="summary-card" style="display:flex; flex-direction:column;">
<div class="s-label">{label_1}</div>
<div style="flex:1; display:flex; align-items:center; justify-content:center;">
<div class="summary-card-val" style="font-weight:bold; color:#222;">{val_1}</div>
</div>
{label_html}
</div>
<div class="summary-card" style="display:flex; flex-direction:column;">
<div class="s-label">{label_2}</div>
<div style="flex:1; display:flex; align-items:center; justify-content:center;">
<div class="summary-card-val" style="font-size:60px; font-weight:bold; color:#222; text-align:center;">{val_2}</div>
</div>
</div>
<div class="summary-card" style="display:flex; flex-direction:column;">
<div class="s-label">{label_3}</div>
<div style="flex:1; display:flex; align-items:center; justify-content:center;">
<div class="summary-card-val" style="font-size:60px; font-weight:bold; color:#222; text-align:center;">{val_3}</div>
</div>
</div>
''', unsafe_allow_html=True)

    # 🆕 방금 전(직전) 게임 기록 — 가장 최근 게임 말고 그 이전 기록 (제목 + 내용, 작은 회색 텍스트)
    if ss.report_seg == "game" and len(data_source) >= 2:
        prev_duration = data_source[-2]
        prev_flight = flight_source[-2] if len(flight_source) >= 2 else 0
        prev_miss = all_misses[-2] if len(all_misses) >= 2 else 0
        st.markdown(
            f'<div style="background:rgba(0,0,0,0.03); border-radius:8px; '
            f'padding:6px 8px; margin-top:12px; margin-bottom:32px;">'
            f'<div style="font-size:10px; font-weight:600; color:#999999; margin-bottom:3px;">직전 게임 기록</div>'
            f'<div style="font-size:7px; color:#999999;">'
            f'게임 소요시간: {round(prev_duration, 2)}초 · '
            f'동작 소요 시간: {round(prev_flight, 2)}초 · '
            f'오답 갯수: {prev_miss}회'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    title_text = "멍멍 우체부 완료 소요 시간 추세 (초)" if ss.report_seg == "game" else "편지 문자 점수 추세"
    
    st.markdown(f'<div style="font-size:14px; font-weight:bold; margin-bottom:8px;">{title_text}</div>', unsafe_allow_html=True)
    
    # Altair 적용: X축 자연수 및 가로 고정, 7일 단위 리셋 (탭 게임 시)
    if not data_source:
        st.markdown('<div class="chart-box"><div class="chart-empty">아직 기록이 없어요</div></div>', unsafe_allow_html=True)
    else:
        if ss.report_seg == "game" and not ss.sample_toggle:
            first_date = ss.games[0]["t"].date()
            latest_date = ss.games[-1]["t"].date()
            current_cycle = (latest_date - first_date).days // 7
            
            chart_data = [g["duration"] for g in ss.games if (g["t"].date() - first_date).days // 7 == current_cycle]
            
            if not chart_data:
                st.markdown('<div class="chart-box"><div class="chart-empty">이번 주엔 아직 기록이 없어요</div></div>', unsafe_allow_html=True)
            else:
                df_chart = pd.DataFrame({
                    "회차": [f"{i}회" for i in range(1, len(chart_data) + 1)],
                    "소요 시간 (초)": chart_data
                })
                chart = alt.Chart(df_chart).mark_line(point=True).encode(
                    x=alt.X("회차:O", axis=alt.Axis(labelAngle=0)), 
                    y=alt.Y("소요 시간 (초):Q")
                ).properties(height=200)
                st.altair_chart(chart, use_container_width=True)
        else:
            if ss.report_seg == "game" and ss.sample_toggle:
                df_sample = pd.DataFrame({
                    "회차": [f"{i}회" for i in range(1, len(data_source) + 1)],
                    "소요 시간 (초)": data_source
                })
                chart = alt.Chart(df_sample).mark_line(point=True).encode(
                    x=alt.X("회차:O", axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("소요 시간 (초):Q")
                ).properties(height=200)
                st.altair_chart(chart, use_container_width=True)
            else:
                st.line_chart(data_source, height=200)

    # 🆕 직전 게임 대비 해석 한 줄 (속도 · 정확도 비교)
    if ss.report_seg == "game" and len(data_source) >= 2:
        cur_duration, prev_duration = data_source[-1], data_source[-2]
        cur_miss, prev_miss = all_misses[-1], all_misses[-2]

        speed_up = cur_duration < prev_duration      # 소요 시간이 짧아졌으면 속도 향상
        accuracy_up = cur_miss < prev_miss            # 오답 갯수가 줄었으면 정확도 향상

        if speed_up and accuracy_up:
            insight_text = "지난 게임보다 더 빠르고 정확해졌어요. 아주 좋은 흐름이에요! 👍"
        elif speed_up and not accuracy_up:
            insight_text = "속도는 빨라졌지만 정확도는 조금 아쉬워요. 서두르지 말고 천천히 터치해 보세요."
        elif not speed_up and accuracy_up:
            insight_text = "조금 신중해지면서 정확도는 좋아졌어요. 다음엔 속도도 함께 올려볼까요?"
        else:
            insight_text = "지난 기록보다 조금 아쉬운 결과예요. 잠깐 쉬었다가 다시 도전해보는 것도 좋아요."

        st.markdown(
            f'<div style="background:rgba(194,132,42,0.08); border-radius:10px; '
            f'padding:10px 12px; margin-top:12px; margin-bottom:20px;">'
            f'<div style="font-size:12px; font-weight:700; color:#c2841a; margin-bottom:4px;">🐾 오늘의 해석</div>'
            f'<div style="font-size:13px; color:#5e5446; line-height:1.5;">{insight_text}</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    
    st.markdown("<br>", unsafe_allow_html=True)

    # 탭 게임 리포트 화면일 때만 '게임으로 돌아가기' 버튼 추가
    if ss.report_seg == "game":
        if st.button("🎮 게임으로 돌아가기", use_container_width=True, type="primary"):
            goto("game")
            st.rerun()

                # ---------- 📄 PDF 리포트 다운로드 ----------
    try:
        pdf_bytes = build_report_pdf(
            name=ss.name,
            seg=ss.report_seg,
            letters=ss.letters,
            games=ss.games,
            is_sample=ss.sample_toggle,
        )
        fname = f"힐링레터_리포트_{datetime.now().strftime('%Y%m%d')}.pdf"
        st.download_button(
            "📄 PDF 리포트 저장하기",
            data=pdf_bytes,
            file_name=fname,
            mime="application/pdf",
            use_container_width=True,
        )
    except Exception as e:
        st.caption(f"PDF 생성 중 문제가 발생했어요: {e}")

    if st.button("보호자와 리포트 공유하기", use_container_width=True):
        if ss.guardian["registered"]:
            
            
            st.toast(f"보호자({ss.guardian['name']})님께 리포트 데이터 전송이 완료되었습니다!", icon="✉️")
        else:
            st.error("등록된 보호자가 없습니다. [MY] 탭에서 보호자를 먼저 등록해 주세요.")

def screen_archive():
    st.markdown('<div class="screen-title" style="font-family:var(--font-serif); '
                'font-size:calc(23px + var(--font-offset)); font-weight:700; line-height:1.4; '
                'margin:0 0 16px 0; color:var(--ink); text-align:left;">편지 보관함</div>', unsafe_allow_html=True)

    # 🆕 보관함 캘린더 전용 간격 보정 (전역 gap 축소로 인한 겹침 방지, 다른 화면엔 영향 없음)
    st.markdown("""
    <style>
    .archive-calendar [data-testid="stVerticalBlock"] {
        gap: 1.4rem !important;
    }
    .archive-calendar [data-testid="stHorizontalBlock"] {
        margin-bottom: 10px !important;
        row-gap: 10px !important;
    }
    .archive-calendar [data-testid="column"] {
        padding-bottom: 6px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="archive-calendar">', unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        if st.button("◀", key="prev_m", use_container_width=True):
            if ss.cal_month == 1:
                ss.cal_month = 12
                ss.cal_year -= 1
            else:
                ss.cal_month -= 1
            st.rerun()
    with c2:
        st.markdown(f"<div style='text-align:center; font-family:var(--font-serif); font-size:18px; font-weight:600; padding-top:6px;'>{ss.cal_year}년 {ss.cal_month}월</div>", unsafe_allow_html=True)
    with c3:
        if st.button("▶", key="next_m", use_container_width=True):
            if ss.cal_month == 12:
                ss.cal_month = 1
                ss.cal_year += 1
            else:
                ss.cal_month += 1
            st.rerun()

    st.markdown('<div style="margin-bottom:16px;"></div>', unsafe_allow_html=True)

    days_kor = ["일", "월", "화", "수", "목", "금", "토"]
    cols = st.columns(7)
    for i, d in enumerate(days_kor):
        cols[i].markdown(f"<div style='text-align:center; color:var(--text-ink-dim); font-size:13px; font-weight:600; margin-bottom:14px;'>{d}</div>", unsafe_allow_html=True)

    cal = calendar.Calendar(firstweekday=6)
    month_days = cal.monthdatescalendar(ss.cal_year, ss.cal_month)

    record_map = {}
    for l in ss.letters:
        d_str = l["t"].strftime("%Y-%m-%d")
        if d_str not in record_map:
            record_map[d_str] = []
        record_map[d_str].append(l)

    for week in month_days:
        cols = st.columns(7)
        for i, day in enumerate(week):
            if day.month == ss.cal_month:
                day_str = day.strftime("%Y-%m-%d")
                has_record = day_str in record_map
                is_selected = (day_str == ss.cal_selected)

                btn_type = "primary" if has_record or is_selected else "secondary"

                if has_record:
                    # 🆕 발바닥 워터마크(B안): 크림색 원 위에 진한 발바닥(인라인 SVG) + 흰 숫자
                    #   - SVG viewBox가 발바닥 '큰 패드'를 세로 중앙에 두도록 맞춰져 있어
                    #     숫자가 발가락 사이가 아니라 패드 위에 정확히 얹힘(잘림 방지).
                    #   - 배경색을 셀 크림(#EFE5CE)으로 채우고 border-radius:50% 라 네모 라인이 안 생김.
                    #   - 색 조절: 아래 fill 값(%238F72C0)만 바꾸면 됨. 진하게 %237A5CB0 / 연하게 %23A98FCB
                    PAW_SVG_URI = (
                        "data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20"
                        "viewBox%3D%270%200%2040%2048%27%3E%3Cg%20fill%3D%27%23C18D5B%27%3E"
                        "%3Cellipse%20cx%3D%278%27%20cy%3D%2714%27%20rx%3D%274%27%20ry%3D%275.5%27/%3E"
                        "%3Cellipse%20cx%3D%2716%27%20cy%3D%277%27%20rx%3D%274.5%27%20ry%3D%276%27/%3E"
                        "%3Cellipse%20cx%3D%2727%27%20cy%3D%277%27%20rx%3D%274.5%27%20ry%3D%276%27/%3E"
                        "%3Cellipse%20cx%3D%2735%27%20cy%3D%2714%27%20rx%3D%274%27%20ry%3D%275.5%27/%3E"
                        "%3Cpath%20d%3D%27M21%2013%20C13%2013%208%2019%208%2025%20C8%2032%2014%2035%2021%2035%20"
                        "C28%2035%2034%2032%2034%2025%20C34%2019%2029%2013%2021%2013%20Z%27/%3E%3C/g%3E%3C/svg%3E"
                    )
                    cols[i].markdown(
                        f"""
                        <style>
                        .st-key-cal_{day_str} button {{
                            background-color: #EFE5CE !important;
                            background-image: url("{PAW_SVG_URI}") !important;
                            background-size: 28px auto !important;
                            background-position: center !important;
                            background-repeat: no-repeat !important;
                            color: #FFFFFF !important;
                            font-weight: 700 !important;
                            border: 1px solid rgba(42,33,24,.18) !important;
                            border-radius: 50% !important;
                        }}
                        .st-key-cal_{day_str} button p {{
                            position: relative !important;
                            z-index: 1 !important;
                        }}
                        </style>
                        """,
                        unsafe_allow_html=True
                    )

                if cols[i].button(str(day.day), key=f"cal_{day_str}", use_container_width=True, type=btn_type):
                    ss.cal_selected = day_str
                    st.rerun()
            else:
                cols[i].markdown("<div style='height:36px;'></div>", unsafe_allow_html=True)

    st.markdown('<div style="margin-bottom:16px;"></div>', unsafe_allow_html=True)

    selected_records = record_map.get(ss.cal_selected, [])
    sel_date_obj = datetime.strptime(ss.cal_selected, "%Y-%m-%d")
    
    st.markdown(f"<div style='font-size:15px; font-weight:600; margin-bottom:12px;'>{sel_date_obj.year}년 {sel_date_obj.month}월 {sel_date_obj.day}일 기록</div>", unsafe_allow_html=True)

    if not selected_records:
        st.markdown('<div class="card"><div class="label" style="text-align:center;">이날은 작성된 편지가 없어요.</div></div>', unsafe_allow_html=True)
    else:
        for i, r in enumerate(selected_records):
            time_str = r["t"].strftime("%p %I:%M").replace("AM", "오전").replace("PM", "오후")
            text = r.get("text", "내용을 불러올 수 없습니다.")
            score = r.get("score", 0)
            letter_msg = r.get("letter_msg", "이 기록은 원문 데이터가 없어요.")
            letter_msg_plain = letter_msg.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ")
            preview = letter_msg_plain if len(letter_msg_plain) <= 24 else letter_msg_plain[:24] + "…"

            with st.expander(f"💌 {preview}   ·   {time_str}", expanded=False):
                st.markdown(f'''
                <div style="margin-bottom:14px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                        <span style="font-size:12px; font-weight:600; color:var(--text-ink-dim);">📮 오늘의 힐링레터</span>
                        <span style="font-size:12px; font-weight:600; color:var(--honey-dark); background:rgba(194,132,42,0.1); padding:2px 8px; border-radius:999px;">{score}점</span>
                    </div>
                    <div style="font-size:14px; line-height:1.6; color:var(--ink); white-space:pre-wrap; word-break:keep-all;">{letter_msg}</div>
                </div>
                <div>
                    <div style="font-size:12px; font-weight:600; color:var(--text-ink-dim); margin-bottom:4px;">✍️ 내 답장</div>
                    <div style="font-size:14px; line-height:1.6; color:var(--ink); white-space:pre-wrap; word-break:keep-all;">{text}</div>
                </div>
                ''', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)  # 🆕 archive-calendar 래퍼 닫기

def screen_info():
    st.markdown('<div class="screen-title" style="font-family:var(--font-serif); '
                'font-size:calc(23px + var(--font-offset)); font-weight:700; line-height:1.4; '
                'margin:0 0 16px 0; color:var(--ink); text-align:left;">ℹ️ 정보 및 안내</div>', unsafe_allow_html=True)
    st.markdown('''
    <div style="font-size:13.5px; color:#767676; margin-bottom:20px; line-height:1.6;">
    타이핑 중 발생하는 미세한 속도 변화(CV), 플라이트 타임, 백스페이스 빈도 등은 손가락 운동의 정밀도를 대변합니다.
    본 프로토타입은 해당 리듬 지표를 기반으로 사용자의 리듬 일관성을 점검합니다.
    </div>
    ''', unsafe_allow_html=True)

    # ── 질환 정보 ──
    st.markdown('<div class="my-section-title">질환 정보</div>', unsafe_allow_html=True)
    st.markdown('''
    <div style="display:flex; gap:10px; margin-bottom:16px;">
        <a href="https://www.amc.seoul.kr/asan/healthinfo/disease/diseaseDetail.do?contentId=31800"
           target="_blank" style="flex:1; text-decoration:none;">
            <div class="my-info-card" style="cursor:pointer;">
                <div class="my-info-card-title">주요 증상</div>
                <div class="my-info-card-sub">초기 신호 알아보기</div>
                <div style="margin-top:10px; font-size:12px; color:#c2841a; font-weight:600;">열기 →</div>
            </div>
        </a>
        <a href="https://www.nhs.uk/conditions/parkinsons-disease/causes/"
           target="_blank" style="flex:1; text-decoration:none;">
            <div class="my-info-card" style="cursor:pointer;">
                <div class="my-info-card-title">원인 및 경과</div>
                <div class="my-info-card-sub">질환의 이해</div>
                <div style="margin-top:10px; font-size:12px; color:#c2841a; font-weight:600;">열기 →</div>
            </div>
        </a>
    </div>
    ''', unsafe_allow_html=True)

    # ── 추천 운동 및 관리법 ──
    st.markdown('<div class="my-section-title">추천 운동 및 관리법 (유튜브)</div>', unsafe_allow_html=True)
    st.markdown('''
    <div style="display:flex; flex-direction:column; gap:10px;">
        <a href="https://www.youtube.com/results?search_query=파킨슨+손가락+운동"
           target="_blank" style="text-decoration:none;">
            <div class="my-info-card" style="cursor:pointer;">
                <div class="my-info-card-title">손가락 미세 운동법</div>
                <div class="my-info-card-sub">일상에서 쉽게 따라할 수 있는 손가락 스트레칭 영상을 확인해보세요.</div>
                <div style="margin-top:10px; font-size:12px; color:#c2841a; font-weight:600;">유튜브에서 보기 →</div>
            </div>
        </a>
        <a href="https://www.youtube.com/results?search_query=파킨슨+균형+운동"
           target="_blank" style="text-decoration:none;">
            <div class="my-info-card" style="cursor:pointer;">
                <div class="my-info-card-title">전신 밸런스 유지 운동</div>
                <div class="my-info-card-sub">균형 감각을 유지하는 데 도움이 되는 10분 홈트레이닝입니다.</div>
                <div style="margin-top:10px; font-size:12px; color:#c2841a; font-weight:600;">유튜브에서 보기 →</div>
            </div>
        </a>
    </div>
    ''', unsafe_allow_html=True)


# ============================================================
# 👤 [시안 반영 전면 개편] 마이페이지 화면
# ============================================================
def screen_my():
    # 1. 최상단 마이페이지 타이틀 및 프로필 영역
    st.markdown(f'<div class="report-title-section" style="font-family:var(--font-serif); '
                f'font-size:calc(23px + var(--font-offset)); font-weight:700; line-height:1.4; '
                f'margin:0 0 16px 0; color:var(--ink); text-align:left;">{L("my_title")}</div>', unsafe_allow_html=True)

    # 초성 추출용 유틸 (예: '보영' -> 'ㅂㅇ')
    def get_initials(name):
        if name == "보영": return "ㅂㅇ"
        return name[:2] if name else "👤"

    # 프로필 사진(업로드 시 base64) 또는 이니셜
    photo = ss.get("profile_photo")
    initials = get_initials(ss.name)

    col_a, col_b = st.columns([1, 4])
    with col_a:
        if photo:
            # 🆕 dlg_profile_photo()에서 이미 검증된 방식(img 태그)과 동일하게 렌더링
            avatar_html = (
                f'<img src="{photo}" style="width:56px;height:56px;border-radius:50%;'
                f'object-fit:cover;display:block;border:1px solid rgba(42,33,24,.1);" />'
            )
        else:
            avatar_html = (
                f'<div style="width:56px;height:56px;border-radius:50%;background:#e3dcd3;'
                f'border:1px solid rgba(42,33,24,.1);display:flex;align-items:center;'
                f'justify-content:center;color:#666;font-weight:700;font-size:16px;">'
                f'{initials}</div>'
            )
        st.markdown(avatar_html, unsafe_allow_html=True)
    with col_b:
        st.markdown(f'<div class="my-profile-name" style="margin-top:16px;">{ss.name}</div>',
                    unsafe_allow_html=True)

    # 2. 내 정보 관리 섹션 — 사진 변경 / 이름·생년월일 변경을 하나의 버튼에서 선택
    st.markdown('<div class="my-section-title">내 정보 관리</div>', unsafe_allow_html=True)
    if st.button("내 정보 변경 (사진 / 이름·생년월일)", use_container_width=True, key="my_btn_edit_info"):
        dlg_edit_info_menu()
        
    # 🆕 dlg_edit_info_menu()에서 넘어온 요청 처리 (중첩 다이얼로그 금지 우회)
    if ss.get("_open_photo_dialog"):
        ss._open_photo_dialog = False
        dlg_profile_photo()
    if ss.get("_open_info_dialog"):
        ss._open_info_dialog = False
        dlg_my_info()

    # 3. 알림 섹션 (주간 / 월간 알림 토글 스위치)
    st.markdown('<div class="my-section-title">알림</div>', unsafe_allow_html=True)
    ss.notif_weekly = st.toggle("주간 변화 알림 — 매주 한 번 추세 요약", value=ss.notif_weekly)
    ss.notif_monthly = st.toggle("월간 변화 알림 — 매월 한 번 상세 리포트", value=ss.notif_monthly)

    # 4. 접근성 섹션 (글자 크기 조절 라디오 버튼)
    st.markdown('<div class="my-section-title">접근성</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:12px; color:#767676; margin-bottom:6px;">글자 크기 조절<br>보기 편한 크기를 선택해 주세요</div>', unsafe_allow_html=True)
    
    font_options = ["기본", "3pt", "6pt"]
    try:
        current_idx = font_options.index(ss.fs_radio)
    except ValueError:
        current_idx = 0
        
    fs_choice = st.radio("글자 크기 선택", font_options, index=current_idx, horizontal=True, label_visibility="collapsed")
    if fs_choice != ss.fs_radio:
        ss.fs_radio = fs_choice
        if fs_choice == "기본":
            ss.font_level = 0
        elif fs_choice == "3pt":
            ss.font_level = 3
        elif fs_choice == "6pt":
            ss.font_level = 6
        st.rerun()

    # 5. 보호자 관리 섹션 (카드 안내 레이아웃 + 보호자 추가 버튼)
    st.markdown('<div class="my-section-title">보호자 관리</div>', unsafe_allow_html=True)
    
    if ss.guardian["registered"]:
        g_status_title = f"등록된 보호자: {ss.guardian['name']}"
        g_status_sub = f"연락처 수단: {ss.guardian['contactType'].upper()} ({ss.guardian['contact']})"
        btn_label = "보호자 정보 수정 / 삭제"
    else:
        g_status_title = "보호자 추가"
        g_status_sub = "보호자를 등록하고 결과를 공유해보세요"
        btn_label = "보호자 추가"

    st.markdown(f'''
    <div class="my-info-card">
        <div class="my-info-card-title">{g_status_title}</div>
        <div class="my-info-card-sub">{g_status_sub}</div>
    </div>
    ''', unsafe_allow_html=True)
    
    if st.button(btn_label, use_container_width=True, key="my_btn_guardian"):
        dlg_guardian()

    # 6. 서비스 안내 섹션 (아코디언 형태의 메뉴 풀다운)
    st.markdown('<div class="my-section-title">서비스 안내</div>', unsafe_allow_html=True)
    with st.expander("서비스 소개 및 연구 배경", expanded=False):
        st.markdown('''
        <style>#service-intro-box, #service-intro-box * { word-break: keep-all !important;
        overflow-wrap: normal !important; word-wrap: normal !important;
        -webkit-hyphens: none !important; hyphens: none !important;
        line-break: strict !important; }</style>
        <div id="service-intro-box" style="white-space:normal !important; text-align:left !important;
        letter-spacing:normal !important; word-spacing:normal !important; text-justify:none !important;">
        힐링레터는 일상적인 타이핑 리듬 데이터(키보드 활공 시간, 지연율 등) 분석을 결합하여, 
        운동 조절 이상 상태를 유발할 수 있는 초기 파킨슨 의심 징후를 선별 보조 목적으로 추적 연구하기 위한 연구용 프로토타입 인터페이스입니다.
        </div>
        ''', unsafe_allow_html=True)
        
    with st.expander("의료 고지사항", expanded=False):
        st.markdown('''
        <style>#medical-notice-box, #medical-notice-box * { word-break: keep-all !important;
        overflow-wrap: normal !important; word-wrap: normal !important;
        -webkit-hyphens: none !important; hyphens: none !important;
        line-break: strict !important; }</style>
        <div id="medical-notice-box" style="white-space:normal !important; text-align:left !important;
        letter-spacing:normal !important; word-spacing:normal !important; text-justify:none !important;">
        본 서비스는 자가 점검용 스크리닝 보조 도구이며 식약처 인증을 획득한 전문 의료기기가 아닙니다. 
        측정 수치 및 변화량 리포트는 어떠한 경우에도 의사의 전문적인 진단 및 임상적 판단을 대신할 수 없습니다. 
        지속적인 이상 증상이 우려될 시 반드시 가까운 대학병원 신경과 전문의 진료를 수강하시기 바랍니다.
        </div>
        ''', unsafe_allow_html=True)  
        
    # 7. 데이터 초기화 버튼
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("데이터 초기화", use_container_width=True, key="my_btn_reset"):
        dlg_reset()


# ============================================================
# 하단 네비게이션 (tabbar)
# ============================================================
def bottom_nav():
    st.markdown('<div style="margin-top:16px;"></div>', unsafe_allow_html=True)

    tabs = [
        ("home", L("nav_home"),
         "M3 11.5 12 4l9 7.5 M5 10v9h14v-9"),
        ("archive", L("nav_archive"),
         "M4 7h16v13H4z M4 7l2-3h12l2 3 M4 11h16"),
        ("report", L("nav_report"),
         "M4 19V10 M10 19V5 M16 19v-7 M4 19h16"),
        ("info", L("nav_info"),
         "M4 4.5h13l3 3v12h-16z M8 8h9 M8 12h9 M8 16h6"),
        ("my", L("nav_my"),
         "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M5 20c1.2-3.5 4-5.5 7-5.5s5.8 2 7 5.5"),
    ]

    NAV_CSS = """
    <style>
    div[data-testid="stHorizontalBlock"]:has(.st-key-nav_home) {
        background: #f0e6d6 !important;
        border-radius: 20px !important;
        padding: 8px 4px !important;
    }

    div[data-testid="stHorizontalBlock"]:has(.st-key-nav_home) button {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 3px !important;
        padding: 4px 0 !important;
        min-height: 52px !important;
        height: auto !important;
    }
    div[data-testid="stHorizontalBlock"]:has(.st-key-nav_home) button p {
        margin: 0 !important;
        font-size: 11px !important;
        font-weight: 500 !important;
    }
    </style>
    """
    st.markdown(NAV_CSS, unsafe_allow_html=True)

    cols = st.columns(5)
    for col, (key, label, path) in zip(cols, tabs):
        active = (ss.screen == key)
        color = "%23c2841a" if active else "%23999999"
        icon_svg = (
            f"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
            f"viewBox='0 0 24 24' fill='none' stroke='{color}' stroke-width='1.8' "
            f"stroke-linecap='round' stroke-linejoin='round'%3E"
            f"%3Cpath d='{path}'/%3E%3C/svg%3E"
        )
        text_color = "#c2841a" if active else "#999999"
        col.markdown(
            f"""
            <style>
            .st-key-nav_{key} button::before {{
                content: '';
                display: block;
                width: 22px;
                height: 22px;
                background-image: url("{icon_svg}");
                background-size: contain;
                background-repeat: no-repeat;
                background-position: center;
            }}
            .st-key-nav_{key} button p {{
                color: {text_color} !important;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )
        if col.button(label, use_container_width=True, key=f"nav_{key}"):
            goto(key)
            st.rerun()

# ============================================================
# 라우팅
# ============================================================
if not ss.intro_done:
    render_intro_video()          # 1단계: 오프닝 영상
elif not ss.logged_in:
    render_onboarding()            # 2단계: 온보딩(두 번째 스샷 화면)
else:
    ensure_daily_letter()
    status_bar()
    screen = ss.screen
    if screen == "home":
        screen_home()
    elif screen == "letter":
        screen_letter()
    elif screen == "game":
        screen_game()
    elif screen == "report":
        screen_report()
    elif screen == "info":
        screen_info()
    elif screen == "my":
        screen_my()
    elif screen == "archive":
        screen_archive()

    bottom_nav()

    st.markdown(
        '<div class="credit" style="display:flex; align-items:flex-start; gap:6px;">'
        '<svg viewBox="0 0 24 24" stroke="currentColor" fill="none" stroke-width="1.6" '
        'style="width:16px; height:16px; flex-shrink:0; margin-top:2px;">'
        '<circle cx="12" cy="12" r="9.5"/><path d="M12 8v5"/><path d="M12 16.2h.01"/></svg>'
        '<span>' + L("home_disc") + '</span></div>',
        unsafe_allow_html=True)
    
