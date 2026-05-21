@echo off
:: 使用 /d 参数同时切换驱动器和目录
cd /d "G:\trae\视频下载网站"

echo 当前目录: %cd%

:: 执行 Git 命令
echo.
echo 1. 检查状态:
"C:\Program Files\Git\bin\git.exe" status

echo.
echo 2. 添加文件:
"C:\Program Files\Git\bin\git.exe" add .

echo.
echo 3. 提交更改:
"C:\Program Files\Git\bin\git.exe" commit -m "更新版本号至v2.5.5，添加详细日志记录"

echo.
echo 4. 推送到 GitHub:
"C:\Program Files\Git\bin\git.exe" push origin master

echo.
echo 推送完成！
pause