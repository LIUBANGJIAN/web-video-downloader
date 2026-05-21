import subprocess

# 使用用户建议的方法
commands = [
    'g:',
    'cd "G:\\trae\\视频下载网站"',
    'git add .',
    'git commit -m "修复语法错误，更新版本号至v2.5.6"',
    'git push origin master'
]

# 执行命令并保存输出
results = []
for cmd in commands:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    results.append(f"命令: {cmd}")
    results.append(f"输出: {result.stdout}")
    if result.stderr:
        results.append(f"错误: {result.stderr}")
    results.append(f"返回码: {result.returncode}")
    results.append("-" * 40)

# 写入文件
with open('git_push_result.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(results))

print("结果已保存到 git_push_result.txt")