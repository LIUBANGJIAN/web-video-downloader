@echo off
chcp 65001
echo.
echo ================================
echo    抖音视频下载器 - 代码推送脚本
echo ================================
echo.

:: 切换到项目目录
cd /d "G:\trae\视频下载网站"
echo 当前目录: %cd%
echo.

:: 检查 git 是否可用
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到 Git，请确保 Git 已安装并添加到 PATH
    pause
    exit /b 1
)

echo 1. 检查 Git 状态:
git status
echo.

echo 2. 添加所有文件:
git add .
echo.

echo 3. 提交更改:
git commit -m "修复语法错误，更新版本号至v2.5.6"
echo.

echo 4. 推送到 GitHub:
git push origin master
echo.

if %errorlevel% equ 0 (
    echo ✅ 推送成功！
) else (
    echo ❌ 推送失败，请检查网络连接或权限
)

pause