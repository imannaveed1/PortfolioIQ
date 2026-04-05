import os
import re
import uuid
import time


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

    print(f"[Screenshotter] Starting for: {url}")

    # Check for system Chromium (Railway/Linux)
    chromium_path = None
    for path in ['/usr/bin/chromium', '/usr/bin/chromium-browser',
                 '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable']:
        if os.path.exists(path):
            chromium_path = path
            break

    with sync_playwright() as p:

        # ── Launch browser ────────────────────────────────────────────────
        launch_kwargs = {
            'headless': True,
            'args': [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-web-security',
                '--ignore-certificate-errors',
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--allow-running-insecure-content',
                '--disable-extensions',
                '--no-first-run',
                '--no-default-browser-check',
                '--window-size=1440,900',
                '--start-maximized',
                '--lang=en-US,en',
            ]
        }
        if chromium_path:
            launch_kwargs['executable_path'] = chromium_path

        try:
            browser = p.chromium.launch(**launch_kwargs)
        except Exception as e:
            raise ConnectionError(f"Could not launch browser: {e}")

        try:
            # ── Create stealth context ────────────────────────────────────
            context = browser.new_context(
                viewport={'width': 1440, 'height': 900},
                screen={'width': 1440, 'height': 900},
                user_agent=(
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                ),
                locale='en-US',
                timezone_id='America/New_York',
                java_script_enabled=True,
                ignore_https_errors=True,
                extra_http_headers={
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0',
                }
            )

            page = context.new_page()

            # ── Hide automation fingerprints ──────────────────────────────
            page.add_init_script("""
                // Hide webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });

                // Mock plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });

                // Mock languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });

                // Mock chrome object
                window.chrome = {
                    runtime: {}
                };

                // Mock permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
                );
            """)

            # ── Block heavy unnecessary resources ─────────────────────────
            def handle_route(route):
                if route.request.resource_type in ['media', 'font']:
                    route.abort()
                else:
                    route.continue_()

            page.route('**/*', handle_route)

            # ── Try loading the page ──────────────────────────────────────
            loaded = False
            last_error = None

            strategies = [
                ('domcontentloaded', 25000),
                ('load', 25000),
                ('networkidle', 20000),
            ]

            for strategy, timeout in strategies:
                try:
                    print(f"[Screenshotter] Trying strategy: {strategy}")
                    page.goto(url, wait_until=strategy, timeout=timeout)
                    loaded = True
                    print(f"[Screenshotter] Loaded with: {strategy}")
                    break
                except Exception as e:
                    last_error = str(e)
                    print(f"[Screenshotter] Failed with {strategy}: {e}")

                    # Try navigating again before next strategy
                    try:
                        page.reload(wait_until='domcontentloaded', timeout=10000)
                        loaded = True
                        break
                    except Exception:
                        pass

            if not loaded:
                raise ConnectionError(
                    f"This website could not be loaded. "
                    f"It may be blocking automated access (common on Behance, Dribbble, LinkedIn). "
                    f"Please try a personal portfolio website instead."
                )

            # ── Wait for content to render ────────────────────────────────
            try:
                # Wait for images to load
                page.wait_for_load_state('domcontentloaded', timeout=5000)
            except Exception:
                pass

            try:
                page.wait_for_timeout(3000)
            except Exception:
                pass

            # ── Scroll to trigger lazy loading ────────────────────────────
            try:
                page.evaluate("window.scrollTo(0, 300)")
                page.wait_for_timeout(500)
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(500)
            except Exception:
                pass

            # ── Get title ─────────────────────────────────────────────────
            title = url
            try:
                title = page.title() or url
            except Exception:
                pass

            # ── Take screenshot ───────────────────────────────────────────
            print(f"[Screenshotter] Taking screenshot. Title: {title}")
            page.screenshot(
                path=filepath,
                full_page=False,
                type='png',
                clip={'x': 0, 'y': 0, 'width': 1440, 'height': 900}
            )

        except ConnectionError:
            raise
        except Exception as e:
            raise ConnectionError(f"Browser error: {str(e)}")
        finally:
            try:
                browser.close()
            except Exception:
                pass

    print(f"[Screenshotter] Done: {filepath}")
    return {
        'path': filepath,
        'filename': filename,
        'title': title,
        'url': url,
    }
