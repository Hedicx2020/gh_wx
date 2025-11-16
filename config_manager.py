#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块 - 使用Excel格式存储配置
"""

import pandas as pd
from pathlib import Path
from datetime import datetime


class ConfigManager:
    def __init__(self, config_file='config.xlsx'):
        self.config_file = Path(__file__).parent / config_file
        self.config = self.load_config()

    def load_config(self):
        """从Excel加载配置文件"""
        if self.config_file.exists():
            try:
                df = pd.read_excel(self.config_file, engine='openpyxl')
                # 将DataFrame转换为字典
                config = {}
                for _, row in df.iterrows():
                    key = row['配置项']
                    value = row['值']

                    # 处理空值
                    if pd.isna(value):
                        value = ""
                    # 处理日期时间对象
                    elif isinstance(value, pd.Timestamp):
                        # 只保留日期部分
                        value = value.strftime('%Y-%m-%d')
                    # 转换为字符串
                    elif not isinstance(value, str):
                        value = str(value)

                    config[key] = value
                return config
            except Exception as e:
                print(f"加载配置失败: {e}")
                return self.get_default_config()
        else:
            return self.get_default_config()

    def get_default_config(self):
        """获取默认配置"""
        return {
            "database_password": "",
            "wechat_files_path": "",
            "output_path": "output",
            "default_start_date": "",
            "default_end_date": "",
            "default_chat_name": "",
            "default_keyword": "",
            "delete_keywords": "",
            "last_updated": ""
        }

    def save_config(self, config):
        """保存配置到Excel"""
        config['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 配置项说明映射
        descriptions = {
            'database_password': '数据库解密密钥(64位十六进制)',
            'wechat_files_path': '微信数据文件路径(db_storage目录)',
            'output_path': '输出目录路径',
            'default_start_date': '搜索开始日期(YYYY-MM-DD)',
            'default_end_date': '搜索结束日期(YYYY-MM-DD)',
            'default_chat_name': '默认聊天对象(群名/好友名)',
            'default_keyword': '默认搜索关键词',
            'delete_keywords': '过滤关键词(多个用逗号分隔)',
            'last_updated': '最后更新时间'
        }

        # 转换为DataFrame
        data = {
            '配置项': list(config.keys()),
            '值': list(config.values()),
            '说明': [descriptions.get(key, '') for key in config.keys()]
        }
        df = pd.DataFrame(data)

        # 保存到Excel
        df.to_excel(self.config_file, index=False, engine='openpyxl')
        self.config = config
        return True

    def get(self, key, default=None):
        """获取配置项"""
        return self.config.get(key, default)

    def set(self, key, value):
        """设置配置项"""
        self.config[key] = value
        self.save_config(self.config)

    def get_all(self):
        """获取所有配置"""
        return self.config.copy()
