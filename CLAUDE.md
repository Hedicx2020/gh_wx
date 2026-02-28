# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a WeChat database decryption tool (`gh_wx_tool`) that decrypts SQLCipher 4.0 encrypted WeChat databases. It provides both a modern web interface and command-line tools, with a key feature being **incremental decryption** that intelligently processes only newly added message databases.

## Key Architecture Components

### 1. Dual-Mode Decryption System

The project implements two decryption modes with distinct logic:

**Full Decrypt Mode** (`decrypt_wechat_databases()` in `src/wechat_decrypt_tool/wechat_decrypt.py`):
- Decrypts all database files (~28 files including contact, message, session, etc.)
- Processes entire `db_storage` directory recursively
- Output organized by account in `output/databases/`

**Incremental Decrypt Mode** (`incremental_decrypt()` in `app.py`):
- Uses `find_max_message_db()` to locate highest-numbered `message_N.db` files
- Compares source directory max vs output directory max using regex pattern `message_(\d+)\.db`
- **Re-decrypts the current maximum** `message_N.db` (it may still be growing)
- **Only decrypts newly added** databases from `output_max+1` to `source_max`
- Skips all non-message databases (contact, session, etc.) - they are only decrypted in full mode
- Critical optimization: reduces decrypt time by ~79%

### 2. SQLCipher 4.0 Decryption Algorithm

Core crypto located in `WeChatDatabaseDecryptor` class:

1. **Salt extraction**: First 16 bytes of encrypted file
2. **Key derivation**: PBKDF2-HMAC-SHA512 with 256,000 iterations
3. **MAC key**: Derived from salt XOR 0x3a with 2 iterations
4. **Page-by-page decryption**: 4096-byte pages using AES-256-CBC
5. **HMAC verification**: SHA512 HMAC for each page (page_data + page_number_little_endian)

Critical implementation details:
- First page offset: 16 bytes (skip salt)
- Reserve size: 80 bytes aligned to 16 (IV=16 + HMAC=64)
- HMAC data: encrypted_data + IV, then update with 4-byte little-endian page number
- Output format: SQLite header + decrypted pages + reserve areas

### 3. Web Application Stack

