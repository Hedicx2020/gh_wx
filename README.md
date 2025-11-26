# 微信数据库解密与聊天记录搜索工具

基于 WeChatDataAnalysis 项目重构，集成了数据库解密、聊天记录导出和搜索功能的 Web 应用。

## 功能特性

- **数据库解密** - 支持首次完整解密和智能增量解密
- **聊天记录导出** - 解析并导出聊天记录到 Excel
- **智能搜索** - 按时间、聊天对象、发言人、关键词搜索
- **媒体文件导出** - 自动提取并导出图片、视频、文件等媒体内容
- **🆕 图片解密** - 自动提取密钥并解密微信缓存的.dat图片文件（仅V4格式）
- **配置管理** - 保存数据库密钥和路径配置

## 项目结构

```
gh_wx/
├── web_app.py                    # 集成Web服务器(主入口)
├── src/                          # 核心模块
│   └── wechat_decrypt_tool/      # 解密工具包
├── scripts/                      # 功能脚本
│   ├── export_final.py           # 聊天记录导出脚本
│   ├── search_messages.py        # 搜索功能模块
│   ├── search_messages_optimized.py  # 优化版搜索器
│   └── media_exporter.py         # 媒体文件导出器
├── utils/                        # 工具模块
│   ├── config_manager.py         # 配置管理
│   ├── message_parser.py         # 消息解析器
│   ├── wechat_key_extractor.py   # 🆕 微信图片密钥提取器
│   └── dat_to_image.py           # 🆕 dat图片解密转换器
├── templates/                    # Web界面模板
├── frontend/                     # 前端静态文件(如有)
├── config.xlsx                   # 配置文件(Excel格式,不提交)
├── pyproject.toml                # UV项目配置
├── .python-version               # Python版本锁定
└── output/                       # 输出目录
    ├── databases/                # 解密后的数据库
    ├── exports/                  # 导出的搜索结果(含媒体文件)
    │   └── 搜索结果_YYYYMMDD_HHMMSS/  # 每次搜索导出独立文件夹
    │       ├── 搜索结果_*.xlsx   # Excel搜索结果
    │       ├── images/           # 图片文件
    │       ├── videos/           # 视频文件
    │       ├── files/            # 文档文件
    │       └── audio/            # 语音文件(暂不支持)
    └── 聊天记录_完整版_v*.xlsx  # 导出的聊天记录
```

## 快速开始

### 1. 安装依赖

**推荐使用 UV (极速包管理器):**

```bash
# 安装所有依赖
uv sync
```

**或使用传统 pip:**

```bash
# 基础功能
pip install cryptography flask flask-cors pandas openpyxl zstandard

# 图片解密功能（V4格式）需要额外安装
pip install pycryptodome pymem
```

### 2. 启动Web服务

**使用 UV:**

```bash
uv run python web_app.py
```

**或直接运行:**

```bash
python web_app.py
```

### 3. 访问Web界面

打开浏览器访问: http://127.0.0.1:5000

## 使用流程

### 数据库解密

1. 访问 Web 界面
2. 输入64位十六进制解密密钥
3. 输入数据库路径 (db_storage 目录)
4. 选择解密模式:
   - **首次解密**: 解密所有数据库
   - **增量解密**: 只解密新增数据库
5. 点击"开始解密"

### 导出聊天记录

解密完成后，运行导出脚本:

```bash
# 使用 UV
uv run python scripts/export_final.py

# 或直接运行
python scripts/export_final.py
```

会生成 `output/聊天记录_完整版_v2.xlsx` 文件。

### Web界面使用

访问 http://127.0.0.1:5000 即可看到横向布局的操作界面:

#### 页面布局

**顶部区域(左右分栏):**
- **左侧 - 数据库配置**:
  - 解密密钥 (64位十六进制)
  - 数据库路径 (db_storage目录)
  - 默认时间范围 (可选,配置后自动填充到搜索)
  - 常用搜索词/过滤词
  - 🔄 加载配置: 从当前目录 config.xlsx 加载
  - 💾 保存配置: 保存所有配置到 config.xlsx

- **右侧 - 解密操作**:
  - 🔓 首次完整解密: 解密所有数据库
  - ⚡ 增量解密: 只解密新增和更新的数据库
  - 使用说明提示

**底部区域 - 搜索聊天记录**:
- 搜索条件横向排列 (4列布局):
  - 时间范围、聊天对象、发言人、搜索关键词
  - 过滤关键词、消息类型、搜索/清空按钮
- 快捷操作:
  - 📝 应用常用搜索词
  - 📥 导出全部结果 (导出Excel + 自动提取媒体文件)
    - 每次导出创建独立文件夹 `搜索结果_YYYYMMDD_HHMMSS/`
    - 自动复制图片、视频、文档文件到对应子文件夹
    - Excel中包含媒体文件相对路径引用
    - 导出完成后可一键打开文件夹

#### 使用流程

1. **首次使用**:
   - 填写配置 → 保存配置 → 首次解密 → 运行 export_final.py

2. **日常使用**:
   - 点击"加载配置"自动加载 config.xlsx
   - 默认时间范围和过滤词自动应用
   - 直接搜索即可

