"""
힐링레터 — 핵심 계산 로직 (통합본)
"""
from __future__ import annotations

import json
import math
import os
import joblib
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ---------- 모델 로드 (로지스틱 3변수) ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

model_path = os.path.join(BASE_DIR, "parkinson_model_3features.pkl")
threshold_path = os.path.join(BASE_DIR, "ml_score_thresholds.json")

# 반드시 먼저 선언해두기
parkinson_model = None
ml_thresholds = None

try:
    parkinson_model = joblib.load(model_path)
    print(f"모델 로드 성공: {model_path}")
except Exception as e:
    print(f"모델 로드 실패: {e}")

try:
    with open(threshold_path, "r", encoding="utf-8") as f:
        ml_thresholds = json.load(f)
    print(f"ML 점수 기준 로드 성공: {threshold_path}")
except Exception as e:
    print(f"ML 점수 기준 로드 실패: {e}")

# ---------- 편지 문구 ----------
HEAL_LETTERS = [
    "오늘 하루도 애쓰셨어요. 잠깐 멈춰서, 지금 기분을 편하게 적어보시겠어요?",
    "작은 일상 속에도 좋은 순간이 있었을 거예요. 오늘 떠오르는 한 가지를 들려주세요.",
    "날씨가 제법 좋았던 것 같아요. 오늘은 어떤 하루를 보내셨나요?",
    "가끔은 아무 일 없어도 괜찮아요. 지금 떠오르는 생각을 천천히 적어보세요.",
    "오늘 누군가와 나눈 대화 중 기억에 남는 게 있었나요? 편하게 적어주세요.",
]

# ---------- raw 키스트로크 → 요약(학습과 동일 정의) ----------
# train_model.py 의 compute_features 와 반드시 동일한 규칙:
#   · 정리 범위 : hold_time ∈ [0.03, 0.4] 초
#   · 왼손 키   : QWERTY 왼쪽 글자 (q w e r t a s d f g z x c v b)
#   · hold_std  : 누름시간 표본표준편차(ddof=1)
#   · hold_p90  : 누름시간 90퍼센타일(numpy 선형보간)
#   · left_cv   : 왼손 누름시간의 변동계수 (std(ddof=1)/mean)
LEFT_KEYS = set("qwertasdfgzxcvb")
HOLD_LO, HOLD_HI = 0.03, 0.4

def summarize_strokes(strokes):
    """브라우저가 넘긴 raw 스트로크 리스트를 학습과 동일하게 요약한다.
    strokes: [{"h": hold_seconds, "k": key_char}, ...]
    반환: (features_dict, 유효_타수)
    """
    holds, left = [], []
    for st in strokes or []:
        try:
            h = float(st.get("h"))
        except (TypeError, ValueError):
            continue
        if not (HOLD_LO <= h <= HOLD_HI):
            continue
        holds.append(h)
        if str(st.get("k", "")).lower() in LEFT_KEYS:
            left.append(h)
    hold_std = float(np.std(holds, ddof=1)) if len(holds) > 1 else 0.0
    hold_p90 = float(np.percentile(holds, 90)) if holds else 0.0
    left_mean = float(np.mean(left)) if left else 0.0
    left_cv = float(np.std(left, ddof=1) / left_mean) if len(left) > 1 and left_mean != 0 else 0.0
    return {"hold_std": hold_std, "left_cv": left_cv, "hold_p90": hold_p90}, len(holds)


# ---------- 머신러닝 예측 함수 ----------
# 학습에 사용된 핵심 변수 3개 순서 (train_model.py 와 반드시 동일)
FEATURE_ORDER = [
    'hold_std',   # 키 누름시간 표준편차
    'left_cv',    # 왼손 키 hold_time 변동계수 (좌우 비대칭)
    'hold_p90',   # 키 누름시간 90퍼센타일
]

