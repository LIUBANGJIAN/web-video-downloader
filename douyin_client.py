"""调用自建 Evil0ctal API 解析与下载抖音视频。"""
import os
import re

import requests

DOUYIN_API_URL = os.environ.get('DOUYIN_API_URL', '').rstrip('/')


def _get_api_urls():
    if DOUYIN_API_URL:
        yield DOUYIN_API_URL
        return

    yield 'http://127.0.0.1:80'
    yield 'http://127.0.0.1:8080'
    yield 'http://localhost:80'
    yield 'http://localhost:8080'
    yield 'http://douyin-api:80'


def extract_douyin_url(text):
    patterns = [
        r'https?://v\.douyin\.com/[a-zA-Z0-9_-]+/?',
        r'https?://www\.douyin\.com/video/[a-zA-Z0-9_-]+/?',
        r'https?://douyin\.com/video/[a-zA-Z0-9_-]+/?',
        r'https?://www\.douyin\.com/discover\?[^\s]+',
        r'https?://[^\s\u4e00-\u9fff，。！？、]+',
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(0).rstrip('.,;，。')
    clean = re.sub(r'[^\w\-:/.?=&%#]', '', text.strip())
    if 'http' in clean and 'douyin' in clean:
        return clean
    if 'douyin.com' in text:
        m = re.search(r'https?://[^\s]+douyin[^\s]*', text)
        if m:
            return m.group(0).rstrip('.,;，。')
    return text.strip()


def _api_get(path, params=None):
    errors = []
    for base_url in _get_api_urls():
        url = f'{base_url}{path}'
        try:
            resp = requests.get(url, params=params, timeout=90)
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


def fetch_hybrid(url, minimal=False):
    body = _api_get('/api/hybrid/video_data', {
        'url': url,
        'minimal': 'true' if minimal else 'false',
    })
    code = body.get('code', body.get('status_code'))
    if code not in (200, '200', 0, None):
        raise RuntimeError(body.get('message') or body.get('msg') or f'API 错误: {code}')
    return body.get('data') or body


def _aweme_from_data(data):
    if not data:
        return None
    if 'aweme_detail' in data:
        return data['aweme_detail']
    if 'aweme_list' in data and data['aweme_list']:
        return data['aweme_list'][0]
    return data


def _parse_qualities(aweme):
    video = aweme.get('video') or {}
    qualities = []
    seen = set()

    bit_rates = video.get('bit_rate') or []
    for br in bit_rates:
        height = br.get('play_addr', {}).get('height') or br.get('gear_name', '')
        if isinstance(height, str):
            m = re.search(r'(\d+)', height)
            height = int(m.group(1)) if m else 0
        height = int(height or 0)
        if height and height not in seen:
            seen.add(height)
            qualities.append(height)

    play = video.get('play_addr') or {}
    h = play.get('height', 0)
    if h and int(h) not in seen:
        qualities.append(int(h))

    download = video.get('download_addr') or {}
    dh = download.get('height', 0)
    if dh and int(dh) not in seen:
        qualities.append(int(dh))

    qualities.sort(reverse=True)
    return qualities


def _pick_play_url(aweme, quality):
    video = aweme.get('video') or {}
    target_h = None if quality in ('best', '', None) else int(quality)

    best_url = None
    best_h = 0
    for br in video.get('bit_rate') or []:
        addr = br.get('play_addr') or {}
        urls = addr.get('url_list') or []
        h = int(addr.get('height') or 0)
        if not urls:
            continue
        if target_h and h == target_h:
            return urls[0]
        if h > best_h:
            best_h = h
            best_url = urls[0]

    if best_url:
        return best_url

    for key in ('download_addr', 'play_addr'):
        addr = video.get(key) or {}
        urls = addr.get('url_list') or []
        if urls:
            return urls[0]

    return None


def parse_video_info(share_text):
    url = extract_douyin_url(share_text)
    if 'douyin' not in url and 'http' not in url:
        raise ValueError('请输入有效的抖音链接')

    data = fetch_hybrid(url, minimal=False)
    aweme = _aweme_from_data(data)
    if not aweme:
        raise ValueError('无法解析视频数据')

    author = aweme.get('author', {}) or {}
    video = aweme.get('video', {}) or {}
    cover = ''
    cover_obj = video.get('cover') or video.get('origin_cover') or {}
    if cover_obj.get('url_list'):
        cover = cover_obj['url_list'][0]

    qualities = _parse_qualities(aweme)
    if not qualities:
        qualities = [1080, 720, 480]

    return {
        'url': url,
        'title': aweme.get('desc') or aweme.get('title') or '抖音视频',
        'author': author.get('nickname') or author.get('unique_id') or '',
        'thumbnail': cover,
        'duration': video.get('duration'),
        'qualities': qualities,
        'defaultQuality': str(qualities[0]) if qualities else 'best',
        'aweme_id': aweme.get('aweme_id', ''),
    }


def download_video_file(share_text, quality, dest_path):
    info = parse_video_info(share_text)
    data = fetch_hybrid(info['url'], minimal=False)
    aweme = _aweme_from_data(data)
    play_url = _pick_play_url(aweme, quality)
    if not play_url:
        raise ValueError('未找到可下载的视频地址')

    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        ),
        'Referer': 'https://www.douyin.com/',
    }
    with requests.get(play_url, headers=headers, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)

    return {
        'title': info['title'],
        'author': info['author'],
        'thumbnail': info['thumbnail'],
        'fileSize': os.path.getsize(dest_path),
        'quality': quality,
    }
