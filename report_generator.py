from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect, String, Circle, Line
from reportlab.graphics import renderPDF
from reportlab.graphics.charts.barcharts import VerticalBarChart
from datetime import datetime
import math


# ─── Color Palette ──────────────────────────────────────────────────────────

C_BG        = colors.HexColor('#0f0f1a')
C_CARD      = colors.HexColor('#1a1a2e')
C_ACCENT    = colors.HexColor('#7c3aed')
C_ACCENT2   = colors.HexColor('#4f46e5')
C_TEXT      = colors.HexColor('#e2e8f0')
C_MUTED     = colors.HexColor('#94a3b8')
C_SUCCESS   = colors.HexColor('#22c55e')
C_WARNING   = colors.HexColor('#f59e0b')
C_DANGER    = colors.HexColor('#ef4444')
C_WHITE     = colors.white
C_BORDER    = colors.HexColor('#2d2d4e')


def score_color(score):
    if score >= 75: return C_SUCCESS
    if score >= 50: return C_WARNING
    return C_DANGER


def priority_color(priority):
    return {'High': C_DANGER, 'Medium': C_WARNING, 'Low': C_SUCCESS}.get(priority, C_ACCENT)


# ─── Drawing Helpers ─────────────────────────────────────────────────────────

def draw_score_donut(score, label, x, y, radius=35):
    d = Drawing(radius * 2 + 20, radius * 2 + 30)
    cx, cy = radius + 10, radius + 15

    # Background ring
    d.add(Circle(cx, cy, radius, strokeColor=C_BORDER, strokeWidth=6, fillColor=None))

    # Score arc (approximated with thin wedge segments)
    angle = score / 100 * 360
    col = score_color(score)
    # Draw filled arc segments
    steps = max(1, int(angle / 5))
    for i in range(steps):
        a1 = math.radians(90 - i * (angle / steps))
        a2 = math.radians(90 - (i + 1) * (angle / steps))
        x1 = cx + (radius - 3) * math.cos(a1)
        y1 = cy + (radius - 3) * math.sin(a1)
        x2 = cx + (radius + 3) * math.cos(a1)
        y2 = cy + (radius + 3) * math.sin(a1)
        x3 = cx + (radius + 3) * math.cos(a2)
        y3 = cy + (radius + 3) * math.sin(a2)
        x4 = cx + (radius - 3) * math.cos(a2)
        y4 = cy + (radius - 3) * math.sin(a2)
        from reportlab.graphics.shapes import Polygon
        d.add(Polygon([x1, y1, x2, y2, x3, y3, x4, y4],
                      fillColor=col, strokeColor=col, strokeWidth=0.5))

    # Score text
    d.add(String(cx, cy + 5, str(int(score)),
                 fontName='Helvetica-Bold', fontSize=18,
                 fillColor=col, textAnchor='middle'))
    d.add(String(cx, cy - 8, '/100',
                 fontName='Helvetica', fontSize=7,
                 fillColor=C_MUTED, textAnchor='middle'))
    # Label
    d.add(String(cx, 4, label,
                 fontName='Helvetica', fontSize=8,
                 fillColor=C_MUTED, textAnchor='middle'))
    return d


def draw_color_swatch(hex_color, width=30, height=30):
    d = Drawing(width, height)
    try:
        col = colors.HexColor(hex_color)
    except:
        col = colors.grey
    d.add(Rect(0, 0, width, height, fillColor=col,
               strokeColor=C_BORDER, strokeWidth=1, rx=4, ry=4))
    return d


def draw_bar(value, max_val=100, width=120, height=10, color=None):
    d = Drawing(width, height)
    col = color or score_color(value)
    d.add(Rect(0, 0, width, height, fillColor=C_BORDER, strokeColor=None, rx=4, ry=4))
    fill_w = max(2, (value / max_val) * width)
    d.add(Rect(0, 0, fill_w, height, fillColor=col, strokeColor=None, rx=4, ry=4))
    return d


# ─── Styles ──────────────────────────────────────────────────────────────────

