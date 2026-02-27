#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信数据库解密与聊天记录搜索 - 集成Web应用
"""

import os
import platform
import subprocess
import sys
import traceback
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_file, Response, stream_with_context
from flask_cors import CORS
import pandas as pd
import json as json_module

# 判断是否是打包后的exe运行
def get_app_path():
    """获取应用程序所在目录（兼容exe和脚本运行）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller打包后的exe
        return Path(sys.executable).parent
    else:
        # 普通Python脚本运行
        return Path(__file__).parent

# 应用根目录（exe所在目录或脚本所在目录）
APP_ROOT = get_app_path()

# 添加路径（用于脚本运行时）
root_path = Path(__file__).parent if not getattr(sys, 'frozen', False) else APP_ROOT
src_path = root_path / "src"
utils_path = root_path / "utils"
scripts_path = root_path / "scripts"

sys.path.insert(0, str(src_path))
sys.path.insert(0, str(utils_path))
sys.path.insert(0, str(scripts_path))

from wechat_decrypt_tool.wechat_decrypt import decrypt_wechat_databases
from wechat_decrypt_tool.logging_config import get_logger
from search_messages_optimized import MessageSearcher  # 使用优化版搜索器
from config_manager import ConfigManager
from wechat_key_extractor import auto_extract_keys, load_keys_from_config, save_keys_to_config
from dat_to_image import DatImageDecryptor
from utils.llm_client import OpenAIClient, LLMConfig
from stock_filter import get_stock_filter, filter_messages_by_markets, preload_stock_data, is_stock_data_loaded
from stock_kline import get_stock_info, get_kline_data, generate_kline_chart

app = Flask(__name__, template_folder='templates')
CORS(app)
app.config['JSON_AS_ASCII'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True  # 模板自动重载
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # 禁用静态文件缓存
app.jinja_env.auto_reload = True
app.jinja_env.cache = {}  # 清除Jinja模板缓存

# 全局配置（使用APP_ROOT确保exe运行时路径正确）
OUTPUT_BASE_DIR = APP_ROOT / "output" / "databases"

# 初始化配置管理器
config_manager = ConfigManager()

# 全局搜索器
searcher = None


def init_searcher():
    """初始化搜索器 - 从解密的数据库目录加载"""
    global searcher
    base_dir = APP_ROOT
    databases_dir = base_dir / 'output' / 'databases'

    # 查找解密后的数据库目录
    if not databases_dir.exists():
        print(f"[ERROR] 数据库目录不存在: {databases_dir}")
        return False

    # 查找包含message和contact数据库的子目录
    account_dirs = [d for d in databases_dir.iterdir() if d.is_dir()]

    if not account_dirs:
        print(f"[ERROR] 未找到账号数据库目录")
        return False

    # 使用第一个找到的账号目录
    db_dir = account_dirs[0]
    print(f"使用数据库目录: {db_dir}")

    # 检查必要的数据库文件
    message_dbs = list(db_dir.glob('message_*.db'))
    contact_db = db_dir / 'contact.db'

    if not message_dbs:
        print(f"[ERROR] 未找到message数据库: {db_dir}")
        return False

    if not contact_db.exists():
        print(f"[ERROR] 未找到contact.db: {contact_db}")
        return False

    try:
        print(f"正在从所有message数据库加载消息...")
        searcher = MessageSearcher(str(db_dir))
        print(f"[OK] 搜索器初始化成功")
        return True
    except Exception as e:
        print(f"[ERROR] 初始化搜索器失败: {e}")
        import traceback
        traceback.print_exc()
        return False


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


# ==================== 数据库解密API ====================

@app.route('/api/decrypt', methods=['POST'])
def decrypt():
    """解密API端点 - 只支持全量解密"""
    try:
        data = request.get_json()

        key = data.get('key')
        db_path = data.get('db_path')

        # 验证参数
        if not key or len(key) != 64:
            return jsonify({
                "status": "error",
                "message": "密钥必须是64位十六进制字符串"
            }), 400

        if not db_path:
            return jsonify({
                "status": "error",
                "message": "数据库路径不能为空"
            }), 400

        # 检查路径是否存在
        if not Path(db_path).exists():
            return jsonify({
                "status": "error",
                "message": f"数据库路径不存在: {db_path}"
            }), 400

        # 执行全量解密
        result = decrypt_wechat_databases(
            db_storage_path=db_path,
            key=key
        )

        return jsonify(result)

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": f"服务器错误: {str(e)}"
        }), 500


@app.route('/api/open-folder', methods=['POST'])
def open_folder():
    """打开输出文件夹"""
    try:
        output_dir = OUTPUT_BASE_DIR.absolute()

        # 根据操作系统使用不同命令
        if platform.system() == 'Windows':
            subprocess.Popen(['explorer', str(output_dir)])
        elif platform.system() == 'Darwin':  # macOS
            subprocess.Popen(['open', str(output_dir)])
        else:  # Linux
            subprocess.Popen(['xdg-open', str(output_dir)])

        return jsonify({"status": "success"})

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/status', methods=['GET'])
def status():
    """获取服务器状态"""
    return jsonify({
        "status": "online",
        "version": "2.5.0",
        "output_directory": str(OUTPUT_BASE_DIR.absolute())
    })


# ==================== 配置管理API ====================

