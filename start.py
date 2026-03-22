import os
import subprocess
import sys

port = os.environ.get('PORT', '8080')
print(f"Starting gunicorn on port {port}")

subprocess.run([
    sys.executable, '-m', 'gunicorn',
    'app:app',
    '--workers', '2',
    '--timeout', '120',
    '--bind', f'0.0.0.0:{port}'
])