3. **配置说明**:
   - 所有配置自动保存到当前目录的 config.xlsx
   - 包含: 密钥、路径、默认时间范围、搜索词、过滤词
   - 下次打开自动加载配置

## 命令行使用

### 解密数据库

编辑 `test_decrypt.py` 设置密钥和路径:

```python
KEY = "your_64_character_hex_key"
ACCOUNT = "your_account"
db_storage_path = r"path\to\db_storage"
```

运行:

```bash
python test_decrypt.py
```

### 搜索示例

```python
import sys
sys.path.insert(0, 'scripts')
from search_messages import MessageSearcher

searcher = MessageSearcher('output/聊天记录_完整版_v2.xlsx')

# 搜索某人的聊天
results = searcher.search(chat_name='张雨蒙')

# 搜索特定时间段
results = searcher.search(
    start_date='2025-11-15',
    end_date='2025-11-15',
    chat_name='研究所'
)

# 导出结果
searcher.export_results(results, 'output/搜索结果.xlsx')
```

## 技术细节

### 加密算法

- 密钥派生: PBKDF2-SHA512, 256,000 轮迭代
- 加密算法: AES-256-CBC
- 完整性验证: HMAC-SHA512
- 页面大小: 4096 字节

### 支持的数据库

- contact.db - 联系人信息
- message_*.db - 聊天消息
- session.db - 会话列表
- sns.db - 朋友圈
- favorite.db - 收藏
- emoticon.db - 表情包

### 消息类型

- 1: 文本
- 3: 图片(含文件路径)
- 34: 语音
- 43: 视频(含文件路径)
- 47: 表情
- 49: 链接/公众号
- 10000: 系统消息
- 21474836529: 公众号文章
- 81604378673: 文件(PDF等,含路径)

## 注意事项

- 密钥必须是 64 位十六进制字符串
- 一个密钥对应一个微信账户
- 解密后的数据库请妥善保管
- Web 服务仅监听本地 (127.0.0.1)

### 新增功能说明

- **发言人识别优化**: 单聊和群聊都能正确区分"我"和其他人的消息
- **文件路径解析**: 图片、视频、PDF等文件类型会显示完整文件路径
- **公众号消息**: 正确解析公众号文章标题和链接
- **配置文件**: 改用Excel格式(config.xlsx)，更易于查看和编辑
- **媒体文件导出**:
  - 根据搜索条件导出对应的图片、视频、文件
  - 每次导出创建独立文件夹，包含Excel和媒体文件
  - 自动从微信FileStorage目录提取文件(基于MD5)
  - 支持的媒体类型: 图片(类型3)、视频(类型43)、文件(类型49/81604378673)
- **🆕 微信图片解密** (仅V4格式，已集成到Web界面):
  - 自动提取XOR密钥（从缩略图文件分析）
  - 自动提取AES密钥（从微信进程内存扫描，需管理员权限）
  - 密钥自动保存到config.xlsx
  - 批量转换.dat图片为.jpg
  - 支持递归处理整个目录

## 🆕 图片解密功能说明

### Web界面使用（推荐）

在Web界面的"图片解密"部分：

**前提条件**：
- 先在"数据库配置"中设置数据库路径（如 `D:\WeChat Files\wxid_xxx\db_storage`）
- 系统将自动从该路径定位图片目录（`msg/attach`）

**使用步骤**：

1. **提取密钥**：
   - 点击"🔑 提取密钥"按钮
   - 系统会自动从 `msg/attach` 目录提取XOR和AES密钥
   - 密钥自动保存到config.xlsx
   - ⚠️ AES密钥提取需要管理员权限和微信运行中

2. **转换图片**：
   - 点击"🖼️ 转换图片"按钮
   - 系统会自动批量转换所有V4格式的.dat文件为.jpg
   - 输出到 `output/images` 目录
   - ⚠️ **当前仅支持缩略图文件**（文件名以`_t.dat`结尾）
   - 完整图文件需要不同的AES密钥（暂不支持）

### 技术原理

**V4格式文件结构**：
- 文件头：`0x07 0x08 V2 0x08 0x07`
- AES-ECB模式加密前半部分
- XOR加密后半部分

**密钥提取原理**：
- XOR密钥：通过分析JPEG文件末尾固定字节（`0xFF 0xD9`）统计推算
- AES密钥：从微信进程内存扫描16字节候选并验证

**参考项目**：[WxDatDecrypt](https://github.com/recarto404/WxDatDecrypt)

## 打包为 EXE

项目已配置好打包脚本，一键即可打包为独立 exe 文件：

```bash
# Windows: 双击运行
build.bat

# 或命令行运行
build.bat
```

打包完成后：
- 发布包位置: `dist_release/`
- 主程序: `dist_release/微信数据筛选工具.exe`
- 可将整个 `dist_release/` 文件夹打包为 zip 分发

**使用方法**：
1. 双击 `微信数据筛选工具.exe`
2. 浏览器会自动打开并访问 http://127.0.0.1:5000
3. 如未自动打开，请手动访问上述地址

**注意**：
- exe 文件约 100-150MB（包含 Python 运行时）
- 首次启动需要几秒钟解压临时文件
- config.xlsx 和 output/ 会在运行时自动创建
- 关闭控制台窗口会停止服务

## 开发者

基于 WeChatDataAnalysis 项目重构