**Frontend** (`frontend/`):
- Vanilla JavaScript (no frameworks) - see `script.js`
- CSS variable-based theming in `style.css` (Indigo theme #4F46E5, gradient background)
- Mode selection triggers `selectMode('full'|'incremental')`
- API calls to Flask backend via `fetch('/api/decrypt', {...})`

**Backend** (`app.py`):
- Flask with CORS enabled
- Static file serving from `FRONTEND_DIR` with extension whitelist
- Three main routes:
  - `POST /api/decrypt` - handles both modes based on `mode` parameter
  - `POST /api/open-folder` - platform-specific folder opening
  - `GET /api/status` - health check

### 4. Path and Account Management

Account name extraction logic (in `decrypt_wechat_databases()`):
- Searches path parts for patterns starting with `wxid_`
- Strips random suffix from `wxid_xxx_randomhash` format
- Falls back to directory name if no pattern match
- Critical: One key corresponds to one account only

## Common Development Tasks

### Run Web Server

```bash
# Development server (auto-reload)
python app.py

# Or use Windows batch script
start_server.bat
```

Server starts on `http://127.0.0.1:5000`

### Command-Line Testing

```bash
# Full decryption test
python test_decrypt.py

# Incremental decryption test (interactive)
python test_incremental.py

# View decrypted database samples
python view_sample.py
```

### Install Dependencies

```bash
pip install flask flask-cors cryptography
```

Required packages:
- `cryptography` - For AES-256-CBC, PBKDF2, HMAC operations
- `flask` - Web framework
- `flask-cors` - Cross-origin support

## Important Implementation Notes

### Incremental Decryption Logic

**Strategy** (as of latest update):
1. **Re-decrypt current max**: Always re-decrypt `message_{output_max}.db` (it may have grown)
2. **Decrypt new databases**: Decrypt `message_{output_max+1}` through `message_{source_max}`
3. **Skip other types**: Do NOT re-decrypt contact.db, session.db, etc. (only done in full mode)

**Implementation details**:
1. If `output_max_num is None`: Error - user should use full decrypt mode first
2. If `source_max < output_max`: Error - source directory anomaly
3. If `source_max == output_max`: Only re-decrypt the max database (1 file)
4. If `source_max > output_max`: Re-decrypt max + all new (1 + gap files)

**Pattern matching**:
- Uses `re.compile(r'message_(\d+)\.db$')`
- Search in `db_storage/message/` subdirectory specifically
- Return format: `(max_number, full_path)` or `(None, None)`

### Frontend-Backend Contract

API request structure:
```json
{
  "mode": "full" | "incremental",
  "key": "64-char hex string",
  "db_path": "path/to/db_storage",
  "account_name": "optional"
}
```

API response structure:
```json
{
  "status": "success" | "error",
  "message": "description",
  "total_databases": int,
  "successful_count": int,
  "failed_count": int,
  "output_directory": "path",
  "processed_files": ["list"],
  "failed_files": ["list"]
}
```

### File Organization

Output structure:
```
output/
├── databases/
│   └── {account_name}/
│       ├── contact.db
│       ├── message_0.db
│       └── ...
└── logs/
    └── {year}/{month}/{day}/
        └── {day}_wechat_tool.log
```

Logging uses unified config in `src/wechat_decrypt_tool/logging_config.py`

### Database File Types

WeChat creates these main database categories:
- `contact*.db` - Contacts, chat rooms, strangers
- `message_N.db` - Main message content (numbered 0-9+)
- `media_N.db` - Media file metadata
- `session.db` - Chat sessions
- `favorite.db` - Favorites/bookmarks
- `sns.db` - Moments/timeline

Only `message_N.db` files use incremental numbering - this is why incremental mode targets them specifically.

## Security and Privacy Notes

- Keys are 64-character hex strings (32 bytes)
- Keys must be extracted using separate tools (not included)
- One key per WeChat account (keys are account-specific)
- Do not log full keys - only show first 16 and last 16 chars
- Decrypted databases contain sensitive personal data

## Testing and Verification

Successful decryption validation:
1. Output file starts with `b"SQLite format 3\x00"`
2. File size equals input size (or slightly different due to header)
3. Can open with `sqlite3.connect()` without errors
4. Tables and data are readable

Known edge cases:
- `message_fts.db` may have 1 HMAC verification failure (page 262145) - expected
- Files already decrypted (starting with SQLite header) are copied directly
- Files < 4096 bytes are skipped as invalid

## PyInstaller 打包

### 打包命令

```bash
pyinstaller wechat_tool.spec --noconfirm
```

输出: `dist/国海金工微信数据筛选工具v2.5.1.exe` (~70MB 单文件)

### 打包配置要点 (`wechat_tool.spec`)

**Python 环境**: PyInstaller 使用 Python 3.9 (`C:\Users\45349\AppData\Local\Programs\Python\Python39`)

**关键依赖收集**:
- `collect_submodules('wechat_decrypt_tool')` - 内部模块
- `collect_submodules('fpdf')` - fpdf2 所有子模块（必须全量收集，手动列举会遗漏）
- `collect_data_files('fpdf')` - fpdf2 内置字体等数据文件
- `collect_all('flask_cors')` / `collect_all('flask')` - Flask 全量收集
- `collect_data_files('pyecharts')` - K线图模板
- `collect_data_files('akshare')` - 股票数据

**excludes 注意事项**:
- `unittest` **不能排除** — fpdf2 的 `fpdf.sign` 模块顶层依赖 `unittest.mock`，排除会导致整个 fpdf 包无法导入
- 可安全排除: torch/tensorflow/sklearn/matplotlib/pyarrow/tkinter 等未使用的大型库

**EXE 环境特殊处理** (`sys.frozen`):
- `sys.executable` 指向 EXE 自身，不能用于 `pip install`（会死循环启动 EXE）
- `APP_ROOT = Path(sys.executable).parent`（EXE 所在目录）
- 必须用 `getattr(sys, 'frozen', False)` 判断是否为打包环境

### 时间戳处理（时区陷阱）

**重要**: 时间过滤必须用 `datetime.fromisoformat()` 而非 `pd.to_datetime()`

- `pd.to_datetime('2025-12-26T00:00').timestamp()` → 按 **UTC** 解析 → 本地时间偏移 8 小时
- `datetime.fromisoformat('2025-12-26T00:00').timestamp()` → 按 **本地时间** 解析 → 正确

前端 `datetime-local` 输入的值是本地时间，后端必须按本地时间处理。`datetime.fromtimestamp()` 显示也是本地时间，两端一致。

### 前端去重逻辑

去重在前端执行（`deduplicateResults` 函数），key 仅使用 `content`（不含 chat_name/sender），支持跨群跨发送者去重。适用于股票推荐等转发场景。

## Static File Serving

The Flask app serves static files with security constraints:
- Only files with allowed extensions: `.html`, `.css`, `.js`, `.png`, `.jpg`, `.svg`, `.ico`
- Files must exist in `FRONTEND_DIR` and be actual files (not directories)
- Path traversal is prevented by checking `file_path.exists() and file_path.is_file()`
