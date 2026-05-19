from flask import Flask, jsonify, request, send_file
from yt_dlp import YoutubeDL
import re
import os
import uuid

app = Flask(__name__)

APP_VERSION = 'v2.0.2'
app.config['UPLOAD_FOLDER'] = os.environ.get('DOWNLOAD_DIR', '/app/downloads')
app.config['PORT'] = int(os.environ.get('PORT', 8787))

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def _sanitize_url(text):
    if not text or not isinstance(text, str):
        return ''
    return text.strip()


def _extract_url_from_text(text):
    """从用户粘贴的文本中提取第一个 http(s) URL。"""
    if not text or not isinstance(text, str):
        return ''
    # 尝试直接返回已清理的文本（如果看起来像 URL）
    t = text.strip()
    if t.startswith('http://') or t.startswith('https://'):
        return t
    # 正则提取第一个 http(s) URL
    m = re.search(r"https?://[\w\-\./?%&=+#~:;,'()]+", text)
    if m:
        return m.group(0)
    return ''


def _quality_format(quality):
    q = str(quality or '').strip()
    if q.lower() in ('best', 'worst', 'source'):
        return q.lower()
    if q.isdigit():
        return f'bestvideo[height<={q}]+bestaudio/best'
    return q or 'best'


def _extract_info(video_url):
    if not video_url:
        raise ValueError('请输入抖音链接或包含链接的文本')

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'noplaylist': True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)

    if info.get('_type') == 'playlist':
        entries = info.get('entries') or []
        if not entries:
            raise ValueError('无法解析视频信息')
        info = entries[0]

    if not info:
        raise ValueError('无法解析视频信息')

    title = info.get('title') or '抖音视频'
    author = info.get('creator') or info.get('uploader') or info.get('uploader_id') or ''
    thumbnail = info.get('thumbnail') or ''
    duration = info.get('duration')

    formats = info.get('formats') or []
    heights = set()
    for fmt in formats:
        if fmt.get('vcodec') == 'none' or fmt.get('height') is None:
            continue
        heights.add(int(fmt['height']))

    qualities = [str(h) for h in sorted(heights, reverse=True)]
    if not qualities:
        qualities = ['best']

    return {
        'url': video_url,
        'title': title,
        'author': author,
        'thumbnail': thumbnail,
        'duration': duration,
        'qualities': qualities,
        'defaultQuality': qualities[0],
    }


def _download_video(url, quality, dest_path):
    format_str = _quality_format(quality)
    ydl_opts = {
        'format': format_str,
        'outtmpl': dest_path,
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
    return info


@app.route('/')
def index():
    return send_file('index.html')


@app.route('/api/version')
def version():
    return jsonify({
        'version': APP_VERSION,
        'backend': 'yt-dlp',
    })


@app.route('/api/info', methods=['POST'])
def video_info():
    data = request.get_json() or {}
    raw = data.get('url', '')
    url = _extract_url_from_text(_sanitize_url(raw))
    if not url:
        return jsonify({'error': '请输入有效的抖音分享链接或将包含链接的文本粘贴到输入框'}), 400
    try:
        info = _extract_info(url)
        return jsonify({'success': True, **info})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download', methods=['POST'])
def download_video():
    data = request.get_json() or {}
    raw = data.get('url', '')
    url = _extract_url_from_text(_sanitize_url(raw))
    quality = data.get('quality', 'best')
    if not url:
        return jsonify({'error': '请输入有效的抖音分享链接或将包含链接的文本粘贴到输入框'}), 400

    video_id = str(uuid.uuid4())
    dest = os.path.join(app.config['UPLOAD_FOLDER'], f'{video_id}.mp4')

    try:
        info = _download_video(url, quality, dest)
        file_size = os.path.getsize(dest) if os.path.isfile(dest) else 0
        return jsonify({
            'success': True,
            'videoUrl': f'/download/{video_id}.mp4',
            'title': info.get('title') or '',
            'author': info.get('creator') or info.get('uploader') or '',
            'thumbnail': info.get('thumbnail') or '',
            'fileSize': file_size,
            'quality': quality,
            'version': APP_VERSION,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/download/<filename>')
def serve_download(filename):
    safe = os.path.basename(filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], safe)
    if not os.path.isfile(path):
        return jsonify({'error': '文件不存在'}), 404
    return send_file(path, as_attachment=True)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=app.config['PORT'], debug=False)
