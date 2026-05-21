from flask import Flask, jsonify, request, send_file, redirect
import re
import os
import uuid
import requests

app = Flask(__name__)

APP_VERSION = 'v2.5.0'
app.config['UPLOAD_FOLDER'] = os.environ.get('DOWNLOAD_DIR', '/app/downloads')
app.config['PORT'] = int(os.environ.get('PORT', 8787))

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

MOBILE_UA = 'Mozilla/5.0 (Linux; Android 11; SAMSUNG SM-G973U) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/14.2 Chrome/87.0.4280.141 Mobile Safari/537.36'

# 尝试导入 Playwright 解析器
try:
    from playwright_parser import parse_with_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError as e:
    print(f"Playwright 导入失败: {e}")
    PLAYWRIGHT_AVAILABLE = False

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
        r'(https?://www\.douyin\.com/note/\d+)',
        r'(https?://www\.iesdouyin\.com/share/note/\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None

def _parse_douyin_url(url):
    """解析抖音分享链接，返回视频/图片信息"""
    try:
        # 从短链接提取token
        match = re.search(r'v\.douyin\.com/([a-zA-Z0-9_-]+)', url)
        if match:
            token = match.group(1)
            if not token.isdigit():
                resolved = _resolve_short_url(token)
                if resolved:
                    if resolved['type'] == 'note':
                        return _parse_douyin_note(resolved['id'])
                    else:
                        url = f'https://www.douyin.com/video/{resolved["id"]}'
        
        # 直接是 /note/ 类型URL
        match = re.search(r'douyin\.com/note/(\d+)', url)
        if match:
            return _parse_douyin_note(match.group(1))
        
        # 分享note类型
        match = re.search(r'iesdouyin\.com/share/note/(\d+)', url)
        if match:
            return _parse_douyin_note(match.group(1))
        
        # 视频类型 - 提取ID
        aweme_id = None
        match = re.search(r'douyin\.com/video/(\d+)', url)
        if match:
            aweme_id = match.group(1)
        else:
            match = re.search(r'share/video/(\d+)', url)
            if match:
                aweme_id = match.group(1)
        
        if not aweme_id:
            return None
        
        # 使用API获取视频详情
        headers = {
            'User-Agent': MOBILE_UA,
            'Accept': 'application/json',
            'Referer': 'https://www.douyin.com/',
        }
        
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
        
        # 如果上面的方法失败，尝试备用方法
        result = _parse_douyin_fallback(url, aweme_id)
        if result:
            return result
        
        # 如果还是失败，尝试使用 Playwright
        if PLAYWRIGHT_AVAILABLE:
            print(f"使用 Playwright 解析: {url}")
            result = parse_with_playwright(url)
            if result:
                return result
        
        return None
        
    except Exception as e:
        app.logger.error(f"解析抖音链接失败: {str(e)}")
        
        # 尝试使用 Playwright
        if PLAYWRIGHT_AVAILABLE:
            try:
                print(f"使用 Playwright 解析(异常后): {url}")
                result = parse_with_playwright(url)
                if result:
                    return result
            except Exception as pw_e:
                app.logger.error(f"Playwright 解析失败: {str(pw_e)}")
        
        return _parse_douyin_fallback(url, None)

def _resolve_short_url(token):
    """尝试解析短链接获取真实ID和类型"""
    try:
        headers = {
            'User-Agent': MOBILE_UA,
        }
        
        response = requests.get(f'https://v.douyin.com/{token}/', headers=headers, allow_redirects=True, timeout=15)
        final_url = response.url
        
        # 视频类型
        match = re.search(r'/video/(\d+)', final_url)
        if match:
            return {'type': 'video', 'id': match.group(1)}
        
        # 图文类型 - 支持 /note/ 和 /share/note/ 格式
        match = re.search(r'/note/(\d+)', final_url)
        if match:
            return {'type': 'note', 'id': match.group(1)}
        
        # 分享视频类型
        match = re.search(r'/share/video/(\d+)', final_url)
        if match:
            return {'type': 'video', 'id': match.group(1)}
        
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
            
            desc_match = re.search(r'"desc":\s*"([^"]+)"', body)
            title = desc_match.group(1) if desc_match else ''
            
            nickname_match = re.search(r'"nickname":\s*"([^"]+)"', body)
            author = nickname_match.group(1) if nickname_match else ''
            
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

