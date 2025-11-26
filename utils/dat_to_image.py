#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信DAT图片解密转换工具（仅支持V4格式）
支持v4(AES+XOR)格式

参考: https://github.com/recarto404/WxDatDecrypt
"""

import os
from pathlib import Path
from typing import Optional, Tuple

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    print("[WARNING] 未安装pycryptodome，无法使用")
    print("[INFO] 安装命令: pip install pycryptodome")


class DatImageDecryptor:
    """DAT图片解密器（仅V4格式）"""

    # V4格式文件头
    V4_SIGNATURE = b"\x07\x08V2\x08\x07"

    def __init__(self, xor_key: Optional[int] = None, aes_key: Optional[str] = None):
        """
        初始化解密器

        参数:
            xor_key: XOR密钥(0-255)
            aes_key: AES密钥(32字节十六进制字符串)
        """
        self.xor_key = xor_key
        self.aes_key = aes_key

    def is_v4_format(self, dat_file_path: str) -> bool:
        """
        检测是否为V4格式

        参数:
            dat_file_path: DAT文件路径

        返回:
            True: V4格式, False: 不是V4格式
        """
        try:
            with open(dat_file_path, 'rb') as f:
                header = f.read(6)
            return header == self.V4_SIGNATURE
        except Exception:
            return False

    def decrypt_v4(self, dat_file_path: str, aes_key: str, xor_key: int) -> Optional[bytes]:
        """
        解密v4格式(AES+XOR混合加密)

        文件结构:
        [0-5]:   签名 (b"\x07\x08V2\x08\x07")
        [6-10]:  AES加密数据大小 (小端序int)
        [11-14]: XOR加密数据大小 (小端序int)
        [15-]:   加密数据

        参数:
            dat_file_path: DAT文件路径
            aes_key: AES密钥(32字节十六进制字符串)
            xor_key: XOR密钥

        返回:
            解密后的图片数据 或 None
        """
        if not HAS_CRYPTO:
            print("[ERROR] v4格式需要pycryptodome库")
            return None

        try:
            with open(dat_file_path, 'rb') as f:
                data = f.read()

            # 解析文件头
            signature = data[:6]
            if signature != b"\x07\x08V2\x08\x07":
                print("[ERROR] v4文件签名不匹配")
                return None

            # 读取大小信息(小端序, 4字节)
            aes_size_original = int.from_bytes(data[6:10], byteorder='little')
            xor_size = int.from_bytes(data[10:14], byteorder='little')

            # AES密钥转换(参考WxDatDecrypt实现)
            # 密钥存储为字符串，使用encode()转换为bytes并取前16字节
            try:
                if isinstance(aes_key, str):
                    aes_key_bytes = aes_key.encode()[:16]
                elif isinstance(aes_key, bytes):
                    aes_key_bytes = aes_key[:16]
                else:
                    print(f"[ERROR] AES密钥类型错误: {type(aes_key)}")
                    return None
            except Exception as e:
                print(f"[ERROR] AES密钥转换失败: {e}")
                return None

            if len(aes_key_bytes) != 16:
                print(f"[ERROR] AES密钥长度错误: {len(aes_key_bytes)} (需要16字节)")
                return None

            # 计算各部分位置
            header_size = 15
            encrypted_data = data[header_size:]

            # AES加密数据需要按16字节对齐
            # 参考WxDatDecrypt实现（对缩略图文件有效）
            aes_size = aes_size_original + AES.block_size - aes_size_original % AES.block_size

            # 分离三部分数据(参考WxDatDecrypt的逻辑)
            aes_data = encrypted_data[:aes_size]

            if xor_size > 0:
                middle_data = encrypted_data[aes_size:-xor_size]
                xor_data = encrypted_data[-xor_size:]
            else:
                middle_data = encrypted_data[aes_size:]
                xor_data = b''

            # AES解密
            cipher = AES.new(aes_key_bytes, AES.MODE_ECB)
            aes_decrypted = cipher.decrypt(aes_data)

            # 去除填充(只保留实际数据)
            try:
                aes_decrypted = unpad(aes_decrypted, AES.block_size)
            except:
                # 手动去除填充
                aes_decrypted = aes_decrypted[:aes_size_original]

            # XOR解密
            if xor_size > 0:
                xor_decrypted = bytes([b ^ xor_key for b in xor_data])
            else:
                xor_decrypted = b''

            # 合并数据
            decrypted_data = aes_decrypted + middle_data + xor_decrypted

            # 验证是否为JPEG
            if decrypted_data[:3] == b'\xFF\xD8\xFF':
                return decrypted_data

            print("[WARNING] 解密后不是有效的JPEG文件")
            return decrypted_data  # 仍然返回,可能是其他格式

        except Exception as e:
            print(f"[ERROR] v4解密失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def decrypt_dat(self, dat_file_path: str) -> Optional[bytes]:
        """
        解密DAT文件（仅V4格式）

        参数:
            dat_file_path: DAT文件路径

        返回:
            解密后的图片数据 或 None
        """
        if not self.is_v4_format(dat_file_path):
            print(f"[ERROR] 文件不是V4格式: {dat_file_path}")
            return None

        if not self.aes_key:
            print(f"[ERROR] 需要AES密钥")
            return None
        if not self.xor_key:
            print(f"[ERROR] 需要XOR密钥")
            return None

        return self.decrypt_v4(dat_file_path, self.aes_key, self.xor_key)

    def convert_dat_to_jpg(self, dat_file_path: str, output_path: Optional[str] = None) -> Optional[str]:
        """
        将DAT文件转换为JPG

        参数:
            dat_file_path: DAT文件路径
            output_path: 输出路径(可选,默认为同目录替换扩展名)

        返回:
            输出文件路径 或 None
        """
        # 解密文件
        decrypted_data = self.decrypt_dat(dat_file_path)
        if decrypted_data is None:
            return None

        # 确定输出路径
        if output_path is None:
            dat_path = Path(dat_file_path)
            output_path = dat_path.parent / f"{dat_path.stem}.jpg"
        else:
            output_path = Path(output_path)
            if output_path.suffix != '.jpg':
                output_path = output_path.with_suffix('.jpg')

        # 写入文件
        try:
            with open(output_path, 'wb') as f:
                f.write(decrypted_data)

            return str(output_path)

        except Exception as e:
            print(f"[ERROR] 写入文件失败: {e}")
            return None

    def batch_convert(self, dat_directory: str, output_directory: Optional[str] = None,
                     recursive: bool = False) -> Tuple[int, int]:
        """
        批量转换目录下的所有DAT文件

        参数:
            dat_directory: DAT文件所在目录
            output_directory: 输出目录(可选)
            recursive: 是否递归子目录

        返回:
            (成功数量, 失败数量)
        """
        dat_dir = Path(dat_directory)
        if not dat_dir.exists():
            print(f"[ERROR] 目录不存在: {dat_directory}")
            return 0, 0

        # 查找所有DAT文件
        if recursive:
            dat_files = list(dat_dir.rglob('*.dat'))
        else:
            dat_files = list(dat_dir.glob('*.dat'))

        if len(dat_files) == 0:
            print(f"[ERROR] 未找到DAT文件: {dat_directory}")
            return 0, 0

        print(f"[INFO] 找到 {len(dat_files)} 个DAT文件")

        # 确定输出目录
        if output_directory:
            output_dir = Path(output_directory)
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = dat_dir

        success = 0
        fail = 0

        for dat_file in dat_files:
            # 跳过非V4格式文件
            if not self.is_v4_format(str(dat_file)):
                print(f"[SKIP] {dat_file.name} (非V4格式)")
                fail += 1
                continue

            # 注意: 当前仅支持缩略图文件（*_t.dat）
            # 完整图文件使用不同的AES密钥（未知）
            if not dat_file.name.endswith('_t.dat'):
                print(f"[SKIP] {dat_file.name} (暂不支持完整图，仅支持缩略图)")
                fail += 1
                continue

            # 确定输出路径
            if output_directory:
                # 保持相对路径结构
                rel_path = dat_file.relative_to(dat_dir)
                output_path = output_dir / rel_path.parent / f"{dat_file.stem}.jpg"
                output_path.parent.mkdir(parents=True, exist_ok=True)
            else:
                output_path = dat_file.parent / f"{dat_file.stem}.jpg"

            # 转换
            result = self.convert_dat_to_jpg(str(dat_file), str(output_path))

            if result:
                print(f"[OK] {dat_file.name} -> {output_path.name}")
                success += 1
            else:
                print(f"[FAIL] {dat_file.name}")
                fail += 1

        print(f"\n[INFO] 批量转换完成: 成功 {success} 个, 失败 {fail} 个")
        return success, fail


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python dat_to_image.py <dat文件或目录> [输出目录] [--xor-key KEY] [--aes-key KEY]")
        print("\n示例:")
        print("  python dat_to_image.py image.dat --xor-key 69")
        print("  python dat_to_image.py dat_directory/ output/ --xor-key 69")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = None
    xor_key = None
    aes_key = None

    # 解析参数
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--xor-key' and i + 1 < len(sys.argv):
            xor_key = int(sys.argv[i + 1])
            i += 2
        elif arg == '--aes-key' and i + 1 < len(sys.argv):
            aes_key = sys.argv[i + 1]
            i += 2
        elif not arg.startswith('--'):
            output_path = arg
            i += 1
        else:
            i += 1

    if xor_key is None:
        print("[ERROR] 请提供XOR密钥: --xor-key KEY")
        sys.exit(1)

    # 创建解密器
    decryptor = DatImageDecryptor(xor_key, aes_key)

    # 转换
    if Path(input_path).is_file():
        result = decryptor.convert_dat_to_jpg(input_path, output_path)
        if result:
            print(f"\n[SUCCESS] 输出: {result}")
    elif Path(input_path).is_dir():
        decryptor.batch_convert(input_path, output_path)
    else:
        print(f"[ERROR] 路径不存在: {input_path}")