# 학습 데이터(MIT)의 hold 계열은 모두 '초' 단위(대략 0.05~0.35초).
# 컴포넌트가 실수로 밀리초(ms)로 넘기면 값이 1000배가 되어 모델이 붕괴한다.
# (검증: ms로 넘기면 전원 점수 33~49로 몰려 모두 파킨슨 판정)
# 아래 가드는 hold_mean 이 초 단위로는 불가능한 크기일 때 ms 로 보고 보정한다.
_HOLD_MAX_SECONDS = 3.0  # 사람이 키를 3초 이상 누르고 있을 일은 없음


def _coerce_features(features_dict):
    """3개 피처를 순서대로 float 로 만들고, 명백한 ms 스케일이면 초로 보정한다."""
    vals = {}
    for k in FEATURE_ORDER:
        v = features_dict.get(k)
        if v is None:
            raise KeyError(f"필수 피처 누락: {k}")
        vals[k] = float(v)

    # 스케일 가드: hold_p90 이 초 단위로 불가능하게 크면 ms 로 보고 보정.
    # left_cv 는 무차원(변동계수)이라 스케일 영향 없음 → 보정 대상에서 제외.
    if vals['hold_p90'] > _HOLD_MAX_SECONDS:
        print(f"[predict_parkinson] 경고: hold_p90={vals['hold_p90']:.1f} 이(가) "
              f"초 단위로 비정상적으로 큽니다. ms 로 간주하고 1/1000 보정합니다.")
        for k in ('hold_std', 'hold_p90'):
            vals[k] = vals[k] / 1000.0
    return vals


def predict_parkinson(features_dict):
    """3개 피처(hold_std, left_cv, hold_p90) → 파킨슨 위험확률 → 건강점수(20~100)."""
    if parkinson_model is None:
        return 50

    # 🔍 디버그: 원본 입력값 그대로 출력 (원인 파악용, 확인 끝나면 지워도 됨)
    print(f"[DEBUG] 입력 타입: {type(features_dict).__name__}")

    # 브라우저가 raw 스트로크 리스트를 넘기면 학습과 동일하게 요약한다.
    if isinstance(features_dict, (list, tuple)):
        summarized, n_kept = summarize_strokes(features_dict)
        print(f"[DEBUG] raw {len(features_dict)}타 → 유효 {n_kept}타 → 요약 {summarized}")
        features_dict = summarized

    try:
        vals = _coerce_features(features_dict or {})
    except (KeyError, TypeError, ValueError) as e:
        print(f"[predict_parkinson] 피처 오류로 중립 점수 반환: {e}")
        return 50

    # 🔍 디버그: 보정 후 실제 모델에 들어가는 값
    print(f"[DEBUG] 보정 후 vals(모델 입력): {vals}")

    df_input = pd.DataFrame([vals])[FEATURE_ORDER]

    # 질환군(양성) 클래스 위치를 안전하게 확인
    classes = list(parkinson_model.classes_)
    if True in classes:
        risk_class = True
    elif 1 in classes:
        risk_class = 1
    else:
        risk_class = classes[-1]
    risk_idx = classes.index(risk_class)

    # 파킨슨 의심 확률 → 안정도 점수 = 100 x (1 - 위험확률)  (높을수록 안정)
    #   ※ 기존의 +20 보정은 제거함 (우리 점수 체계로 통일)
    prob = parkinson_model.predict_proba(df_input)[0][risk_idx]
    final_score = int(round(100 * (1 - prob)))
    final_score = max(0, min(100, final_score))

    # 🔍 디버그: 확률과 최종 점수
    print(f"[DEBUG] risk_class={risk_class} prob(위험확률)={prob:.4f} "
          f"final_score={final_score}")

    return int(final_score)

# ---------- 통계 유틸 ----------
def mean(arr):
    return sum(arr) / len(arr) if arr else 0.0

def stdev(arr):
    if len(arr) < 2:
        return 0.0
    m = mean(arr)
    return math.sqrt(mean([(v - m) * (v - m) for v in arr]))

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

