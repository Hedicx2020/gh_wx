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
        # 配置文件在项目根目录,不是utils目录
        self.config_file = Path(__file__).parent.parent / config_file
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
            "last_updated": "",
            # LLM大模型配置 (OpenAI兼容格式)
            "llm_api_base": "https://api.deepseek.com/v1",  # 默认使用DeepSeek API
            "llm_model": "deepseek-chat",  # 默认模型名称
            "llm_api_key": "",
            "llm_temperature": "0.7",
            "llm_max_tokens": "2000"
        }

    def save_config(self, config):
        """保存配置到Excel"""
        # 合并配置：先从当前配置或默认配置开始，然后用新配置更新
        # 这样可以确保不会丢失任何配置项
        merged_config = self.config.copy()
        merged_config.update(config)
        merged_config['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

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
            'last_updated': '最后更新时间',
            # LLM配置说明 (OpenAI兼容格式)
            'llm_api_base': 'API地址(OpenAI兼容格式,如https://api.deepseek.com/v1)',
            'llm_model': '模型名称(如deepseek-chat, gpt-4o等)',
            'llm_api_key': 'API密钥',
            'llm_temperature': '温度参数(0-1,越高越随机)',
            'llm_max_tokens': '最大生成token数'
        }

        # 转换为DataFrame
        data = {
            '配置项': list(merged_config.keys()),
            '值': list(merged_config.values()),
            '说明': [descriptions.get(key, '') for key in merged_config.keys()]
        }
        df = pd.DataFrame(data)

        # 保存到Excel
        df.to_excel(self.config_file, index=False, engine='openpyxl')
        self.config = merged_config
        return True

    def get(self, key, default=None):
        """获取配置项"""
        return self.config.get(key, default)

    def set(self, key, value):
        """设置配置项"""
        self.config[key] = value
        self.save_config(self.config)

    def get_all(self, reload=False):
        """获取所有配置
        
        Args:
            reload: 是否重新从文件加载配置
        """
        if reload:
            self.config = self.load_config()
        return self.config.copy()
    
    def reload_config(self):
        """强制重新从文件加载配置"""
        self.config = self.load_config()
        return self.config.copy()
