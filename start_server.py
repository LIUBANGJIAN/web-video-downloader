import subprocess
import sys

if __name__ == '__main__':
    subprocess.run([sys.executable, '-m', 'flask', 'run', '--host=0.0.0.0', '--port=8787'], 
                   env={'FLASK_APP': 'app.py'},
                   cwd='G:\\trae\\视频下载网站',
                   check=True)