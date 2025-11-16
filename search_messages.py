#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信聊天记录搜索工具
支持按时间、群名、个人名、内容关键词搜索
直接从解密的数据库读取数据
"""

import pandas as pd
import sys
import sqlite3
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')


def get_contact_map(contact_db_path):
    """获取联系人映射"""
    conn = sqlite3.connect(contact_db_path)
    query = """
    SELECT username, remark, nick_name, alias
    FROM contact
    WHERE delete_flag = 0
    """

    contact_map = {}
    for row in conn.execute(query):
        username, remark, nick_name, alias = row
        display_name = remark or nick_name or alias or username
        contact_map[username] = display_name

    conn.close()
    return contact_map


def extract_sender_from_content(content, contact_map):
    """从群聊消息内容中提取发言人wxid"""
    if not content:
        return None, content

    if isinstance(content, bytes):
        try:
            content = content.decode('utf8', errors='ignore')
        except:
            return None, content

    if not isinstance(content, str):
        return None, content

    if ':\n' in content:
        parts = content.split(':\n', 1)
        if len(parts) == 2:
            potential_wxid = parts[0].strip()
            actual_content = parts[1]

            if potential_wxid in contact_map:
                return potential_wxid, actual_content
            elif potential_wxid[:-2] in contact_map:
                return potential_wxid[:-2], actual_content

    return None, content


def parse_xml_content(content):
    """解析XML格式的消息内容"""
    try:
        # 确保content是字符串
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='ignore')
        elif not isinstance(content, str):
            content = str(content)

        root = ET.fromstring(content)
        title = root.findtext('.//title', '')
        url = root.findtext('.//url', '')
        desc = root.findtext('.//des', '')

        if title:
            result = f'{title}'
            if desc:
                result += f' | {desc[:50]}'
            if url:
                result += f' | {url[:50]}'
            return result
        return '[链接/公众号]'
    except:
        return '[链接/公众号]'


def parse_message_by_type(msg_type, content):
    """根据消息类型解析内容"""
    # 确保content是安全的字符串
    if content is None:
        content = ''
    elif isinstance(content, bytes):
        try:
            content = content.decode('utf-8', errors='ignore')
        except:
            content = ''
    elif not isinstance(content, str):
        try:
            content = str(content)
        except:
            content = ''

    type_handlers = {
        1: lambda c: c or '',  # 文本
        3: lambda c: '[图片]',
        34: lambda c: '[语音]',
        43: lambda c: '[视频]',
        47: lambda c: '[表情]',
        48: lambda c: '[位置]',
        49: lambda c: parse_xml_content(c),
        10000: lambda c: f'[系统: {c[:50]}]' if c else '[系统消息]',
        10002: lambda c: '[撤回了一条消息]',
    }

    handler = type_handlers.get(msg_type, lambda c: f'[类型{msg_type}]')
    try:
        return handler(content)
    except Exception as e:
        return f'[类型{msg_type}]'


class MessageSearcher:
    def __init__(self, db_directory):
        """
        初始化搜索器 - 从解密的数据库目录加载所有消息

        参数:
            db_directory: 解密后的数据库目录路径 (包含message_*.db和contact.db)
        """
        db_path = Path(db_directory)

        # 查找所有message数据库
        message_dbs = sorted(db_path.glob('message_*.db'))
        contact_db = db_path / 'contact.db'

        if not message_dbs:
            raise FileNotFoundError(f"未找到message数据库: {db_path}")
        if not contact_db.exists():
            raise FileNotFoundError(f"未找到contact.db: {contact_db}")

        print(f"[OK] 找到 {len(message_dbs)} 个消息数据库")

        # 加载联系人映射
        self.contact_map = get_contact_map(str(contact_db))
        print(f"[OK] 加载 {len(self.contact_map)} 个联系人")

        # 从所有数据库加载消息
        self.df = self._load_all_messages(message_dbs)
        print(f"[OK] 加载了 {len(self.df)} 条聊天记录")

    def _load_all_messages(self, message_dbs):
        """从所有message数据库加载消息"""
        all_messages = []

        for db_idx, db_file in enumerate(message_dbs):
            print(f"  处理数据库 {db_idx+1}/{len(message_dbs)}: {db_file.name}")

            try:
                conn = sqlite3.connect(str(db_file))
                cursor = conn.cursor()

                # 获取Name2Id映射
                cursor.execute('SELECT user_name FROM Name2Id WHERE user_name IS NOT NULL')
                name2id_list = [r[0] for r in cursor.fetchall()]

                username_to_md5 = {}
                for user_name in name2id_list:
                    md5_hash = hashlib.md5(user_name.encode()).hexdigest()
                    username_to_md5[md5_hash] = user_name

                # 获取所有消息表
                cursor.execute('SELECT name FROM sqlite_master WHERE type="table" AND name LIKE "Msg_%"')
                msg_tables = [r[0] for r in cursor.fetchall()]

                # 处理每个聊天表
                for table_name in msg_tables:
                    try:
                        md5_part = table_name.replace('Msg_', '')
                        chat_user_id = username_to_md5.get(md5_part, '未知聊天')
                        is_group = chat_user_id.endswith('@chatroom')
                        chat_display_name = self.contact_map.get(chat_user_id, chat_user_id)

                        query = f"""
                        SELECT create_time, local_type, message_content, real_sender_id, status
                        FROM {table_name}
                        WHERE create_time > 0
                        ORDER BY create_time ASC
                        """

                        for row in cursor.execute(query):
                            try:
                                create_time, local_type, content, real_sender_id, status = row

                                # 处理时间
                                try:
                                    msg_time = datetime.fromtimestamp(create_time)
                                except:
                                    continue

                                # 安全地处理content - 可能是bytes或有编码问题
                                if content is not None:
                                    if isinstance(content, bytes):
                                        try:
                                            content = content.decode('utf-8', errors='ignore')
                                        except:
                                            content = str(content, errors='ignore')
                                    elif not isinstance(content, str):
                                        content = str(content)
                                else:
                                    content = ''

                                is_self = (status == 2)

                                # 确定发言人
                                if is_group:
                                    sender_wxid, actual_content = extract_sender_from_content(content, self.contact_map)
                                    if sender_wxid:
                                        sender_name = self.contact_map.get(sender_wxid, sender_wxid)
                                        content = actual_content
                                    elif is_self:
                                        sender_name = '我'
                                    else:
                                        sender_name = '未知成员'
                                else:
                                    sender_name = '我' if is_self else chat_display_name

                                # 解析消息内容
                                parsed_content = parse_message_by_type(local_type, content)

                            except Exception as e:
                                # 跳过有问题的单条记录
                                continue

                            all_messages.append({
                                '时间': msg_time,
                                '聊天对象': chat_display_name,
                                '发言人': sender_name,
                                '消息类型': local_type,
                                '内容': parsed_content,
                            })

                    except Exception as e:
                        continue

                conn.close()

            except Exception as e:
                print(f"  [ERROR] 处理数据库失败: {e}")
                continue

        return pd.DataFrame(all_messages) if all_messages else pd.DataFrame(columns=['时间', '聊天对象', '发言人', '消息类型', '内容'])

    def search(self,
               start_date=None,
               end_date=None,
               chat_name=None,
               sender_name=None,
               keyword=None,
               message_type=None,
               delete_keywords=None):
        """
        搜索聊天记录

        参数:
            start_date: 开始日期 (格式: 'YYYY-MM-DD')
            end_date: 结束日期 (格式: 'YYYY-MM-DD')
            chat_name: 聊天对象名称 (支持模糊匹配)
            sender_name: 发言人名称 (支持模糊匹配)
            keyword: 内容关键词
            message_type: 消息类型 (1=文本, 3=图片, 34=语音等)
            delete_keywords: 要过滤掉的关键词列表或逗号分隔的字符串

        返回:
            DataFrame: 搜索结果
        """
        result = self.df.copy()

        # 时间范围筛选
        if start_date:
            start = pd.to_datetime(start_date)
            result = result[result['时间'] >= start]
            print(f"[筛选] 开始时间: {start_date}")

        if end_date:
            end = pd.to_datetime(end_date) + pd.Timedelta(days=1)  # 包含当天
            result = result[result['时间'] < end]
            print(f"[筛选] 结束时间: {end_date}")

        # 聊天对象筛选
        if chat_name:
            result = result[result['聊天对象'].str.contains(chat_name, na=False, case=False)]
            print(f"[筛选] 聊天对象包含: {chat_name}")

        # 发言人筛选
        if sender_name:
            result = result[result['发言人'].str.contains(sender_name, na=False, case=False)]
            print(f"[筛选] 发言人包含: {sender_name}")

        # 内容关键词筛选
        if keyword:
            # 安全地转换为字符串,处理可能的bytes对象
            content_series = result['内容'].apply(lambda x: str(x) if not isinstance(x, bytes) else x.decode('utf-8', errors='ignore') if x else '')
            result = result[content_series.str.contains(keyword, na=False, case=False)]
            print(f"[筛选] 内容包含: {keyword}")

        # 消息类型筛选
        if message_type is not None:
            result = result[result['消息类型'] == message_type]
            print(f"[筛选] 消息类型: {message_type}")

        # 删除关键词过滤
        if delete_keywords:
            # 如果是字符串,按逗号分隔
            if isinstance(delete_keywords, str):
                keywords_list = [kw.strip() for kw in delete_keywords.split(',') if kw.strip()]
            else:
                keywords_list = delete_keywords

            # 过滤掉包含任何删除关键词的记录
            if keywords_list:
                original_count = len(result)
                for kw in keywords_list:
                    # 安全地转换为字符串,处理可能的bytes对象
                    content_series = result['内容'].apply(lambda x: str(x) if not isinstance(x, bytes) else x.decode('utf-8', errors='ignore') if x else '')
                    result = result[~content_series.str.contains(kw, na=False, case=False)]
                filtered_count = original_count - len(result)
                if filtered_count > 0:
                    print(f"[过滤] 删除了包含关键词 {keywords_list} 的 {filtered_count} 条记录")

        print(f"\n[结果] 找到 {len(result)} 条符合条件的记录\n")
        return result

    def display_results(self, df, max_rows=50):
        """显示搜索结果"""
        if len(df) == 0:
            print("没有找到符合条件的记录")
            return

        print("=" * 100)
        print(f"搜索结果 (共{len(df)}条,显示前{min(max_rows, len(df))}条)")
        print("=" * 100)

        for idx, row in df.head(max_rows).iterrows():
            print(f"\n【记录 {idx+1}】")
            print(f"  时间: {row['时间'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  聊天对象: {row['聊天对象']}")
            print(f"  发言人: {row['发言人']}")

            # 消息类型说明
            type_name = {
                1: '文本',
                3: '图片',
                34: '语音',
                43: '视频',
                47: '表情',
                49: '链接/公众号',
                10000: '系统消息',
                10002: '撤回消息'
            }.get(row['消息类型'], f"类型{row['消息类型']}")
            print(f"  类型: {type_name}")

            # 内容
            content = str(row['内容'])[:200]
            print(f"  内容: {content}")
            print("-" * 100)

    def export_results(self, df, output_file):
        """导出搜索结果到Excel"""
        if len(df) == 0:
            print("没有记录可导出")
            return

        df.to_excel(output_file, index=False, engine='openpyxl')
        print(f"\n[OK] 已导出 {len(df)} 条记录到: {output_file}")

    def statistics(self, df):
        """统计搜索结果"""
        if len(df) == 0:
            return

        print("\n" + "=" * 80)
        print("统计信息")
        print("=" * 80)

        print(f"\n总消息数: {len(df)}")
        print(f"聊天对象数: {df['聊天对象'].nunique()}")
        print(f"发言人数: {df['发言人'].nunique()}")

        # 消息类型分布
        print(f"\n消息类型分布:")
        type_map = {
            1: '文本',
            3: '图片',
            34: '语音',
            43: '视频',
            47: '表情',
            49: '链接/公众号',
            10000: '系统消息'
        }
        type_counts = df['消息类型'].value_counts().head(10)
        for msg_type, count in type_counts.items():
            type_name = type_map.get(msg_type, f'类型{msg_type}')
            print(f"  {type_name}: {count}条")

        # Top发言人
        print(f"\nTop 10 发言人:")
        top_senders = df['发言人'].value_counts().head(10)
        for sender, count in top_senders.items():
            print(f"  {sender}: {count}条")


def main():
    """交互式搜索界面"""
    base_dir = Path(__file__).parent
    excel_file = base_dir / 'output' / '聊天记录_完整版_v2.xlsx'

    if not excel_file.exists():
        print(f"错误: 找不到聊天记录文件 {excel_file}")
        return

    searcher = MessageSearcher(excel_file)

    print("\n" + "=" * 80)
    print("微信聊天记录搜索工具")
    print("=" * 80)
    print("\n使用说明:")
    print("  - 直接回车跳过该筛选条件")
    print("  - 时间格式: YYYY-MM-DD (如: 2025-11-15)")
    print("  - 名称支持模糊匹配 (如: 输入'张'可匹配所有包含'张'的名字)")
    print("\n" + "=" * 80)

    # 获取搜索条件
    start_date = input("\n开始日期 (YYYY-MM-DD): ").strip() or None
    end_date = input("结束日期 (YYYY-MM-DD): ").strip() or None
    chat_name = input("聊天对象 (群名/好友名): ").strip() or None
    sender_name = input("发言人名称: ").strip() or None
    keyword = input("内容关键词: ").strip() or None

    print("\n消息类型: 1=文本, 3=图片, 34=语音, 43=视频, 47=表情, 49=链接")
    msg_type_input = input("消息类型 (直接回车=全部): ").strip()
    message_type = int(msg_type_input) if msg_type_input else None

    # 执行搜索
    print("\n" + "=" * 80)
    print("开始搜索...")
    print("=" * 80)

    results = searcher.search(
        start_date=start_date,
        end_date=end_date,
        chat_name=chat_name,
        sender_name=sender_name,
        keyword=keyword,
        message_type=message_type
    )

    # 显示结果
    if len(results) > 0:
        searcher.display_results(results, max_rows=20)
        searcher.statistics(results)

        # 询问是否导出
        export = input("\n是否导出结果到Excel? (y/n): ").strip().lower()
        if export == 'y':
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = base_dir / 'output' / f'搜索结果_{timestamp}.xlsx'
            searcher.export_results(results, output_file)
    else:
        print("没有找到符合条件的记录")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户取消搜索")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
