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

# 添加路径
root_path = Path(__file__).parent
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

app = Flask(__name__)
CORS(app)
app.config['JSON_AS_ASCII'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True  # 模板自动重载
app.jinja_env.auto_reload = True

# 全局配置
OUTPUT_BASE_DIR = Path(__file__).parent / "output" / "databases"

# 初始化配置管理器
config_manager = ConfigManager()

# 全局搜索器
searcher = None


def init_searcher():
    """初始化搜索器 - 从解密的数据库目录加载"""
    global searcher
    base_dir = Path(__file__).parent
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
        "version": "2.0.0",
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

        # 转换结果 - 显示所有结果
        results_list = []
        for idx, row in results.iterrows():
            results_list.append({
                'id': int(idx),
                'time': row['时间'].strftime('%Y-%m-%d %H:%M:%S') if pd.notna(row['时间']) else '',
                'chat_name': str(row['聊天对象']),
                'sender': str(row['发言人']),
                'type': int(row['消息类型']),
                'type_name': get_message_type_name(int(row['消息类型'])),
                'content': str(row['内容'])  # 显示完整内容
            })

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
        output_path = Path(__file__).parent / 'output' / filename

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
    file_path = Path(__file__).parent / 'output' / filename
    if file_path.exists():
        return send_file(str(file_path), as_attachment=True)
    else:
        return jsonify({
            'success': False,
            'message': '文件不存在'
        })


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


def get_message_type_name(msg_type):
    """获取消息类型名称"""
    type_map = {
        1: '文本',
        3: '图片',
        34: '语音',
        43: '视频',
        47: '表情',
        48: '位置',
        49: '链接/公众号',
        10000: '系统消息',
        10002: '撤回消息',
        21474836529: '公众号文章',
        81604378673: '文件'
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
        output_dir = Path(__file__).parent / 'output' / 'images'
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