@app.route('/api/config', methods=['GET'])
def get_config():
    """获取配置 - 每次请求都从Excel实时读取"""
    # 为避免任何缓存或进程状态导致的旧数据，使用新的ConfigManager实例读取
    fresh_config_manager = ConfigManager()
    config = fresh_config_manager.get_all(reload=True)

    response = jsonify({
        'success': True,
        'config': config,
        'debug': {
            'config_file': str(fresh_config_manager.config_file),
            'file_exists': fresh_config_manager.config_file.exists()
        }
    })
    # 禁用浏览器/代理缓存，避免返回旧配置
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/api/config/debug', methods=['GET'])
def debug_config():
    """调试配置文件读取"""
    import pandas as pd
    from pathlib import Path
    
    result = {
        'cwd': str(Path.cwd()),
        'config_file': str(Path.cwd() / 'config.xlsx'),
        'file_exists': (Path.cwd() / 'config.xlsx').exists(),
    }
    
    try:
        df = pd.read_excel(Path.cwd() / 'config.xlsx', engine='openpyxl')
        result['columns'] = df.columns.tolist()
        result['rows'] = []
        for idx, row in df.iterrows():
            result['rows'].append(dict(row))
    except Exception as e:
        result['error'] = str(e)
    
    return jsonify(result)


@app.route('/api/config', methods=['POST'])
def save_config():
    """保存配置"""
    try:
        data = request.json
        config_manager.save_config(data)
        return jsonify({
            'success': True,
            'message': '配置已保存'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'保存失败: {str(e)}'
        })


# ==================== 聊天记录搜索API ====================

@app.route('/api/search', methods=['POST'])
def search():
    """搜索接口"""
    global searcher

    if searcher is None:
        if not init_searcher():
            return jsonify({
                'success': False,
                'message': '搜索器未初始化,请先导出聊天记录'
            })

    try:
        data = request.json

        # 获取搜索参数
        start_date = data.get('start_date') or None
        end_date = data.get('end_date') or None
        chat_name = data.get('chat_name') or None
        sender_name = data.get('sender_name') or None
        keyword = data.get('keyword') or None
        message_type = data.get('message_type')

        # 获取删除关键词(优先使用前端传来的,否则从配置读取)
        delete_keywords = data.get('delete_keywords') or config_manager.get('delete_keywords', '')

        # 获取是否排除自己的消息
        exclude_self = data.get('exclude_self') == 'true' or data.get('exclude_self') == True

        # 获取排除的聊天对象
        exclude_contacts = data.get('exclude_contacts') or None

        # 获取股票市场筛选参数（支持多选）
        stock_markets = data.get('stock_markets') or []
        # 是否匹配数字代码（默认False，只匹配名称）
        match_stock_code = data.get('match_stock_code', False)

        # 转换消息类型
        if message_type == '':
            message_type = None
        elif message_type is not None:
            message_type = int(message_type)

        # 执行搜索(优化版,按需加载)
        results = searcher.search(
            start_date=start_date,
            end_date=end_date,
            chat_name=chat_name,
            sender_name=sender_name,
            keyword=keyword,
            message_type=message_type,
            delete_keywords=delete_keywords,
            exclude_self=exclude_self
        )

        # 获取微信文件根目录（用于构建完整文件路径）
        wechat_files_path = config_manager.get('wechat_files_path')
        wechat_root = Path(wechat_files_path).parent if wechat_files_path else None
        wechat_root_str = str(wechat_root) if wechat_root else ''

        # 转换结果 - 显示所有结果
        results_list = []
        import re
        for idx, row in results.iterrows():
            content = str(row['内容'])

            # 将内容中的相对路径替换为完整路径
            # 格式: "路径:msg/file/2025-09/xxx.pdf" -> "路径:C:\Users\...\msg\file\2025-09\xxx.pdf"
            if wechat_root_str and '路径:msg/' in content:
                def replace_path(match):
                    relative = match.group(1)
                    full = str(wechat_root / relative)
                    return f'路径:{full}'
                content = re.sub(r'路径:(msg/[^\s|]+)', replace_path, content)

            result_item = {
                'id': int(idx),
                'time': row['时间'].strftime('%Y-%m-%d %H:%M:%S') if pd.notna(row['时间']) else '',
                'chat_name': str(row['聊天对象']),
                'sender': str(row['发言人']),
                'type': int(row['消息类型']),
                'type_name': get_message_type_name(int(row['消息类型'])),
                'content': content  # 显示完整内容（路径已转换）
            }
            # 添加文件路径字段（如果有）- 构建完整路径
            if '路径' in row and pd.notna(row['路径']) and row['路径']:
                relative_path = str(row['路径'])
                if wechat_root and relative_path.startswith('msg/'):
                    # 构建完整路径：wechat_root / relative_path
                    full_path = wechat_root / relative_path
                    result_item['file_path'] = str(full_path)
                else:
                    result_item['file_path'] = relative_path
            results_list.append(result_item)

        # 排除特定聊天对象（同时匹配聊天对象和发言人）
        if exclude_contacts:
            exclude_list = [name.strip() for name in exclude_contacts.split(',') if name.strip()]
            if exclude_list:
                before_exclude = len(results_list)
                results_list = [
                    r for r in results_list
                    if not any(ex in r['chat_name'] or ex in r['sender'] for ex in exclude_list)
                ]
                print(f"[排除对象] 排除: {exclude_list}, 排除前: {before_exclude}, 排除后: {len(results_list)}")

        # 股票市场筛选（如果有选择）
        original_count = len(results_list)
        if stock_markets:
            print(f"[股票筛选] 选择的市场: {stock_markets}, 匹配代码: {match_stock_code}, 筛选前数量: {original_count}")
            results_list = filter_messages_by_markets(results_list, stock_markets, match_code=match_stock_code)
            print(f"[股票筛选] 筛选后数量: {len(results_list)}")

        # 统计信息
        stats = {
            'total': original_count,  # 筛选前的总数
            'displayed': len(results_list),  # 筛选后显示的数量
            'chat_count': len(set(r['chat_name'] for r in results_list)) if results_list else 0,
            'sender_count': len(set(r['sender'] for r in results_list)) if results_list else 0,
            'stock_filtered': bool(stock_markets),  # 是否进行了股票筛选
            'stock_markets': stock_markets  # 筛选的市场
        }

        # 消息类型分布（基于筛选后的结果）
        if results_list:
            type_counts = {}
            for r in results_list:
                type_name = r['type_name']
                type_counts[type_name] = type_counts.get(type_name, 0) + 1
            # 取前5个
            stats['type_distribution'] = dict(sorted(type_counts.items(), key=lambda x: -x[1])[:5])
        else:
            stats['type_distribution'] = {}

        return jsonify({
            'success': True,
            'results': results_list,
            'stats': stats
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'搜索失败: {str(e)}'
        })


