@echo off
cd /d "G:\trae\视频下载网站"
"C:\Program Files\Git\bin\git.exe" add .
"C:\Program Files\Git\bin\git.exe" commit -m "v3.0.6: Optimize download workflow, auto trigger download"
"C:\Program Files\Git\bin\git.exe" push origin master
pause