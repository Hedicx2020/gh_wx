# -*- mode: python ; coding: utf-8 -*-
"""
微信数据库解密工具 v2.5.1 打包配置
优化打包体积,只包含必需的依赖
"""

from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

# 需要的内部模块
wechat_hidden = collect_submodules('wechat_decrypt_tool')

# fpdf2 所有子模块
fpdf_hidden = collect_submodules('fpdf')

# pyecharts 数据文件（地图与模板）- K线图必需
pyecharts_datas = collect_data_files(
    'pyecharts',
    includes=[
        'datasets/*',
        'render/templates/*',
    ]
)

# baostock数据文件（如果有）
try:
    baostock_datas = collect_data_files('baostock')
except:
    baostock_datas = []

# akshare数据文件（K线复盘必需）
try:
    akshare_datas = collect_data_files('akshare', includes=['file_fold/*'])
except:
    akshare_datas = []

# fpdf2数据文件（内置字体等）
try:
    fpdf2_datas = collect_data_files('fpdf')
except:
    fpdf2_datas = []

# 收集所有flask_cors相关文件
flask_cors_datas, flask_cors_binaries, flask_cors_hiddenimports = collect_all('flask_cors')
flask_datas, flask_binaries, flask_hiddenimports = collect_all('flask')

a = Analysis(
    ['web_app.py'],
    pathex=['.', 'src', 'utils', 'scripts'],
    binaries=flask_cors_binaries + flask_binaries,
    datas=[
        ('templates', 'templates'),
        ('src', 'src'),
        ('utils', 'utils'),
        ('scripts', 'scripts'),
        ('README.md', '.')
    ] + flask_cors_datas + flask_datas + pyecharts_datas + baostock_datas + akshare_datas + fpdf2_datas,
    hiddenimports=[
        # Flask Web框架
        'flask',
        'flask_cors',
        'flask_cors.decorator',
        'flask_cors.core',
        'flask_cors.extension',
        'flask.json',
        'jinja2',
        'werkzeug',
        'werkzeug.routing',
        'werkzeug.utils',
        'click',
        'itsdangerous',
        'markupsafe',

        # 数据处理
        'pandas',
        'pandas._libs',
        'pandas._libs.tslibs',
        'numpy',
        'openpyxl',
        'openpyxl.cell',
        'openpyxl.cell._writer',

        # 加密解密
        'cryptography',
        'cryptography.hazmat.primitives.ciphers',
        'cryptography.hazmat.primitives.ciphers.modes',
        'cryptography.hazmat.primitives.ciphers.algorithms',
        'cryptography.hazmat.primitives.kdf.pbkdf2',
        'cryptography.hazmat.backends',
        'cryptography.hazmat.backends.openssl',
        'zstandard',

        # 数据库
        'pymysql',
        'pymysql.cursors',
        'sqlite3',

        # 图片处理
        'PIL',
        'PIL.Image',
        'PIL.ImageFile',

        # 网络请求
        'requests',
        'urllib3',

        # 股票数据
        'baostock',
        'baostock.data',
        'baostock.common',

        # akshare股票数据(K线复盘)
        'akshare',
        'akshare.stock',
        'akshare.index',

        # 图表生成
        'pyecharts',
        'pyecharts.charts',
        'pyecharts.options',
        'pyecharts.render',
        'pyecharts.commons.utils',

        # PDF生成 - reportlab (用户手册)
        'reportlab',
        'reportlab.lib',
        'reportlab.lib.pagesizes',
        'reportlab.lib.styles',
        'reportlab.lib.units',
        'reportlab.lib.colors',
        'reportlab.lib.enums',
        'reportlab.platypus',
        'reportlab.pdfbase',
        'reportlab.pdfbase.pdfmetrics',
        'reportlab.pdfbase.ttfonts',

        # PDF生成 - fpdf2 依赖
        'defusedxml',
        'fontTools',
        'fontTools.ttLib',

        # JSON处理
        'json',
        'simplejson',
    ] + flask_cors_hiddenimports + flask_hiddenimports + wechat_hidden + fpdf_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 精简体积：排除未使用的大型依赖
        # 深度学习框架（未使用）
        'torch', 'torchvision', 'torchaudio', 'torchtext',
        'tensorflow', 'tensorflow_intel', 'keras', 'tensorboard',

        # 机器学习库（未使用）
        'sklearn', 'scipy', 'statsmodels', 'xgboost', 'lightgbm',

        # 可视化库（已用pyecharts）
        'matplotlib', 'seaborn', 'plotly', 'bokeh',

        # 大数据处理（未使用）
        'pyarrow', 'tables', 'dask', 'polars',

        # 开发工具（运行时不需要）
        'notebook', 'jupyter', 'jupyterlab', 'ipython', 'IPython',
        'jedi', 'parso', 'pylint', 'pytest', 'black', 'mypy',

        # 测试框架（运行时不需要）
        'nose', 'coverage', 'hypothesis',

        # 其他不需要的包
        'tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
        'curses', 'pydoc', 'doctest',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='国海金工微信数据筛选工具v2.5.1',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

