# 微信数据库解密与聊天记录搜索工具

基于 WeChatDataAnalysis 项目重构，集成了数据库解密、聊天记录导出和搜索功能的 Web 应用。

## 功能特性

- **数据库解密** - 支持首次完整解密和智能增量解密
- **聊天记录导出** - 解析并导出聊天记录到 Excel
- **智能搜索** - 按时间、聊天对象、发言人、关键词搜索
- **配置管理** - 保存数据库密码和路径配置

## 项目结构

```
gh_wx_tool/
├── src/                          # 核心模块
│   └── wechat_decrypt_tool/      # 解密工具包
├── templates/                    # Web界面模板
├── web_app.py                    # 集成Web服务器
├── export_final.py               # 聊天记录导出脚本
├── search_messages.py            # 搜索功能模块
├── config_manager.py             # 配置管理
├── test_decrypt.py               # 命令行解密脚本
├── config.xlsx                   # 配置文件(Excel格式)
└── output/                       # 输出目录
    ├── databases/                # 解密后的数据库
    └── 聊天记录_完整版_v*.xlsx  # 导出的聊天记录
```

## 快速开始

### 1. 安装依赖

```bash
pip install cryptography flask flask-cors pandas openpyxl
```

### 2. 启动Web服务

双击 `启动Web搜索.bat` 或运行:

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
python export_final.py
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
  - 📥 导出全部结果 (导出所有搜索到的数据)

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

## 开发者

基于 WeChatDataAnalysis 项目重构
