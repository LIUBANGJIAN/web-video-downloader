from flask import Flask, jsonify, request, send_file
import os
import uuid

import cookie_manager
import douyin_client

app = Flask(__name__)

APP_VERSION = 'v2.0.0'
app.config['UPLOAD_FOLDER'] = os.environ.get('DOWNLOAD_DIR', '/app/downloads')
app.config['PORT'] = int(os.environ.get('PORT', 8787))

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

cookie_manager.start_monitor()


@app.route('/')
def index():
    return send_file('index.html')


@app.route('/api/version')
def version():
    st = cookie_manager.get_status()
    return jsonify({
        'version': APP_VERSION,
        'backend': 'Evil0ctal/Douyin_TikTok_Download_API',
        'douyinApi': os.environ.get('DOUYIN_API_URL', 'http://127.0.0.1:80'),
        'cookieStatus': st['status'],
        'cookieMessage': st['message'],
    })


@app.route('/api/cookie/status')
def cookie_status():
    return jsonify(cookie_manager.get_status())


@app.route('/api/cookie/check', methods=['POST'])
def cookie_check():
    return jsonify(cookie_manager.check_validity(force=True))


@app.route('/api/cookie/qrcode', methods=['POST'])
def cookie_qrcode():
    return jsonify(cookie_manager.start_qr_login())


@app.route('/api/info', methods=['POST'])
def video_info():
    st = cookie_manager.get_status()
    if st['status'] != 'valid':
        return jsonify({
            'error': '请先扫码登录抖音',
            'needLogin': True,
            'cookieStatus': st['status'],
        }), 401

    data = request.get_json() or {}
    url = data.get('url', '')
    if not url:
        return jsonify({'error': '请输入抖音链接'}), 400

    try:
        info = douyin_client.parse_video_info(url)
        return jsonify({'success': True, **info})
    except Exception as e:
        msg = str(e)
        if 'cookie' in msg.lower():
            cookie_manager.check_validity(force=True)
            return jsonify({'error': 'Cookie 已失效，请重新扫码', 'needLogin': True}), 401
        if '解析服务不可用' in msg:
            return jsonify({'error': msg}), 502
        return jsonify({'error': msg}), 500


@app.route('/api/download', methods=['POST'])
def download_video():
    st = cookie_manager.get_status()
    if st['status'] != 'valid':
        return jsonify({'error': '请先扫码登录抖音', 'needLogin': True}), 401

    data = request.get_json() or {}
    url = data.get('url', '')
    quality = data.get('quality', 'best')
    if not url:
        return jsonify({'error': '请输入抖音链接'}), 400

    video_id = str(uuid.uuid4())
    dest = os.path.join(app.config['UPLOAD_FOLDER'], f'{video_id}.mp4')

    try:
        meta = douyin_client.download_video_file(url, quality, dest)
        return jsonify({
            'success': True,
            'videoUrl': f'/download/{video_id}.mp4',
            'title': meta['title'],
            'author': meta['author'],
            'thumbnail': meta.get('thumbnail', ''),
            'fileSize': meta['fileSize'],
            'quality': quality,
            'version': APP_VERSION,
        })
    except Exception as e:
        msg = str(e)
        if 'cookie' in msg.lower():
            cookie_manager.check_validity(force=True)
            return jsonify({'error': 'Cookie 已失效，请重新扫码', 'needLogin': True}), 401
        if '解析服务不可用' in msg:
            return jsonify({'error': msg}), 502
        return jsonify({'error': msg}), 500


@app.route('/download/<filename>')}]}
def serve_download(filename):
    safe = os.path.basename(filename)
    return send_file(
        os.path.join(app.config['UPLOAD_FOLDER'], safe),
        as_attachment=True,
    )


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=app.config['PORT'], debug=False)
