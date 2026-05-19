from flask import Flask, jsonify, request, send_file, Response
from yt_dlp import YoutubeDL
import re
import os
import uuid
import subprocess
from urllib.parse import urlparse, parse_qs
import requests
import time

app = Flask(__name__)

APP_VERSION = 'v2.4.0'
app.config['UPLOAD_FOLDER'] = os.environ.get('DOWNLOAD_DIR', '/app/downloads')
app.config['PORT'] = int(os.environ.get('PORT', 8787))

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

NODE_AVAILABLE = False
NODE_VERSION = ""
YTDLP_VERSION = ""

def check_nodejs():
    global NODE_AVAILABLE, NODE_VERSION
    try:
        result = subprocess.run(['node', '-v'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            NODE_AVAILABLE = True
            NODE_VERSION = result.stdout.strip()
            app.logger.info(f"✅ Node.js 可用: {NODE_VERSION}")
        else:
            app.logger.warning("❌ Node.js 不可用")
    except FileNotFoundError:
        app.logger.warning("❌ Node.js 未找到")
    except Exception as e:
        app.logger.warning(f"❌ 检查 Node.js 失败: {str(e)}")

def check_ytdlp():
    global YTDLP_VERSION
    try:
        import yt_dlp
        YTDLP_VERSION = yt_dlp.version.__version__
        app.logger.info(f"✅ yt-dlp 版本: {YTDLP_VERSION}")
    except Exception as e:
        YTDLP_VERSION = "未知"
        app.logger.warning(f"❌ 获取 yt-dlp 版本失败: {str(e)}")

check_nodejs()
check_ytdlp()

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'

def _sanitize_url(url):
    if not url:
        return ''
    url = url.strip()
    url = re.sub(r'[\x00-\x1f\x7f]', '', url)
    return url

def _extract_url_from_text(text):
    if not text:
        return None
    patterns = [
        r'(https?://v\.douyin\.com/[a-zA-Z0-9_-]+)',
        r'(https?://www\.douyin\.com/video/\d+)',
        r'(https?://www\.douyin\.com/\d+/)',
        r'(https?://b23\.tv/[a-zA-Z0-9]+)',
        r'(https?://www\.bilibili\.com/video/[a-zA-Z0-9_]+)',
        r'(https?://youtube\.com/shorts/[a-zA-Z0-9_-]+)',
        r'(https?://youtu\.be/[a-zA-Z0-9_-]+)',
        r'(https?://www\.youtube\.com/watch\?v=[a-zA-Z0-9_-]+)',
        r'(https?://v\.kuaishou\.com/[a-zA-Z0-9_-]+)',
        r'(https?://www\.xiaohongshu\.com/discovery/item/[a-zA-Z0-9]+)',
        r'(https?://xhslink\.com/[a-zA-Z0-9]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None

def _get_site_from_url(url):
    if not url:
        return None
    domain = urlparse(url).netloc.lower()
    if 'douyin' in domain:
        return 'douyin'
    elif 'bilibili' in domain or 'b23.tv' in domain:
        return 'bilibili'
    elif 'youtube' in domain or 'youtu.be' in domain:
        return 'youtube'
    elif 'kuaishou' in domain:
        return 'kuaishou'
    elif 'xiaohongshu' in domain or 'xhslink' in domain:
        return 'xiaohongshu'
    return None

def _get_douyin_video_id(url):
    """从抖音链接中提取视频ID"""
    patterns = [
        r'/video/(\d+)',
        r'/\d+/(")?(\d+)',
        r'video_id=(\d+)',
        r'modal_id=(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1) if match.lastindex == 1 else match.group(2) if match.lastindex == 2 else match.group(0)
    return None

def _parse_douyin_url(url):
    """解析抖音分享链接，返回视频信息"""
    try:
        # 处理短链接
        if 'v.douyin.com' in url:
            headers = {
                'User-Agent': USER_AGENT,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            response = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
            url = response.url
        
        video_id = _get_douyin_video_id(url)
        if not video_id:
            return None
        
        # 调用抖音API获取视频信息
        api_url = f'https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id={video_id}&aid=1128&version_name=23.5.0&device_platform=android&os_version=2333'
        
        headers = {
            'User-Agent': USER_AGENT,
            'Referer': 'https://www.douyin.com/',
            'Accept': 'application/json, text/plain, */*',
        }
        
        response = requests.get(api_url, headers=headers, timeout=10)
        data = response.json()
        
        if data.get('status_code') != 0:
            return None
        
        aweme = data.get('aweme_detail', {})
        if not aweme:
            return None
        
        # 提取视频信息
        video_info = aweme.get('video', {})
        play_addr = video_info.get('play_addr', {})
        
        # 获取无水印视频链接
        video_url = None
        if play_addr.get('url_list'):
            video_url = play_addr['url_list'][0]
        
        # 获取封面
        cover = video_info.get('cover', {}).get('url_list', [''])[0] if video_info.get('cover') else ''
        
        # 获取作者信息
        author = aweme.get('author', {})
        author_name = author.get('nickname', '')
        
        return {
            'title': aweme.get('desc', ''),
            'author': author_name,
            'thumbnail': cover,
            'video_url': video_url,
            'video_id': video_id,
        }
    except Exception as e:
        app.logger.error(f"解析抖音链接失败: {str(e)}")
        return None

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/api/version')
def version():
    return jsonify({
        'version': APP_VERSION,
        'backend': 'yt-dlp',
        'node_available': NODE_AVAILABLE,
        'node_version': NODE_VERSION,
        'ytdlp_version': YTDLP_VERSION,
    })

@app.route('/api/info', methods=['POST'])
def video_info():
    data = request.get_json() or {}
    raw = data.get('url', '')
    url = _extract_url_from_text(_sanitize_url(raw))
    if not url:
        return jsonify({'error': '请输入有效的视频链接或将包含链接的文本粘贴到输入框'}), 400

    try:
        site = _get_site_from_url(url)
        
        # 抖音链接使用直接解析
        if site == 'douyin':
            info = _parse_douyin_url(url)
            if info and info.get('video_url'):
                return jsonify({
                    'success': True,
                    'title': info.get('title', ''),
                    'author': info.get('author', ''),
                    'thumbnail': info.get('thumbnail', ''),
                    'formats': [{'format_id': 'default', 'quality': '默认', 'url': info['video_url']}],
                    'site': site,
                    'version': APP_VERSION,
                })
        
        # 其他平台使用yt-dlp
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            formats = []
            if info.get('formats'):
                for f in info['formats']:
                    if f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                        formats.append({
                            'format_id': f.get('format_id', ''),
                            'quality': f.get('format_note', f.get('height', 'unknown')),
                            'url': f.get('url', ''),
                        })
            
            if not formats and info.get('url'):
                formats.append({
                    'format_id': 'default',
                    'quality': '默认',
                    'url': info['url'],
                })
            
            return jsonify({
                'success': True,
                'title': info.get('title', ''),
                'author': info.get('uploader', info.get('creator', '')),
                'thumbnail': info.get('thumbnail', ''),
                'formats': formats,
                'site': site,
                'version': APP_VERSION,
            })
            
    except Exception as e:
        error_msg = str(e)
        app.logger.error(f"解析失败: {error_msg}")
        return jsonify({'error': f'解析失败: {error_msg}'}), 500

@app.route('/api/download', methods=['POST'])
def download_video():
    data = request.get_json() or {}
    raw = data.get('url', '')
    url = _extract_url_from_text(_sanitize_url(raw))
    quality = data.get('quality', 'best')
    if not url:
        return jsonify({'error': '请输入有效的视频链接或将包含链接的文本粘贴到输入框'}), 400

    video_id = str(uuid.uuid4())
    dest = os.path.join(app.config['UPLOAD_FOLDER'], f'{video_id}.mp4')

    try:
        site = _get_site_from_url(url)
        
        # 抖音链接直接下载
        if site == 'douyin':
            info = _parse_douyin_url(url)
            if info and info.get('video_url'):
                headers = {
                    'User-Agent': USER_AGENT,
                    'Referer': 'https://www.douyin.com/',
                }
                response = requests.get(info['video_url'], headers=headers, stream=True, timeout=30)
                with open(dest, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                file_size = os.path.getsize(dest)
                return jsonify({
                    'success': True,
                    'videoUrl': f'/download/{video_id}.mp4',
                    'title': info.get('title', ''),
                    'author': info.get('author', ''),
                    'thumbnail': info.get('thumbnail', ''),
                    'fileSize': file_size,
                    'quality': '默认',
                    'version': APP_VERSION,
                })
        
        # 其他平台使用yt-dlp下载
        ydl_opts = {
            'format': quality if quality != 'best' else 'best[height<=1080]/best',
            'outtmpl': dest,
            'quiet': True,
            'no_warnings': True,
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            file_size = os.path.getsize(dest) if os.path.isfile(dest) else 0
            return jsonify({
                'success': True,
                'videoUrl': f'/download/{video_id}.mp4',
                'title': info.get('title', ''),
                'author': info.get('creator') or info.get('uploader', ''),
                'thumbnail': info.get('thumbnail', ''),
                'fileSize': file_size,
                'quality': quality,
                'version': APP_VERSION,
            })
            
    except Exception as e:
        app.logger.error(f"下载失败: {str(e)}")
        return jsonify({'error': f'下载失败: {str(e)}'}), 500

@app.route('/download/<filename>')
def serve_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return jsonify({'error': '文件不存在'}), 404

if __name__ == '__main__':
    port = app.config['PORT']
    app.run(host='0.0.0.0', port=port)
