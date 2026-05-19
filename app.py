from flask import Flask, jsonify, request, send_file
import re
import os
import uuid
import requests

app = Flask(__name__)

APP_VERSION = 'v2.4.4'
app.config['UPLOAD_FOLDER'] = os.environ.get('DOWNLOAD_DIR', '/app/downloads')
app.config['PORT'] = int(os.environ.get('PORT', 8787))

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

MOBILE_UA = 'Mozilla/5.0 (Linux; Android 11; SAMSUNG SM-G973U) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/14.2 Chrome/87.0.4280.141 Mobile Safari/537.36'

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
        r'(https?://www\.douyin\.com/user/[^/\s]+/video/\d+)',
        r'(https?://www\.iesdouyin\.com/share/video/\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None

def _parse_douyin_url(url):
    """解析抖音分享链接，返回视频/图片信息（参考 douyinVd 库的实现）"""
    try:
        # 提取可能的ID
        aweme_id = None
        
        # 从短链接提取token
        match = re.search(r'v\.douyin\.com/([a-zA-Z0-9_-]+)', url)
        if match:
            token = match.group(1)
            # 如果token看起来像数字ID，直接使用
            if token.isdigit():
                aweme_id = token
            else:
                # 尝试解析短链接获取真实ID
                aweme_id = _resolve_short_url(token)
        
        # 如果没有找到，尝试从视频URL提取
        if not aweme_id:
            match = re.search(r'douyin\.com/video/(\d+)', url)
            if match:
                aweme_id = match.group(1)
        
        # 如果还是没有，尝试从其他URL模式提取
        if not aweme_id:
            match = re.search(r'share/video/(\d+)', url)
            if match:
                aweme_id = match.group(1)
        
        if not aweme_id:
            return None
        
        # 使用douyinVd库的方法 - 直接调用API
        headers = {
            'User-Agent': MOBILE_UA,
            'Accept': 'application/json',
            'Referer': 'https://www.douyin.com/',
        }
        
        # 尝试获取视频详情
        api_url = f'https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={aweme_id}'
        
        response = requests.get(api_url, headers=headers, timeout=15)
        data = response.json()
        
        if data.get('status_code') == 0 and data.get('item_list'):
            item = data['item_list'][0]
            
            # 视频类型
            if item.get('video'):
                video = item['video']
                play_addr = video.get('play_addr', {})
                url_list = play_addr.get('url_list', [])
                
                if url_list:
                    video_url = url_list[0]
                    if 'ratio=' not in video_url:
                        video_url = f'{video_url}&ratio=1080p'
                    
                    title = item.get('desc', '')
                    author = item.get('author', {}).get('nickname', '')
                    cover_list = video.get('cover', {}).get('url_list', [])
                    thumbnail = cover_list[0] if cover_list else ''
                    
                    return {
                        'type': 'video',
                        'title': title,
                        'author': author,
                        'thumbnail': thumbnail,
                        'video_url': video_url,
                        'video_id': aweme_id,
                    }
            
            # 图片类型
            if item.get('images'):
                images = item['images']
                img_list = []
                for img in images:
                    url_list = img.get('url_list', [])
                    if url_list:
                        img_list.append(url_list[0])
                
                if img_list:
                    title = item.get('desc', '')
                    author = item.get('author', {}).get('nickname', '')
                    
                    return {
                        'type': 'image',
                        'title': title,
                        'author': author,
                        'thumbnail': img_list[0] if img_list else '',
                        'image_url_list': img_list,
                    }
        
        # 如果上面的方法失败，尝试另一种API
        return _parse_douyin_fallback(url, aweme_id)
        
    except Exception as e:
        app.logger.error(f"解析抖音链接失败: {str(e)}")
        return _parse_douyin_fallback(url, None)

def _resolve_short_url(token):
    """尝试解析短链接获取真实视频ID"""
    try:
        headers = {
            'User-Agent': MOBILE_UA,
        }
        
        # 使用移动UA访问短链接，获取重定向后的URL
        response = requests.get(f'https://v.douyin.com/{token}/', headers=headers, allow_redirects=True, timeout=15)
        final_url = response.url
        
        # 从最终URL提取视频ID
        match = re.search(r'/video/(\d+)', final_url)
        if match:
            return match.group(1)
        
        return None
    except Exception as e:
        app.logger.error(f"解析短链接失败: {str(e)}")
        return None

