import os
import subprocess
import sys

port = os.environ.get('PORT', '8080')
print(f"Starting gunicorn on port {port}")

subprocess.run([
    sys.executable, '-m', 'gunicorn',
    'app:app',
    '--workers', '1',
    '--timeout', '180',
    '--bind', f'0.0.0.0:{port}',
    '--preload',
])