from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
import uuid
import re
import subprocess
import sys

app = Flask(__name__)

APP_VERSION = "v1.4.0"

app.config['UPLOAD_FOLDER'] = os.environ.get('DOWNLOAD_DIR', '/app/downloads')
app.config['PORT'] = int(os.environ.get('PORT', 8787))

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

NODE_AVAILABLE = False
NODE_PATH = ""

def check_nodejs():
    global NODE_AVAILABLE, NODE_PATH
    try:
        result = subprocess.run(['which', 'node'], capture_output=True, text=True)
        NODE_PATH = result.stdout.strip()
        if NODE_PATH:
            version_result = subprocess.run(['node', '-v'], capture_output=True, text=True)
            if version_result.returncode == 0:
                NODE_AVAILABLE = True
                app.logger.info(f"✅ Node.js 可用: {version_result.stdout.strip()}")
            else:
                app.logger.warning("❌ Node.js 不可用")
        else:
            app.logger.warning("❌ Node.js 未找到")
    except Exception as e:
        app.logger.warning(f"❌ 检查 Node.js 失败: {str(e)}")

check_nodejs()

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/api/version')
def version():
    return jsonify({'version': APP_VERSION, 'node_available': NODE_AVAILABLE})

def extract_url(text):
    patterns = [
        r'https?://v\.douyin\.com/[a-zA-Z0-9_-]+/?',
        r'https?://www\.douyin\.com/video/[a-zA-Z0-9_-]+/?',
        r'https?://douyin\.com/video/[a-zA-Z0-9_-]+/?',
        r'https?://www\.bilibili\.com/video/[a-zA-Z0-9]+/?',
        r'https?://bilibili\.com/video/[a-zA-Z0-9]+/?',
        r'https?://www\.youtube\.com/watch\?v=[a-zA-Z0-9_-]+',
        r'https?://youtu\.be/[a-zA-Z0-9_-]+',
        r'https?://[^\s]+',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            url = match.group(0).rstrip('.,')
            if url:
                return url
    
    clean_text = re.sub(r'[^a-zA-Z0-9_\-:/.]', '', text.strip())
    if 'http' in clean_text:
        return clean_text
    
    return text.strip()

def get_site_type(url):
    if 'douyin' in url.lower() or 'v.douyin' in url.lower():
        return 'douyin'
    elif 'bilibili' in url.lower() or 'bilibili.com' in url.lower():
        return 'bilibili'
    elif 'youtube' in url.lower() or 'youtu.be' in url.lower():
        return 'youtube'
    return 'other'

@app.route('/api/download', methods=['POST'])
def download_video():
    try:
        data = request.get_json()
        url = data.get('url', '')
        
        if not url:
            return jsonify({'error': '请输入视频链接'}), 400
        
        clean_url = extract_url(url)
        
        if not clean_url or 'http' not in clean_url:
            return jsonify({'error': '请输入有效的视频链接'}), 400
        
        video_id = str(uuid.uuid4())
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{video_id}.%(ext)s')
        
        site_type = get_site_type(clean_url)
        
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': output_path,
            'quiet': False,
            'no_warnings': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'ignoreerrors': False,
            'retries': 2,
            'merge_output_format': 'mp4',
            'timeout': 60,
        }
        
        if site_type == 'bilibili':
            ydl_opts.update({
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
            })
        elif site_type == 'douyin':
            ydl_opts.update({
                'extractor_args': {
                    'douyin': ['--no-check-certificate']
                },
            })
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=True)
            
            if not info:
                return jsonify({'error': '无法获取视频信息'}), 500
            
            video_title = info.get('title', '视频')
            video_ext = info.get('ext', 'mp4')
            video_file = os.path.join(app.config['UPLOAD_FOLDER'], f'{video_id}.{video_ext}')
            
            thumbnail = info.get('thumbnail', '')
            if thumbnail:
                if not thumbnail.startswith('http'):
                    thumbnail = ''
            
            video_url = f'/download/{video_id}.{video_ext}'
            
            if os.path.exists(video_file):
                file_size = os.path.getsize(video_file)
                return jsonify({
                    'success': True,
                    'videoUrl': video_url,
                    'title': video_title,
                    'author': info.get('uploader', ''),
                    'ext': video_ext,
                    'thumbnail': thumbnail,
                    'fileSize': file_size,
                    'version': APP_VERSION,
                    'nodeAvailable': NODE_AVAILABLE
                })
            else:
                return jsonify({'error': '视频下载失败'}), 500
                
    except Exception as e:
        error_msg = str(e)
        error_lower = error_msg.lower()
        
        if 'sign token' in error_lower or 'captcha' in error_lower or '风控' in error_msg:
            error_msg = '⚠️ 当前 IP 触发风控，请稍后再试或更换网络'
        elif 'cookies' in error_lower or 'cookie' in error_lower:
            if not NODE_AVAILABLE:
                error_msg = '⚠️ 服务器 Node.js 环境未配置，无法解析抖音加密参数'
            else:
                error_msg = '⚠️ 该视频需要登录才能下载，请尝试其他视频'
        elif 'format' in error_lower and 'available' in error_lower:
            error_msg = '⚠️ 当前格式不可用，正在尝试其他格式...'
            return download_fallback(clean_url, video_id)
        
        return jsonify({'error': error_msg}), 500

def download_fallback(url, video_id):
    try:
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{video_id}_fallback.%(ext)s')
        
        ydl_opts = {
            'format': 'best',
            'outtmpl': output_path,
            'quiet': False,
            'no_warnings': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'retries': 1,
            'timeout': 30,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            if not info:
                return jsonify({'error': '无法获取视频信息'}), 500
            
            video_title = info.get('title', '视频')
            video_ext = info.get('ext', 'mp4')
            video_file = os.path.join(app.config['UPLOAD_FOLDER'], f'{video_id}_fallback.{video_ext}')
            
            thumbnail = info.get('thumbnail', '')
            if thumbnail and not thumbnail.startswith('http'):
                thumbnail = ''
            
            if os.path.exists(video_file):
                return jsonify({
                    'success': True,
                    'videoUrl': f'/download/{video_id}_fallback.{video_ext}',
                    'title': video_title,
                    'author': info.get('uploader', ''),
                    'ext': video_ext,
                    'thumbnail': thumbnail,
                    'version': APP_VERSION,
                    'nodeAvailable': NODE_AVAILABLE
                })
            else:
                return jsonify({'error': '视频下载失败'}), 500
    except Exception as e:
        return jsonify({'error': f'下载失败: {str(e)}'}), 500

@app.route('/download/<filename>')
def serve_download(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename), as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=app.config['PORT'], debug=True)