def _parse_douyin_fallback(url, aweme_id=None):
    """备用解析方法 - 从页面HTML提取信息"""
    try:
        headers = {
            'User-Agent': MOBILE_UA,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://www.douyin.com/',
        }
        
        # 获取页面内容
        response = requests.get(url, headers=headers, allow_redirects=True, timeout=15)
        body = response.text
        
        # 尝试多种模式提取视频ID
        patterns = [
            r'"video":{"play_addr":{"uri":"([a-z0-9]+)"',
            r'"uri":"([a-z0-9]+)".*?"play_addr"',
            r'video_id.*?"([a-z0-9]+)"',
            r'aweme_id.*?"(\d+)"',
        ]
        
        video_id = None
        for pattern in patterns:
            match = re.search(pattern, body)
            if match:
                video_id = match.group(1)
                break
        
        if video_id:
            video_url = f'https://www.iesdouyin.com/aweme/v1/play/?video_id={video_id}&ratio=1080p&line=0'
            
            # 提取标题
            desc_match = re.search(r'"desc":\s*"([^"]+)"', body)
            title = desc_match.group(1) if desc_match else ''
            
            # 提取作者昵称
            nickname_match = re.search(r'"nickname":\s*"([^"]+)"', body)
            author = nickname_match.group(1) if nickname_match else ''
            
            # 提取封面
            cover_match = re.search(r'"cover":\s*{"uri":"[^"]+","url_list":\["([^"]+)"', body)
            thumbnail = cover_match.group(1) if cover_match else ''
            
            return {
                'type': 'video',
                'title': title,
                'author': author,
                'thumbnail': thumbnail,
                'video_url': video_url,
                'video_id': video_id,
            }
        else:
            # 尝试图片类型
            img_list = _parse_douyin_images(body)
            if img_list:
                desc_match = re.search(r'"desc":\s*"([^"]+)"', body)
                title = desc_match.group(1) if desc_match else ''
                
                nickname_match = re.search(r'"nickname":\s*"([^"]+)"', body)
                author = nickname_match.group(1) if nickname_match else ''
                
                return {
                    'type': 'image',
                    'title': title,
                    'author': author,
                    'thumbnail': img_list[0] if img_list else '',
                    'image_url_list': img_list,
                }
        
        return None
    except Exception as e:
        app.logger.error(f"备用解析失败: {str(e)}")
        return None

def _parse_douyin_images(body):
    """解析抖音图文链接，提取图片列表"""
    try:
        content = body.replace(r'\\u002F', '/').replace('/', '/')
        reg = r'{"uri":"[^\s"]+","url_list":\["(https://p\d{1,2}-sign.douyinpic.com/[^"]+?)"'
        matches = re.findall(reg, content)
        
        if not matches:
            reg2 = r'"url_list":\["(https://p\d{1,2}-sign.douyinpic.com/[^"]+?)"'
            matches = re.findall(reg2, content)
        
        filtered = [url for url in matches if '/obj/' not in url]
        unique = list(dict.fromkeys(filtered))
        
        return unique
    except Exception as e:
        app.logger.error(f"解析图片列表失败: {str(e)}")
        return []

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/api/version')
def version():
    return jsonify({
        'version': APP_VERSION,
        'backend': 'douyinVd',
        'playwright': False,
    })

@app.route('/api/info', methods=['POST'])
def video_info():
    data = request.get_json() or {}
    raw = data.get('url', '')
    url = _extract_url_from_text(_sanitize_url(raw))
    if not url:
        return jsonify({'error': '请输入有效的抖音视频或图文链接'}), 400

    info = _parse_douyin_url(url)
    if not info:
        return jsonify({'error': '解析失败，请检查链接是否有效或网络环境'}), 500

    if info.get('type') == 'video':
        return jsonify({
            'success': True,
            'title': info.get('title', ''),
            'author': info.get('author', ''),
            'thumbnail': info.get('thumbnail', ''),
            'formats': [{'format_id': 'default', 'quality': '默认', 'url': info['video_url']}],
            'site': 'douyin',
            'version': APP_VERSION,
        })
    else:
        return jsonify({
            'success': True,
            'title': info.get('title', ''),
            'author': info.get('author', ''),
            'thumbnail': info.get('thumbnail', ''),
            'image_url_list': info.get('image_url_list', []),
            'site': 'douyin',
            'type': 'image',
            'version': APP_VERSION,
        })

@app.route('/api/download', methods=['POST'])
def download_video():
    data = request.get_json() or {}
    raw = data.get('url', '')
    url = _extract_url_from_text(_sanitize_url(raw))
    if not url:
        return jsonify({'error': '请输入有效的抖音视频或图文链接'}), 400

    info = _parse_douyin_url(url)
    if not info:
        return jsonify({'error': '解析失败，请检查链接是否有效或网络环境'}), 500

    try:
        if info.get('type') == 'video':
            video_url = info['video_url']
            video_id = str(uuid.uuid4())
            dest = os.path.join(app.config['UPLOAD_FOLDER'], f'{video_id}.mp4')
            
            headers = {
                'User-Agent': MOBILE_UA,
                'Referer': 'https://www.douyin.com/',
            }
            
            response = requests.get(video_url, headers=headers, stream=True, timeout=60)
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
                'version': APP_VERSION,
            })
        else:
            img_list = info.get('image_url_list', [])
            if img_list:
                img_url = img_list[0]
                ext = img_url.split('.')[-1] if '.' in img_url else 'jpg'
                img_id = str(uuid.uuid4())
                dest = os.path.join(app.config['UPLOAD_FOLDER'], f'{img_id}.{ext}')
                
                headers = {
                    'User-Agent': MOBILE_UA,
                    'Referer': 'https://www.douyin.com/',
                }
                
                response = requests.get(img_url, headers=headers, stream=True, timeout=30)
                with open(dest, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                file_size = os.path.getsize(dest)
                return jsonify({
                    'success': True,
                    'videoUrl': f'/download/{img_id}.{ext}',
                    'title': info.get('title', ''),
                    'author': info.get('author', ''),
                    'thumbnail': info.get('thumbnail', ''),
                    'fileSize': file_size,
                    'imageCount': len(img_list),
                    'imageUrls': img_list,
                    'version': APP_VERSION,
                })
            
            return jsonify({'error': '未找到图片'}), 500
            
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