@app.route('/api/export', methods=['POST'])
def export():
    """导出搜索结果"""
    global searcher

    if searcher is None:
        return jsonify({
            'success': False,
            'message': '搜索器未初始化'
        })

    try:
        data = request.json

        # 执行相同的搜索
        start_date = data.get('start_date') or None
        end_date = data.get('end_date') or None
        chat_name = data.get('chat_name') or None
        sender_name = data.get('sender_name') or None
        keyword = data.get('keyword') or None
        message_type = data.get('message_type')

        # 获取删除关键词(优先使用前端传来的,否则从配置读取)
        delete_keywords = data.get('delete_keywords') or config_manager.get('delete_keywords', '')

        # 获取是否排除自己的消息
        exclude_self = data.get('exclude_self') == 'true' or data.get('exclude_self') == True

        if message_type == '':
            message_type = None
        elif message_type is not None:
            message_type = int(message_type)

        results = searcher.search(
            start_date=start_date,
            end_date=end_date,
            chat_name=chat_name,
            sender_name=sender_name,
            keyword=keyword,
            message_type=message_type,
            delete_keywords=delete_keywords,
            exclude_self=exclude_self
        )

        if len(results) == 0:
            return jsonify({
                'success': False,
                'message': '没有搜索结果可导出'
            })

        # 导出到临时文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'搜索结果_{timestamp}.xlsx'
        output_path = APP_ROOT / 'output' / filename

        searcher.export_results(results, str(output_path))

        return jsonify({
            'success': True,
            'filename': filename,
            'count': len(results)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'导出失败: {str(e)}'
        })


@app.route('/api/download/<filename>')
def download(filename):
    """下载文件"""
    file_path = APP_ROOT / 'output' / filename
    if file_path.exists():
        return send_file(str(file_path), as_attachment=True)
    else:
        return jsonify({
            'success': False,
            'message': '文件不存在'
        })


@app.route('/api/export/contacts', methods=['GET'])
def export_contacts():
    """导出通讯录到Excel"""
    try:
        import sqlite3

        # 查找联系人数据库
        contact_dbs = list(OUTPUT_BASE_DIR.glob('*/contact.db'))
        if not contact_dbs:
            return jsonify({'success': False, 'message': '未找到联系人数据库，请先解密数据库'})

        all_contacts = []
        for db_path in contact_dbs:
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()

                # 查询联系人信息（包含群聊）
                cursor.execute('''
                    SELECT nick_name, remark, alias, username, local_type
                    FROM contact
                    WHERE delete_flag = 0
                    AND username NOT LIKE 'gh_%'
                    ORDER BY local_type, remark, nick_name
                ''')

                for row in cursor.fetchall():
                    nick_name, remark, alias, username, local_type = row
                    # 过滤系统账号
                    if username in ['filehelper', 'newsapp', 'fmessage', 'medianote', 'floatbottle', 'weixin']:
                        continue

                    # 判断类型
                    if '@chatroom' in (username or ''):
                        contact_type = '群聊'
                    elif local_type == 1:
                        contact_type = '好友'
                    else:
                        contact_type = '其他'

                    all_contacts.append({
                        '昵称': nick_name or '',
                        '备注': remark or '',
                        '微信号': alias or '',
                        '原始ID': username or '',
                        '类型': contact_type
                    })
                conn.close()
            except Exception as e:
                print(f"读取 {db_path} 失败: {e}")
                continue

        if not all_contacts:
            return jsonify({'success': False, 'message': '未找到联系人数据'})

        # 去重（按原始ID）
        seen = set()
        unique_contacts = []
        for c in all_contacts:
            if c['原始ID'] not in seen:
                seen.add(c['原始ID'])
                unique_contacts.append(c)

        # 导出到Excel
        df = pd.DataFrame(unique_contacts)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'contacts_{timestamp}.xlsx'
        output_path = APP_ROOT / 'output' / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_excel(str(output_path), index=False)

        return jsonify({
            'success': True,
            'filename': filename,
            'count': len(unique_contacts)
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'导出失败: {str(e)}'})


@app.route('/api/stats')
def get_stats():
    """获取数据库统计信息"""
    global searcher

    if searcher is None:
        if not init_searcher():
            return jsonify({
                'success': False,
                'message': '未找到聊天记录文件'
            })

    try:
        df = searcher.df

        stats = {
            'total_messages': len(df),
            'total_chats': df['聊天对象'].nunique(),
            'total_senders': df['发言人'].nunique(),
            'date_range': {
                'start': df['时间'].min().strftime('%Y-%m-%d'),
                'end': df['时间'].max().strftime('%Y-%m-%d')
            },
            'top_chats': df['聊天对象'].value_counts().head(10).to_dict(),
            'top_senders': df['发言人'].value_counts().head(10).to_dict(),
            'message_types': {}
        }

        # 消息类型分布
        type_counts = df['消息类型'].value_counts().to_dict()
        for msg_type, count in type_counts.items():
            stats['message_types'][get_message_type_name(int(msg_type))] = int(count)

        return jsonify({
            'success': True,
            'stats': stats
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })


