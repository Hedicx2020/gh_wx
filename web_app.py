#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信数据库解密与聊天记录搜索 - 集成Web应用
"""

import os
import platform
import re
import subprocess
import sys
import traceback
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd

# 添加src目录到路径
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))
sys.path.insert(0, os.path.dirname(__file__))

from wechat_decrypt_tool.wechat_decrypt import decrypt_wechat_databases, WeChatDatabaseDecryptor
from wechat_decrypt_tool.logging_config import get_logger
from search_messages_optimized import MessageSearcher  # 使用优化版搜索器
from config_manager import ConfigManager

app = Flask(__name__)
CORS(app)
app.config['JSON_AS_ASCII'] = False

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


def find_max_message_db(directory):
    """
    查找目录中最大编号的message数据库

    参数:
        directory: 要搜索的目录路径

    返回:
        (max_number, db_path) 或 (None, None)
    """
    max_num = -1
    max_path = None

    directory = Path(directory)

    if not directory.exists():
        return None, None

    # 搜索message_*.db文件
    pattern = re.compile(r'message_(\d+)\.db$')

    for root, dirs, files in os.walk(directory):
        for file in files:
            match = pattern.match(file)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
                    max_path = os.path.join(root, file)

    if max_num >= 0:
        return max_num, max_path
    return None, None


def incremental_decrypt(db_storage_path, key, account_name=None):
    """
    增量解密：智能解密更新的数据库

    逻辑：
    1. message_*.db: 只重新解密最大编号的和新增的数据库
    2. 其他数据库 (contact.db, session.db, sns.db等): 全部重新解密（因为会持续更新）
    3. 跳过不需要解密的数据库 (key_info.db等)

    参数:
        db_storage_path: 源数据库路径
        key: 解密密钥
        account_name: 账号名称

    返回:
        解密结果字典
    """
    logger = get_logger(__name__)

    # 查找源目录中最大编号的message数据库
    source_max_num, source_max_path = find_max_message_db(db_storage_path)

    if source_max_num is None:
        return {
            "status": "error",
            "message": "未找到message数据库文件",
            "total_databases": 0,
            "successful_count": 0,
            "failed_count": 0,
            "output_directory": str(OUTPUT_BASE_DIR.absolute()),
            "processed_files": [],
            "failed_files": []
        }

    # 确定账号名
    if not account_name:
        # 从路径中提取账号名：取db_storage的父目录名
        storage_path = Path(db_storage_path)
        if storage_path.name == "db_storage":
            # 如果路径就是db_storage目录，取其父目录名
            account_name = storage_path.parent.name
        else:
            # 如果路径包含db_storage，找到它并取其父目录名
            path_parts = storage_path.parts
            for i, part in enumerate(path_parts):
                if part == "db_storage" and i > 0:
                    account_name = path_parts[i - 1]
                    break

        if not account_name or len(account_name) <= 3:
            account_name = "unknown_account"

    # 查找输出目录中最大编号的message数据库
    output_dir = OUTPUT_BASE_DIR / account_name
    output_max_num, output_max_path = find_max_message_db(output_dir)

    # 确定要解密的数据库列表
    databases_to_decrypt = []

    if output_max_num is None:
        # 输出目录没有任何message数据库，这是首次解密，应该用完整解密
        logger.warning("输出目录无message数据库，建议使用首次解密模式")
        return {
            "status": "error",
            "message": "未找到已解密的数据库，请使用首次解密模式",
            "total_databases": 0,
            "successful_count": 0,
            "failed_count": 0,
            "output_directory": str(output_dir.absolute()),
            "processed_files": [],
            "failed_files": []
        }

    # 策略1：处理 message_*.db 数据库
    # - 重新解密最大编号的message数据库（output_max_num）
    # - 解密所有新增的数据库（output_max_num+1 到 source_max_num）

    if source_max_num >= output_max_num:
        # 重新解密当前最大编号的数据库（可能还在增长）
        db_name = f"message_{output_max_num}.db"
        source_db_path = Path(db_storage_path) / "message" / db_name
        if source_db_path.exists():
            databases_to_decrypt.append({
                'path': str(source_db_path),
                'name': db_name,
                'number': output_max_num,
                'reason': '更新'
            })

        # 解密新增的数据库
        if source_max_num > output_max_num:
            for num in range(output_max_num + 1, source_max_num + 1):
                db_name = f"message_{num}.db"
                source_db_path = Path(db_storage_path) / "message" / db_name
                if source_db_path.exists():
                    databases_to_decrypt.append({
                        'path': str(source_db_path),
                        'name': db_name,
                        'number': num,
                        'reason': '新增'
                    })
    else:
        # source_max_num < output_max_num，异常情况
        logger.warning(f"源目录最大编号({source_max_num}) < 输出目录最大编号({output_max_num})")
        return {
            "status": "error",
            "message": f"源目录编号异常: 源目录最大编号({source_max_num}) < 已解密编号({output_max_num})",
            "total_databases": 0,
            "successful_count": 0,
            "failed_count": 0,
            "output_directory": str(output_dir.absolute()),
            "processed_files": [],
            "failed_files": []
        }

    # 策略2：处理其他需要更新的数据库（contact, session, sns等）
    # 需要持续更新的数据库列表
    update_databases = [
        'contact.db', 'contact_fts.db',
        'session.db',
        'sns.db',
        'favorite.db', 'favorite_fts.db',
        'emoticon.db',
        'general.db',
        'bizchat.db',
        'biz_message_0.db', 'biz_message_1.db', 'biz_message_2.db', 'biz_message_3.db',
        'head_image.db',
        'media_0.db',
        'hardlink.db',
        'message_resource.db'
    ]

    # 查找源目录中的这些数据库
    storage_path = Path(db_storage_path)
    for db_name in update_databases:
        # 在db_storage及其子目录中搜索
        for root, _, files in os.walk(storage_path):
            if db_name in files:
                source_db_path = Path(root) / db_name
                databases_to_decrypt.append({
                    'path': str(source_db_path),
                    'name': db_name,
                    'number': -1,
                    'reason': '更新'
                })
                break

    logger.info(f"增量解密: {len(databases_to_decrypt)} 个数据库")

    if not databases_to_decrypt:
        return {
            "status": "success",
            "message": "数据库已是最新，无需增量解密",
            "total_databases": 0,
            "successful_count": 0,
            "failed_count": 0,
            "output_directory": str(output_dir.absolute()),
            "processed_files": [],
            "failed_files": []
        }

    # 创建解密器
    try:
        decryptor = WeChatDatabaseDecryptor(key)
    except ValueError as e:
        return {
            "status": "error",
            "message": f"密钥错误: {e}",
            "total_databases": len(databases_to_decrypt),
            "successful_count": 0,
            "failed_count": len(databases_to_decrypt),
            "output_directory": str(output_dir.absolute()),
            "processed_files": [],
            "failed_files": []
        }

    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)

    # 执行解密
    success_count = 0
    processed_files = []
    failed_files = []

    for db_info in databases_to_decrypt:
        db_path = db_info['path']
        db_name = db_info['name']
        reason = db_info['reason']
        output_path = output_dir / db_name

        if decryptor.decrypt_database(db_path, str(output_path)):
            success_count += 1
            processed_files.append(str(output_path))
            logger.info(f"✓ {db_name} [{reason}]")
        else:
            failed_files.append(db_path)
            logger.error(f"✗ {db_name} 解密失败")

    return {
        "status": "success" if success_count > 0 else "error",
        "message": f"增量解密完成: 成功 {success_count}/{len(databases_to_decrypt)}",
        "total_databases": len(databases_to_decrypt),
        "successful_count": success_count,
        "failed_count": len(databases_to_decrypt) - success_count,
        "output_directory": str(output_dir.absolute()),
        "processed_files": processed_files,
        "failed_files": failed_files
    }


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


# ==================== 数据库解密API ====================

@app.route('/api/decrypt', methods=['POST'])
def decrypt():
    """解密API端点"""
    try:
        data = request.get_json()

        mode = data.get('mode')  # 'full' 或 'incremental'
        key = data.get('key')
        db_path = data.get('db_path')
        account_name = data.get('account_name')

        # 验证参数
        if not mode or mode not in ['full', 'incremental']:
            return jsonify({
                "status": "error",
                "message": "无效的解密模式"
            }), 400

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

        # 执行解密
        if mode == 'full':
            # 首次解密：解密所有数据库
            result = decrypt_wechat_databases(
                db_storage_path=db_path,
                key=key
            )
        else:
            # 增量解密：只解密最新的message数据库
            result = incremental_decrypt(
                db_storage_path=db_path,
                key=key,
                account_name=account_name
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
    """获取配置"""
    return jsonify({
        'success': True,
        'config': config_manager.get_all()
    })


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
                'content': str(row['内容'])[:200]  # 限制内容长度
            })

        # 统计信息
        stats = {
            'total': len(results),
            'displayed': len(results_list),
            'chat_count': results['聊天对象'].nunique() if len(results) > 0 else 0,
            'sender_count': results['发言人'].nunique() if len(results) > 0 else 0
        }

        # 消息类型分布
        if len(results) > 0:
            type_dist = results['消息类型'].value_counts().head(5).to_dict()
            stats['type_distribution'] = {
                get_message_type_name(k): int(v) for k, v in type_dist.items()
            }
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


if __name__ == '__main__':
    # 初始化搜索器
    print("正在初始化搜索器...")
    if init_searcher():
        print("✓ 搜索器初始化成功")
    else:
        print("⚠ 搜索器初始化失败,请先运行 export_final.py 导出聊天记录")

    print("\n" + "=" * 60)
    print("微信数据库解密与聊天记录搜索 - 集成Web应用")
    print("=" * 60)
    print(f"\n访问地址: http://127.0.0.1:5000")
    print(f"输出目录: {OUTPUT_BASE_DIR.absolute()}")
    print("\n功能:")
    print("  1. 数据库解密 (首次/增量)")
    print("  2. 聊天记录搜索")
    print("  3. 配置管理")
    print("\n按 Ctrl+C 停止服务器\n")

    app.run(host='0.0.0.0', port=5000, debug=True)
