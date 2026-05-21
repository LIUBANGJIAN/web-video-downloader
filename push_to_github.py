import subprocess
import os

def run_command(cmd, cwd=None):
    print(f"执行命令: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    print(f"输出: {result.stdout}")
    if result.stderr:
        print(f"错误: {result.stderr}")
    return result.returncode == 0

if __name__ == '__main__':
    repo_path = r'G:\trae\视频下载网站'
    os.chdir(repo_path)
    
    print("=== 开始推送代码到 GitHub ===")
    
    # git status
    print("\n1. 检查状态:")
    run_command("git status")
    
    # git add
    print("\n2. 添加文件:")
    if not run_command("git add ."):
        print("git add 失败")
        exit(1)
    
    # git commit
    print("\n3. 提交更改:")
    if not run_command('git commit -m "修复版本号显示问题，添加缓存控制"'):
        print("git commit 失败")
        exit(1)
    
    # git push
    print("\n4. 推送到远程仓库:")
    if run_command("git push origin master"):
        print("\n✅ 推送成功！")
    else:
        print("\n❌ 推送失败")
        exit(1)