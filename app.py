from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
import uuid
import re

app = Flask(__name__)

APP_VERSION = "v1.3.0"

app.config['UPLOAD_FOLDER'] = os.environ.get('DOWNLOAD_DIR', '/app/downloads')
app.config['PORT'] = int(os.environ.get('PORT', 8787))

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/api/version')
def version():
    return jsonify({'version': APP_VERSION})

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
        
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': output_path,
            'quiet': False,
            'no_warnings': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'ignoreerrors': False,
            'retries': 3,
            'merge_output_format': 'mp4',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=True)
            
            if not info:
                return jsonify({'error': '无法获取视频信息'}), 500
            
            video_title = info.get('title', '视频')
            video_ext = info.get('ext', 'mp4')
            video_file = os.path.join(app.config['UPLOAD_FOLDER'], f'{video_id}.{video_ext}')
            video_thumbnail = info.get('thumbnail', '')
            
            if os.path.exists(video_file):
                return jsonify({
                    'success': True,
                    'videoUrl': f'/download/{video_id}.{video_ext}',
                    'title': video_title,
                    'author': info.get('uploader', ''),
                    'ext': video_ext,
                    'thumbnail': video_thumbnail,
                    'version': APP_VERSION
                })
            else:
                return jsonify({'error': '视频下载失败'}), 500
                
    except Exception as e:
        error_msg = str(e)
        return jsonify({'error': error_msg}), 500

@app.route('/download/<filename>')
def serve_download(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename), as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=app.config['PORT'], debug=True)