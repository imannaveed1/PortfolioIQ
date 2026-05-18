import os
import re
import uuid
import requests


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
    url = normalize_url(url)
    if not is_valid_url(url):
        raise ValueError(f"Invalid URL: {url}")

    os.makedirs(output_dir, exist_ok=True)
    filename = f"screenshot_{uuid.uuid4().hex}.png"
    filepath = os.path.join(output_dir, filename)

    print(f"[Screenshotter] Taking screenshot via API for: {url}")

    ACCESS_KEY = "0x0vtRz9SeXXYA"

    api_url = "https://api.screenshotone.com/take"
    params = {
        "access_key": ACCESS_KEY,
        "url": url,
        "viewport_width": 1440,
        "viewport_height": 900,
        "format": "png",
        "block_ads": "true",
        "block_cookie_banners": "true",
        "block_trackers": "true",
        "delay": 2,
        "timeout": 30,
    }

    try:
        response = requests.get(api_url, params=params, timeout=60, stream=True)

        if response.status_code != 200:
            error_text = response.text[:200] if response.text else "Unknown error"
            raise ConnectionError(f"Screenshot API error {response.status_code}: {error_text}")

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"[Screenshotter] Done: {filepath}")

        # Try to get page title
        title = url
        try:
            head_response = requests.get(url, timeout=10)
            import re as re2
            match = re2.search(r'<title>(.*?)</title>', head_response.text, re2.IGNORECASE)
            if match:
                title = match.group(1).strip()
        except Exception:
            pass

        return {
            'path': filepath,
            'filename': filename,
            'title': title,
            'url': url,
        }

    except ConnectionError:
        raise
    except Exception as e:
        raise ConnectionError(f"Screenshot API failed: {str(e)}")
