"""
keystroke_letter — 키 입력 리듬 캡처 (양방향 Streamlit 컴포넌트, 빌드 불필요)

브라우저에서 keydown/keyup 을 잡아 각 키의 hold time 과 flight time 을 '초' 단위로
계산해 5개 피처(hold_std, flight_min, hold_mean, hold_median, press_interval_median)를
Python 으로 돌려준다. 이 5개는 train_model.py / logic.py 의 FEATURE_ORDER 와 동일하며
학습 데이터(MIT)와 같은 '초' 단위이다.

반환 dict:
    {
        "submitId": float,          # 제출마다 고유 (app.py 에서 중복 처리 방지)
        "text": str,                # 답장 본문
        "features": {5개 피처, 초 단위},
        "rhythmScore": int,         # 참고용 휴리스틱 점수 (공식 점수 아님)
        "cv": float,
        "avgInterval": float,       # ms
        "pauseCount": int,
        "backspaceCount": int,
    }
"""
import os
import streamlit.components.v1 as components

_FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")

# 정적 HTML 프런트엔드 (npm 빌드 없이 동작)
_component = components.declare_component("keystroke_letter", path=_FRONTEND_DIR)


def keystroke_letter(date_label, letter_message, already_done=False,
                     font_offset=0, reset_nonce=0, key=None):
    """편지 입력 화면을 렌더링하고, 제출 시 리듬 분석 결과 dict 를 반환한다."""
    return _component(
        date_label=date_label,
        letter_message=letter_message,
        already_done=already_done,
        font_offset=font_offset,
        reset_nonce=reset_nonce,
        key=key,
        default=None,
    )
