import subprocess
import os

os.chdir(r"G:\trae\视频下载网站")

git_path = r"C:\Program Files\Git\bin\git.exe"

commands = [
    [git_path, "add", "."],
    [git_path, "commit", "-m", "v3.0.7: Fix bug - return latest downloaded video file instead of first one"],
    [git_path, "push", "origin", "master"]
]

for cmd in commands:
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(f"Exit code: {result.returncode}")
    if result.stdout:
        print(f"Output: {result.stdout}")
    if result.stderr:
        print(f"Error: {result.stderr}")
    if result.returncode != 0:
        break

print("Done!")