#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信消息解析器 - 增强版
处理各种消息类型的内容解析
"""
import xml.etree.ElementTree as ET
import zstandard as zstd
import re


def decompress_content(content):
    """
    解压compress_content字段
    用于系统消息等压缩内容
    """
    try:
        if isinstance(content, bytes):
            dctx = zstd.ZstdDecompressor()
            decompressed = dctx.decompress(content).strip(b'\x00').strip()
            return decompressed.decode('utf-8', errors='ignore').strip()
        return str(content)
    except Exception as e:
        return str(content)


def parse_xml_content(content):
    """
    解析XML格式的消息内容
    用于类型49(链接/公众号/文件)等
    """
    try:
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='ignore')
        elif not isinstance(content, str):
            content = str(content)

        # 尝试解析XML
        root = ET.fromstring(content)

        # 提取appmsg节点
        appmsg = root.find('.//appmsg')
        if appmsg is None:
            return '[链接/公众号]'

        # 获取消息类型
        msg_type_node = appmsg.find('type')
        msg_type = int(msg_type_node.text) if msg_type_node is not None else 0

        # 基本信息
        title = root.findtext('.//title', '')
        desc = root.findtext('.//des', '')
        url = root.findtext('.//url', '')
        sourcedisplayname = root.findtext('.//sourcedisplayname', '')
        appname = root.findtext('.//appname', '')

        # 特殊处理: 类型6的文件消息,提取详细信息
        if msg_type == 6:
            appattach = root.find('.//appattach')
            if appattach is not None:
                totallen = appattach.findtext('totallen', '')
                fileext = appattach.findtext('fileext', '')
                md5 = root.findtext('.//md5', '')

                parts = []
                if title:
                    parts.append(f'📎 {title}')
                if totallen:
                    size_str = format_file_size(totallen)
                    parts.append(f'大小:{size_str}')
                if fileext:
                    parts.append(f'类型:{fileext.upper()}')
                if md5:
                    parts.append(f'MD5:{md5[:8]}...')
                    # 添加文件路径
                    file_path = build_file_path(md5, 'File', fileext)
                    if file_path:
                        parts.append(f'路径:{file_path}')

                if parts:
                    return ' | '.join(parts)

        # 根据type判断具体类型
        type_handlers = {
            1: lambda: format_link(title, desc, url, sourcedisplayname),  # 普通链接
            3: lambda: format_music(title, desc),  # 音乐
            4: lambda: format_video(title, desc),  # 视频
            5: lambda: format_link(title, desc, url, sourcedisplayname),  # 链接
            6: lambda: format_file(title),  # 文件
            8: lambda: format_emoji(title),  # 动画表情
            19: lambda: format_share(title, desc),  # 合并转发的聊天记录
            33: lambda: format_applet(title, sourcedisplayname or appname),  # 小程序
            36: lambda: format_file(title),  # 文件
            49: lambda: format_article(title, url, sourcedisplayname),  # 公众号文章 - 显示链接
            51: lambda: format_share(title, desc),  # 视频号
            57: lambda: format_message(title, desc),  # 引用消息
            2000: lambda: format_transfer(title),  # 转账
            2001: lambda: format_red_packet(title),  # 红包
        }

        handler = type_handlers.get(msg_type, lambda: format_default(title, desc, url, msg_type))
        return handler()

    except Exception as e:
        return '[链接/公众号]'


def format_link(title, desc, url, source):
    """格式化链接消息"""
    parts = []
    if title:
        parts.append(f'🔗 {title}')
    if url:
        parts.append(f'链接: {url}')
    if desc and desc != title:
        parts.append(f'{desc[:50]}')
    if source:
        parts.append(f'来源:{source}')
    return ' | '.join(parts) if parts else '[链接]'


def format_music(title, artist):
    """格式化音乐分享"""
    if title and artist:
        return f'🎵 {title} - {artist[:30]}'
    elif title:
        return f'🎵 {title}'
    return '[音乐]'


def format_video(title, desc):
    """格式化视频分享"""
    if title:
        return f'📹 {title[:50]}'
    return '[视频分享]'


def format_file(filename):
    """格式化文件消息"""
    if filename:
        return f'📎 文件:{filename}'
    return '[文件]'


def format_emoji(title):
    """格式化动画表情"""
    if title:
        return f'[动画表情:{title}]'
    return '[动画表情]'


def format_share(title, desc):
    """格式化分享消息"""
    if title:
        return f'📤 {title[:50]}'
    return '[分享]'


def format_applet(title, appname):
    """格式化小程序"""
    if title and appname:
        return f'小程序:{title} ({appname})'
    elif title:
        return f'小程序:{title}'
    return '[小程序]'


def format_article(title, url, source):
    """格式化公众号文章 - 显示标题、链接和来源"""
    parts = []

    if title:
        parts.append(f'📰 {title}')

    if url:
        parts.append(f'链接: {url}')

    if source:
        parts.append(f'来源: {source}')

    if parts:
        return ' | '.join(parts)

    return '[公众号文章]'


def format_message(title, desc):
    """格式化引用消息"""
    if title:
        return f'↩️ 引用:{title[:40]}'
    return '[引用消息]'


def format_transfer(title):
    """格式化转账"""
    return f'💰 {title}' if title else '[转账]'


def format_red_packet(title):
    """格式化红包"""
    return f'🧧 {title}' if title else '[红包]'


def format_default(title, desc, url, msg_type):
    """默认格式化 - 包含URL"""
    parts = []

    if title:
        parts.append(title[:80])

    if url:
        parts.append(f'链接: {url}')

    if desc and desc != title:
        parts.append(desc[:50])

    if parts:
        return f'[类型{msg_type}] ' + ' | '.join(parts)

    return f'[类型{msg_type}]'


def parse_system_message(content):
    """
    解析系统消息
    类型10000
    """
    if not content:
        return '[系统消息]'

    try:
        if isinstance(content, bytes):
            content_str = content.decode('utf-8', errors='ignore')
        else:
            content_str = str(content)

        # 常见系统消息模式
        patterns = {
            r'"(.+?)" 撤回了一条消息': lambda m: f'🔙 {m.group(1)} 撤回了一条消息',
            r'"(.+?)"邀请"(.+?)"加入了群聊': lambda m: f'👥 {m.group(1)} 邀请 {m.group(2)} 加入群聊',
            r'"(.+?)"通过扫描"(.+?)"分享的二维码加入群聊': lambda m: f'👥 {m.group(1)} 通过二维码加入群聊',
            r'"(.+?)"修改群名为"(.+?)"': lambda m: f'✏️ {m.group(1)} 修改群名为 {m.group(2)}',
            r'你邀请"(.+?)"加入了群聊': lambda m: f'👥 你邀请 {m.group(1)} 加入群聊',
            r'你将"(.+?)"移出了群聊': lambda m: f'👋 你将 {m.group(1)} 移出群聊',
        }

        for pattern, formatter in patterns.items():
            match = re.search(pattern, content_str)
            if match:
                return formatter(match)

        # 如果没有匹配到模式,返回前50个字符
        clean_content = content_str[:50].strip()
        if clean_content:
            return f'[系统: {clean_content}]'

        return '[系统消息]'

    except Exception as e:
        return '[系统消息]'


def is_zstd_compressed(data):
    """
    检测数据是否为zstd压缩
    zstd魔术字节: 0x28 0xB5 0x2F 0xFD
    """
    if isinstance(data, bytes) and len(data) >= 4:
        return data[:4] == b'\x28\xb5\x2f\xfd'
    return False


def format_file_size(size_bytes):
    """格式化文件大小"""
    try:
        size = int(size_bytes)
        if size < 1024:
            return f'{size}B'
        elif size < 1024 * 1024:
            return f'{size / 1024:.1f}KB'
        else:
            return f'{size / (1024 * 1024):.2f}MB'
    except:
        return str(size_bytes)


def build_file_path(md5, file_type='File', ext=''):
    """
    根据MD5构建可能的文件路径
    微信文件存储规则: FileStorage/{类型}/{子目录}/{MD5}{扩展名}

    参数:
        md5: 文件MD5值
        file_type: 文件类型 (Image/File/Video等)
        ext: 文件扩展名 (可选)
    """
    if not md5:
        return None

    # 使用MD5的前2位作为子目录(微信的常见做法)
    subdir = md5[:2]

    # 添加扩展名
    if ext and not ext.startswith('.'):
        ext = '.' + ext

    # 构建相对路径(相对于微信数据目录)
    # 格式: FileStorage/{类型}/{子目录}/{MD5}{扩展名}
    file_path = f'FileStorage/{file_type}/{subdir}/{md5}{ext}'

    return file_path


def parse_image_content(content):
    """
    解析图片消息的压缩XML内容
    提取MD5、文件大小和存储路径等信息
    """
    try:
        if isinstance(content, bytes) and is_zstd_compressed(content):
            # 解压缩
            dctx = zstd.ZstdDecompressor()
            decompressed = dctx.decompress(content)
            xml_str = decompressed.strip(b'\x00').decode('utf-8', errors='ignore').strip()

            # 解析XML
            root = ET.fromstring(xml_str)
            img = root.find('.//img')

            if img is not None:
                md5 = img.get('md5', '')
                length = img.get('length', '')

                parts = []

                if md5:
                    parts.append(f'[图片] MD5:{md5[:8]}...')

                if length:
                    size_str = format_file_size(length)
                    parts.append(f'大小:{size_str}')

                if md5:
                    # 添加推测的存储路径
                    file_path = build_file_path(md5, 'Image')
                    if file_path:
                        parts.append(f'路径:{file_path}')

                if parts:
                    return ' | '.join(parts)

        return '[图片]'
    except:
        return '[图片]'


def parse_file_content(content):
    """
    解析文件消息的压缩XML内容
    提取文件名、大小、MD5等信息
    适用于类型6(文件)等
    """
    try:
        if isinstance(content, bytes) and is_zstd_compressed(content):
            # 解压缩
            dctx = zstd.ZstdDecompressor()
            decompressed = dctx.decompress(content)
            xml_str = decompressed.strip(b'\x00').decode('utf-8', errors='ignore').strip()

            # 解析XML
            root = ET.fromstring(xml_str)

            # 提取文件信息
            title = root.findtext('.//title', '')
            file_type_node = root.find('.//type')
            file_type = int(file_type_node.text) if file_type_node is not None and file_type_node.text else 0

            # 如果是类型6(文件),从appattach获取详细信息
            if file_type == 6:
                appattach = root.find('.//appattach')
                if appattach is not None:
                    totallen = appattach.findtext('totallen', '')
                    fileext = appattach.findtext('fileext', '')
                    md5 = root.findtext('.//md5', '')

                    parts = []

                    # 文件名
                    if title:
                        parts.append(f'📎 {title}')

                    # 文件大小
                    if totallen:
                        size_str = format_file_size(totallen)
                        parts.append(f'大小:{size_str}')

                    # 文件类型
                    if fileext:
                        parts.append(f'类型:{fileext.upper()}')

                    # MD5
                    if md5:
                        parts.append(f'MD5:{md5[:8]}...')

                    # 文件路径
                    if md5:
                        file_path = build_file_path(md5, 'File', fileext)
                        if file_path:
                            parts.append(f'路径:{file_path}')

                    if parts:
                        return ' | '.join(parts)
                    elif title:
                        return f'📎 {title}'

            # 其他类型的文件消息
            if title:
                return f'📎 文件:{title}'

        return '[文件]'
    except:
        return '[文件]'


def parse_message_by_type(msg_type, content, compress_content=None):
    """
    根据消息类型解析内容 - 增强版
    支持处理zstd压缩的message_content

    参数:
        msg_type: 消息类型
        content: message_content字段
        compress_content: compress_content字段(可选)

    返回:
        解析后的可读内容
    """
    # 保留原始content用于特殊类型(如图片)的解析 - 必须在解压前保存!
    original_content = content

    # 检测content是否为zstd压缩数据
    # 某些消息的local_type字段异常(如21474836529),但message_content包含压缩的XML
    if isinstance(content, bytes) and is_zstd_compressed(content):
        try:
            # 解压缩content
            dctx = zstd.ZstdDecompressor()
            decompressed = dctx.decompress(content)
            # 清理null字节并转为字符串
            content = decompressed.strip(b'\x00').decode('utf-8', errors='ignore').strip()

            # 尝试从XML中提取真实的消息类型
            # 这种情况下,local_type通常是异常值,真实类型在XML的<type>节点中
            if content.startswith('<?xml'):
                try:
                    root = ET.fromstring(content)
                    appmsg = root.find('.//appmsg')
                    if appmsg is not None:
                        type_node = appmsg.find('type')
                        if type_node is not None and type_node.text:
                            # 获取XML中的真实类型
                            real_type = int(type_node.text)
                            # 如果是类型5(链接)且有sourcedisplayname,则视为公众号文章
                            sourcedisplayname = root.findtext('.//sourcedisplayname', '')
                            if real_type == 5 and sourcedisplayname:
                                # 直接解析为公众号文章
                                return parse_xml_content(content)
                            # 其他类型49的消息也走XML解析
                            elif real_type in [1, 3, 4, 5, 6, 8, 19, 33, 36, 49, 51, 57, 2000, 2001]:
                                return parse_xml_content(content)
                except:
                    pass
        except Exception as e:
            # 解压失败,继续按原流程处理
            pass

    # 安全地转换content为字符串(用于文本类型)
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

    # 类型处理映射
    type_handlers = {
        1: lambda: content or '',  # 文本
        3: lambda: parse_image_content(original_content),  # 图片 - 使用原始bytes
        34: lambda: '[语音]',  # 语音
        43: lambda: '[视频]',  # 视频
        47: lambda: '[表情]',  # 表情包
        48: lambda: '[位置]',  # 位置
        49: lambda: parse_xml_content(content),  # 链接/公众号/文件
        10000: lambda: parse_system_message(compress_content if compress_content else content),  # 系统消息
        10002: lambda: '[撤回了一条消息]',  # 撤回消息
    }

    handler = type_handlers.get(msg_type, lambda: f'[类型{msg_type}]')

    try:
        return handler()
    except Exception as e:
        return f'[类型{msg_type}]'
