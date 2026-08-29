"""
힐링레터 — PDF 리포트 생성 (reportlab)

reportlab 내장 한글 CID 폰트(HYGothic-Medium / HYSMyeongJo-Medium)를 사용하므로
별도 폰트 파일 없이도 한글이 깨지지 않습니다.

사용법 (app.py 의 screen_report 안에서):
    from report_pdf import build_report_pdf
    pdf_bytes = build_report_pdf(
        name=ss.name,
        seg=ss.report_seg,          # "letter" | "game"
        letters=ss.letters,         # 편지 기록 리스트
        games=ss.games,             # 게임 기록 리스트
        is_sample=ss.sample_toggle, # 예시 데이터 여부
    )
    st.download_button("📄 PDF 저장", data=pdf_bytes, file_name="report.pdf", mime="application/pdf")
"""
from __future__ import annotations

import io
import os
import json
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

# 이 파일이 있는 폴더 (green.png 등 이미지가 같은 폴더에 있음)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _emoji_image_for_score(score: float):
    """점수 → 이모티콘 이미지 경로. 웹의 score_emoji_html 과 동일한 기준.
    upper/lower 는 ml_score_thresholds.json 에서 읽고, 없으면 66.6/49.9 사용."""
    upper, lower = 66.6, 49.9
    try:
        p = os.path.join(_BASE_DIR, "ml_score_thresholds.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                th = json.load(f)
            upper = th.get("upper", upper)
            lower = th.get("lower", lower)
    except Exception:
        pass

    if score >= upper:
        fname = "green.png"      # 안정
    elif score > lower:
        fname = "yellow.png"     # 관찰 필요
    else:
        fname = "red.png"        # 상담 권장

    path = os.path.join(_BASE_DIR, fname)
    return path if os.path.exists(path) else None

# ---- 한글 폰트 등록 (reportlab 내장 CID 폰트, 폰트 파일 불필요) ----
_FONT = "HYGothic-Medium"          # 고딕(본문)
_FONT_SERIF = "HYSMyeongJo-Medium" # 명조(제목)
_fonts_ready = False


def _ensure_fonts():
    global _fonts_ready
    if _fonts_ready:
        return
    pdfmetrics.registerFont(UnicodeCIDFont(_FONT))
    pdfmetrics.registerFont(UnicodeCIDFont(_FONT_SERIF))
    _fonts_ready = True


# ---- 원본 색상 (styles.py 톤과 동일 계열) ----
_INK = colors.HexColor("#2A2118")
_INK_DIM = colors.HexColor("#6B6152")
_HONEY = colors.HexColor("#C2842A")
_HONEY_DARK = colors.HexColor("#A0681A")
_SAGE = colors.HexColor("#4E7D5C")
_PAPER = colors.HexColor("#FBF3E3")
_CARD = colors.HexColor("#EFE5CE")
_LINE = colors.HexColor("#D9CDB2")


def _mean(arr):
    return sum(arr) / len(arr) if arr else 0.0


def build_report_pdf(
    name: str,
    seg: str,                       # "letter" | "game"
    letters: list[dict] | None = None,
    games: list[dict] | None = None,
    is_sample: bool = False,
) -> bytes:
    """리포트 PDF 를 만들어 bytes 로 반환한다."""
    _ensure_fonts()
    letters = letters or []
    games = games or []

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    # 배경
    c.setFillColor(_PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    x = 20 * mm
    y = H - 24 * mm

    # ---------- 헤더 ----------
    c.setFillColor(_HONEY_DARK)
    c.setFont(_FONT, 10)
    c.drawString(x, y, "HEALING LETTER")
    y -= 10 * mm

    c.setFillColor(_INK)
    c.setFont(_FONT_SERIF, 22)
    c.drawString(x, y, "변화 리포트")
    y -= 8 * mm

    seg_label = "편지 문자" if seg == "letter" else "멍멍 우체부"
    c.setFillColor(_INK_DIM)
    c.setFont(_FONT, 11)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    c.drawString(x, y, f"{name} 님 · {seg_label} · 생성일 {generated}")
    y -= 5 * mm
    if is_sample:
        c.setFillColor(_HONEY)
        c.drawString(x, y, "※ 예시 데이터 기반 미리보기입니다 (실제 기록 아님)")
        y -= 5 * mm

    y -= 3 * mm
    c.setStrokeColor(_LINE)
    c.setLineWidth(1)
    c.line(x, y, W - x, y)
    y -= 12 * mm

    # ---------- 데이터 준비 (편지=점수, 게임=소요시간) ----------
    if seg == "game":
        if is_sample:
            values = [8.5, 7.9, 8.2, 6.8, 5.9, 6.1, 5.3, 4.8]
            misses = [1, 2, 0, 1, 0, 0, 1, 0]
            times = [None] * len(values)
        else:
            values = [g["duration"] for g in games]
            misses = [g.get("miss", 0) for g in games]
            times = [g.get("t") for g in games]
        stats = [
            ("최근 소요시간", f"{round(values[-1], 2)}초" if values else "-", None),
            ("최고(최소) 기록", f"{round(min(values), 2)}초" if values else "-", None),
            ("게임 횟수", f"{len(values)}회" if values else "-", None),
        ]
        chart_title = "멍멍 우체부 완료 소요 시간 추세 (초)"
        unit = "초"
        lower_is_better = True
    else:
        if is_sample:
            values = [70, 74, 72, 75, 81, 79, 83]
            misses = []
            times = [None] * len(values)
        else:
            values = [l["score"] for l in letters]
            misses = []
            times = [l.get("t") for l in letters]
        avg = round(_mean(values)) if values else 0
        emoji_path = _emoji_image_for_score(avg) if values else None
        stats = [
            ("평균 기록", f"{avg}점" if values else "-", emoji_path),  # 3번째=이미지 경로
            ("최고 기록", f"{max(values)}점" if values else "-", None),
            ("기록 일수", f"{len(values)}일" if values else "-", None),
        ]
        chart_title = "편지 문자 점수 추세"
        unit = "점"
        lower_is_better = False

    # ---------- 요약 카드 3개 ----------
    card_w = (W - x * 2 - 8 * mm) / 3
    card_h = 26 * mm
    cx = x
    for label, value, img_path in stats:
        c.setFillColor(_CARD)
        c.roundRect(cx, y - card_h, card_w, card_h, 6, fill=1, stroke=0)
        c.setFillColor(_INK_DIM)
        c.setFont(_FONT, 10)
        c.drawCentredString(cx + card_w / 2, y - 8 * mm, label)
        if img_path:
            # 이모티콘 이미지 (초록/노랑/빨강 얼굴)
            img_size = 15 * mm
            try:
                c.drawImage(
                    ImageReader(img_path),
                    cx + card_w / 2 - img_size / 2,
                    y - card_h + 3 * mm,
                    width=img_size, height=img_size,
                    mask="auto",  # 투명 배경 처리
                )
            except Exception:
                c.setFillColor(_INK)
                c.setFont(_FONT_SERIF, 18)
                c.drawCentredString(cx + card_w / 2, y - 19 * mm, value)
        else:
            c.setFillColor(_INK)
            c.setFont(_FONT_SERIF, 18)
            c.drawCentredString(cx + card_w / 2, y - 19 * mm, value)
        cx += card_w + 4 * mm
    y -= card_h + 12 * mm

    # ---------- 추세 차트 ----------
    c.setFillColor(_INK)
    c.setFont(_FONT, 12)
    c.drawString(x, y, chart_title)
    y -= 6 * mm

    ch = 55 * mm
    cw = W - x * 2
    cxx = x
    cyy = y - ch
    c.setFillColor(_CARD)
    c.roundRect(cxx, cyy, cw, ch, 6, fill=1, stroke=0)

    pad = 8 * mm
    px0 = cxx + pad
    py0 = cyy + pad
    pw = cw - pad * 2
    ph = ch - pad * 2

    if values:
        vmin = min(values)
        vmax = max(values)
        span = (vmax - vmin) or 1
        n = len(values)
        step = pw / (n - 1) if n > 1 else 0
        pts = []
        for i, v in enumerate(values):
            ppx = px0 + i * step
            # 값이 낮을수록 좋은 게임은 그대로, 점수는 그대로 (위=큰 값)
            ppy = py0 + ((v - vmin) / span) * ph
            pts.append((ppx, ppy))
        c.setStrokeColor(_HONEY)
        c.setLineWidth(1.8)
        for i in range(1, len(pts)):
            c.line(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1])
        c.setFillColor(_HONEY)
        for ppx, ppy in pts:
            c.circle(ppx, ppy, 1.8, fill=1, stroke=0)
    else:
        c.setFillColor(_INK_DIM)
        c.setFont(_FONT, 10)
        c.drawCentredString(cxx + cw / 2, cyy + ch / 2, "아직 기록이 없어요")

    y = cyy - 12 * mm

    # ---------- 게임: 오답 요약 / 편지: 안내 ----------
    if seg == "game" and values:
        c.setFillColor(_INK)
        c.setFont(_FONT, 12)
        c.drawString(x, y, "세부 지표")
        y -= 8 * mm
        rows = [
            ("최근 오답 갯수", f"{misses[-1]}회" if misses else "-"),
            ("평균 오답 갯수", f"{_mean(misses):.1f}회" if misses else "-"),
        ]
        c.setFont(_FONT, 11)
        for label, value in rows:
            c.setFillColor(_INK_DIM)
            c.drawString(x, y, label)
            c.setFillColor(_INK)
            c.drawRightString(W - x, y, value)
            y -= 3 * mm
            c.setStrokeColor(_LINE)
            c.setLineWidth(0.5)
            c.line(x, y, W - x, y)
            y -= 6 * mm

    # ---------- 개별 기록 (최근 10건) ----------
    if values:
        y -= 4 * mm
        c.setFillColor(_INK)
        c.setFont(_FONT, 12)
        c.drawString(x, y, "개별 기록 (최근순)")
        y -= 8 * mm

        pairs = list(zip(times, values))
        recent = list(reversed(pairs))[:10]
        c.setFont(_FONT, 10)
        for t, v in recent:
            if y < 30 * mm:
                c.showPage()
                c.setFillColor(_PAPER)
                c.rect(0, 0, W, H, fill=1, stroke=0)
                y = H - 24 * mm
            date_str = t.strftime("%Y-%m-%d %H:%M") if hasattr(t, "strftime") else "예시 데이터"
            c.setFillColor(_INK_DIM)
            c.drawString(x, y, date_str)
            c.setFillColor(_HONEY_DARK)
            vstr = f"{round(v, 2)}{unit}" if seg == "game" else f"{v}{unit}"
            c.drawRightString(W - x, y, vstr)
            y -= 7 * mm

    # ---------- 하단 고지 ----------
    c.setFillColor(_INK_DIM)
    c.setFont(_FONT, 8)
    c.drawString(
        x, 15 * mm,
        "힐링레터는 의료기기가 아니며 의학적 진단을 내리지 않습니다. 결과가 걱정되시면 신경과 전문의와 상담해 주세요."
    )

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()