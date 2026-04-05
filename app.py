import os
import uuid
import json
import traceback
import threading
import numpy as np
from flask import Flask, request, jsonify, send_file, render_template, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
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
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'portfolioiq-secret-2024')
app.json_encoder = NumpyEncoder

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Create folders at startup
os.makedirs('uploads', exist_ok=True)
os.makedirs('reports', exist_ok=True)

# ─── Database Models ──────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(150), unique=True, nullable=False)
    password   = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    analyses   = db.relationship('Analysis', backref='user', lazy=True)

class Analysis(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    source_type = db.Column(db.String(10))
    source_name = db.Column(db.String(500))
    overall     = db.Column(db.Float)
    style       = db.Column(db.String(50))
    scores_json = db.Column(db.Text)
    full_json   = db.Column(db.Text)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all(checkfirst=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ─── Helpers ──────────────────────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_analysis(results):
    try:
        record = Analysis(
            user_id     = current_user.id if current_user.is_authenticated else None,
            source_type = results['source']['type'],
            source_name = results['source'].get('url') or results['source'].get('name', ''),
            overall     = results['scores']['overall'],
            style       = results['style']['detected'],
            scores_json = json.dumps(results['scores']),
            full_json   = json.dumps(results),
        )
        db.session.add(record)
        db.session.commit()
        return record.id
    except Exception as e:
        print(f"[DB] Error saving analysis: {e}")
        return None

# ─── Auth Routes ──────────────────────────────────────────────────────────────

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        data     = request.get_json()
        name     = data.get('name', '').strip()
        email    = data.get('email', '').strip().lower()
        password = data.get('password', '')

        if not name or not email or not password:
            return jsonify({'error': 'All fields are required'}), 400

        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400

        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already registered'}), 400

        user = User(
            name     = name,
            email    = email,
            password = generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return jsonify({'success': True, 'name': user.name})

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data     = request.get_json()
        email    = data.get('email', '').strip().lower()
        password = data.get('password', '')

        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            return jsonify({'error': 'Invalid email or password'}), 401

        login_user(user)
        return jsonify({'success': True, 'name': user.name})

    return render_template('login.html')


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/history')
@login_required
def history():
    analyses = Analysis.query.filter_by(user_id=current_user.id)\
                .order_by(Analysis.created_at.desc()).all()
    return render_template('history.html', analyses=analyses, user=current_user)


@app.route('/history/<int:analysis_id>')
@login_required
def view_analysis(analysis_id):
    record = Analysis.query.filter_by(id=analysis_id, user_id=current_user.id).first()
    if not record:
        return redirect(url_for('history'))
    try:
        data = json.loads(record.full_json) if record.full_json else {}
    except Exception:
        data = {}
    if not data and record.scores_json:
        try:
            data['scores'] = json.loads(record.scores_json)
        except Exception:
            data['scores'] = {}
    return render_template('view_analysis.html', data=data, record=record)


@app.route('/auth/status')
def auth_status():
    if current_user.is_authenticated:
        return jsonify({'logged_in': True, 'name': current_user.name, 'email': current_user.email})
    return jsonify({'logged_in': False})

# ─── Main Routes ──────────────────────────────────────────────────────────────

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
        analysis_id = save_analysis(results)
        results['analysis_id'] = analysis_id
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
        return jsonify({'error': 'Page took too long to load.'}), 408
    if result_container.get('error'):
        return jsonify({'error': result_container['error']}), 502

    shot = result_container.get('shot')
    if not shot:
        return jsonify({'error': 'Screenshot failed.'}), 500

    try:
        results = analyze_portfolio(shot['path'])
        results['source'] = {
            'type': 'url',
            'url': shot['url'],
            'title': shot['title'],
            'screenshot': shot['filename'],
        }
        analysis_id = save_analysis(results)
        results['analysis_id'] = analysis_id
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

        return jsonify({
            'total_analyses': total,
            'average_score': round(float(avg_score), 1),
            'most_common_style': top_style[0] if top_style else 'N/A',
            'total_users': User.query.count(),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=False, port=5000, threaded=True)
