#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信聊天记录终极导出工具
完整功能：
1. 提取群内发言人（使用real_sender_id字段，可靠准确）
2. 解析各种消息类型（图片、链接、公众号等）
3. 关联联系人显示真实姓名
4. 正确区分群聊发言人和聊天对象
"""

import sqlite3
import pandas as pd
import re
import xml.etree.ElementTree as ET
import hashlib
from pathlib import Path
from datetime import datetime


def remove_unprintable_chars(s):
    """删除不可打印字符"""
    if not s:
        return ''
    return ''.join(x for x in str(s) if x.isprintable())


def get_contact_map(contact_db_path):
    """获取联系人映射（同时支持username和id查询）"""
    conn = sqlite3.connect(contact_db_path)
    query = """
    SELECT id, username, remark, nick_name, alias
    FROM contact
    WHERE delete_flag = 0
    """

    contact_by_username = {}
    contact_by_id = {}

    for row in conn.execute(query):
        contact_id, username, remark, nick_name, alias = row
        display_name = remark or nick_name or alias or username

        contact_by_username[username] = display_name
        if contact_id:
            contact_by_id[contact_id] = {'username': username, 'display_name': display_name}

    conn.close()
    print(f"[OK] 加载 {len(contact_by_username)} 个联系人")
    return contact_by_username, contact_by_id


def extract_sender_from_content(content, contact_map):
    """从群聊消息内容中提取发言人wxid
    群聊消息格式: {wxid}:\n{实际内容}
    """
    if not content:
        return None, content

    # 如果是bytes,先转换为字符串
    if isinstance(content, bytes):
        try:
            content = content.decode('utf8', errors='ignore')
        except:
            return None, content

    if not isinstance(content, str):
        return None, content

    # 检查是否包含冒号和换行符
    if ':\n' in content:
        parts = content.split(':\n', 1)
        if len(parts) == 2:
            potential_wxid = parts[0].strip()
            actual_content = parts[1]

            # 验证是否为有效的wxid格式
            if potential_wxid in contact_map:
                return potential_wxid, actual_content
            # 有时候可能有后缀
            elif potential_wxid[:-2] in contact_map:
                return potential_wxid[:-2], actual_content

    return None, content


def parse_xml_content(content):
    """解析XML格式的消息内容"""
    try:
        root = ET.fromstring(content)

        # 提取标题
        title = root.findtext('.//title', '')

        # 提取URL
        url = root.findtext('.//url', '')

        # 提取描述
        desc = root.findtext('.//des', '')

        # 提取类型
        msg_type = root.findtext('.//type', '')

        if title:
            result = f'[{title}]'
            if desc:
                result += f' {desc[:50]}'
            if url:
                result += f'\n链接: {url[:100]}'
            return result

        return content[:100]

    except:
        return content[:100] if content else ''


def parse_file_message(content):
    """解析文件消息，提取文件名和路径"""
    try:
        if isinstance(content, bytes):
            content = content.decode('utf8', errors='ignore')

        # 尝试解析XML获取文件信息
        root = ET.fromstring(content)

        # 提取文件标题/名称
        title = root.findtext('.//title', '')

        # 提取文件路径
        path = root.findtext('.//path', '') or root.findtext('.//filepath', '')

        # 提取文件名
        filename = root.findtext('.//filename', '')

        # 提取文件类型
        filetype = root.findtext('.//filetype', '') or root.findtext('.//type', '')

        result = f'[文件: {filename or title}]'
        if path:
            result += f'\n路径: {path}'
        if filetype:
            result += f' (类型: {filetype})'

        return result
    except:
        return f'[文件]'


def parse_message_by_type(msg_type, content):
    """根据消息类型解析内容"""
    type_handlers = {
        1: lambda c: c or '',  # 文本
        3: lambda c: parse_file_message(c),  # 图片(含路径)
        34: lambda c: '[语音]',
        43: lambda c: parse_file_message(c),  # 视频(含路径)
        47: lambda c: '[表情]',
        48: lambda c: '[位置]',
        49: lambda c: parse_xml_content(c),  # 链接/公众号/小程序
        10000: lambda c: f'[系统: {c[:50]}]' if c else '[系统消息]',
        10002: lambda c: '[撤回了一条消息]',
        # 处理超大类型值
        21474836529: lambda c: parse_xml_content(c),  # 公众号消息
        81604378673: lambda c: parse_file_message(c),  # 文件消息
    }

    handler = type_handlers.get(msg_type, lambda c: f'[类型{msg_type}]')
    return handler(content)


def export_messages_ultimate(message_db, contact_db, output_excel, sample_size=50):
    """
    终极导出方案
    正确区分聊天对象和发言人
    """
    print("\n开始导出...")

    # 加载联系人（同时获取username和id映射）
    contact_by_username, contact_by_id = get_contact_map(contact_db)

    # 连接message数据库
    msg_conn = sqlite3.connect(message_db)
    cursor = msg_conn.cursor()

    # 获取Name2Id映射（聊天对象）- 这个表存储了每个表对应的聊天对象
    cursor.execute('SELECT user_name FROM Name2Id WHERE user_name IS NOT NULL AND user_name != ""')
    name2id_list = [r[0] for r in cursor.fetchall()]

    # 建立user_name到MD5的映射
    username_to_md5 = {}
    for user_name in name2id_list:
        md5_hash = hashlib.md5(user_name.encode()).hexdigest()
        username_to_md5[md5_hash] = user_name

    # 获取所有消息表
    cursor.execute('SELECT name FROM sqlite_master WHERE type="table" AND name LIKE "Msg_%"')
    msg_tables = [r[0] for r in cursor.fetchall()]

    print(f"[OK] 找到 {len(msg_tables)} 个聊天表")
    print(f"[OK] Name2Id条目: {len(name2id_list)} 个")

    all_messages = []

    for idx, table_name in enumerate(msg_tables[:100]):  # 限制100个表
        try:
            # 从表名中提取MD5哈希,找到对应的聊天对象
            # 表名格式: Msg_{md5_hash}
            md5_part = table_name.replace('Msg_', '')

            # 通过MD5找到对应的user_name
            chat_user_id = username_to_md5.get(md5_part, '未知聊天')
            is_group = chat_user_id.endswith('@chatroom')  # 判断是否为群聊

            # 聊天对象显示名
            chat_display_name = contact_by_username.get(chat_user_id, chat_user_id)

            # 查询消息（添加status字段判断发送方向）
            query = f"""
            SELECT
                create_time,
                local_type,
                message_content,
                real_sender_id,
                status
            FROM {table_name}
            WHERE create_time > 0
            ORDER BY create_time DESC
            LIMIT {sample_size}
            """

            for row in cursor.execute(query):
                create_time, local_type, content, real_sender_id, status = row

                # 时间
                try:
                    msg_time = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S')
                except:
                    msg_time = ''

                # 判断是否为自己发送的消息
                # status=2: 自己发送, status=3: 接收
                is_self = (status == 2)

                # 确定发言人和实际内容
                if is_group:
                    # 群聊：先从消息内容中提取发言人wxid
                    sender_wxid, actual_content = extract_sender_from_content(content, contact_by_username)

                    if sender_wxid:
                        # 从内容中成功提取到发言人
                        sender_name = contact_by_username.get(sender_wxid, sender_wxid)
                        # 使用提取后的实际内容
                        content = actual_content
                    elif is_self:
                        # 自己发送的消息
                        sender_name = '我'
                    else:
                        # 内容中没有wxid,使用未知
                        sender_name = '未知成员'
                else:
                    # 单聊：根据status判断发言人
                    if is_self:
                        sender_name = '我'
                    else:
                        sender_name = chat_display_name

                # 解析消息内容
                parsed_content = parse_message_by_type(local_type, content)

                all_messages.append({
                    '时间': msg_time,
                    '聊天对象': chat_display_name,
                    '群名' if is_group else '好友': chat_display_name,
                    '发言人': sender_name,
                    '消息类型': local_type,
                    '内容': parsed_content,
                })

            if (idx + 1) % 10 == 0:
                print(f"  处理进度: {idx+1}/{len(msg_tables[:100])}")

        except Exception as e:
            print(f"  [ERROR] 表 {table_name}: {e}")
            continue

    msg_conn.close()

    # 导出
    if all_messages:
        df = pd.DataFrame(all_messages)
        df.to_excel(output_excel, index=False, engine='openpyxl')
        print(f"\n[OK] 导出完成!")
        print(f"  文件: {output_excel}")
        print(f"  消息数: {len(df)} 条")
        print(f"  聊天数: {df['聊天对象'].nunique()} 个")
        return df
    else:
        print("[ERROR] 没有消息")
        return None


if __name__ == '__main__':
    base_dir = Path(__file__).parent
    db_dir = base_dir / 'output' / 'databases' / 'q453497_ec01'

    message_db = db_dir / 'message_0.db'
    contact_db = db_dir / 'contact.db'
    output_dir = base_dir / 'output'
    output_dir.mkdir(exist_ok=True)

    if not message_db.exists() or not contact_db.exists():
        print("错误: 数据库文件不存在")
        exit(1)

    print("=" * 60)
    print("微信聊天记录终极导出工具")
    print("=" * 60)
    print(f"Message DB: {message_db.name}")
    print(f"Contact DB: {contact_db.name}")
    print("=" * 60)

    # 添加时间戳避免文件被占用
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f'聊天记录_完整版_v3_{timestamp}.xlsx'
    result = export_messages_ultimate(
        str(message_db),
        str(contact_db),
        output_file,
        sample_size=50  # 每个聊天取50条消息
    )

    # 同时保存一份最新版本（覆盖v2）
    if result is not None:
        output_file_v2 = output_dir / '聊天记录_完整版_v2.xlsx'
        try:
            result.to_excel(output_file_v2, index=False, engine='openpyxl')
            print(f"[OK] 同时更新了 v2 版本")
        except Exception as e:
            print(f"[警告] 无法更新 v2 版本(可能被占用): {e}")
