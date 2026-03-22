import os
import uuid
import json
import traceback
import threading
import numpy as np
from flask import Flask, request, jsonify, send_file, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.utils import secure_filename
from analyzer import analyze_portfolio
from report_generator import generate_pdf_report


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer): return int(obj)
        if isinstance(obj, np.floating): return float(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        if isinstance(obj, np.bool_): return bool(obj)
        return super().default(obj)


app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['REPORT_FOLDER'] = 'reports'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///portfolioiq.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.json_encoder = NumpyEncoder

db = SQLAlchemy(app)

# ─── Database Model ───────────────────────────────────────────────────────────

class Analysis(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    source_type = db.Column(db.String(10))
    source_name = db.Column(db.String(500))
    overall     = db.Column(db.Float)
    style       = db.Column(db.String(50))
    scores_json = db.Column(db.Text)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# ─── Helpers ──────────────────────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_analysis(results):
    try:
        record = Analysis(
            source_type = results['source']['type'],
            source_name = results['source'].get('url') or results['source'].get('name', ''),
            overall     = results['scores']['overall'],
            style       = results['style']['detected'],
            scores_json = json.dumps(results['scores']),
        )
        db.session.add(record)
        db.session.commit()
    except Exception as e:
        print(f"[DB] Error saving analysis: {e}")

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400
    file = request.files['image']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400

    filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        results = analyze_portfolio(filepath)
        results['source'] = {'type': 'upload', 'name': file.filename}
        save_analysis(results)
        return jsonify(results)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/analyze-url', methods=['POST'])
def analyze_url():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'No URL provided'}), 400

    url = data['url'].strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    print(f"\n[URL Analysis] Starting: {url}")

    result_container = {}

    def do_screenshot():
        try:
            from screenshotter import screenshot_url
            shot = screenshot_url(url, output_dir=app.config['UPLOAD_FOLDER'])
            result_container['shot'] = shot
        except Exception as e:
            result_container['error'] = str(e)
            traceback.print_exc()

    t = threading.Thread(target=do_screenshot)
    t.start()
    t.join(timeout=60)

    if t.is_alive():
        return jsonify({'error': 'Page took too long to load. Try a different URL.'}), 408

    if result_container.get('error'):
        return jsonify({'error': result_container['error']}), 502

    shot = result_container.get('shot')
    if not shot:
        return jsonify({'error': 'Screenshot failed. Check the URL and try again.'}), 500

    try:
        results = analyze_portfolio(shot['path'])
        results['source'] = {
            'type': 'url',
            'url': shot['url'],
            'title': shot['title'],
            'screenshot': shot['filename'],
        }
        save_analysis(results)
        return jsonify(results)
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/report', methods=['POST'])
def report():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    report_id = uuid.uuid4().hex
    report_path = os.path.join(app.config['REPORT_FOLDER'], f"report_{report_id}.pdf")

    try:
        generate_pdf_report(data, report_path)
        return send_file(report_path, as_attachment=True,
                         download_name='portfolio_analysis.pdf',
                         mimetype='application/pdf')
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/stats')
def stats():
    try:
        total     = Analysis.query.count()
        avg_score = db.session.query(db.func.avg(Analysis.overall)).scalar() or 0
        top_style = db.session.query(
            Analysis.style, db.func.count(Analysis.style)
        ).group_by(Analysis.style).order_by(db.func.count(Analysis.style).desc()).first()

        recent = Analysis.query.order_by(Analysis.created_at.desc()).limit(5).all()
        recent_list = [{
            'source': a.source_name,
            'score': a.overall,
            'style': a.style,
            'date': a.created_at.strftime('%Y-%m-%d %H:%M')
        } for a in recent]

        return jsonify({
            'total_analyses': total,
            'average_score': round(float(avg_score), 1),
            'most_common_style': top_style[0] if top_style else 'N/A',
            'recent': recent_list
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('reports', exist_ok=True)
    app.run(debug=False, port=5000, threaded=True)
