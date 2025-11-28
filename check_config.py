# -*- coding: utf-8 -*-
import pandas as pd
import os

print("=== 检查配置文件 ===")

# 检查根目录
root_config = r'D:\gh_wx\config.xlsx'
dist_config = r'D:\gh_wx\dist\config.xlsx'

print(f"\n根目录配置文件存在: {os.path.exists(root_config)}")
print(f"dist目录配置文件存在: {os.path.exists(dist_config)}")

# 读取根目录配置
if os.path.exists(root_config):
    print(f"\n=== 根目录 config.xlsx ===")
    df = pd.read_excel(root_config, engine='openpyxl')
    print(f"列名: {df.columns.tolist()}")
    for idx, row in df.iterrows():
        key = row.get('配置项', 'N/A')
        value = row.get('值', 'N/A')
        if key in ['database_password', 'wechat_files_path']:
            print(f"  {key} = '{value}'")

# 读取dist目录配置
if os.path.exists(dist_config):
    print(f"\n=== dist目录 config.xlsx ===")
    df = pd.read_excel(dist_config, engine='openpyxl')
    print(f"列名: {df.columns.tolist()}")
    for idx, row in df.iterrows():
        key = row.get('配置项', 'N/A')
        value = row.get('值', 'N/A')
        if key in ['database_password', 'wechat_files_path']:
            print(f"  {key} = '{value}'")

