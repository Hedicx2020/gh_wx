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

## Static File Serving

The Flask app serves static files with security constraints:
- Only files with allowed extensions: `.html`, `.css`, `.js`, `.png`, `.jpg`, `.svg`, `.ico`
- Files must exist in `FRONTEND_DIR` and be actual files (not directories)
- Path traversal is prevented by checking `file_path.exists() and file_path.is_file()`
