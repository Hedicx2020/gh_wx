#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信聊天记录搜索工具 - 优化版
按需加载,只处理符合时间范围的消息,大幅提升搜索速度
"""

import pandas as pd
import sys
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
import zstandard as zstd

# 添加utils路径以导入message_parser
utils_path = Path(__file__).parent.parent / "utils"
sys.path.insert(0, str(utils_path))

from message_parser import parse_message_by_type

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


def extract_path_from_parsed_content(parsed_content):
    """
    从解析后的内容中提取路径或URL

    参数:
        parsed_content: 解析后的消息内容字符串

    返回:
        提取的路径或URL，如果没有则返回空字符串
    """
    if not isinstance(parsed_content, str):
        return ''

    # 提取文件路径（格式：路径:xxx）
    if '路径:' in parsed_content:
        parts = parsed_content.split('路径:')
        if len(parts) > 1:
            # 提取路径部分（可能在 | 之前）
            path_part = parts[1].split('|')[0].strip()
            return path_part

    # 提取URL链接（格式：链接: xxx）
    if '链接:' in parsed_content or '链接：' in parsed_content:
        # 统一处理中英文冒号
        content_normalized = parsed_content.replace('链接：', '链接:')
        parts = content_normalized.split('链接:')
        if len(parts) > 1:
            # 提取URL部分（可能在 | 之前）
            url_part = parts[1].split('|')[0].strip()
            return url_part

    return ''


def extract_sender_from_content(content, contact_map):
    """从群聊消息内容中提取发言人wxid"""
    if not content:
        return None, content

    # 处理压缩的content
    if isinstance(content, bytes):
        # 检查是否是zstd压缩 (magic bytes: 0x28 0xB5 0x2F 0xFD)
        if len(content) >= 4 and content[:4] == b'\x28\xb5\x2f\xfd':
            try:
                dctx = zstd.ZstdDecompressor()
                decompressed = dctx.decompress(content)
                content = decompressed.decode('utf-8', errors='ignore')
            except:
                # 解压失败，尝试直接decode
                try:
                    content = content.decode('utf8', errors='ignore')
                except:
                    return None, content
        else:
            # 不是压缩数据，直接decode
            try:
                content = content.decode('utf8', errors='ignore')
            except:
                return None, content

    if not isinstance(content, str):
        return None, content

    # 提取wxid前缀 (格式: wxid_xxx:\n实际内容)
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


class MessageSearcher:
    def __init__(self, db_directory):
        """
        初始化搜索器 - 按需加载(优化版)

        参数:
            db_directory: 解密后的数据库目录路径
        """
        db_path = Path(db_directory)

        # 只保存数据库路径,不预加载数据
        self.message_dbs = sorted(db_path.glob('message_*.db'))
        self.contact_db = db_path / 'contact.db'

        if not self.message_dbs:
            raise FileNotFoundError(f"未找到message数据库: {db_path}")
        if not self.contact_db.exists():
            raise FileNotFoundError(f"未找到contact.db: {self.contact_db}")

        print(f"[OK] 找到 {len(self.message_dbs)} 个消息数据库")

        # 加载联系人映射
        self.contact_map = get_contact_map(str(self.contact_db))
        print(f"[OK] 加载 {len(self.contact_map)} 个联系人")

        # 从数据库路径中提取用户wxid (例如: output/databases/q453497_ec01 -> q453497)
        self.user_wxid = self._extract_user_wxid_from_path(db_path)

        # 获取用户所有的ID（包括wxid和QQ号等）
        self.user_ids = self._get_user_ids()
        if self.user_ids:
            print(f"[OK] 检测到用户ID: {', '.join(self.user_ids)}")
        else:
            print(f"[WARNING] 无法自动检测用户ID,可能影响发言人判断")

        print(f"[优化] 搜索器将按需加载数据,只处理符合条件的消息")

    def _extract_user_wxid_from_path(self, db_path):
        """从数据库路径中提取用户wxid

        例如: output/databases/q453497_ec01 -> q453497
        或: output/databases/wxid_xxx_yyy -> wxid_xxx
        """
        import re

        # 获取最后一级目录名 (例如: q453497_ec01)
        dir_name = db_path.name

        # 移除后缀 (_ec01, _随机字符串等)
        # 匹配模式: wxid_开头 或 纯数字QQ号
        if dir_name.startswith('wxid_'):
            # wxid_xxx_yyy -> wxid_xxx
            match = re.match(r'(wxid_[^_]+)', dir_name)
            if match:
                return match.group(1)
        else:
            # q453497_ec01 -> q453497 (移除下划线后的部分)
            match = re.match(r'([^_]+)', dir_name)
            if match:
                return match.group(1)

        # 如果匹配失败，返回整个目录名
        return dir_name

    def _get_user_ids(self):
        """获取用户所有的ID（直接使用从路径提取的wxid）"""
        # 用户的主ID就是从路径中提取的wxid
        user_ids = {self.user_wxid} if self.user_wxid else set()

        if user_ids:
            print(f"[DEBUG] 用户wxid (从路径提取): {self.user_wxid}")

        return user_ids

    def search(self,
               start_date=None,
               end_date=None,
               chat_name=None,
               sender_name=None,
               keyword=None,
               message_type=None,
               delete_keywords=None,
               exclude_self=False):
        """
        优化搜索 - 在数据库层面过滤时间,只加载符合条件的数据

        参数:
            start_date: 开始日期 (格式: 'YYYY-MM-DD')
            end_date: 结束日期 (格式: 'YYYY-MM-DD')
            chat_name: 聊天对象名称 (支持单个字符串或列表，逗号分隔)
            sender_name: 发言人名称 (支持单个字符串或列表，逗号分隔)
            keyword: 内容关键词 (支持单个字符串或列表，逗号分隔，OR逻辑)
            message_type: 消息类型
            delete_keywords: 要过滤掉的关键词 (支持单个字符串或列表，逗号分隔，OR逻辑)
            exclude_self: 是否排除自己的消息

        返回:
            DataFrame: 搜索结果
        """
        # 转换chat_name为列表格式
        if chat_name:
            if isinstance(chat_name, str):
                # 支持逗号分隔的字符串（同时支持全角，和半角,）
                # 先统一替换全角逗号为半角逗号
                chat_name_normalized = chat_name.replace('，', ',')
                chat_names = [name.strip() for name in chat_name_normalized.split(',') if name.strip()]
            elif isinstance(chat_name, list):
                chat_names = [name.strip() for name in chat_name if name.strip()]
            else:
                chat_names = []
        else:
            chat_names = []

        # 转换sender_name为列表格式
        if sender_name:
            if isinstance(sender_name, str):
                # 支持逗号分隔的字符串（同时支持全角，和半角,）
                # 先统一替换全角逗号为半角逗号
                sender_name_normalized = sender_name.replace('，', ',')
                sender_names = [name.strip() for name in sender_name_normalized.split(',') if name.strip()]
            elif isinstance(sender_name, list):
                sender_names = [name.strip() for name in sender_name if name.strip()]
            else:
                sender_names = []
        else:
            sender_names = []

        # 转换keyword为列表格式（支持多个关键词，任意一个匹配即可）
        if keyword:
            if isinstance(keyword, str):
                # 支持逗号分隔的字符串（同时支持全角，和半角,）
                keyword_normalized = keyword.replace('，', ',')
                keywords = [kw.strip() for kw in keyword_normalized.split(',') if kw.strip()]
            elif isinstance(keyword, list):
                keywords = [kw.strip() for kw in keyword if kw.strip()]
            else:
                keywords = []
        else:
            keywords = []

        # 转换delete_keywords为列表格式（任意一个匹配就过滤掉）
        if delete_keywords:
            if isinstance(delete_keywords, str):
                # 支持逗号分隔的字符串（同时支持全角，和半角,）
                delete_kw_normalized = delete_keywords.replace('，', ',')
                delete_kw_list = [kw.strip() for kw in delete_kw_normalized.split(',') if kw.strip()]
            elif isinstance(delete_keywords, list):
                delete_kw_list = [kw.strip() for kw in delete_keywords if kw.strip()]
            else:
                delete_kw_list = []
        else:
            delete_kw_list = []

        if chat_names:
            print(f"[筛选] 聊天对象: {', '.join(chat_names)}")
        if sender_names:
            print(f"[筛选] 发言人: {', '.join(sender_names)}")
        if keywords:
            print(f"[筛选] 搜索关键词: {', '.join(keywords)}")
        if delete_kw_list:
            print(f"[筛选] 过滤关键词: {', '.join(delete_kw_list)}")
        # 计算时间戳范围(在SQL层面过滤)
        start_timestamp = None
        end_timestamp = None

        if start_date:
            start_timestamp = int(pd.to_datetime(start_date).timestamp())
            print(f"[筛选] 开始时间: {start_date} (时间戳>={start_timestamp})")

        if end_date:
            end_timestamp = int((pd.to_datetime(end_date) + pd.Timedelta(days=1)).timestamp())
            print(f"[筛选] 结束时间: {end_date} (时间戳<{end_timestamp})")

        all_messages = []
        processed_count = 0
        skipped_count = 0

        # 按需从每个数据库加载符合条件的数据
        for db_idx, db_file in enumerate(self.message_dbs):
            try:
                conn = sqlite3.connect(str(db_file))
                cursor = conn.cursor()

                # 检查是否存在Name2Id表
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Name2Id'")
                has_name2id = cursor.fetchone() is not None

                if not has_name2id:
                    # 跳过没有Name2Id表的数据库（如message_resource.db）
                    conn.close()
                    continue

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

                        # 构建WHERE子句 - 在数据库层面过滤时间
                        where_clauses = ["create_time > 0"]

                        if start_timestamp:
                            where_clauses.append(f"create_time >= {start_timestamp}")

                        if end_timestamp:
                            where_clauses.append(f"create_time < {end_timestamp}")

                        if message_type is not None:
                            where_clauses.append(f"local_type = {message_type}")

                        where_clause = " AND ".join(where_clauses)

                        # 使用JOIN获取sender_username - 这是WeChat 4.0正确的发言人判断方法
                        # 添加compress_content字段用于解析系统消息等压缩内容
                        query = f"""
                        SELECT msg.create_time, msg.local_type, msg.message_content,
                               msg.real_sender_id, msg.status, Name2Id.user_name as sender_username,
                               msg.compress_content
                        FROM {table_name} as msg
                        LEFT JOIN Name2Id ON msg.real_sender_id = Name2Id.rowid
                        WHERE {where_clause}
                        ORDER BY msg.create_time ASC
                        """

                        for row in cursor.execute(query):
                            try:
                                create_time, local_type, content, real_sender_id, status, sender_username, compress_content = row
                                processed_count += 1

                                # 处理时间
                                try:
                                    msg_time = datetime.fromtimestamp(create_time)
                                except:
                                    continue

                                # 保留content原始类型(bytes或str),供后续解析器判断是否压缩
                                original_content = content

                                # 使用sender_username判断是否是自己发的消息(WeChat 4.0正确方法)
                                # 检查sender_username是否在用户的所有ID中（包括wxid、QQ号等）
                                is_self = (sender_username in self.user_ids) if (sender_username and self.user_ids) else False

                                # 确定发言人
                                # 核心逻辑:
                                # - 使用sender_username(通过real_sender_id JOIN Name2Id获取)来判断发言人
                                # - 群聊: 优先从content提取wxid,否则用sender_username判断
                                # - 私聊: 用sender_username判断是否是自己
                                # 用于解析器的内容(如果群聊中提取了发言人,则去掉wxid前缀)
                                content_for_parser = original_content
                                # 用于关键词过滤的内容(字符串格式)
                                content_for_extraction = ''

                                if is_group:
                                    # 群聊消息 - 先尝试从原始content中提取发言人wxid
                                    # extract_sender_from_content会自动处理压缩的content
                                    sender_wxid, actual_content = extract_sender_from_content(original_content, self.contact_map)
                                    if sender_wxid:
                                        # 从群聊content中成功提取了发言人wxid
                                        sender_name_val = self.contact_map.get(sender_wxid, sender_wxid)
                                        # 重要: 更新用于解析器的内容,去掉wxid前缀
                                        content_for_parser = actual_content
                                        # 用于关键词过滤
                                        content_for_extraction = actual_content if isinstance(actual_content, str) else str(actual_content)
                                    elif is_self:
                                        # 没提取到发言人wxid,但sender_username显示是自己发的
                                        sender_name_val = '我'
                                    elif sender_username:
                                        # 没提取到发言人wxid,使用sender_username作为发言人
                                        sender_name_val = self.contact_map.get(sender_username, sender_username)
                                    else:
                                        # 完全无法确定发言人
                                        sender_name_val = '未知成员'
                                else:
                                    # 私聊消息
                                    if is_self:
                                        # sender_username显示是自己发的消息
                                        sender_name_val = '我'
                                    else:
                                        # sender_username显示是对方发的消息
                                        sender_name_val = chat_display_name

                                # 如果content_for_extraction还是空的，需要转换用于关键词过滤
                                if not content_for_extraction and original_content:
                                    if isinstance(original_content, bytes):
                                        try:
                                            content_for_extraction = original_content.decode('utf-8', errors='ignore')
                                        except:
                                            content_for_extraction = ''
                                    elif isinstance(original_content, str):
                                        content_for_extraction = original_content
                                    else:
                                        content_for_extraction = str(original_content)

                                # 第一阶段：聊天对象过滤(先过滤聊天对象)
                                if chat_names:
                                    # 检查chat_display_name是否匹配任一聊天对象
                                    chat_match = False
                                    for cname in chat_names:
                                        if cname.lower() in chat_display_name.lower():
                                            chat_match = True
                                            break
                                    if not chat_match:
                                        skipped_count += 1
                                        continue

                                # 第二阶段：发言人过滤（在聊天对象筛选后进行）
                                # 排除自己的消息(在确定发言人后判断)
                                if exclude_self and sender_name_val == '我':
                                    skipped_count += 1
                                    continue

                                # 发言人过滤
                                if sender_names:
                                    # 检查sender_name_val是否匹配任一发言人
                                    sender_match = False
                                    for sname in sender_names:
                                        if sname.lower() in sender_name_val.lower():
                                            sender_match = True
                                            break
                                    if not sender_match:
                                        skipped_count += 1
                                        continue

                                # 关键词过滤 - 支持多个关键词，任意一个匹配即可（OR逻辑）
                                if keywords:
                                    # 检查content_for_extraction是否匹配任一关键词
                                    keyword_match = False
                                    for kw in keywords:
                                        if kw.lower() in content_for_extraction.lower():
                                            keyword_match = True
                                            break
                                    if not keyword_match:
                                        skipped_count += 1
                                        continue

                                # 删除关键词过滤 - 支持多个过滤词，任意一个匹配就过滤掉（OR逻辑）
                                if delete_kw_list:
                                    should_skip = False
                                    for kw in delete_kw_list:
                                        if kw.lower() in content_for_extraction.lower():
                                            should_skip = True
                                            break
                                    if should_skip:
                                        skipped_count += 1
                                        continue

                                # 解析消息内容 - 使用增强的解析器,传入content_for_parser(群聊中已去掉wxid前缀)、compress_content和create_time
                                # 这样解析器可以检测zstd压缩并正确处理，同时能构建正确的文件路径
                                parsed_content = parse_message_by_type(local_type, content_for_parser, compress_content, create_time)

                                # 提取路径或URL
                                path_or_url = extract_path_from_parsed_content(parsed_content)

                                all_messages.append({
                                    '时间': msg_time,
                                    '聊天对象': chat_display_name,
                                    '发言人': sender_name_val,
                                    '消息类型': local_type,
                                    '内容': parsed_content,
                                    '路径': path_or_url,
                                })

                            except Exception as e:
                                continue

                    except Exception as e:
                        continue

                conn.close()

            except Exception as e:
                print(f"  [ERROR] 处理数据库 {db_file.name} 失败: {e}")
                continue

        print(f"\n[优化] 处理了 {processed_count} 条记录,跳过 {skipped_count} 条")
        print(f"[结果] 找到 {len(all_messages)} 条符合条件的记录\n")

        return pd.DataFrame(all_messages) if all_messages else pd.DataFrame(columns=['时间', '聊天对象', '发言人', '消息类型', '内容'])

    def export_results(self, df, output_file):
        """导出搜索结果到Excel"""
        if len(df) == 0:
            print("没有记录可导出")
            return

        # 清理Excel不支持的非法字符
        def clean_text(text):
            if not isinstance(text, str):
                return text
            # 移除Excel不支持的控制字符(保留换行符和制表符)
            import re
            # 移除0x00-0x08, 0x0B-0x0C, 0x0E-0x1F的控制字符
            cleaned = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F]', '', text)
            return cleaned

        # 清理DataFrame中的所有文本列
        df_clean = df.copy()
        for col in df_clean.columns:
            if df_clean[col].dtype == 'object':
                df_clean[col] = df_clean[col].apply(clean_text)

        df_clean.to_excel(output_file, index=False, engine='openpyxl')
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