@app.route('/api/stock/stats', methods=['GET'])
def get_stock_stats():
    """获取股票数据统计信息"""
    try:
        loaded = is_stock_data_loaded()
        stock_filter = get_stock_filter()
        db_status = stock_filter.get_db_status()
        
        # 只有在数据已加载时才获取统计
        if loaded:
            stats = stock_filter.get_market_stats()
        else:
            stats = {'a_stock': 0, 'hk_stock': 0, 'us_stock': 0}
        
        return jsonify({
            'success': True,
            'stats': stats,
            'loaded': loaded,
            'db_status': db_status,
            'markets': {
                'a_stock': 'A股',
                'hk_stock': '港股',
                'us_stock': '美股'
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'loaded': False,
            'message': f'获取股票统计失败: {str(e)}'
        })


@app.route('/api/stock/preload', methods=['POST'])
def preload_stocks_api():
    """手动触发股票数据预加载"""
    try:
        if is_stock_data_loaded():
            return jsonify({
                'success': True,
                'message': '股票数据已加载'
            })
        
        # 同步加载
        preload_stock_data()
        
        return jsonify({
            'success': True,
            'message': '股票数据加载完成'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'加载失败: {str(e)}'
        })


@app.route('/api/stock/review', methods=['POST'])
def stock_review():
    """股票K线复盘接口"""
    global searcher

    try:
        data = request.json
        
        code = data.get('code', '').strip()
        start_date = data.get('start_date', '')
        end_date = data.get('end_date', '')
        # 额外搜索关键词（逗号分隔）
        extra_search_keywords = data.get('search_keywords', '').strip()
        # 过滤关键词（排除含有这些词的消息）
        delete_keywords = data.get('delete_keywords', '').strip()
        
        if not code:
            return jsonify({
                'success': False,
                'message': '请输入股票代码'
            })
        
        if not start_date or not end_date:
            return jsonify({
                'success': False,
                'message': '请选择日期范围'
            })
        
        # 获取股票信息
        try:
            stock_info = get_stock_info(code)
            stock_name = stock_info.get('name', '')
            stock_code = stock_info.get('code', code)
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'获取股票信息失败: {str(e)}'
            })
        
        # 获取K线数据
        try:
            kline_data = get_kline_data(code, start_date, end_date)
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'获取K线数据失败: {str(e)}'
            })
        
        # 搜索相关聊天记录
        messages = []
        if searcher is None:
            init_searcher()
        
        if searcher is not None:
            # 构建搜索关键词列表（名称和代码都搜索）
            search_keywords = []
            if stock_name and stock_name != code:
                search_keywords.append(stock_name)
            # 也搜索纯数字代码
            code_only = stock_code.split('.')[-1] if '.' in stock_code else code
            if code_only and code_only.isdigit():
                search_keywords.append(code_only)
            
            # 添加用户指定的额外搜索关键词
            if extra_search_keywords:
                for kw in extra_search_keywords.split(','):
                    kw = kw.strip()
                    if kw and kw not in search_keywords:
                        search_keywords.append(kw)
            
            print(f"[复盘] 搜索关键词: {search_keywords}")
            if delete_keywords:
                print(f"[复盘] 过滤关键词: {delete_keywords}")
            
            seen = set()
            for keyword in search_keywords:
                if not keyword:
                    continue
                try:
                    # 搜索包含关键词的聊天记录
                    results = searcher.search(
                        start_date=start_date,
                        end_date=end_date,
                        keyword=keyword,
                        message_type=1,  # 只搜索文本消息
                        delete_keywords=delete_keywords  # 应用过滤关键词
                    )
                    
                    # 转换为列表格式并去重
                    for idx, row in results.iterrows():
                        time_str = row['时间'].strftime('%Y-%m-%d %H:%M:%S') if pd.notna(row['时间']) else ''
                        date_only = time_str.split(' ')[0]
                        chat_name = str(row['聊天对象'])
                        sender = str(row['发言人'])
                        content = str(row['内容'])
                        
                        # 去重: 同一日+内容（不管谁发的，只要内容相同就去重）
                        # 对内容进行标准化：去除首尾空白、统一换行符
                        content_normalized = content.strip().replace('\r\n', '\n').replace('\r', '\n')
                        dedup_key = f"{date_only}|{content_normalized}"
                        if dedup_key in seen:
                            continue
                        seen.add(dedup_key)
                        
                        messages.append({
                            'time': time_str,
                            'chat_name': chat_name,
                            'sender': sender,
                            'content': content
                        })
                    print(f"[复盘] 关键词'{keyword}'找到 {len(results)} 条记录")
                except Exception as e:
                    print(f"[复盘] 搜索关键词'{keyword}'失败: {e}")
        
        # 生成K线图
        try:
            chart_html = generate_kline_chart(
                kline_data,
                messages,
                stock_name=stock_name,
                stock_code=stock_code
            )
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'生成K线图失败: {str(e)}'
            })
        
        # 按日期分组消息
        messages_by_date = {}
        for msg in messages:
            date = msg['time'].split(' ')[0]
            if date not in messages_by_date:
                messages_by_date[date] = []
            messages_by_date[date].append(msg)
        
        # 将DataFrame转换为可序列化的列表
        kline_list = kline_data.to_dict('records') if hasattr(kline_data, 'to_dict') else kline_data
        
        return jsonify({
            'success': True,
            'stock_name': stock_name,
            'stock_code': stock_code,
            'chart_html': chart_html,
            'messages': messages,
            'messages_by_date': messages_by_date,
            'message_count': len(messages),
            'kline_data': kline_list,
            'kline_count': len(kline_data)
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'复盘失败: {str(e)}'
        })


