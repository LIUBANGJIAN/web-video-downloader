from flask import Flask, jsonify, request, send_file, redirect
import os
import subprocess
import sys
import json

app = Flask(__name__)

APP_VERSION = 'v3.0.6'
app.config['UPLOAD_FOLDER'] = os.environ.get('DOWNLOAD_DIR', '/app/downloads')
app.config['PORT'] = int(os.environ.get('PORT', 8787))

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 检查 douyin-downloader 是否可用
DOUYIN_DOWNLOADER_AVAILABLE = False
DOUYIN_DOWNLOADER_CMD = "douyin-dl"

# 测试 douyin-downloader 是否可用
def check_douyin_downloader():
    global DOUYIN_DOWNLOADER_AVAILABLE, DOUYIN_DOWNLOADER_CMD
    
    # 首先尝试命令行工具 douyin-dl
    try:
        result = subprocess.run([DOUYIN_DOWNLOADER_CMD, '--version'],
                              capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout:
            DOUYIN_DOWNLOADER_AVAILABLE = True
            print(f"✓ douyin-downloader 已安装: {result.stdout.strip()}")
            return
        print(f"✗ 命令行测试失败, 返回码: {result.returncode}")
        print(f"  stderr: {result.stderr[:200]}")
    except Exception as e:
        print(f"✗ 命令行检查失败: {e}")
    
    # 如果命令行不可用，尝试查找 cli.main 模块
    try:
        result = subprocess.run([sys.executable, '-c', 'from cli.main import main; print("OK")'],
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            DOUYIN_DOWNLOADER_AVAILABLE = True
            DOUYIN_DOWNLOADER_CMD = [sys.executable, '-m', 'cli.main']
            print("✓ cli.main 模块可导入")
            return
    except Exception as e:
        print(f"✗ cli.main 导入失败: {e}")
    
    print("✗ douyin-downloader 不可用")

check_douyin_downloader()

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/api/version')
def get_version():
    return jsonify({
        'version': APP_VERSION,
        'backend': 'douyin-downloader',
        'playwright': False,
        'douyin_downloader': DOUYIN_DOWNLOADER_AVAILABLE
    })

@app.route('/api/parse', methods=['POST'])
def parse_url():
    if not DOUYIN_DOWNLOADER_AVAILABLE:
        return jsonify({'success': False, 'message': 'douyin-downloader 未安装'})
    
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'success': False, 'message': '请输入抖音链接'})
        
        # 使用 douyin-downloader 命令行工具解析链接
        # 创建临时配置文件
        config_content = f'''
link:
  - "{url}"
path: {app.config['UPLOAD_FOLDER']}
mode:
  - post
number:
  post: 1
database: false
browser_fallback:
  enabled: false
'''
        config_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_config.yml')
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        # 运行 douyin-downloader
        result = subprocess.run(
            [DOUYIN_DOWNLOADER_CMD, '-c', config_path, '-v'],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        # 清理临时配置
        os.remove(config_path)
        
        if result.returncode == 0:
            # 解析输出，提取视频信息
            output = result.stdout
            # 尝试从输出中提取信息
            video_info = {
                'success': True,
                'type': 'video',
                'title': '解析成功',
                'author': '',
                'thumbnail': '',
                'video_url': url,
                'video_id': ''
            }
            return jsonify(video_info)
        else:
            error_msg = result.stderr[:200] if result.stderr else result.stdout[:200]
            return jsonify({'success': False, 'message': f'解析失败: {error_msg}'})
    
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': '解析超时'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'解析失败: {str(e)}'})

@app.route('/api/download', methods=['POST'])
def download_video():
    if not DOUYIN_DOWNLOADER_AVAILABLE:
        return jsonify({'success': False, 'message': 'douyin-downloader 未安装'})
    
    try:
        data = request.get_json()
        url = data.get('url', '')
        
        if not url:
            return jsonify({'success': False, 'message': '请提供下载链接'})
        
        # 创建配置文件
        config_content = f'''
link:
  - "{url}"
path: {app.config['UPLOAD_FOLDER']}
mode:
  - post
number:
  post: 1
database: false
browser_fallback:
  enabled: false
'''
        config_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_config.yml')
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        # 运行 douyin-downloader
        result = subprocess.run(
            [DOUYIN_DOWNLOADER_CMD, '-c', config_path],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        # 清理临时配置
        os.remove(config_path)
        
        if result.returncode == 0:
            # 查找下载的文件
            downloaded_files = []
            for item in os.listdir(app.config['UPLOAD_FOLDER']):
                if item.endswith('.mp4') or item.endswith('.json'):
                    downloaded_files.append(item)
            
            if downloaded_files:
                # 返回第一个视频文件
                video_file = [f for f in downloaded_files if f.endswith('.mp4')][0]
                return jsonify({
                    'success': True,
                    'filename': video_file,
                    'download_url': f'/download/{video_file}'
                })
            else:
                return jsonify({'success': False, 'message': '下载成功但未找到文件'})
        else:
            error_msg = result.stderr[:200] if result.stderr else result.stdout[:200]
            return jsonify({'success': False, 'message': f'下载失败: {error_msg}'})
    
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': '下载超时'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'下载失败: {str(e)}'})

@app.route('/download/<filename>')
def serve_download(filename):
    try:
        return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename), as_attachment=True)
    except Exception as e:
        return jsonify({'success': False, 'message': '文件不存在'}), 404

@app.route('/api/direct-download', methods=['GET'])
def direct_download():
    if not DOUYIN_DOWNLOADER_AVAILABLE:
        return jsonify({'success': False, 'message': 'douyin-downloader 未安装'}), 500
    
    url = request.args.get('url', '')
    if not url:
        return jsonify({'success': False, 'message': '缺少url参数'}), 400
    
    try:
        config_content = f'''
link:
  - "{url}"
path: {app.config['UPLOAD_FOLDER']}
mode:
  - post
number:
  post: 1
database: false
browser_fallback:
  enabled: false
'''
        config_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_config.yml')
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        result = subprocess.run(
            [DOUYIN_DOWNLOADER_CMD, '-c', config_path],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        os.remove(config_path)
        
        if result.returncode == 0:
            downloaded_files = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) if f.endswith('.mp4')]
            if downloaded_files:
                return send_file(os.path.join(app.config['UPLOAD_FOLDER'], downloaded_files[0]), as_attachment=True)
            else:
                return jsonify({'success': False, 'message': '下载失败'}), 400
        else:
            return jsonify({'success': False, 'message': '下载失败'}), 400
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/quick-download', methods=['POST'])
def quick_download():
    if not DOUYIN_DOWNLOADER_AVAILABLE:
        return jsonify({'success': False, 'message': 'douyin-downloader 未安装'}), 500
    
    data = request.get_json()
    url = data.get('url', '')
    
    if not url:
        return jsonify({'success': False, 'message': '缺少url参数'}), 400
    
    # 直接返回原始URL，让前端处理
    return jsonify({
        'success': True,
        'video_url': url,
        'title': '',
        'author': ''
    })

if __name__ == '__main__':
    print(f"服务器启动，版本: {APP_VERSION}")
    print(f"douyin-downloader 可用: {DOUYIN_DOWNLOADER_AVAILABLE}")
    print(f"运行在: http://0.0.0.0:{app.config['PORT']}")
    app.run(host='0.0.0.0', port=app.config['PORT'], debug=True)