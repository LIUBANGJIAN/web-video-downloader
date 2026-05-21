import subprocess
import sys
import os

# 测试 douyin-downloader 安装情况
print("=== 测试 douyin-downloader 安装 ===")

# 检查是否安装
result = subprocess.run([sys.executable, '-m', 'pip', 'show', 'douyin-downloader'], capture_output=True, text=True)
print(f"pip show 返回码: {result.returncode}")
if result.returncode == 0:
    print("pip show 输出:")
    print(result.stdout)
else:
    print("pip show 错误:")
    print(result.stderr)

# 查找 run.py
print("\n=== 查找 run.py ===")
import site
for sp in site.getsitepackages():
    run_path = os.path.join(sp, 'douyin_downloader', 'run.py')
    print(f"检查: {run_path} - {'存在' if os.path.exists(run_path) else '不存在'}")

# 尝试运行
print("\n=== 尝试运行 ===")
try:
    result = subprocess.run([sys.executable, '-m', 'douyin_downloader', '--help'], capture_output=True, text=True)
    print(f"返回码: {result.returncode}")
    print("stdout:", result.stdout[:500])
    print("stderr:", result.stderr[:500])
except Exception as e:
    print(f"运行失败: {e}")