def get_message_type_name(msg_type):
    """获取消息类型名称"""
    type_map = {
        1: '文本',
        3: '图片',
        6: '文件',
        34: '语音',
        43: '视频',
        47: '表情',
        48: '位置',
        49: '链接/公众号',
        10000: '系统消息',
        10002: '撤回消息',
        21474836529: '公众号文章',
        25769803825: '文件',
        81604378673: '聊天记录转发'
    }
    return type_map.get(msg_type, f'类型{msg_type}')


@app.route('/api/image/extract-keys', methods=['POST'])
def extract_image_keys():
    """提取图片解密密钥（自动从config.xlsx读取路径）"""
    try:
        # 从config_manager获取配置
        config = config_manager.get_all()
        wechat_files_path = config.get('wechat_files_path')

        if not wechat_files_path:
            return jsonify({
                'success': False,
                'message': '请先在"数据库配置"中设置数据库路径，系统将自动定位图片目录'
            })

        # 微信文件根目录：wechat_files_path的上级目录
        # 例如：wechat_files_path = "D:\WeChat Files\wxid_xxx\db_storage"
        # 则根目录为："D:\WeChat Files\wxid_xxx"
        wechat_root = Path(wechat_files_path).parent

        # 提取密钥（会自动在msg/attach目录下查找dat文件）
        xor_key, aes_key = auto_extract_keys(str(wechat_root), 'config.xlsx')

        if xor_key is None:
            return jsonify({
                'success': False,
                'message': '未能提取密钥，请检查配置的数据库路径是否正确'
            })

        return jsonify({
            'success': True,
            'message': '密钥提取成功',
            'xor_key': xor_key,
            'aes_key': aes_key,
            'has_aes_key': aes_key is not None,
            'dat_path': str(wechat_root / 'msg' / 'attach')
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'提取密钥失败: {str(e)}'
        })


@app.route('/api/image/convert', methods=['POST'])
def convert_dat_images():
    """批量转换dat文件为jpg（自动从config.xlsx读取路径）"""
    try:
        # 从config_manager获取配置
        config = config_manager.get_all()
        wechat_files_path = config.get('wechat_files_path')

        if not wechat_files_path:
            return jsonify({
                'success': False,
                'message': '请先在"数据库配置"中设置数据库路径'
            })

        # dat文件目录：wechat_files_path的上级/msg/attach
        wechat_root = Path(wechat_files_path).parent
        dat_dir = wechat_root / 'msg' / 'attach'

        if not dat_dir.exists():
            return jsonify({
                'success': False,
                'message': f'图片目录不存在: {dat_dir}'
            })

        # 从配置加载密钥
        xor_key, aes_key = load_keys_from_config('config.xlsx')

        if xor_key is None:
            return jsonify({
                'success': False,
                'message': '未找到密钥，请先点击"提取密钥"按钮'
            })

        if aes_key is None:
            return jsonify({
                'success': False,
                'message': '未找到AES密钥，V4格式需要AES密钥（需管理员权限提取）'
            })

        # 输出目录：output/images
        output_dir = APP_ROOT / 'output' / 'images'
        output_dir.mkdir(parents=True, exist_ok=True)

        # 创建解密器
        decryptor = DatImageDecryptor(xor_key, aes_key)

        # 批量转换
        success, fail = decryptor.batch_convert(
            str(dat_dir),
            str(output_dir),
            recursive=True
        )

        return jsonify({
            'success': True,
            'message': f'转换完成：成功 {success} 个，失败 {fail} 个',
            'total': success + fail,
            'success_count': success,
            'fail_count': fail,
            'dat_dir': str(dat_dir),
            'output_dir': str(output_dir)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'转换失败: {str(e)}'
        })


@app.route('/api/image/get-keys', methods=['GET'])
def get_image_keys():
    """获取已保存的密钥"""
    try:
        xor_key, aes_key = load_keys_from_config('config.xlsx')

        return jsonify({
            'success': True,
            'has_xor_key': xor_key is not None,
            'has_aes_key': aes_key is not None,
            'xor_key': xor_key,
            'aes_key': aes_key[:8] + '...' + aes_key[-8:] if aes_key else None  # 只显示部分密钥
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })


# ==================== AI大模型问答API (OpenAI兼容格式) ====================

# 全局LLM客户端缓存
_llm_client = None
_llm_config_cache = None


def get_llm_client(api_base=None, model=None, api_key=None, temperature=0.7, max_tokens=2000):
    """获取或创建LLM客户端 (统一使用OpenAI兼容格式)"""
    global _llm_client, _llm_config_cache
    
    # 如果没有传入参数，从配置文件加载
    if api_base is None or api_key is None:
        config = config_manager.get_all(reload=True)
        api_base = api_base or config.get('llm_api_base', '')
        model = model or config.get('llm_model', '')
        api_key = api_key or config.get('llm_api_key', '')
        temperature = float(config.get('llm_temperature', 0.7))
        max_tokens = int(config.get('llm_max_tokens', 2000))
    
    current_config = {
        'api_base': api_base,
        'model': model,
        'api_key': api_key,
        'temperature': temperature,
        'max_tokens': max_tokens,
    }
    
    # 检查必需的配置
    if not api_base or not api_key or not model:
        return None
    
    # 如果配置没变，返回缓存的客户端
    if _llm_client and _llm_config_cache == current_config:
        return _llm_client
    
    try:
        llm_config = LLMConfig(
            provider='openai',
            api_key=api_key,
            api_base=api_base,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )
        _llm_client = OpenAIClient(llm_config)
        _llm_config_cache = current_config
        return _llm_client
    except Exception as e:
        print(f"创建LLM客户端失败: {e}")
        return None