# ---------- 점수 밴드 ----------
def band_for(score):
    """
    안정도 점수(=100x(1-파킨슨확률))를 3구간으로 분류한다.
    상한 upper(안정 경계, 민감도 85%) / 하한 lower(상담 경계, 특이도 85%)는
    ml_score_thresholds.json 에서 읽는다. 파일이 없으면 66.6 / 49.9 를 사용한다.
    """

    if ml_thresholds is not None and "upper" in ml_thresholds and "lower" in ml_thresholds:
        upper = ml_thresholds["upper"]   # 안정 경계 (민감도 기준)
        lower = ml_thresholds["lower"]   # 상담 경계 (특이도 기준)

        # 점수 = 100 x (1 - 파킨슨확률), 높을수록 안정
        #   upper 이상        → 안정
        #   lower ~ upper 사이 → 관찰 필요
        #   lower 이하        → 상담 권장
        if score >= upper:
            return {"label": "안정", "cls": "safe"}
        if score <= lower:
            return {"label": "상담 권장", "cls": "alert"}
        return {"label": "관찰 필요", "cls": "watch"}

    # 기준 파일이 없을 경우 fallback (우리 기본 컷오프)
    if score >= 66.6:
        return {"label": "안정", "cls": "safe"}
    if score > 49.9:
        return {"label": "관찰 필요", "cls": "watch"}
    return {"label": "상담 권장", "cls": "alert"}

# ---------- 편지 리듬 점수 ----------
def compute_letter_metrics(events, text):
    NON_PRINT = {
        "ShiftLeft", "ShiftRight", "ControlLeft", "ControlRight",
        "AltLeft", "AltRight", "MetaLeft", "MetaRight",
        "CapsLock", "Tab", "Escape",
    }

    def printable_down_times(evs):
        return [e["t"] for e in evs if e["type"] == "down" and e["code"] not in NON_PRINT]

    def intervals_from_down_times(times):
        res = []
        for i in range(1, len(times)):
            d = times[i] - times[i - 1]
            if 0 < d < 6000:
                res.append(d)
        return res

    down_times = printable_down_times(events)
    all_intervals = intervals_from_down_times(down_times)

    PAUSE_MS = 900
    active_intervals = [d for d in all_intervals if d <= PAUSE_MS]
    pause_count = len([d for d in all_intervals if d > PAUSE_MS])

    avg_interval = mean(active_intervals)
    sd_interval = stdev(active_intervals)
    cv = sd_interval / avg_interval if avg_interval > 0 else 0.0

    backspace_count = len([e for e in events if e["type"] == "down" and e["code"] == "Backspace"])
    backspace_rate = backspace_count / max(len(text), 1)

    cv_norm = clamp((cv - 0.15) / (0.75 - 0.15), 0, 1)
    score = 100 - cv_norm * 70
    score -= min(pause_count * 3, 15)
    score -= min(backspace_rate * 100, 15)
    score = round(clamp(score, 0, 100))

    return {
        "score": int(score),
        "avgInterval": avg_interval,
        "cv": cv,
        "pauseCount": pause_count,
        "backspaceCount": backspace_count,
        "sampleSize": len(active_intervals),
    }

# ---------- 게임 결과 점수 ----------
def compute_game_result(perfect, good, miss, offsets, total_drops):
    total_hits = perfect + good
    accuracy = round((total_hits / total_drops) * 100) if total_drops else 0
    consistency = round(clamp(100 - stdev(offsets) * 0.45, 0, 100))
    combined = round(accuracy * 0.5 + consistency * 0.5)
    return {
        "accuracy": accuracy,
        "consistency": consistency,
        "score": combined,
        "perfect": perfect,
        "good": good,
        "miss": miss,
    }

# ---------- 예시 데이터 ----------
def sample_series():
    today = datetime.now()
    base = [62, 58, 65, 70, 68, 74, 77, 73, 80, 78]
    out = []
    n = len(base)
    for i, v in enumerate(base):
        d = today - timedelta(days=(n - 1 - i))
        out.append({"t": d, "score": v})
    return out

def fmt_date(d: datetime):
    return f"{d.month}.{d.day}"