def make_styles():
    base = getSampleStyleSheet()

    styles = {
        'title': ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=26,
                                textColor=C_WHITE, spaceAfter=4, leading=32),
        'subtitle': ParagraphStyle('subtitle', fontName='Helvetica', fontSize=12,
                                   textColor=C_MUTED, spaceAfter=16),
        'section_header': ParagraphStyle('section_header', fontName='Helvetica-Bold',
                                         fontSize=13, textColor=C_ACCENT, spaceAfter=8,
                                         spaceBefore=16, leading=18),
        'body': ParagraphStyle('body', fontName='Helvetica', fontSize=9,
                               textColor=C_TEXT, leading=14, spaceAfter=4),
        'small': ParagraphStyle('small', fontName='Helvetica', fontSize=8,
                                textColor=C_MUTED, leading=12),
        'label': ParagraphStyle('label', fontName='Helvetica-Bold', fontSize=8,
                                textColor=C_MUTED, leading=10),
        'mono': ParagraphStyle('mono', fontName='Courier', fontSize=8,
                               textColor=C_TEXT, leading=12),
        'highlight': ParagraphStyle('highlight', fontName='Helvetica-Bold', fontSize=10,
                                    textColor=C_WHITE, leading=14),
        'center': ParagraphStyle('center', fontName='Helvetica', fontSize=9,
                                 textColor=C_TEXT, alignment=TA_CENTER),
    }
    return styles


# ─── Section builders ────────────────────────────────────────────────────────

def section_divider(title, styles):
    return [
        Spacer(1, 0.3 * cm),
        HRFlowable(width='100%', thickness=1, color=C_BORDER),
        Spacer(1, 0.1 * cm),
        Paragraph(title.upper(), styles['section_header']),
    ]


def build_header(data, styles, page_width):
    now = datetime.now().strftime('%B %d, %Y · %H:%M')
    info = data.get('image_info', {})
    style_det = data.get('style', {})
    scores = data.get('scores', {})

    header_table = Table([
        [
            Paragraph('Portfolio Design Analysis', styles['title']),
            Paragraph(f"Generated: {now}<br/>Resolution: {info.get('width','?')}×{info.get('height','?')}px<br/>Style: <b>{style_det.get('detected','Unknown')}</b>",
                      styles['small'])
        ]
    ], colWidths=[12 * cm, 6 * cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))

    # Overall score banner
    overall = scores.get('overall', 0)
    col = score_color(overall)
    banner_data = [[
        Paragraph(f'<font color="#ffffff"><b>Overall Score</b></font>', styles['center']),
        Paragraph(f'<font size="22"><b>{overall:.0f}</b></font>/100', styles['center']),
        Paragraph(f'<font color="#94a3b8">Design Style: <b>{style_det.get("detected","?")}</b> · {style_det.get("confidence",0):.0f}% confidence</font>',
                  styles['center']),
    ]]
    banner = Table(banner_data, colWidths=[4 * cm, 4 * cm, 10 * cm])
    banner.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), C_CARD),
        ('ROUNDEDCORNERS', [6]),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BOX', (0, 0), (-1, -1), 1, C_ACCENT),
    ]))

    return [header_table, Spacer(1, 0.4 * cm), banner]


def build_scores_section(scores, styles):
    elems = section_divider('Score Breakdown', styles)

    score_items = [
        ('Overall', scores.get('overall', 0)),
        ('Contrast', scores.get('contrast', 0)),
        ('Balance', scores.get('balance', 0)),
        ('Whitespace', scores.get('whitespace', 0)),
        ('Color Variety', scores.get('color_variety', 0)),
        ('Complexity', scores.get('complexity', 0)),
    ]

    rows = []
    for label, val in score_items:
        col = score_color(val)
        rating = 'Excellent' if val >= 75 else 'Good' if val >= 60 else 'Fair' if val >= 40 else 'Poor'
        rows.append([
            Paragraph(label, styles['label']),
            draw_bar(val, width=160, height=8),
            Paragraph(f'<b>{val:.0f}</b>', styles['highlight']),
            Paragraph(rating, styles['small']),
        ])

    table = Table(rows, colWidths=[3.5 * cm, 7 * cm, 2 * cm, 3 * cm])
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [C_CARD, colors.HexColor('#161625')]),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('BOX', (0, 0), (-1, -1), 1, C_BORDER),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, C_BORDER),
    ]))
    elems.append(table)
    return elems