@app.route('/api/llm/chat', methods=['POST'])
def llm_chat():
    """发送聊天消息到大模型"""
    try:
        data = request.json
        
        message = data.get('message', '')
        context = data.get('context', '')  # 搜索结果上下文
        history = data.get('history', [])  # 对话历史
        
        if not message:
            return jsonify({
                'success': False,
                'message': '消息不能为空'
            })
        
        # 获取LLM客户端
        client = get_llm_client()
        
        if not client:
            return jsonify({
                'success': False,
                'message': '请先配置大模型（设置提供商和API密钥）'
            })
        
        # 构建消息列表
        messages = []
        
        # 添加历史消息
        for h in history:
            messages.append({
                'role': h.get('role', 'user'),
                'content': h.get('content', '')
            })
        
        # 添加当前消息
        messages.append({
            'role': 'user',
            'content': message
        })
        
        # 调用大模型
        response_text = client.chat(messages, context=context)
        
        return jsonify({
            'success': True,
            'response': response_text
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'调用大模型失败: {str(e)}'
        })


@app.route('/api/llm/chat/stream', methods=['POST'])
def llm_chat_stream():
    """流式聊天接口 (Server-Sent Events)"""
    try:
        data = request.json
        
        message = data.get('message', '')
        context = data.get('context', '')
        history = data.get('history', [])
        
        # 获取LLM配置
        api_base = data.get('api_base', '')
        model = data.get('model', '')
        api_key = data.get('api_key', '')
        temperature = float(data.get('temperature', 0.7))
        max_tokens = int(data.get('max_tokens', 2000))
        
        if not message:
            return jsonify({
                'success': False,
                'message': '消息不能为空'
            })
        
        client = get_llm_client(api_base, model, api_key, temperature, max_tokens)
        
        if not client:
            return jsonify({
                'success': False,
                'message': '请先配置API地址、模型和密钥'
            })
        
        # 构建消息列表
        messages = []
        for h in history:
            messages.append({
                'role': h.get('role', 'user'),
                'content': h.get('content', '')
            })
        messages.append({
            'role': 'user',
            'content': message
        })
        
        def generate():
            try:
                for chunk in client.stream_chat(messages, context=context):
                    yield f"data: {json_module.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
                yield f"data: {json_module.dumps({'done': True})}\n\n"
            except Exception as e:
                yield f"data: {json_module.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        
        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'流式调用失败: {str(e)}'
        })


@app.route('/api/llm/test', methods=['POST'])
def test_llm_connection():
    """测试大模型连接 (OpenAI兼容格式)"""
    try:
        data = request.json or {}
        
        # 从请求中获取配置，或从配置文件加载
        api_base = data.get('api_base', '')
        model = data.get('model', '')
        api_key = data.get('api_key', '')
        temperature = float(data.get('temperature', 0.7))
        max_tokens = int(data.get('max_tokens', 2000))
        
        client = get_llm_client(api_base, model, api_key, temperature, max_tokens)
        
        if not client:
            return jsonify({
                'success': False,
                'message': '请先配置API地址、模型名称和API密钥'
            })
        
        # 发送一个简单的测试消息
        test_messages = [{'role': 'user', 'content': '你好，请用一句话介绍自己。'}]
        response = client.chat(test_messages)
        
        return jsonify({
            'success': True,
            'message': '连接测试成功',
            'response': response[:200] + '...' if len(response) > 200 else response
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'连接测试失败: {str(e)}'
        })


# ==================== 并发批量LLM处理API ====================

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

def process_single_message_llm(msg_data: dict, prompt: str, idx: int, llm_config: dict) -> dict:
    """处理单条消息的LLM调用"""
    try:
        # 构建上下文
        context = f"时间:{msg_data.get('time', '')}\n对象:{msg_data.get('chat_name', '')}\n发送者:{msg_data.get('sender', '')}\n内容:{msg_data.get('content', '')}"

        # 创建LLM客户端
        client = get_llm_client(
            api_base=llm_config.get('api_base'),
            model=llm_config.get('model'),
            api_key=llm_config.get('api_key'),
            temperature=llm_config.get('temperature', 0.7),
            max_tokens=llm_config.get('max_tokens', 2000)
        )

        if not client:
            return {'idx': idx, 'error': 'LLM客户端创建失败'}

        # 调用LLM
        messages = [{'role': 'user', 'content': prompt}]
        response = client.chat(messages, context=context)

        return {
            'idx': idx,
            'time': msg_data.get('time', ''),
            'chat_name': msg_data.get('chat_name', ''),
            'sender': msg_data.get('sender', ''),
            'content': msg_data.get('content', ''),
            'response': response
        }
    except Exception as e:
        return {'idx': idx, 'error': str(e)}


