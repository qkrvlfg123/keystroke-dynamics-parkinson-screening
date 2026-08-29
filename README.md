# 힐링레터 앱 — 교체 파일 (로지스틱 3변수 모델)

원래 앱 폴더에 아래 파일들을 덮어쓰면 됩니다. 나머지 자산(styles.py, charts.py,
components/keystroke, 이미지, opening.mp4 등)은 기존 그대로 두세요.

## 파일 목록
| 파일 | 역할 |
|---|---|
| app.py | 메인 앱 (이모지 색 기준을 우리 구간 66.6/49.9 로 수정) |
| logic.py | 예측·점수·구간 로직 + raw 스트로크 요약 함수(summarize_strokes) |
| index.html | 키 입력 캡처. raw 스트로크(누름시간+키)만 전송, 최소 80자 |
| parkinson_model_3features.pkl | 로지스틱 3변수 모델(hold_std, left_cv, hold_p90) |
| ml_score_thresholds.json | 구간 컷오프(상한 66.6 / 하한 49.9) |
| train_model.py | 요약 CSV로 모델 재학습(재현·버전 맞춤용) |
| requirements.txt | 필요한 패키지 |

## 동작 개요
1. 사용자가 편지를 80자 이상 입력 → index.html 이 각 키의 누름시간+키문자(raw)를 전송
2. logic.py 가 학습과 동일한 규칙으로 요약: hold_std, left_cv, hold_p90
   - 정리: hold_time ∈ [0.03, 0.4]초 / 왼손키: q w e r t a s d f g z x c v b
3. 로지스틱 모델 → 파킨슨 확률 → 점수 = 100 x (1 - 확률)
4. 구간: 안정(≥66.6) / 관찰 필요(49.9~66.6) / 상담 권장(≤49.9)

## 성능 (요약 CSV, LOOCV)
AUC 0.860 · 정확도 0.800 · 민감도 0.762 · 특이도 0.837

## 주의
- 모델 .pkl 은 scikit-learn 1.7.2 으로 생성됨. 팀 환경 버전이 다르면
  train_model.py 를 한 번 실행해 .pkl 을 재생성하는 것을 권장(요약 CSV 필요).
- 학습은 요약 CSV(MIT 정제본) 기준. 앱의 raw 요약은 이를 상관 0.92 로 근사하므로
  일부(약 8%) 사례에서 밴드가 달라질 수 있음(원 MIT 전처리 코드 부재로 인한 한계).
- 편지는 학습(~2000타)보다 짧아 최소 80자로 피처 안정성을 확보(left_cv 오차 ~12~15%).