def build_palette_section(palette, styles):
    elems = section_divider('Color Palette', styles)

    rows = [[
        Paragraph('Swatch', styles['label']),
        Paragraph('Hex', styles['label']),
        Paragraph('RGB', styles['label']),
        Paragraph('Usage %', styles['label']),
        Paragraph('Brightness', styles['label']),
        Paragraph('H / S / V', styles['label']),
        Paragraph('Type', styles['label']),
    ]]

    for c in palette:
        r, g, b = c['rgb']
        rows.append([
            draw_color_swatch(c['hex'], 20, 16),
            Paragraph(f"<b>{c['hex']}</b>", styles['mono']),
            Paragraph(f"{r}, {g}, {b}", styles['small']),
            Paragraph(f"{c['percentage']:.1f}%", styles['body']),
            Paragraph(f"{c['brightness']:.0f}", styles['body']),
            Paragraph(f"{c['hue']:.0f}° / {c['saturation']:.0f}% / {c['value']:.0f}%", styles['small']),
            Paragraph('Dark' if c['is_dark'] else 'Light', styles['small']),
        ])

    table = Table(rows, colWidths=[1.8*cm, 2.5*cm, 2.5*cm, 2*cm, 2.5*cm, 3.2*cm, 1.5*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_ACCENT),
        ('TEXTCOLOR', (0, 0), (-1, 0), C_WHITE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_CARD, colors.HexColor('#161625')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 1, C_BORDER),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, C_BORDER),
    ]))
    elems.append(table)
    return elems


def build_contrast_section(contrast, styles):
    elems = section_divider('Contrast Analysis', styles)

    best = contrast.get('best_pair', {}) or {}
    summary_data = [
        [Paragraph('Best Contrast Ratio', styles['label']),
         Paragraph(f"<b>{contrast.get('best_ratio', 0):.2f}:1</b>", styles['highlight'])],
        [Paragraph('WCAG AA Pass Rate', styles['label']),
         Paragraph(f"<b>{contrast.get('wcag_aa_pass_rate', 0):.1f}%</b>", styles['highlight'])],
        [Paragraph('Best Pair', styles['label']),
         Paragraph(f"{best.get('color1','?')} → {best.get('color2','?')}", styles['mono'])],
        [Paragraph('AA Status', styles['label']),
         Paragraph('<b>✓ PASS</b>' if best.get('wcag_aa') else '✗ FAIL', styles['highlight'])],
    ]

    t = Table(summary_data, colWidths=[6*cm, 10*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), C_CARD),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('BOX', (0, 0), (-1, -1), 1, C_BORDER),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, C_BORDER),
    ]))
    elems.append(t)
    elems.append(Spacer(1, 0.3*cm))

    # Top contrast pairs table
    pairs = contrast.get('pairs', [])[:6]
    if pairs:
        elems.append(Paragraph('Top Contrast Pairs', styles['label']))
        elems.append(Spacer(1, 0.15*cm))
        pair_rows = [[
            Paragraph('Color 1', styles['label']),
            Paragraph('Color 2', styles['label']),
            Paragraph('Ratio', styles['label']),
            Paragraph('AA', styles['label']),
            Paragraph('AAA', styles['label']),
        ]]
        for p in pairs:
            pair_rows.append([
                Paragraph(p['color1'], styles['mono']),
                Paragraph(p['color2'], styles['mono']),
                Paragraph(f"{p['ratio']:.2f}:1", styles['body']),
                Paragraph('✓' if p['wcag_aa'] else '✗', styles['body']),
                Paragraph('✓' if p['wcag_aaa'] else '✗', styles['body']),
            ])
        pt = Table(pair_rows, colWidths=[4*cm, 4*cm, 3*cm, 2*cm, 2*cm])
        pt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), C_ACCENT2),
            ('TEXTCOLOR', (0, 0), (-1, 0), C_WHITE),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_CARD, colors.HexColor('#161625')]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('BOX', (0, 0), (-1, -1), 1, C_BORDER),
            ('LINEBELOW', (0, 0), (-1, -2), 0.5, C_BORDER),
        ]))
        elems.append(pt)

    return elems