@app.route('/api/llm/batch/stream', methods=['POST'])
def llm_batch_stream():
    """并发批量处理消息，SSE流式返回"""
    try:
        data = request.json
        messages = data.get('messages', [])
        prompt = data.get('prompt', '')
        concurrency = min(int(data.get('concurrency', 3)), 10)  # 默认3，最大10

        if not messages:
            return jsonify({'success': False, 'message': '消息列表为空'})

        if not prompt:
            return jsonify({'success': False, 'message': '提示词不能为空'})

        # LLM配置
        llm_config = {
            'api_base': data.get('api_base', ''),
            'model': data.get('model', ''),
            'api_key': data.get('api_key', ''),
            'temperature': float(data.get('temperature', 0.7)),
            'max_tokens': int(data.get('max_tokens', 2000))
        }

        if not llm_config['api_base'] or not llm_config['api_key'] or not llm_config['model']:
            return jsonify({'success': False, 'message': 'API配置不完整'})

        def generate():
            results_lock = threading.Lock()
            completed_count = 0
            total = len(messages)

            # 发送开始信号
            yield f"data: {json_module.dumps({'type': 'start', 'total': total, 'concurrency': concurrency}, ensure_ascii=False)}\n\n"

            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                # 提交所有任务
                futures = {
                    executor.submit(process_single_message_llm, msg, prompt, idx, llm_config): idx
                    for idx, msg in enumerate(messages)
                }

                # 按完成顺序处理结果
                for future in as_completed(futures):
                    idx = futures[future]
                    try:
                        result = future.result(timeout=120)  # 2分钟超时
                        with results_lock:
                            completed_count += 1

                        # SSE 格式返回每条结果
                        yield f"data: {json_module.dumps({'type': 'result', 'idx': idx, 'completed': completed_count, 'total': total, 'data': result}, ensure_ascii=False)}\n\n"

                    except Exception as e:
                        with results_lock:
                            completed_count += 1
                        yield f"data: {json_module.dumps({'type': 'error', 'idx': idx, 'completed': completed_count, 'total': total, 'error': str(e)}, ensure_ascii=False)}\n\n"

            # 发送完成信号
            yield f"data: {json_module.dumps({'type': 'done', 'total': total}, ensure_ascii=False)}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'批量处理失败: {str(e)}'
        })


@app.route('/api/llm/export', methods=['POST'])
def export_chat_history():
    """导出AI对话历史到Excel"""
    try:
        data = request.json
        history = data.get('history', [])
        context = data.get('context', '')
        
        if not history:
            return jsonify({
                'success': False,
                'message': '没有对话记录可导出'
            })
        
        # 构建导出数据
        export_data = []
        for msg in history:
            export_data.append({
                '角色': '用户' if msg.get('role') == 'user' else 'AI助手',
                '内容': msg.get('content', '')
            })
        
        # 创建DataFrame
        df = pd.DataFrame(export_data)
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'AI对话记录_{timestamp}.xlsx'
        output_path = APP_ROOT / 'output' / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 导出到Excel
        with pd.ExcelWriter(str(output_path), engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='对话记录', index=False)
            
            # 如果有上下文，也导出
            if context:
                context_df = pd.DataFrame([{'上下文内容': context}])
                context_df.to_excel(writer, sheet_name='搜索上下文', index=False)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'count': len(history)
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'导出失败: {str(e)}'
        })


@app.route('/api/report/pdf', methods=['POST'])
def export_report_pdf():
    """导出股票推荐报告为PDF"""
    try:
        data = request.json
        recommendations = data.get('recommendations', [])
        summary = data.get('summary', {})

        if not recommendations:
            return jsonify({'success': False, 'message': '没有数据可导出'})

        # 尝试使用fpdf2生成PDF
        try:
            from fpdf import FPDF

            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)

            # 添加中文字体
            chinese_font = 'Helvetica'
            for fp in ['C:/Windows/Fonts/simhei.ttf', 'C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simsun.ttc']:
                if os.path.exists(fp):
                    pdf.add_font('Chinese', '', fp)
                    chinese_font = 'Chinese'
                    break

            # 标题
            pdf.set_font(chinese_font, '', 16)
            pdf.cell(0, 10, '股票推荐报告', align='C')
            pdf.ln(15)

            # 摘要
            pdf.set_font(chinese_font, '', 10)
            pdf.cell(0, 8, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            pdf.ln(8)
            pdf.cell(0, 8, f"总处理: {summary.get('total', 0)} | 有效推荐: {summary.get('valid', 0)} | 已过滤: {summary.get('filtered', 0)}")
            pdf.ln(12)

            # 表头
            pdf.set_fill_color(74, 159, 216)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font(chinese_font, '', 9)

            col_widths = [30, 22, 22, 25, 90]
            headers = ['时间', '股票', '推荐人', '群组', '推荐理由']
            for i, header in enumerate(headers):
                pdf.cell(col_widths[i], 8, header, 1, 0, 'C', True)
            pdf.ln()

            # 数据行 - 使用multi_cell支持自动换行
            pdf.set_text_color(0, 0, 0)
            pdf.set_font(chinese_font, '', 8)

            line_height = 5
            for rec in recommendations:
                # 准备数据
                time_str = str(rec.get('time', ''))[:16]
                stock_str = str(rec.get('stock', ''))[:12]
                sender_str = str(rec.get('sender', ''))[:10]
                group_str = str(rec.get('group', ''))[:12]
                reason_str = str(rec.get('reason', ''))[:100]  # 允许更长的理由

                # 计算推荐理由需要的行数
                reason_width = col_widths[4] - 2
                char_per_line = int(reason_width / 2.5)  # 估算每行字符数
                reason_lines = max(1, (len(reason_str) + char_per_line - 1) // char_per_line)
                row_height = max(line_height * reason_lines, line_height * 2)

                # 保存当前位置
                x_start = pdf.get_x()
                y_start = pdf.get_y()

                # 绘制前4列（固定高度单元格）
                pdf.cell(col_widths[0], row_height, time_str, 1, 0, 'L')
                pdf.cell(col_widths[1], row_height, stock_str, 1, 0, 'L')
                pdf.cell(col_widths[2], row_height, sender_str, 1, 0, 'L')
                pdf.cell(col_widths[3], row_height, group_str, 1, 0, 'L')

                # 第5列使用multi_cell支持换行
                x_reason = pdf.get_x()
                pdf.multi_cell(col_widths[4], line_height, reason_str, 1, 'L')

                # 移到下一行
                pdf.set_xy(x_start, y_start + row_height)

            # 保存PDF (使用ASCII文件名避免URL编码问题)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'stock_report_{timestamp}.pdf'
            output_path = APP_ROOT / 'output' / filename
            output_path.parent.mkdir(parents=True, exist_ok=True)
            pdf.output(str(output_path))

            return jsonify({
                'success': True,
                'filename': filename,
                'filepath': str(output_path)
            })

        except ImportError:
            # 如果没有fpdf2，导出为Excel
            df = pd.DataFrame(recommendations)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'stock_report_{timestamp}.xlsx'
            output_path = APP_ROOT / 'output' / filename
            output_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_excel(str(output_path), index=False)

            return jsonify({
                'success': True,
                'filename': filename,
                'filepath': str(output_path),
                'note': 'PDF库未安装(pip install fpdf2)，已导出为Excel格式'
            })

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'导出失败: {str(e)}'
        })


