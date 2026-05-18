"""抖音 Cookie：二维码登录、写入 Evil0ctal 配置、健康检查。"""
import base64
import os
import re
import threading
import time

import requests
import yaml

CONFIG_PATH = os.environ.get('DOUYIN_CONFIG_PATH', '/data/douyin/config.yaml')
DOUYIN_API_URL = os.environ.get('DOUYIN_API_URL', '').rstrip('/')
TEST_URL = os.environ.get(
    'DOUYIN_COOKIE_TEST_URL',
    'https://v.douyin.com/MpeyIZyxMTA/',
)
CHECK_INTERVAL = int(os.environ.get('COOKIE_CHECK_INTERVAL', '300'))


def _get_api_urls():
    if DOUYIN_API_URL:
        yield DOUYIN_API_URL
        return

    yield 'http://127.0.0.1:80'
    yield 'http://127.0.0.1:8080'
    yield 'http://localhost:80'
    yield 'http://localhost:8080'
    yield 'http://douyin-api:80'


def _request_douyin_api(path, params=None):
    errors = []
    for base_url in _get_api_urls():
        url = f'{base_url}{path}'
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as exc:
            errors.append(f'{base_url}: {exc}')
            if DOUYIN_API_URL:
                break

    raise RuntimeError(
        '解析服务不可用，请检查 DOUYIN_API_URL 或后端服务是否已启动。'
        f' 尝试地址: {", ".join(_get_api_urls())}; 错误: {" | ".join(errors)}'
    )

_lock = threading.Lock()
_status = 'checking'  # checking | valid | invalid | scanning
_qr_base64 = ''
_message = ''
_login_thread = None


def _ensure_config_dir():
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)


def _cookies_to_header(cookies):
    parts = []
    for c in cookies:
        domain = c.get('domain', '')
        if 'douyin' not in domain and domain not in ('', '.douyin.com'):
            continue
        name = c.get('name', '')
        value = c.get('value', '')
        if name and value is not None:
            parts.append(f'{name}={value}')
    return '; '.join(parts)


def _write_config(cookie_header):
    _ensure_config_dir()
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        f.write(f'Cookie: {cookie_header}\n')


def _read_cookie_header():
    if not os.path.isfile(CONFIG_PATH):
        return ''
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        return (data.get('Cookie') or '').strip()
    except Exception:
        return ''


def _test_cookie_with_api():
    cookie = _read_cookie_header()
    if not cookie or len(cookie) < 20:
        return False, '未配置 Cookie'
    try:
        body = _request_douyin_api(
            '/api/hybrid/video_data',
            params={'url': TEST_URL, 'minimal': 'true'},
        )
        code = body.get('code', body.get('status_code', 0))
        if code in (200, '200', 0):
            return True, 'Cookie 有效'
        msg = body.get('message') or body.get('msg') or str(body)[:200]
        if 'cookie' in str(msg).lower():
            return False, 'Cookie 已失效'
        return False, msg
    except Exception as e:
        return False, f'解析服务不可用: {e}'


def get_status():
    with _lock:
        return {
            'status': _status,
            'qrCode': _qr_base64,
            'message': _message,
            'hasCookie': bool(_read_cookie_header()),
        }


def check_validity(force=False):
    global _status, _message
    with _lock:
        if _status == 'scanning' and not force:
            return get_status()
        _status = 'checking'
        _message = '正在检查 Cookie...'

    ok, msg = _test_cookie_with_api()
    with _lock:
        _status = 'valid' if ok else 'invalid'
        _message = msg
    return get_status()


def _run_qr_login():
    global _status, _qr_base64, _message
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        with _lock:
            _status = 'invalid'
            _message = '未安装 Playwright，请重新构建 Docker 镜像'
            _qr_base64 = ''
        return

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage'],
            )
            context = browser.new_context(
                user_agent=(
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
                ),
                viewport={'width': 1280, 'height': 900},
                locale='zh-CN',
            )
            page = context.new_page()
            page.goto('https://www.douyin.com/', wait_until='domcontentloaded', timeout=60000)
            time.sleep(3)

            for text in ('登录', '扫码登录'):
                try:
                    page.get_by_text(text, exact=False).first.click(timeout=3000)
                    time.sleep(1)
                    break
                except Exception:
                    continue

            time.sleep(2)
            png = None
            selectors = [
                'img[src*="qr"]',
                '.login-qrcode img',
                'div[class*="qrcode"] img',
                'canvas',
            ]
            for sel in selectors:
                el = page.query_selector(sel)
                if el:
                    try:
                        png = el.screenshot(type='png')
                        break
                    except Exception:
                        continue
            if not png:
                panel = page.query_selector('div[class*="login"]')
                png = panel.screenshot(type='png') if panel else page.screenshot(type='png')

            with _lock:
                _qr_base64 = base64.b64encode(png).decode('ascii')
                _message = '请使用抖音 App 扫描二维码登录'

            logged_in = False
            for _ in range(180):
                cookies = context.cookies()
                names = {c.get('name', '') for c in cookies}
                if names & {'sessionid', 'sid_tt', 'uid_tt', 'passport_csrf_token'}:
                    header = _cookies_to_header(cookies)
                    if len(header) > 50:
                        _write_config(header)
                        logged_in = True
                        break
                time.sleep(1)

            browser.close()

            with _lock:
                if logged_in:
                    _status = 'valid'
                    _qr_base64 = ''
                    _message = '登录成功，Cookie 已更新'
                else:
                    _status = 'invalid'
                    _qr_base64 = ''
                    _message = '扫码超时或失败，请重试'

    except Exception as e:
        with _lock:
            _status = 'invalid'
            _qr_base64 = ''
            _message = f'二维码登录失败: {e}'


def start_qr_login():
    global _login_thread, _status
    with _lock:
        if _status == 'scanning':
            return get_status()
        if _login_thread and _login_thread.is_alive():
            return get_status()
        _status = 'scanning'
        _qr_base64 = ''
        _message = '正在生成二维码...'

    _login_thread = threading.Thread(target=_run_qr_login, daemon=True)
    _login_thread.start()
    return get_status()


def start_monitor():
    def loop():
        time.sleep(10)
        while True:
            try:
                st = get_status()
                if st['status'] != 'scanning':
                    check_validity()
            except Exception:
                pass
            time.sleep(CHECK_INTERVAL)

    threading.Thread(target=loop, daemon=True).start()