def build_layout_section(balance, whitespace, edge_density, styles):
    elems = section_divider('Layout & Whitespace', styles)

    rows = [
        ['L/R Balance', f"{balance.get('lr_balance', 0):.1f}%", balance.get('lr_balance', 0)],
        ['T/B Balance', f"{balance.get('tb_balance', 0):.1f}%", balance.get('tb_balance', 0)],
        ['Edge Balance', f"{balance.get('edge_balance', 0):.1f}%", balance.get('edge_balance', 0)],
        ['Overall Balance', f"{balance.get('overall', 0):.1f}%", balance.get('overall', 0)],
        ['Whitespace Ratio', f"{whitespace.get('whitespace_ratio', 0):.1f}%", whitespace.get('score', 0)],
        ['Negative Space', f"{whitespace.get('negative_space', 0):.1f}%", whitespace.get('score', 0)],
        ['Edge Density', f"{edge_density:.1f}%", max(0, 100 - edge_density * 5)],
    ]

    table_rows = []
    for label, val_str, score in rows:
        table_rows.append([
            Paragraph(label, styles['label']),
            draw_bar(min(100, score), width=140, height=8),
            Paragraph(f'<b>{val_str}</b>', styles['body']),
        ])

    t = Table(table_rows, colWidths=[5*cm, 6.5*cm, 3*cm])
    t.setStyle(TableStyle([
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [C_CARD, colors.HexColor('#161625')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('BOX', (0, 0), (-1, -1), 1, C_BORDER),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, C_BORDER),
    ]))
    elems.append(t)
    return elems


def build_style_section(style, styles):
    elems = section_divider('Design Style Detection', styles)

    detected = style.get('detected', 'Unknown')
    confidence = style.get('confidence', 0)
    scores_dict = style.get('scores', {})

    elems.append(Paragraph(
        f'Detected: <b>{detected}</b> &nbsp;|&nbsp; Confidence: <b>{confidence:.0f}%</b>',
        styles['highlight']
    ))
    elems.append(Spacer(1, 0.2*cm))

    style_rows = []
    for style_name, score_val in sorted(scores_dict.items(), key=lambda x: -x[1]):
        style_rows.append([
            Paragraph(style_name, styles['label']),
            draw_bar(score_val, width=140, height=8, color=C_ACCENT if style_name == detected else C_MUTED),
            Paragraph(f'{score_val:.0f}%', styles['body']),
        ])

    t = Table(style_rows, colWidths=[5*cm, 6.5*cm, 3*cm])
    t.setStyle(TableStyle([
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [C_CARD, colors.HexColor('#161625')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('BOX', (0, 0), (-1, -1), 1, C_BORDER),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, C_BORDER),
    ]))
    elems.append(t)
    return elems


def build_suggestions_section(suggestions, styles):
    elems = section_divider('Improvement Recommendations', styles)

    for i, s in enumerate(suggestions):
        priority = s.get('priority', 'Low')
        pc = priority_color(priority)

        rows = [
            [
                Paragraph(f'#{i+1}', styles['label']),
                Paragraph(f'<b>{s.get("issue","")}</b>', styles['highlight']),
                Paragraph(priority, styles['label']),
            ],
            [
                Paragraph('', styles['body']),
                Paragraph(s.get('suggestion', ''), styles['body']),
                Paragraph(s.get('category', ''), styles['small']),
            ]
        ]
        t = Table(rows, colWidths=[1.2*cm, 13*cm, 3.3*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), C_CARD),
            ('LEFTBORDERPADDING', (0, 0), (0, -1), 0),
            ('LINEBEFORE', (0, 0), (0, -1), 3, pc),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('BOX', (0, 0), (-1, -1), 1, C_BORDER),
        ]))
        elems.append(KeepTogether([t, Spacer(1, 0.2*cm)]))

    return elems


def build_footer(styles):
    return [
        Spacer(1, 0.5*cm),
        HRFlowable(width='100%', thickness=0.5, color=C_BORDER),
        Spacer(1, 0.15*cm),
        Paragraph(
            f'Portfolio Design Analyzer · Report generated {datetime.now().strftime("%B %d, %Y")} · Powered by OpenCV + scikit-learn',
            ParagraphStyle('footer', fontName='Helvetica', fontSize=7,
                           textColor=C_MUTED, alignment=TA_CENTER)
        ),
    ]


# ─── Main PDF Generator ──────────────────────────────────────────────────────

def generate_pdf_report(data, output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        title='Portfolio Design Analysis',
        author='Portfolio Analyzer',
    )

    page_width = A4[0] - 3.6*cm
    styles = make_styles()
    story = []

    # Build all sections
    story += build_header(data, styles, page_width)
    story += build_scores_section(data.get('scores', {}), styles)
    story += build_palette_section(data.get('palette', []), styles)
    story += build_contrast_section(data.get('contrast', {}), styles)
    story += build_layout_section(
        data.get('balance', {}),
        data.get('whitespace', {}),
        data.get('edge_density', 0),
        styles
    )
    story += build_style_section(data.get('style', {}), styles)
    story += build_suggestions_section(data.get('suggestions', []), styles)
    story += build_footer(styles)

    # Dark background on all pages
    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(C_BG)
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