@app.route('/api/stock/review/export', methods=['POST'])
def export_review_messages():
    """导出复盘数据到Excel（包含K线数据和聊天记录）"""
    try:
        data = request.json
        stock_name = data.get('stock_name', '')
        stock_code = data.get('stock_code', '')
        messages = data.get('messages', [])
        kline_data = data.get('kline_data', [])
        messages_by_date = data.get('messages_by_date', {})
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = stock_name.replace('/', '_').replace('\\', '_')[:20]
        filename = f'复盘_{safe_name}_{stock_code}_{timestamp}.xlsx'
        output_path = APP_ROOT / 'output' / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with pd.ExcelWriter(str(output_path), engine='openpyxl') as writer:
            # Sheet 1: K线数据 + 当日聊天记录摘要
            if kline_data:
                kline_export = []
                for kline in kline_data:
                    date = kline.get('date', '')
                    # 获取当日的聊天记录
                    day_messages = messages_by_date.get(date, [])
                    # 合并当日消息为摘要
                    msg_summary = '\n---\n'.join([
                        f"[{m.get('time', '').split(' ')[-1] if ' ' in m.get('time', '') else ''}] {m.get('sender', '')}: {m.get('content', '')[:100]}..."
                        if len(m.get('content', '')) > 100 else
                        f"[{m.get('time', '').split(' ')[-1] if ' ' in m.get('time', '') else ''}] {m.get('sender', '')}: {m.get('content', '')}"
                        for m in day_messages
                    ]) if day_messages else ''
                    
                    kline_export.append({
                        '日期': date,
                        '开盘': kline.get('open', ''),
                        '收盘': kline.get('close', ''),
                        '最高': kline.get('high', ''),
                        '最低': kline.get('low', ''),
                        '成交量': kline.get('volume', ''),
                        '涨跌幅': kline.get('pctChg', ''),
                        '消息数': len(day_messages),
                        '当日聊天摘要': msg_summary
                    })
                
                kline_df = pd.DataFrame(kline_export)
                kline_df.to_excel(writer, sheet_name='K线与消息', index=False)
            
            # Sheet 2: 完整聊天记录
            if messages:
                msg_export = []
                for msg in messages:
                    msg_export.append({
                        '时间': msg.get('time', ''),
                        '日期': msg.get('time', '').split(' ')[0] if ' ' in msg.get('time', '') else msg.get('time', ''),
                        '聊天对象': msg.get('chat_name', ''),
                        '发送者': msg.get('sender', ''),
                        '内容': msg.get('content', '')
                    })
                msg_df = pd.DataFrame(msg_export)
                msg_df.to_excel(writer, sheet_name='完整聊天记录', index=False)
            
            # Sheet 3: 股票基本信息
            info_df = pd.DataFrame([{
                '股票名称': stock_name,
                '股票代码': stock_code,
                'K线天数': len(kline_data),
                '消息总数': len(messages),
                '导出时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }])
            info_df.to_excel(writer, sheet_name='基本信息', index=False)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'count': len(messages),
            'kline_count': len(kline_data)
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'导出失败: {str(e)}'
        })


if __name__ == '__main__':
    import webbrowser
    import threading
    
    # 初始化搜索器
    print("正在初始化搜索器...")
    if init_searcher():
        print("✓ 搜索器初始化成功")
    else:
        print("⚠ 搜索器初始化失败,请先解密数据库")

    # 后台预加载股票数据
    def preload_stocks():
        try:
            preload_stock_data()
        except Exception as e:
            print(f"⚠ 股票数据预加载失败: {e}")
    
    threading.Thread(target=preload_stocks, daemon=True).start()

    print("\n" + "=" * 60)
    print("微信数据库解密与聊天记录搜索 - 集成Web应用")
    print("=" * 60)
    print(f"\n访问地址: http://127.0.0.1:5000")
    print(f"输出目录: {OUTPUT_BASE_DIR.absolute()}")
    print("\n功能:")
    print("  1. 数据库解密")
    print("  2. 聊天记录搜索")
    print("  3. 配置管理")
    print("  4. 股票筛选 (A股/港股/美股)")
    print("\n按 Ctrl+C 停止服务器\n")

    # 自动打开浏览器
    def open_browser():
        import time
        time.sleep(1.5)  # 等待服务器启动
        webbrowser.open('http://127.0.0.1:5000')

    threading.Thread(target=open_browser, daemon=True).start()

    app.run(host='0.0.0.0', port=5000, debug=False)  # 关闭debug模式避免双开浏览器
