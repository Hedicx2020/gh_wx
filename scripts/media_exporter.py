#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信媒体文件导出模块
根据搜索结果导出图片、文件、语音、视频等媒体文件
支持DAT格式图片转JPG
"""

import io
import logging
import re
import shutil
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
import xml.etree.ElementTree as ET
import zstandard as zstd
import pandas as pd
from PIL import Image

# 配置日志
logger = logging.getLogger(__name__)

# 常量定义
class MessageType:
    """消息类型常量"""
    IMAGE = 3
    AUDIO = 34
    VIDEO = 43
    FILE = 49
    FILE_ALT = 81604378673


class MediaType:
    """媒体类型常量"""
    IMAGE = 'Image'
    VIDEO = 'Video'
    FILE = 'File'
    AUDIO = 'Audio'


# 文件扩展名映射
DEFAULT_EXTENSIONS = {
    MessageType.IMAGE: 'jpg',
    MessageType.VIDEO: 'mp4',
}

# ZSTD压缩标识
ZSTD_MAGIC = b'\x28\xb5\x2f\xfd'

# V4格式标识
V4_HEADER = b"\x07\x08V2\x08\x07"

# DAT文件XOR密钥
DAT_XOR_KEY = 0xFF

# JPEG质量
JPEG_QUALITY = 95

# Excel非法字符正则
EXCEL_INVALID_CHARS = re.compile(r'[\x00-\x08\x0B-\x0C\x0E-\x1F]')


def decompress_content(content: bytes) -> Optional[str]:
    """
    解压缩消息内容

    参数:
        content: 压缩的内容字节

    返回:
        解压后的字符串，失败返回None
    """
    try:
        if len(content) >= 4 and content[:4] == ZSTD_MAGIC:
            # zstd压缩数据
            dctx = zstd.ZstdDecompressor()
            decompressed = dctx.decompress(content)
            return decompressed.strip(b'\x00').decode('utf-8', errors='ignore').strip()
        elif isinstance(content, bytes):
            return content.decode('utf-8', errors='ignore')
    except Exception as e:
        logger.debug(f"解压缩内容失败: {e}")
    return None


def parse_xml_content(content: str, msg_type: int) -> Tuple[Optional[str], str, str]:
    """
    从XML内容中解析MD5、扩展名和文件名

    参数:
        content: XML字符串内容
        msg_type: 消息类型

    返回:
        (md5, file_ext, file_name) 元组
    """
    try:
        root = ET.fromstring(content)

        # 图片消息
        if msg_type == MessageType.IMAGE:
            img = root.find('.//img')
            if img is not None:
                md5 = img.get('md5', '')
                return md5, DEFAULT_EXTENSIONS.get(MessageType.IMAGE, 'jpg'), ''

        # 文件消息
        elif msg_type in [MessageType.FILE, MessageType.FILE_ALT]:
            md5 = root.findtext('.//md5', '')
            file_ext = root.findtext('.//fileext', '')
            file_name = root.findtext('.//title', '')
            return md5, file_ext, file_name

        # 视频消息
        elif msg_type == MessageType.VIDEO:
            videomsg = root.find('.//videomsg')
            if videomsg is not None:
                md5 = videomsg.get('md5', '')
                return md5, DEFAULT_EXTENSIONS.get(MessageType.VIDEO, 'mp4'), ''

    except ET.ParseError as e:
        logger.debug(f"XML解析失败: {e}")
    except Exception as e:
        logger.debug(f"解析XML内容时出错: {e}")

    return None, '', ''


def extract_md5_from_content(content: Any, msg_type: int) -> Tuple[Optional[str], str, str]:
    """
    从消息内容中提取MD5值

    参数:
        content: 消息内容（可能是bytes或str）
        msg_type: 消息类型

    返回:
        (md5, file_ext, file_name) 元组
    """
    # 处理字节内容
    if isinstance(content, bytes):
        content = decompress_content(content)
        if content is None:
            return None, '', ''

    # 验证内容类型
    if not content or not isinstance(content, str):
        return None, '', ''

    # 尝试解析XML
    if content.startswith('<?xml') or content.startswith('<msg'):
        return parse_xml_content(content, msg_type)

    return None, '', ''


def load_v4_decryptor() -> Optional[Any]:
    """
    加载V4解密器

    返回:
        DatImageDecryptor实例，失败返回None
    """
    try:
        script_dir = Path(__file__).parent.parent
        utils_dir = script_dir / 'utils'
        sys.path.insert(0, str(utils_dir))

        from dat_to_image import DatImageDecryptor
        from wechat_key_extractor import load_keys_from_config

        config_path = script_dir / 'config.xlsx'
        if config_path.exists():
            xor_key, aes_key = load_keys_from_config(str(config_path))
            if xor_key and aes_key:
                return DatImageDecryptor(xor_key, aes_key)
    except Exception as e:
        logger.debug(f"加载V4解密器失败: {e}")
    return None


def decrypt_v3_dat(dat_path: Path, output_path: Path) -> bool:
    """
    使用V3格式解密DAT文件

    参数:
        dat_path: DAT文件路径
        output_path: 输出JPG路径

    返回:
        成功返回True，失败返回False
    """
    try:
        with open(dat_path, 'rb') as f:
            dat_data = bytearray(f.read())

        # 微信DAT加密: 每个字节异或0xFF
        decrypted_data = bytearray([b ^ DAT_XOR_KEY for b in dat_data])

        # 尝试用PIL打开解密后的数据
        img = Image.open(io.BytesIO(decrypted_data))
        # 转换为RGB模式(如果是RGBA)
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        # 保存为JPG
        img.save(output_path, 'JPEG', quality=JPEG_QUALITY)
        return True
    except Exception as e:
        logger.debug(f"V3解密失败: {e}")
        return False


def convert_dat_to_jpg(dat_path: Path, output_path: Path) -> bool:
    """
    将微信DAT格式图片转换为JPG
    支持V3(XOR)和V4(AES+XOR)格式

    参数:
        dat_path: DAT文件路径
        output_path: 输出JPG路径

    返回:
        成功返回True，失败返回False
    """
    try:
        # 检查是否是V4格式
        is_v4 = False
        try:
            with open(dat_path, 'rb') as f:
                header = f.read(6)
            is_v4 = header == V4_HEADER
        except Exception:
            pass

        # 尝试使用V4解密器
        if is_v4 and str(dat_path).endswith('_t.dat'):
            decryptor = load_v4_decryptor()
            if decryptor:
                result_path = decryptor.convert_dat_to_jpg(str(dat_path), str(output_path))
                if result_path:
                    return True

        # V3格式：XOR 0xFF解密
        if decrypt_v3_dat(dat_path, output_path):
            return True

        # 如果解密失败，尝试直接当作普通图片处理
        try:
            img = Image.open(dat_path)
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            img.save(output_path, 'JPEG', quality=JPEG_QUALITY)
            return True
        except Exception as e:
            logger.debug(f"直接打开图片失败: {e}")
            return False

    except Exception as e:
        logger.error(f"DAT转JPG失败: {e}")
        return False


def build_media_path(md5: str, media_type: str, ext: str = '') -> Optional[str]:
    """
    根据MD5构建微信媒体文件路径

    参数:
        md5: 文件MD5值
        media_type: 媒体类型 ('Image', 'File', 'Video', 'Audio')
        ext: 文件扩展名

    返回:
        相对路径字符串，失败返回None
    """
    if not md5:
        return None

    # 微信存储规则: FileStorage/{类型}/{MD5前2位}/{MD5}{扩展名}
    subdir = md5[:2]

    if ext and not ext.startswith('.'):
        ext = '.' + ext

    return f'FileStorage/{media_type}/{subdir}/{md5}{ext}'


def find_source_file(source_base_path: Path, md5: str, media_type: str, ext: str) -> Optional[Tuple[Path, str]]:
    """
    查找源媒体文件

    参数:
        source_base_path: 微信数据根目录
        md5: 文件MD5
        media_type: 媒体类型
        ext: 文件扩展名

    返回:
        (源文件路径, 原始路径字符串) 元组，未找到返回None
    """
    # 首先尝试带扩展名的路径
    relative_path = build_media_path(md5, media_type, ext)
    if relative_path:
        source_path = source_base_path / relative_path
        if source_path.exists():
            return source_path, str(source_path)

    # 尝试不带扩展名
    if ext:
        relative_path_no_ext = build_media_path(md5, media_type, '')
        if relative_path_no_ext:
            source_path_no_ext = source_base_path / relative_path_no_ext
            if source_path_no_ext.exists():
                return source_path_no_ext, str(source_path_no_ext)

    # 对于图片，尝试查找DAT文件
    if media_type == MediaType.IMAGE:
        dat_relative_path = build_media_path(md5, media_type, '.dat')
        if dat_relative_path:
            dat_path = source_base_path / dat_relative_path
            if dat_path.exists():
                return dat_path, str(dat_path)

    return None


def copy_media_file(
    source_base_path: Path,
    md5: str,
    media_type: str,
    ext: str,
    dest_folder: Path,
    convert_dat: bool = False
) -> Tuple[bool, Optional[Path], Optional[str]]:
    """
    复制媒体文件到目标文件夹

    参数:
        source_base_path: 微信数据根目录(包含FileStorage的上级目录)
        md5: 文件MD5
        media_type: 媒体类型
        ext: 文件扩展名
        dest_folder: 目标文件夹
        convert_dat: 是否将DAT图片转换为JPG(仅对图片有效)

    返回:
        (success, copied_path, original_source_path) 元组
    """
    if not md5:
        return False, None, None

    # 查找源文件
    source_info = find_source_file(source_base_path, md5, media_type, ext)
    if not source_info:
        return False, None, None

    source_path, original_source_path = source_info

    # 创建目标文件夹
    dest_folder.mkdir(parents=True, exist_ok=True)

    # 复制文件
    try:
        # 如果是DAT图片且需要转换
        if media_type == MediaType.IMAGE and convert_dat and source_path.suffix.lower() == '.dat':
            # 转换DAT为JPG
            dest_filename = source_path.stem + '.jpg'
            dest_path = dest_folder / dest_filename
            if convert_dat_to_jpg(source_path, dest_path):
                return True, dest_path, original_source_path
            else:
                # 转换失败，直接复制DAT文件
                dest_path = dest_folder / source_path.name
                shutil.copy2(source_path, dest_path)
                return True, dest_path, original_source_path
        else:
            # 普通复制
            dest_path = dest_folder / source_path.name
            shutil.copy2(source_path, dest_path)
            return True, dest_path, original_source_path

    except Exception as e:
        logger.error(f"复制文件失败: {e}")
        return False, None, None


class MediaExporter:
    """媒体文件导出器"""

    def __init__(self, wechat_data_path: str):
        """
        初始化导出器

        参数:
            wechat_data_path: 微信数据根目录路径(包含FileStorage文件夹的路径)
        """
        self.wechat_data_path = Path(wechat_data_path)
        self.convert_dat = False

        # 检查FileStorage是否存在
        self.file_storage_path = self.wechat_data_path / 'FileStorage'
        if not self.file_storage_path.exists():
            logger.warning(f"FileStorage目录不存在: {self.file_storage_path}")

    def _export_media(
        self,
        content: Any,
        msg_type: int,
        dest_folder: Path,
        media_type: str,
        default_ext: str,
        folder_name: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        通用媒体导出方法

        参数:
            content: 消息内容
            msg_type: 消息类型
            dest_folder: 目标文件夹
            media_type: 媒体类型字符串
            default_ext: 默认扩展名
            folder_name: 文件夹名称（用于路径显示）

        返回:
            (媒体路径, 原始路径) 元组
        """
        md5, ext, _ = extract_md5_from_content(content, msg_type)
        if not md5:
            return None, None

        success, dest_path, original_path = copy_media_file(
            self.wechat_data_path,
            md5,
            media_type,
            ext or default_ext,
            dest_folder,
            convert_dat=self.convert_dat if media_type == MediaType.IMAGE else False
        )

        if success and dest_path:
            return f'{folder_name}/{dest_path.name}', original_path
        return None, None

    def _export_image(self, content: Any, dest_folder: Path) -> Tuple[Optional[str], Optional[str]]:
        """导出图片文件，返回(媒体路径, 原始路径)元组"""
        return self._export_media(
            content, MessageType.IMAGE, dest_folder,
            MediaType.IMAGE, DEFAULT_EXTENSIONS[MessageType.IMAGE], 'images'
        )

    def _export_video(self, content: Any, dest_folder: Path) -> Tuple[Optional[str], Optional[str]]:
        """导出视频文件，返回(媒体路径, 原始路径)元组"""
        return self._export_media(
            content, MessageType.VIDEO, dest_folder,
            MediaType.VIDEO, DEFAULT_EXTENSIONS[MessageType.VIDEO], 'videos'
        )

    def _export_file(self, content: Any, msg_type: int, dest_folder: Path) -> Tuple[Optional[str], Optional[str]]:
        """导出文件，返回(媒体路径, 原始路径)元组"""
        md5, ext, _ = extract_md5_from_content(content, msg_type)
        if not md5:
            return None, None

        success, dest_path, original_path = copy_media_file(
            self.wechat_data_path,
            md5,
            MediaType.FILE,
            ext,
            dest_folder
        )

        if success and dest_path:
            return f'files/{dest_path.name}', original_path
        return None, None

    def _update_path_column(
        self,
        export_df: pd.DataFrame,
        idx: Any,
        media_path: Optional[str],
        original_path: Optional[str]
    ) -> None:
        """
        更新DataFrame中的路径列

        参数:
            export_df: 导出的DataFrame
            idx: 行索引
            media_path: 媒体路径
            original_path: 原始路径
        """
        if original_path:
            export_df.at[idx, '路径'] = original_path
        elif media_path:
            export_df.at[idx, '路径'] = media_path

    def _clean_excel_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        清理Excel不支持的非法字符

        参数:
            df: 原始DataFrame

        返回:
            清理后的DataFrame
        """
        df_clean = df.copy()

        # 删除临时列(以_开头的列)
        columns_to_drop = [col for col in df_clean.columns if col.startswith('_')]
        if columns_to_drop:
            df_clean = df_clean.drop(columns=columns_to_drop)

        # 清理Excel不支持的非法字符
        def clean_text(text: Any) -> Any:
            if not isinstance(text, str):
                return text
            return EXCEL_INVALID_CHARS.sub('', text)

        for col in df_clean.columns:
            if df_clean[col].dtype == 'object':
                df_clean[col] = df_clean[col].apply(clean_text)

        return df_clean

    def export_search_results(
        self,
        search_df: pd.DataFrame,
        output_base_dir: str,
        export_media: bool = True,
        convert_dat: bool = False
    ) -> Tuple[Optional[Path], Dict[str, Any]]:
        """
        导出搜索结果到文件夹

        参数:
            search_df: 搜索结果DataFrame
            output_base_dir: 输出基础目录
            export_media: 是否导出媒体文件(默认True)
            convert_dat: 是否将DAT图片转为JPG(默认False)

        返回:
            (export_folder_path, stats) 元组
        """
        if len(search_df) == 0:
            logger.info("没有搜索结果可导出")
            return None, {'total': 0, 'excel': 0, 'media': 0}

        # 创建导出文件夹: 搜索结果_YYYYMMDD_HHMMSS
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        export_folder_name = f'搜索结果_{timestamp}'
        export_folder = Path(output_base_dir) / export_folder_name
        export_folder.mkdir(parents=True, exist_ok=True)

        logger.info(f"导出文件夹: {export_folder}")
        if convert_dat:
            logger.info("DAT转JPG已启用")

        # 创建媒体子文件夹
        media_folders = {
            'images': export_folder / 'images',
            'videos': export_folder / 'videos',
            'files': export_folder / 'files',
            'audio': export_folder / 'audio'
        }

        # 统计信息
        stats = {
            'total': len(search_df),
            'excel': 0,
            'media_images': 0,
            'media_videos': 0,
            'media_files': 0,
            'media_audio': 0,
            'media_failed': 0,
            'dat_converted': 0
        }

        # 准备导出数据(只添加"路径"列)
        export_df = search_df.copy()
        export_df['路径'] = ''

        # 保存convert_dat到实例变量供_export_image等方法使用
        self.convert_dat = convert_dat

        # 如果启用媒体导出，处理每条消息
        if export_media:
            logger.info("开始导出媒体文件...")

            # 消息类型处理映射
            type_handlers = {
                MessageType.IMAGE: lambda row: self._handle_image(row, export_df, media_folders, stats),
                MessageType.VIDEO: lambda row: self._handle_video(row, export_df, media_folders, stats),
                MessageType.FILE: lambda row: self._handle_file(row, export_df, media_folders, stats),
                MessageType.FILE_ALT: lambda row: self._handle_file(row, export_df, media_folders, stats),
                MessageType.AUDIO: lambda row: self._handle_audio(row, export_df),
            }

            for idx, row in export_df.iterrows():
                try:
                    msg_type = int(row['消息类型'])
                    handler = type_handlers.get(msg_type)
                    if handler:
                        handler((idx, row))
                except (ValueError, KeyError) as e:
                    logger.warning(f"处理消息时出错 (索引 {idx}): {e}")

        # 导出Excel
        excel_filename = f'搜索结果_{timestamp}.xlsx'
        excel_path = export_folder / excel_filename

        export_df_clean = self._clean_excel_data(export_df)
        export_df_clean.to_excel(excel_path, index=False, engine='openpyxl')
        stats['excel'] = 1

        logger.info(f"Excel已导出: {excel_filename}")
        logger.info(f"总消息数: {stats['total']}")
        logger.info(f"图片: {stats['media_images']} | 视频: {stats['media_videos']} | 文件: {stats['media_files']}")
        if stats['media_failed'] > 0:
            logger.warning(f"导出失败: {stats['media_failed']}")

        return export_folder, stats

    def _handle_image(
        self,
        row_data: Tuple[Any, pd.Series],
        export_df: pd.DataFrame,
        media_folders: Dict[str, Path],
        stats: Dict[str, Any]
    ) -> None:
        """处理图片消息"""
        idx, row = row_data
        raw_content = row.get('_raw_content', '')
        media_path, original_path = self._export_image(raw_content, media_folders['images'])

        if media_path:
            stats['media_images'] += 1
            if self.convert_dat and original_path and original_path.endswith('.dat'):
                stats['dat_converted'] += 1
        else:
            stats['media_failed'] += 1

        self._update_path_column(export_df, idx, media_path, original_path)

    def _handle_video(
        self,
        row_data: Tuple[Any, pd.Series],
        export_df: pd.DataFrame,
        media_folders: Dict[str, Path],
        stats: Dict[str, Any]
    ) -> None:
        """处理视频消息"""
        idx, row = row_data
        raw_content = row.get('_raw_content', '')
        media_path, original_path = self._export_video(raw_content, media_folders['videos'])

        if media_path:
            stats['media_videos'] += 1
        else:
            stats['media_failed'] += 1

        self._update_path_column(export_df, idx, media_path, original_path)

    def _handle_file(
        self,
        row_data: Tuple[Any, pd.Series],
        export_df: pd.DataFrame,
        media_folders: Dict[str, Path],
        stats: Dict[str, Any]
    ) -> None:
        """处理文件消息"""
        idx, row = row_data
        msg_type = int(row['消息类型'])
        raw_content = row.get('_raw_content', '')
        media_path, original_path = self._export_file(raw_content, msg_type, media_folders['files'])

        if media_path:
            stats['media_files'] += 1
        # 类型49不一定都是文件，所以不计入失败

        self._update_path_column(export_df, idx, media_path, original_path)

    def _handle_audio(self, row_data: Tuple[Any, pd.Series], export_df: pd.DataFrame) -> None:
        """处理语音消息"""
        idx, row = row_data
        export_df.at[idx, '路径'] = '[语音文件暂不支持]'


# 测试代码
if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).parent.parent / 'utils'))
    from search_messages_optimized import MessageSearcher

    # 示例: 导出特定日期的图片消息
    db_dir = Path(__file__).parent.parent / 'output' / 'databases' / 'your_account'
    wechat_data_path = Path('path/to/wechat/data')  # 替换为实际路径

    if db_dir.exists():
        searcher = MessageSearcher(str(db_dir))
        results = searcher.search(
            start_date='2025-11-01',
            end_date='2025-11-17',
            message_type=MessageType.IMAGE  # 只搜索图片
        )

        exporter = MediaExporter(str(wechat_data_path))
        export_folder, stats = exporter.export_search_results(
            results,
            output_base_dir=Path(__file__).parent.parent / 'output' / 'exports'
        )

        print(f"\n导出完成: {export_folder}")
        print(f"统计: {stats}")