def _parse_douyin_note(note_id):
    """专门解析抖音图文链接"""
    try:
        headers = {
            'User-Agent': MOBILE_UA,
            'Referer': 'https://www.douyin.com/',
        }
        
        # 方法1：尝试使用移动端API
        api_url = f'https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={note_id}'
        api_response = requests.get(api_url, headers=headers, timeout=15)
        api_data = api_response.json()
        
        if api_data.get('status_code') == 0 and api_data.get('item_list'):
            item = api_data['item_list'][0]
            images = item.get('images', [])
            if images:
                img_list = []
                for img in images:
                    url_list = img.get('url_list', [])
                    if url_list:
                        img_list.append(url_list[0])
                
                if img_list:
                    return {
                        'type': 'image',
                        'title': item.get('desc', ''),
                        'author': item.get('author', {}).get('nickname', ''),
                        'thumbnail': img_list[0] if img_list else '',
                        'image_url_list': img_list,
                    }
        
        # 方法2：尝试使用移动端分享页面
        share_url = f'https://www.iesdouyin.com/share/note/{note_id}'
        share_response = requests.get(share_url, headers=headers, timeout=15)
        
        img_list = _parse_douyin_images(share_response.text)
        if img_list:
            desc_match = re.search(r'"desc":\s*"([^"]+)"', share_response.text)
            title = desc_match.group(1) if desc_match else ''
            
            nickname_match = re.search(r'"nickname":\s*"([^"]+)"', share_response.text)
            author = nickname_match.group(1) if nickname_match else ''
            
            return {
                'type': 'image',
                'title': title,
                'author': author,
                'thumbnail': img_list[0] if img_list else '',
                'image_url_list': img_list,
            }
        
        # 方法3：尝试PC页面
        pc_url = f'https://www.douyin.com/note/{note_id}'
        pc_response = requests.get(pc_url, headers=headers, allow_redirects=True, timeout=15)
        
        img_list = _parse_douyin_images(pc_response.text)
        if img_list:
            desc_match = re.search(r'"desc":\s*"([^"]+)"', pc_response.text)
            title = desc_match.group(1) if desc_match else ''
            
            nickname_match = re.search(r'"nickname":\s*"([^"]+)"', pc_response.text)
            author = nickname_match.group(1) if nickname_match else ''
            
            return {
                'type': 'image',
                'title': title,
                'author': author,
                'thumbnail': img_list[0] if img_list else '',
                'image_url_list': img_list,
            }
        
        # 方法4：使用Playwright解析（图文链接优先使用）
        if PLAYWRIGHT_AVAILABLE:
            # 使用移动端分享页面格式，更容易被解析
            mobile_url = f'https://www.iesdouyin.com/share/note/{note_id}'
            print(f"使用 Playwright 解析图文: {mobile_url}")
            result = parse_with_playwright(mobile_url)
            if result:
                return result
        
        return None
    except Exception as e:
        app.logger.error(f"解析图文链接失败: {str(e)}")
        
        # 尝试使用Playwright
        if PLAYWRIGHT_AVAILABLE:
            try:
                mobile_url = f'https://www.iesdouyin.com/share/note/{note_id}'
                print(f"使用 Playwright 解析图文(异常后): {mobile_url}")
                result = parse_with_playwright(mobile_url)
                if result:
                    return result
            except Exception as pw_e:
                app.logger.error(f"Playwright 解析图文失败: {str(pw_e)}")
        
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
    response = send_file('index.html')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/api/version')
def version():
    return jsonify({
        'version': APP_VERSION,
        'backend': 'douyinVd + Playwright',
        'playwright': PLAYWRIGHT_AVAILABLE,
    })

@app.route('/api/proxy')
def proxy_image():
    """代理图片请求，解决跨域问题"""
    url = request.args.get('url')
    if not url:
        return jsonify({'error': '缺少URL参数'}), 400
    
    try:
        headers = {
            'User-Agent': MOBILE_UA,
            'Referer': 'https://www.douyin.com/',
        }
        
        response = requests.get(url, headers=headers, stream=True, timeout=15)
        
        content_type = response.headers.get('Content-Type', 'image/jpeg')
        
        return response.content, 200, {'Content-Type': content_type}
    
    except Exception as e:
        app.logger.error(f"代理图片失败: {str(e)}")
        return jsonify({'error': '代理失败'}), 500

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

@app.route('/api/direct-download')
def direct_download():
    """直接下载API - 用于iOS快捷指令等外部调用"""
    url = request.args.get('url')
    if not url:
        return jsonify({'error': '缺少URL参数', 'code': 400}), 400
    
    info = _parse_douyin_url(url)
    if not info:
        return jsonify({'error': '解析失败', 'code': 500}), 500
    
    try:
        if info.get('type') == 'video':
            video_url = info['video_url']
            return redirect(video_url)
        else:
            img_list = info.get('image_url_list', [])
            if img_list:
                return redirect(img_list[0])
            return jsonify({'error': '未找到图片', 'code': 500}), 500
            
    except Exception as e:
        app.logger.error(f"直接下载失败: {str(e)}")
        return jsonify({'error': '下载失败', 'code': 500}), 500

@app.route('/api/quick-download')
def quick_download():
    """快速下载API - 返回JSON格式的下载链接，便于快捷指令处理多图"""
    url = request.args.get('url')
    if not url:
        return jsonify({'error': '缺少URL参数', 'code': 400}), 400
    
    info = _parse_douyin_url(url)
    if not info:
        return jsonify({'error': '解析失败', 'code': 500}), 500
    
    if info.get('type') == 'video':
        return jsonify({
            'success': True,
            'type': 'video',
            'title': info.get('title', ''),
            'author': info.get('author', ''),
            'download_url': info['video_url'],
            'thumbnail': info.get('thumbnail', ''),
        })
    else:
        return jsonify({
            'success': True,
            'type': 'image',
            'title': info.get('title', ''),
            'author': info.get('author', ''),
            'download_urls': info.get('image_url_list', []),
            'thumbnail': info.get('thumbnail', ''),
        })

if __name__ == '__main__':
    port = app.config['PORT']
    app.run(host='0.0.0.0', port=port)