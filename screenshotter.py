import os
import re
import uuid


def is_valid_url(url: str) -> bool:
    pattern = re.compile(
        r'^(https?://)'
        r'([a-zA-Z0-9\-]+\.)+[a-zA-Z]{2,}'
        r'(:\d+)?(/.*)?$'
    )
    return bool(pattern.match(url.strip()))


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url


def screenshot_url(url: str, output_dir: str = 'uploads') -> dict:
    from playwright.sync_api import sync_playwright

    url = normalize_url(url)
    if not is_valid_url(url):
        raise ValueError(f"Invalid URL: {url}")

    os.makedirs(output_dir, exist_ok=True)
    filename = f"screenshot_{uuid.uuid4().hex}.png"
    filepath = os.path.join(output_dir, filename)

    print(f"[Screenshotter] Launching browser for: {url}")

    # Check for system Chromium (used on Railway/Linux)
    chromium_path = None
    system_paths = [
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        '/usr/bin/google-chrome',
        '/usr/bin/google-chrome-stable',
    ]
    for path in system_paths:
        if os.path.exists(path):
            chromium_path = path
            print(f"[Screenshotter] Using system Chromium: {path}")
            break

    with sync_playwright() as p:
        launch_args = {
            'headless': True,
            'args': [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-web-security',
                '--ignore-certificate-errors',
                '--single-process',
            ]
        }

        if chromium_path:
            launch_args['executable_path'] = chromium_path

        browser = p.chromium.launch(**launch_args)

        page = browser.new_page(
            viewport={'width': 1440, 'height': 900},
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )
        )

        loaded = False
        last_error = None

        for strategy in ['networkidle', 'domcontentloaded', 'load']:
            try:
                print(f"[Screenshotter] Trying wait_until='{strategy}'...")
                page.goto(url, wait_until=strategy, timeout=25000)
                loaded = True
                print(f"[Screenshotter] Page loaded with strategy: {strategy}")
                break
            except Exception as e:
                last_error = str(e)
                print(f"[Screenshotter] Strategy '{strategy}' failed: {e}")
                continue

        if not loaded:
            browser.close()
            raise ConnectionError(f"Could not load {url}. Error: {last_error}")

        try:
            page.wait_for_timeout(2500)
        except Exception:
            pass

        title = ''
        try:
            title = page.title() or url
        except Exception:
            title = url

        print(f"[Screenshotter] Taking screenshot. Title: {title}")
        page.screenshot(path=filepath, full_page=False, type='png')
        browser.close()

    print(f"[Screenshotter] Done: {filepath}")
    return {
        'path': filepath,
        'filename': filename,
        'title': title,
        'url': url,
    }
