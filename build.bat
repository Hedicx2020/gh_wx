@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   微信数据筛选工具 v2.0 - 打包脚本
echo ========================================
echo.

REM 检查 PyInstaller
echo [1/4] 检查依赖...
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo   正在安装 PyInstaller...
    python -m pip install pyinstaller
)

REM 安装必要的依赖
echo   检查运行依赖...
python -m pip install baostock pyecharts simplejson prettytable -q

REM 清理旧文件
echo.
echo [2/4] 清理旧文件...
if exist build rmdir /s /q build
if exist dist_release rmdir /s /q dist_release
echo   ✓ 清理完成

REM 开始打包
echo.
echo [3/4] 开始打包（需要几分钟）...
pyinstaller wechat_tool.spec --noconfirm

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
copy "dist\国海金工微信数据筛选工具v2.0.exe" "dist_release\" >nul
copy README.md "dist_release\" >nul
copy config.xlsx "dist_release\" >nul
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
echo 主程序: dist_release\国海金工微信数据筛选工具v2.0.exe
echo.
echo 新功能:
echo   - 个股K线复盘
echo   - 鼠标悬停显示聊天记录
echo.
echo 提示: 双击exe会自动打开浏览器
echo       可以将 dist_release 文件夹打包为 zip 分发
echo.
pause
