# -*- coding: utf-8 -*-
"""
힐링레터 파킨슨 선별 모델 학습 (요약 CSV 값 그대로 · 로지스틱 3변수)
- 입력: 4th_FINAL_2nd_summary_variables_subject_85rows.csv  (발표에 쓴 확정 요약값)
- 피처: hold_std, left_cv, hold_p90
- 모델: 로지스틱 회귀 (스케일러 포함 Pipeline)
- 점수: 100 x (1 - 파킨슨확률)   (+20 보정 없음)
- 구간: 상한=민감도>=T 최소점 / 하한=특이도>=T 최대점 (회색지대>=5점, T=0.85부터)
- 출력: parkinson_model_3features.pkl, ml_score_thresholds.json
  ※ 브라우저(index.html)는 raw 키스트로크로 같은 3변수를 근사 계산한다.
    요약값은 MIT 정제 파이프라인 산출물이라, 브라우저 근사값과 소폭 차이가 있을 수 있다
    (상관 ~0.92). 발표·검증 수치는 이 요약값 기준으로 100% 일치한다.
"""
import os, json
import numpy as np, pandas as pd, joblib
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (roc_auc_score, accuracy_score, recall_score,
                             confusion_matrix)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(BASE_DIR, "4th_FINAL_2nd_summary_variables_subject_85rows.csv")
FEATURES = ["hold_std", "left_cv", "hold_p90"]

df = pd.read_csv(CSV)
X, y = df[FEATURES], df["gt"]
yb = y.astype(int).values

model = Pipeline([
    ("imputer", SimpleImputer(strategy="median")),
    ("scaler",  StandardScaler()),
    ("clf",     LogisticRegression(C=1.0, max_iter=5000, random_state=42)),
])

# LOOCV 성능
proba_cv = cross_val_predict(model, X, y, cv=LeaveOneOut(), method="predict_proba")[:, 1]
pred_cv = (proba_cv >= 0.5).astype(int)
tn, fp, fn, tp = confusion_matrix(yb, pred_cv).ravel()
print("=== LOOCV (로지스틱 · 3변수 · 요약CSV) ===")
print(f"  AUC={roc_auc_score(yb, proba_cv):.3f} 정확도={accuracy_score(yb, pred_cv):.3f} "
      f"민감도={recall_score(yb, pred_cv):.3f} 특이도={tn/(tn+fp):.3f}")

# 전체 적합 후 저장
model.fit(X, y)
joblib.dump(model, os.path.join(BASE_DIR, "parkinson_model_3features.pkl"))

# 점수 = 100 x (1 - 파킨슨확률)
classes = list(model.classes_)
risk_class = True if True in classes else (1 if 1 in classes else classes[-1])
risk_idx = classes.index(risk_class)
# 컷오프는 LOOCV 확률로 계산 (발표 문서와 동일한 정직한 기준)
score = 100 * (1 - proba_cv)

# 3구간 컷오프: 상한=민감도>=T 최소, 하한=특이도>=T 최대, 회색지대>=5점
def _spec(yt, yp):
    tn, fp, fn, tp = confusion_matrix(yt, yp).ravel(); return tn/(tn+fp)
grid = np.round(np.linspace(0, 100, 1001), 1); MIN_GAP = 5.0
sens_at = lambda t: recall_score(yb, (score < t).astype(int))
spec_at = lambda t: _spec(yb, (score < t).astype(int))
T = 0.85
while T <= 0.98:
    up = [t for t in grid if sens_at(t) >= T]
    lo = [t for t in grid if spec_at(t) >= T]
    U = min(up) if up else None
    L = max(lo) if lo else None
    if U is not None and L is not None and (U - L) >= MIN_GAP:
        break
    T = round(T + 0.01, 2)
UPPER, LOWER = float(U), float(L)
thresholds = {"upper": round(UPPER, 1), "lower": round(LOWER, 1), "target": round(T, 2),
              "risk_class": str(risk_class), "scoring": "score=100*(1-prob_PD)",
              "description": "Logistic·3변수(요약CSV) 점수 100*(1-확률), 민감도/특이도 3구간"}
with open(os.path.join(BASE_DIR, "ml_score_thresholds.json"), "w", encoding="utf-8") as f:
    json.dump(thresholds, f, ensure_ascii=False, indent=2)

# 구간 분포 출력
z = np.where(score >= UPPER, "안정", np.where(score <= LOWER, "상담 권장", "관찰 필요"))
ct = pd.crosstab(pd.Series(z, name="구간"),
                 pd.Series(np.where(yb == 1, "PD", "Control"), name="실제")
                 ).reindex(["안정", "관찰 필요", "상담 권장"]).fillna(0).astype(int)
print(f"\n상한 UPPER={UPPER:.1f} 하한 LOWER={LOWER:.1f} 회색지대폭={UPPER-LOWER:.1f} (TARGET={T:.2f})")
print(ct.to_string())
print(f"대조군 평균 {score[yb==0].mean():.1f} | 환자 평균 {score[yb==1].mean():.1f}")
