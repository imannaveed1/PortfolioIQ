import cv2
import numpy as np
from sklearn.cluster import KMeans
import colorsys


# ─── Numpy Sanitizer ─────────────────────────────────────────────────────────

def convert(obj):
    if isinstance(obj, dict):
        return {k: convert(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert(i) for i in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    else:
        return obj


def rgb_to_hex(r, g, b):
    return '#{:02x}{:02x}{:02x}'.format(int(r), int(g), int(b))

def relative_luminance(r, g, b):
    def linearize(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)

def contrast_ratio(c1, c2):
    l1 = relative_luminance(*c1)
    l2 = relative_luminance(*c2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)

def color_brightness(r, g, b):
    return (r * 299 + g * 587 + b * 114) / 1000

def is_dark(r, g, b):
    return color_brightness(r, g, b) < 128

def rgb_to_hsv_values(r, g, b):
    h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
    return h * 360, s * 100, v * 100


def extract_color_palette(image_rgb, n_colors=8):
    pixels = image_rgb.reshape(-1, 3).astype(np.float32)
    if len(pixels) > 10000:
        idx = np.random.choice(len(pixels), 10000, replace=False)
        pixels_sample = pixels[idx]
    else:
        pixels_sample = pixels

    kmeans = KMeans(n_clusters=n_colors, random_state=42, n_init=10, max_iter=200)
    kmeans.fit(pixels_sample)
    centers = kmeans.cluster_centers_
    labels = kmeans.predict(pixels)
    counts = np.bincount(labels, minlength=n_colors)
    total = int(counts.sum())

    palette = []
    for i in np.argsort(-counts):
        r, g, b = float(centers[i][0]), float(centers[i][1]), float(centers[i][2])
        pct = float(counts[i]) / total * 100
        h_val, s_val, v_val = rgb_to_hsv_values(r, g, b)
        palette.append({
            'hex': rgb_to_hex(r, g, b),
            'rgb': [int(r), int(g), int(b)],
            'percentage': round(pct, 1),
            'brightness': round(float(color_brightness(r, g, b)), 1),
            'is_dark': bool(is_dark(r, g, b)),
            'hue': round(float(h_val), 1),
            'saturation': round(float(s_val), 1),
            'value': round(float(v_val), 1),
        })
    return palette


def analyze_contrast(palette):
    pairs = []
    for i in range(len(palette)):
        for j in range(i + 1, len(palette)):
            c1 = palette[i]['rgb']
            c2 = palette[j]['rgb']
            ratio = float(contrast_ratio(c1, c2))
            pairs.append({
                'color1': palette[i]['hex'],
                'color2': palette[j]['hex'],
                'ratio': round(ratio, 2),
                'wcag_aa': bool(ratio >= 4.5),
                'wcag_aaa': bool(ratio >= 7.0),
                'wcag_large': bool(ratio >= 3.0),
            })
    pairs.sort(key=lambda x: -x['ratio'])
    best = pairs[0] if pairs else None
    aa_count = sum(1 for p in pairs if p['wcag_aa'])
    total = len(pairs)
    return {
        'pairs': pairs[:10],
        'best_ratio': float(best['ratio']) if best else 0.0,
        'best_pair': best,
        'worst_pair': pairs[-1] if pairs else None,
        'wcag_aa_pass_rate': round(aa_count / total * 100, 1) if total else 0.0,
        'overall_score': round(min(100.0, float(best['ratio']) / 21 * 100), 1) if best else 0.0,
    }


def analyze_layout_balance(image_gray):
    h, w = image_gray.shape
    top    = float(image_gray[:h//2].mean())
    bottom = float(image_gray[h//2:].mean())
    left   = float(image_gray[:, :w//2].mean())
    right  = float(image_gray[:, w//2:].mean())
    q1 = float(image_gray[:h//2, :w//2].mean())
    q2 = float(image_gray[:h//2, w//2:].mean())
    q3 = float(image_gray[h//2:, :w//2].mean())
    q4 = float(image_gray[h//2:, w//2:].mean())

    lr_balance = float(1.0 - abs(left - right) / (left + right + 1e-6))
    tb_balance = float(1.0 - abs(top - bottom) / (top + bottom + 1e-6))

    edges = cv2.Canny(image_gray, 50, 150)
    e_vals = [float(edges[:h//2, :w//2].mean()), float(edges[:h//2, w//2:].mean()),
              float(edges[h//2:, :w//2].mean()), float(edges[h//2:, w//2:].mean())]
    edge_balance = float(max(0.0, 1.0 - float(np.std(e_vals)) / 50.0))
    overall = float(lr_balance * 0.4 + tb_balance * 0.3 + edge_balance * 0.3)

    return {
        'lr_balance': round(lr_balance * 100, 1),
        'tb_balance': round(tb_balance * 100, 1),
        'edge_balance': round(edge_balance * 100, 1),
        'overall': round(overall * 100, 1),
        'quadrant_brightness': [round(q1,1), round(q2,1), round(q3,1), round(q4,1)],
        'quadrant_labels': ['Top-Left', 'Top-Right', 'Bottom-Left', 'Bottom-Right'],
        'score': round(overall * 100, 1),
    }


def estimate_whitespace(image_rgb, image_gray):
    whitespace_ratio = float((image_gray > 230).sum()) / float(image_gray.size)
    dark_ratio       = float((image_gray < 25).sum())  / float(image_gray.size)
    neg_space = whitespace_ratio + dark_ratio

    if 0.20 <= neg_space <= 0.60:
        score = 100.0
    elif neg_space < 0.20:
        score = (neg_space / 0.20) * 100.0
    else:
        score = max(0.0, 100.0 - (neg_space - 0.60) / 0.40 * 100.0)

    return {
        'whitespace_ratio': round(whitespace_ratio * 100, 1),
        'dark_ratio':       round(dark_ratio * 100, 1),
        'negative_space':   round(neg_space * 100, 1),
        'score':            round(score, 1),
        'rating': 'Excellent' if score >= 80 else 'Good' if score >= 60 else 'Needs Work',
    }


def detect_design_style(palette, contrast_data, whitespace_data, edge_density):
    avg_saturation = float(np.mean([c['saturation'] for c in palette]))
    avg_brightness = float(np.mean([c['brightness'] for c in palette]))
    num_dark  = sum(1 for c in palette if c['is_dark'])
    num_light = len(palette) - num_dark
    best_contrast = float(contrast_data['best_ratio'])
    neg_space     = float(whitespace_data['negative_space'])
    edge_density  = float(edge_density)

    features = {
        'avg_saturation': avg_saturation,
        'avg_brightness': avg_brightness,
        'dark_ratio':     num_dark / len(palette) if palette else 0.0,
        'best_contrast':  best_contrast,
        'neg_space':      neg_space,
        'edge_density':   edge_density,
    }

    hues = [c['hue'] for c in palette if c['saturation'] > 20]
    hue_spread = float(np.std(hues)) if hues else 0.0

    styles = {
        'Minimalist':    float((neg_space > 40)*0.35 + (avg_saturation < 30)*0.25 + (edge_density < 0.05)*0.25 + (len(palette) <= 4)*0.15),
        'Dark Mode':     float((features['dark_ratio'] > 0.6)*0.5 + (avg_brightness < 80)*0.3 + (best_contrast > 6)*0.2),
        'Brutalist':     float((edge_density > 0.10)*0.35 + (best_contrast > 8)*0.3 + (avg_saturation > 50)*0.2 + (neg_space < 30)*0.15),
        'Glassmorphism': float((30 < avg_brightness < 200)*0.3 + (20 < avg_saturation < 60)*0.3 + (num_light > num_dark)*0.2 + (neg_space > 30)*0.2),
        'Corporate':     float((20 < avg_saturation < 60)*0.3 + (0.04 < edge_density < 0.12)*0.3 + (3 < best_contrast < 9)*0.2 + (30 < neg_space < 60)*0.2),
        'Playful':       float((avg_saturation > 60)*0.35 + (hue_spread > 60)*0.35 + (edge_density > 0.06)*0.3),
        'Editorial':     float((best_contrast > 7)*0.35 + (neg_space > 35)*0.3 + (avg_saturation < 40)*0.2 + (0.05 < edge_density < 0.10)*0.15),
    }

    detected   = max(styles, key=styles.get)
    confidence = round(styles[detected] * 100, 1)
    ranked     = sorted(styles.items(), key=lambda x: -x[1])

    return {
        'detected':   detected,
        'confidence': confidence,
        'scores':     {k: round(v * 100, 1) for k, v in ranked},
        'features':   {k: round(v, 3) for k, v in features.items()},
    }


def calculate_design_score(contrast, balance, whitespace, edge_density, palette):
    contrast_score      = float(min(100.0, contrast['best_ratio'] / 7.0 * 100))
    balance_score       = float(balance['score'])
    ws_score            = float(whitespace['score'])
    color_variety_score = float(max(0, min(100, 100 - abs(len(palette) - 5) * 10)))

    if 0.03 <= edge_density <= 0.12:
        complexity_score = 100.0
    elif edge_density < 0.03:
        complexity_score = float(edge_density / 0.03 * 100)
    else:
        complexity_score = float(max(0.0, 100.0 - (edge_density - 0.12) / 0.08 * 100))

    overall = (contrast_score*0.25 + balance_score*0.25 + ws_score*0.20 +
               color_variety_score*0.15 + complexity_score*0.15)

    return {
        'overall':       round(overall, 1),
        'contrast':      round(contrast_score, 1),
        'balance':       round(balance_score, 1),
        'whitespace':    round(ws_score, 1),
        'color_variety': round(color_variety_score, 1),
        'complexity':    round(complexity_score, 1),
    }


def generate_suggestions(scores, contrast, balance, whitespace, style, palette):
    suggestions = []

    if scores['contrast'] < 60:
        suggestions.append({'priority': 'High', 'category': 'Accessibility',
            'issue': 'Low contrast between key colors',
            'suggestion': f"Best contrast ratio is {contrast['best_ratio']:.1f}:1. Aim for 4.5:1+ for normal text (WCAG AA)."})

    if scores['balance'] < 60:
        weak = 'left-right' if balance['lr_balance'] < balance['tb_balance'] else 'top-bottom'
        suggestions.append({'priority': 'High', 'category': 'Layout',
            'issue': f'Poor {weak} visual balance',
            'suggestion': 'Redistribute visual weight across the layout. Add counterbalancing elements on the lighter side.'})

    if scores['whitespace'] < 60:
        if whitespace['negative_space'] < 20:
            suggestions.append({'priority': 'Medium', 'category': 'Spacing',
                'issue': 'Layout feels cluttered',
                'suggestion': 'Increase padding, margins, and line-height. Negative space is a design element, not wasted space.'})
        else:
            suggestions.append({'priority': 'Low', 'category': 'Spacing',
                'issue': 'Excessive whitespace may feel empty',
                'suggestion': 'Add more content or visual elements to create a more engaging layout.'})

    if scores['color_variety'] < 60:
        if len(palette) > 7:
            suggestions.append({'priority': 'Medium', 'category': 'Color',
                'issue': 'Too many dominant colors',
                'suggestion': 'Limit palette to 3-5 colors. Use the 60-30-10 rule.'})
        else:
            suggestions.append({'priority': 'Low', 'category': 'Color',
                'issue': 'Limited color palette may feel flat',
                'suggestion': 'Add 1-2 accent colors to guide attention and add visual interest.'})

    if scores['complexity'] < 60:
        suggestions.append({'priority': 'Medium', 'category': 'Visual Complexity',
            'issue': 'Layout is visually overcrowded',
            'suggestion': 'Reduce decorative elements and use a consistent spacing grid.'})

    suggestions.append({'priority': 'Info', 'category': 'Design Style',
        'issue': f'Detected style: {style["detected"]} ({style["confidence"]:.0f}% confidence)',
        'suggestion': f'Your design reads as {style["detected"]}. Study reference portfolios in this style for consistency.'})

    return suggestions


def analyze_portfolio(image_path):
    img_bgr = cv2.imread(image_path)
    if img_bgr is None:
        raise ValueError(f"Cannot read image: {image_path}")

    h, w = img_bgr.shape[:2]
    scale = min(1.0, 800 / max(h, w))
    if scale < 1.0:
        img_bgr = cv2.resize(img_bgr, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_AREA)

    img_rgb  = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    h, w = img_bgr.shape[:2]

    edges = cv2.Canny(img_gray, 50, 150)
    edge_density = float(edges.sum()) / (255.0 * float(edges.size))

    palette     = extract_color_palette(img_rgb, n_colors=8)
    contrast    = analyze_contrast(palette)
    balance     = analyze_layout_balance(img_gray)
    whitespace  = estimate_whitespace(img_rgb, img_gray)
    style       = detect_design_style(palette, contrast, whitespace, edge_density)
    scores      = calculate_design_score(contrast, balance, whitespace, edge_density, palette)
    suggestions = generate_suggestions(scores, contrast, balance, whitespace, style, palette)

    result = {
        'image_info': {'width': int(w), 'height': int(h), 'aspect_ratio': round(float(w)/float(h), 2)},
        'palette':      palette,
        'contrast':     contrast,
        'balance':      balance,
        'whitespace':   whitespace,
        'edge_density': round(edge_density * 100, 2),
        'style':        style,
        'scores':       scores,
        'suggestions':  suggestions,
    }

    return convert(result)
