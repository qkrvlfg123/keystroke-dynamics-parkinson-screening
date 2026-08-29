"""
힐링레터 — SVG 차트 생성 (원본 drawSparkline / drawWaveform / drawTrendChart 포팅)
색상은 원본 그대로: honey #C2842A, honey-dark #A0681A, sage #4E7D5C
"""
from __future__ import annotations

from logic import clamp


def sparkline(values, w=280, h=40, pad=4):
    """원본 drawSparkline — 홈 화면 미니 추이선"""
    if not values:
        values = [70, 70, 70]
    mx, mn = 100, 0
    step = (w - pad * 2) / (len(values) - 1) if len(values) > 1 else 0
    path = ""
    for i, v in enumerate(values):
        x = pad + i * step
        y = h - pad - ((v - mn) / (mx - mn)) * (h - pad * 2)
        path += ("M" if i == 0 else "L") + f"{x:.1f} {y:.1f} "
    last = values[-1]
    last_x = pad + (len(values) - 1) * step
    last_y = h - pad - ((last - mn) / (mx - mn)) * (h - pad * 2)
    inner = (
        f'<path d="{path}" fill="none" stroke="#C2842A" stroke-width="2" stroke-linecap="round"/>'
        f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="3" fill="#C2842A"/>'
    )
    return (
        f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" '
        f'style="width:100%;height:38px;margin-top:6px;">{inner}</svg>'
    )


def waveform(flights, w=300, h=46, pad=4):
    """원본 drawWaveform — 실시간 입력 리듬 (정적 미리보기용)"""
    if len(flights) < 2:
        inner = ('<line x1="4" y1="23" x2="296" y2="23" stroke="rgba(42,33,24,.2)" '
                 'stroke-width="1.5" stroke-dasharray="3,4"/>')
    else:
        mx = max(max(flights), 50)
        step = (w - pad * 2) / (len(flights) - 1)
        path = ""
        for i, v in enumerate(flights):
            x = pad + i * step
            y = h - pad - clamp(v / mx, 0, 1) * (h - pad * 2)
            path += ("M" if i == 0 else "L") + f"{x:.1f} {y:.1f} "
        inner = (f'<path d="{path}" fill="none" stroke="#A0681A" stroke-width="2" '
                 f'stroke-linecap="round" stroke-linejoin="round" opacity="0.85"/>')
    return (f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" '
            f'style="width:100%;height:46px;display:block;">{inner}</svg>')


def trend_chart(series, w=280, h=110, pad=14):
    """원본 drawTrendChart — 리포트 추세선 (75점 기준선 + 데이터 점)"""
    if not series:
        inner = ('<text x="140" y="55" text-anchor="middle" font-size="11" '
                 'fill="rgba(42,33,24,.4)">아직 기록이 없어요</text>')
        return (f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" '
                f'style="width:100%;height:130px;">{inner}</svg>')

    mx, mn = 100, 0
    step = (w - pad * 2) / (len(series) - 1) if len(series) > 1 else 0
    path, dots = "", ""
    for i, s in enumerate(series):
        x = pad + i * step
        y = h - pad - ((s["score"] - mn) / (mx - mn)) * (h - pad * 2)
        path += ("M" if i == 0 else "L") + f"{x:.1f} {y:.1f} "
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="#C2842A"/>'
    grid_y1 = h - pad - (75 / 100) * (h - pad * 2)
    inner = (
        f'<line x1="{pad}" y1="{grid_y1:.1f}" x2="{w - pad}" y2="{grid_y1:.1f}" '
        f'stroke="rgba(78,125,92,.4)" stroke-dasharray="3,4"/>'
        f'<path d="{path}" fill="none" stroke="#C2842A" stroke-width="2.2" '
        f'stroke-linecap="round" stroke-linejoin="round"/>{dots}'
    )
    return (f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" '
            f'style="width:100%;height:130px;">{inner}</svg>')


def hero_wave():
    """원본 hero-wave 장식 물결"""
    return (
        '<svg class="hero-wave" viewBox="0 0 480 46" preserveAspectRatio="none">'
        '<path d="M0 23 Q 20 6, 38 23 T 76 23 Q 94 38, 112 23 T 150 23 Q 168 10, 186 23 '
        'T 224 23 Q 242 32, 260 23 T 298 23 Q 316 8, 334 23 T 372 23 Q 390 30, 408 23 '
        'T 446 23 T 480 23" fill="none" stroke="#C2842A" stroke-width="1.6" '
        'stroke-linecap="round"/></svg>'
    )


def chip_html(band):
    """원본 chipHtml"""
    return (f'<span class="chip {band["cls"]}"><span class="chip-dot"></span>'
            f'{band["label"]}</span>')
