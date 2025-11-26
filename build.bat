@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   微信数据筛选工具 - 打包脚本
echo ========================================
echo.

REM 检查 PyInstaller
echo [1/4] 检查依赖...
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo   正在安装 PyInstaller...
    python -m pip install pyinstaller
)

REM 清理旧文件
echo.
echo [2/4] 清理旧文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist dist_release rmdir /s /q dist_release
if exist *.spec del /q *.spec
echo   ✓ 清理完成

REM 开始打包
echo.
echo [3/4] 开始打包（需要几分钟）...
pyinstaller --name=微信数据筛选工具 ^
    --onefile ^
    --console ^
    --paths=src ^
    --paths=utils ^
    --paths=scripts ^
    --add-data "templates;templates" ^
    --add-data "src;src" ^
    --add-data "utils;utils" ^
    --add-data "scripts;scripts" ^
    --add-data "README.md;." ^
    --hidden-import=flask ^
    --hidden-import=flask_cors ^
    --hidden-import=flask.app ^
    --hidden-import=flask.json ^
    --hidden-import=flask.sessions ^
    --hidden-import=pandas ^
    --hidden-import=openpyxl ^
    --hidden-import=cryptography ^
    --hidden-import=zstandard ^
    --hidden-import=webbrowser ^
    --hidden-import=threading ^
    --copy-metadata flask ^
    --copy-metadata flask-cors ^
    --copy-metadata werkzeug ^
    --copy-metadata jinja2 ^
    web_app.py

if errorlevel 1 (
    echo.
    echo ✗ 打包失败！请查看错误信息
    pause
    exit /b 1
)

REM 创建发布包
echo.
echo [4/4] 创建发布包...
mkdir dist_release 2>nul
copy "dist\微信数据筛选工具.exe" "dist_release\" >nul
copy README.md "dist_release\" >nul
mkdir "dist_release\output" 2>nul
mkdir "dist_release\output\databases" 2>nul
mkdir "dist_release\output\logs" 2>nul
echo   ✓ 发布包创建完成

REM 完成
echo.
echo ========================================
echo   ✓ 打包完成！
echo ========================================
echo.
echo 发布包: dist_release\
echo 主程序: dist_release\微信数据筛选工具.exe
echo.
echo 提示: 双击exe会自动打开浏览器
echo       可以将 dist_release 文件夹打包为 zip 分发
echo.
pause
