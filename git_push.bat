@echo off
cd /d "G:\trae\视频下载网站"
echo 检查 Git 状态...
git status
echo.
echo 执行 git add...
git add .
echo.
echo 执行 git commit...
git commit -m "修复版本号显示问题，添加缓存控制"
echo.
echo 执行 git push...
git push origin master
echo.
echo 操作完成！
pause