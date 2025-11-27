# -*- coding: utf-8 -*-
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER
import os

# Register Chinese font
font_path = 'C:/Windows/Fonts/simhei.ttf'
if os.path.exists(font_path):
    pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
    print('Font registered')

# Text content using Unicode escapes
T = {
    'title': '\u56fd\u6d77\u91d1\u5de5\u5fae\u4fe1\u6570\u636e\u7b5b\u9009\u5de5\u5177 v1.2',
    'guide': '\u7528\u6237\u4f7f\u7528\u6307\u5357',
    'intro': '\u672c\u6307\u5357\u5c06\u6307\u5bfc\u60a8\u5b8c\u6210\u4ee5\u4e0b\u64cd\u4f5c\uff1a',
    'step1': '\u2022 \u4f7f\u7528 DbkeyHookUI.exe \u83b7\u53d6\u5fae\u4fe1\u6570\u636e\u5e93\u5bc6\u94a5',
    'step2': '\u2022 \u914d\u7f6e config.xlsx \u6587\u4ef6',
    'step3': '\u2022 \u4f7f\u7528\u6570\u636e\u7b5b\u9009\u5de5\u5177\u8fdb\u884c\u6570\u636e\u89e3\u5bc6\u548c\u641c\u7d22',
    'version': '\u7248\u672c\uff1av1.2 | \u66f4\u65b0\u65e5\u671f\uff1a2025\u5e7411\u6708',
    'ch1': '\u4e00\u3001\u5de5\u5177\u5305\u6587\u4ef6\u8bf4\u660e',
    'ch1_intro': '\u5de5\u5177\u5305\u5305\u542b\u4ee5\u4e0b\u6587\u4ef6\uff1a',
    'file_name': '\u6587\u4ef6\u540d',
    'file_desc': '\u8bf4\u660e',
    'file1_desc': '\u5fae\u4fe1\u6570\u636e\u5e93\u5bc6\u94a5\u83b7\u53d6\u5de5\u5177',
    'file2_desc': '\u914d\u7f6e\u6587\u4ef6\uff08\u5bc6\u94a5\u3001\u8def\u5f84\u3001\u641c\u7d22\u53c2\u6570\u7b49\uff09',
    'file3_name': '\u56fd\u6d77\u91d1\u5de5\u5fae\u4fe1\u6570\u636e\u7b5b\u9009\u5de5\u5177v1.2.exe',
    'file3_desc': '\u4e3b\u7a0b\u5e8f\uff08\u6570\u636e\u89e3\u5bc6\u3001\u641c\u7d22\u3001AI\u5206\u6790\uff09',
    'tip_same_dir': '\u3010\u63d0\u793a\u3011\u8bf7\u5c06\u6240\u6709\u6587\u4ef6\u653e\u7f6e\u5728\u540c\u4e00\u76ee\u5f55\u4e0b\u8fd0\u884c\u3002',
    'ch2': '\u4e8c\u3001\u83b7\u53d6\u5fae\u4fe1\u6570\u636e\u5e93\u5bc6\u94a5',
    'ch2_1': '2.1 \u524d\u63d0\u6761\u4ef6',
    'ch2_1_1': '\u2022 \u7535\u8111\u4e0a\u5df2\u5b89\u88c5\u5fae\u4fe1\u5ba2\u6237\u7aef',
    'ch2_2': '2.2 \u83b7\u53d6\u5bc6\u94a5\uff08Key\uff09',
    'step1_title': '<b>\u6b65\u9aa41\uff1a\u542f\u52a8\u5bc6\u94a5\u83b7\u53d6\u5de5\u5177</b>',
    'step1_desc': '\u53cc\u51fb\u8fd0\u884c DbkeyHookUI.exe\uff0c\u70b9\u51fb\u3010\u6253\u5f00\u5fae\u4fe1\u3011\u6309\u94ae\u542f\u52a8\u5fae\u4fe1\u5ba2\u6237\u7aef\u3002',
    'step2_title': '<b>\u6b65\u9aa42\uff1a\u5f00\u59cb\u83b7\u53d6</b>',
    'step2_desc': '\u70b9\u51fb\u3010\u5f00\u59cb\u83b7\u53d6\u3011\u6309\u94ae\uff0c\u7136\u540e\u5728\u5fae\u4fe1\u5ba2\u6237\u7aef\u767b\u5f55\u8d26\u53f7\u3002',
    'step3_title': '<b>\u6b65\u9aa43\uff1a\u590d\u5236\u5bc6\u94a5</b>',
    'step3_desc': '\u767b\u5f55\u6210\u529f\u540e\uff0c\u7a0b\u5e8f\u4f1a\u81ea\u52a8\u663e\u793a Key\uff0864\u4f4d\u5341\u516d\u8fdb\u5236\u5bc6\u94a5\uff09\uff0c\u590d\u5236\u5e76\u4fdd\u5b58\u3002',
    'ch2_3': '2.3 \u83b7\u53d6\u6570\u636e\u76ee\u5f55\u8def\u5f84',
    'path_step1_title': '<b>\u6b65\u9aa41\uff1a\u6253\u5f00\u5fae\u4fe1\u8bbe\u7f6e</b>',
    'path_step1_desc': '\u5728\u5fae\u4fe1\u5ba2\u6237\u7aef\u4e2d\uff0c\u70b9\u51fb\u5de6\u4e0b\u89d2\u3010\u8bbe\u7f6e\u3011\u6309\u94ae\u3002',
    'path_step2_title': '<b>\u6b65\u9aa42\uff1a\u67e5\u770b\u5b58\u50a8\u8def\u5f84</b>',
    'path_step2_desc': '\u5728\u8bbe\u7f6e\u9875\u9762\u4e2d\uff0c\u627e\u5230\u3010\u5b58\u50a8\u8def\u5f84\u3011\u9009\u9879\uff0c\u70b9\u51fb\u8fdb\u5165\u3002',
    'path_step3_title': '<b>\u6b65\u9aa43\uff1a\u590d\u5236 db_storage \u8def\u5f84</b>',
    'path_step3_desc': '\u70b9\u51fb\u8fdb\u5165\u5b58\u50a8\u76ee\u5f55\uff0c\u627e\u5230 db_storage \u6587\u4ef6\u5939\uff0c\u590d\u5236\u5176\u5b8c\u6574\u7edd\u5bf9\u8def\u5f84\u3002',
    'path_example_title': '\u8def\u5f84\u793a\u4f8b\uff08\u5982\u4e0b\u56fe\u6240\u793a\uff09\uff1a',
    'save_title': '<b>\u6b65\u9aa44\uff1a\u8bb0\u5f55\u4fe1\u606f</b>',
    'save_desc': '\u8bf7\u786e\u4fdd\u5df2\u590d\u5236\u5e76\u4fdd\u5b58\u4ee5\u4e0b\u4e24\u9879\u4fe1\u606f\uff1a',
    'save1': '1. Key\uff0864\u4f4d\u5bc6\u94a5\uff09- \u4ece DbkeyHookUI.exe \u83b7\u53d6',
    'save2': '2. db_storage \u7edd\u5bf9\u8def\u5f84 - \u4ece\u5fae\u4fe1\u8bbe\u7f6e\u83b7\u53d6',
    'key_example': '\u3010\u91cd\u8981\u3011\u5bc6\u94a5\u793a\u4f8b\uff0864\u4f4d\u5341\u516d\u8fdb\u5236\u5b57\u7b26\u4e32\uff09\uff1a',
    'key_sample': '1a900760178748a1b88643e0fc78daa1f93109ee420c4b24b3e1d2d5010d42e2',
    'path_example': '\u3010\u91cd\u8981\u3011\u6570\u636e\u76ee\u5f55\u8def\u5f84\u793a\u4f8b\uff1a',
    'path_sample': 'C:\\\\Users\\\\\u7528\u6237\u540d\\\\xwechat_files\\\\wxid_xxx\\\\db_storage',
    'notes': '\u3010\u6ce8\u610f\u4e8b\u9879\u3011',
    'note1': '\u2022 \u83b7\u53d6\u5bc6\u94a5\u65f6\u5fae\u4fe1\u5fc5\u987b\u5904\u4e8e\u767b\u5f55\u72b6\u6001',
    'note2': '\u2022 \u6bcf\u4e2a\u5fae\u4fe1\u8d26\u53f7\u7684\u5bc6\u94a5\u662f\u552f\u4e00\u7684',
    'note3': '\u2022 \u91cd\u65b0\u767b\u5f55\u5fae\u4fe1\u540e\u5bc6\u94a5\u53ef\u80fd\u4f1a\u6539\u53d8',
    'note4': '\u2022 \u8bf7\u59a5\u5584\u4fdd\u7ba1\u5bc6\u94a5\uff0c\u4e0d\u8981\u6cc4\u9732\u7ed9\u4ed6\u4eba',
    'ch3': '\u4e09\u3001\u914d\u7f6e config.xlsx \u6587\u4ef6',
    'ch3_1': '3.1 \u6253\u5f00\u914d\u7f6e\u6587\u4ef6',
    'ch3_1_desc': '\u4f7f\u7528 Excel \u6216 WPS \u6253\u5f00 config.xlsx \u6587\u4ef6\u3002',
    'ch3_2': '3.2 \u914d\u7f6e\u9879\u8bf4\u660e',
    'config_item': '\u914d\u7f6e\u9879',
    'config_desc': '\u8bf4\u660e',
    'config_example': '\u793a\u4f8b\u503c',
    'cfg1': 'database_password',
    'cfg1_desc': '\u5fae\u4fe1\u6570\u636e\u5e93\u5bc6\u94a5\uff0864\u4f4dKey\uff09',
    'cfg1_ex': '1a900760...42e2',
    'cfg2': 'wechat_files_path',
    'cfg2_desc': '\u5fae\u4fe1\u6570\u636e\u6587\u4ef6\u8def\u5f84',
    'cfg2_ex': 'C:\\\\Users\\\\...\\\\db_storage',
    'cfg3': 'default_start_date',
    'cfg3_desc': '\u9ed8\u8ba4\u641c\u7d22\u5f00\u59cb\u65e5\u671f',
    'cfg3_ex': '2025-11-01',
    'cfg4': 'default_end_date',
    'cfg4_desc': '\u9ed8\u8ba4\u641c\u7d22\u7ed3\u675f\u65e5\u671f',
    'cfg4_ex': '2025-11-27',
    'cfg5': 'default_chat_name',
    'cfg5_desc': '\u9ed8\u8ba4\u641c\u7d22\u7684\u804a\u5929\u5bf9\u8c61',
    'cfg5_ex': '\u5de5\u4f5c\u4ea4\u6d41\u7fa4',
    'cfg6': 'default_keyword',
    'cfg6_desc': '\u9ed8\u8ba4\u641c\u7d22\u5173\u952e\u8bcd\uff08\u53ef\u7559\u7a7a\uff09',
    'cfg6_ex': '',
    'cfg7': 'delete_keywords',
    'cfg7_desc': '\u8fc7\u6ee4\u5173\u952e\u8bcd\uff08\u9017\u53f7\u5206\u9694\uff09',
    'cfg7_ex': '\u5e7f\u544a,\u63a8\u9500',
    'cfg8': 'llm_api_base',
    'cfg8_desc': 'AI\u63a5\u53e3\u5730\u5740',
    'cfg8_ex': 'https://api.deepseek.com/v1',
    'cfg9': 'llm_api_key',
    'cfg9_desc': 'AI\u63a5\u53e3\u5bc6\u94a5',
    'cfg9_ex': 'sk-xxx...',
    'cfg10': 'llm_model',
    'cfg10_desc': 'AI\u6a21\u578b\u540d\u79f0',
    'cfg10_ex': 'deepseek-chat',
    'ch3_3': '3.3 \u5fc5\u586b\u914d\u7f6e\u9879',
    'ch3_3_desc': '\u4ee5\u4e0b\u4e24\u9879\u4e3a\u5fc5\u586b\uff0c\u5426\u5219\u65e0\u6cd5\u6b63\u5e38\u4f7f\u7528\uff1a',
    'req1': '1. <b>database_password</b>\uff1a\u4ece DbkeyHookUI.exe \u83b7\u53d6\u7684\u5bc6\u94a5',
    'req2': '2. <b>wechat_files_path</b>\uff1a\u5fae\u4fe1\u6570\u636e\u5e93\u6587\u4ef6\u8def\u5f84',
    'ch3_4': '3.4 \u4fdd\u5b58\u914d\u7f6e',
    'ch3_4_desc': '\u4fee\u6539\u5b8c\u6210\u540e\uff0c\u4fdd\u5b58\u6587\u4ef6\uff08Ctrl+S\uff09\u5e76\u5173\u95ed Excel\u3002',
    'tip_config': '\u3010\u63d0\u793a\u3011\u914d\u7f6e\u6587\u4ef6\u5fc5\u987b\u4e0e\u4e3b\u7a0b\u5e8f\u653e\u5728\u540c\u4e00\u76ee\u5f55\u4e0b\u3002',
    'ch4': '\u56db\u3001\u4f7f\u7528\u6570\u636e\u7b5b\u9009\u5de5\u5177',
    'ch4_1': '4.1 \u542f\u52a8\u7a0b\u5e8f',
    'ch4_1_desc1': '\u53cc\u51fb\u8fd0\u884c\u3010\u56fd\u6d77\u91d1\u5de5\u5fae\u4fe1\u6570\u636e\u7b5b\u9009\u5de5\u5177v1.2.exe\u3011',
    'ch4_1_desc2': '\u7a0b\u5e8f\u542f\u52a8\u540e\u4f1a\u81ea\u52a8\u6253\u5f00\u6d4f\u89c8\u5668\uff0c\u663e\u793a\u64cd\u4f5c\u754c\u9762\u3002',
    'ch4_1_url': '\u5982\u679c\u6d4f\u89c8\u5668\u672a\u81ea\u52a8\u6253\u5f00\uff0c\u8bf7\u624b\u52a8\u8bbf\u95ee\uff1ahttp://127.0.0.1:5000',
    'ch4_2': '4.2 \u754c\u9762\u8bf4\u660e',
    'ch4_2_desc': '\u754c\u9762\u5206\u4e3a\u4e09\u4e2a\u4e3b\u8981\u6a21\u5757\uff1a',
    'module': '\u6a21\u5757',
    'module_desc': '\u529f\u80fd\u8bf4\u660e',
    'mod1': '\u6a21\u5757 A: \u6838\u5fc3\u89e3\u5bc6',
    'mod1_desc': '\u52a0\u8f7d\u914d\u7f6e\u3001\u89e3\u5bc6\u5fae\u4fe1\u6570\u636e\u5e93',
    'mod2': '\u6a21\u5757 B: AI\u667a\u80fd\u5206\u6790',
    'mod2_desc': '\u914d\u7f6eAI\u6a21\u578b\uff0c\u5bf9\u641c\u7d22\u7ed3\u679c\u8fdb\u884c\u667a\u80fd\u5206\u6790',
    'mod3': '\u6a21\u5757 C: \u641c\u7d22\u804a\u5929',
    'mod3_desc': '\u6309\u6761\u4ef6\u641c\u7d22\u804a\u5929\u8bb0\u5f55\uff0c\u652f\u6301\u80a1\u7968\u7b5b\u9009',
    'ch4_3': '4.3 \u64cd\u4f5c\u6d41\u7a0b',
    'op1_title': '<b>\u7b2c\u4e00\u6b65\uff1a\u52a0\u8f7d\u914d\u7f6e</b>',
    'op1_desc': '\u70b9\u51fb\u3010\u52a0\u8f7d\u914d\u7f6e\u3011\u6309\u94ae\uff0c\u7cfb\u7edf\u4f1a\u81ea\u52a8\u8bfb\u53d6 config.xlsx \u4e2d\u7684\u914d\u7f6e\u4fe1\u606f\u3002',
    'op2_title': '<b>\u7b2c\u4e8c\u6b65\uff1a\u89e3\u5bc6\u6570\u636e\u5e93\uff08\u9996\u6b21\u4f7f\u7528\u5fc5\u987b\u6267\u884c\uff09</b>',
    'op2_desc': '\u70b9\u51fb\u3010\u5168\u91cf\u89e3\u5bc6\u3011\u6309\u94ae\uff0c\u7cfb\u7edf\u4f1a\u89e3\u5bc6\u5fae\u4fe1\u6570\u636e\u5e93\u6587\u4ef6\u3002',
    'op2_1': '\u2022 \u89e3\u5bc6\u8fc7\u7a0b\u9700\u8981\u4e00\u5b9a\u65f6\u95f4\uff0c\u8bf7\u8010\u5fc3\u7b49\u5f85',
    'op2_2': '\u2022 \u89e3\u5bc6\u540e\u7684\u6587\u4ef6\u4fdd\u5b58\u5728 output/databases/ \u76ee\u5f55\u4e0b',
    'op2_3': '\u2022 \u9996\u6b21\u4f7f\u7528\u5fc5\u987b\u6267\u884c\u5168\u91cf\u89e3\u5bc6',
    'op3_title': '<b>\u7b2c\u4e09\u6b65\uff1a\u641c\u7d22\u804a\u5929\u8bb0\u5f55</b>',
    'op3_desc': '\u5728\u641c\u7d22\u6a21\u5757\u4e2d\u8bbe\u7f6e\u4ee5\u4e0b\u53c2\u6570\uff1a',
    'op3_1': '\u2022 <b>\u5f00\u59cb\u65e5\u671f/\u7ed3\u675f\u65e5\u671f</b>\uff1a\u641c\u7d22\u7684\u65f6\u95f4\u8303\u56f4',
    'op3_2': '\u2022 <b>\u804a\u5929\u5bf9\u8c61</b>\uff1a\u7fa4\u540d\u6216\u8054\u7cfb\u4eba\u540d\u79f0\uff08\u652f\u6301\u6a21\u7cca\u5339\u914d\uff09',
    'op3_3': '\u2022 <b>\u5173\u952e\u8bcd</b>\uff1a\u641c\u7d22\u7684\u5173\u952e\u8bcd\uff08\u53ef\u9009\uff09',
    'op3_4': '\u2022 <b>\u80a1\u7968\u7b5b\u9009</b>\uff1a\u53ef\u9009\u62e9\u7b5b\u9009\u5305\u542bA\u80a1/\u6e2f\u80a1/\u7f8e\u80a1\u4fe1\u606f\u7684\u6d88\u606f',
    'op3_btn': '\u70b9\u51fb\u3010\u641c\u7d22\u804a\u5929\u3011\u6309\u94ae\u6267\u884c\u641c\u7d22\u3002',
    'ch4_4': '4.4 \u80a1\u7968\u7b5b\u9009\u529f\u80fd',
    'ch4_4_desc': '\u80a1\u7968\u7b5b\u9009\u529f\u80fd\u53ef\u4ee5\u8fc7\u6ee4\u51fa\u5305\u542b\u80a1\u7968\u4fe1\u606f\u7684\u804a\u5929\u8bb0\u5f55\uff1a',
    'stock1': '\u2022 <b>[A\u80a1]</b>\uff1a\u7b5b\u9009\u5305\u542bA\u80a1\u80a1\u7968\u540d\u79f0\u7684\u6d88\u606f',
    'stock2': '\u2022 <b>[\u6e2f\u80a1]</b>\uff1a\u7b5b\u9009\u5305\u542b\u6e2f\u80a1\u80a1\u7968\u540d\u79f0\u7684\u6d88\u606f',
    'stock3': '\u2022 <b>[\u7f8e\u80a1]</b>\uff1a\u7b5b\u9009\u5305\u542b\u7f8e\u80a1\u80a1\u7968\u540d\u79f0\u7684\u6d88\u606f',
    'stock4': '\u2022 <b>\u5339\u914d\u4ee3\u7801</b>\uff1a\u52fe\u9009\u540e\u540c\u65f6\u5339\u914d\u80a1\u7968\u4ee3\u7801\uff08\u5982600519\u3001AAPL\uff09',
    'stock_tip': '\u3010\u63d0\u793a\u3011\u53ef\u4ee5\u540c\u65f6\u9009\u62e9\u591a\u4e2a\u5e02\u573a\u8fdb\u884c\u7b5b\u9009\u3002',
    'ch4_5': '4.5 AI\u667a\u80fd\u5206\u6790',
    'ch4_5_desc': '\u641c\u7d22\u5b8c\u6210\u540e\uff0c\u53ef\u4ee5\u4f7f\u7528AI\u5bf9\u7ed3\u679c\u8fdb\u884c\u5206\u6790\uff1a',
    'ai1': '1. \u5728AI\u6a21\u5757\u4e2d\u70b9\u51fb\u3010\u52a0\u8f7d\u3011\u52a0\u8f7dAI\u914d\u7f6e',
    'ai2': '2. \u5728\u5bf9\u8bdd\u6846\u4e2d\u8f93\u5165\u95ee\u9898',
    'ai3': '3. \u70b9\u51fb\u3010\u53d1\u9001\u3011\u83b7\u53d6AI\u5206\u6790\u7ed3\u679c',
    'ch4_6': '4.6 \u5bfc\u51fa\u6570\u636e',
    'ch4_6_desc': '\u641c\u7d22\u7ed3\u679c\u53ef\u4ee5\u5bfc\u51fa\u4e3aExcel\u6587\u4ef6\uff1a',
    'ch4_6_btn': '\u70b9\u51fb\u3010\u5bfc\u51faExcel\u3011\u6309\u94ae\uff0c\u6587\u4ef6\u5c06\u4fdd\u5b58\u5230 output/ \u76ee\u5f55\u4e0b\u3002',
    'ch5': '\u4e94\u3001\u5e38\u89c1\u95ee\u9898\u89e3\u7b54',
    'q1': 'Q1\uff1a\u7a0b\u5e8f\u542f\u52a8\u540e\u6d4f\u89c8\u5668\u6ca1\u6709\u81ea\u52a8\u6253\u5f00\uff1f',
    'a1': 'A\uff1a\u8bf7\u624b\u52a8\u6253\u5f00\u6d4f\u89c8\u5668\uff0c\u8bbf\u95ee http://127.0.0.1:5000',
    'q2': 'Q2\uff1a\u89e3\u5bc6\u5931\u8d25\uff0c\u63d0\u793a\u5bc6\u94a5\u9519\u8bef\uff1f',
    'a2': 'A\uff1a\u8bf7\u68c0\u67e5\u4ee5\u4e0b\u51e0\u70b9\uff1a',
    'a2_1': '\u2022 \u786e\u8ba4\u5bc6\u94a5\u662f\u5426\u6b63\u786e\uff0864\u4f4d\u5341\u516d\u8fdb\u5236\uff09',
    'a2_2': '\u2022 \u786e\u8ba4\u5fae\u4fe1\u8d26\u53f7\u662f\u5426\u4e0e\u83b7\u53d6\u5bc6\u94a5\u65f6\u4e00\u81f4',
    'a2_3': '\u2022 \u91cd\u65b0\u4f7f\u7528 DbkeyHookUI.exe \u83b7\u53d6\u5bc6\u94a5',
    'q3': 'Q3\uff1a\u641c\u7d22\u4e0d\u5230\u804a\u5929\u8bb0\u5f55\uff1f',
    'a3': 'A\uff1a\u8bf7\u68c0\u67e5\u4ee5\u4e0b\u51e0\u70b9\uff1a',
    'a3_1': '\u2022 \u786e\u8ba4\u5df2\u6267\u884c\u5168\u91cf\u89e3\u5bc6',
    'a3_2': '\u2022 \u68c0\u67e5\u65e5\u671f\u8303\u56f4\u662f\u5426\u6b63\u786e',
    'a3_3': '\u2022 \u68c0\u67e5\u804a\u5929\u5bf9\u8c61\u540d\u79f0\u662f\u5426\u6b63\u786e\uff08\u652f\u6301\u6a21\u7cca\u5339\u914d\uff09',
    'q4': 'Q4\uff1a\u80a1\u7968\u7b5b\u9009\u529f\u80fd\u663e\u793a\u672a\u52a0\u8f7d\uff1f',
    'a4': 'A\uff1a\u70b9\u51fb\u3010\u52a0\u8f7d\u80a1\u7968\u6570\u636e\u3011\u6309\u94ae\u624b\u52a8\u52a0\u8f7d\uff0c\u6216\u68c0\u67e5\u7f51\u7edc\u8fde\u63a5\u662f\u5426\u6b63\u5e38\u3002',
    'q5': 'Q5\uff1aAI\u5206\u6790\u529f\u80fd\u65e0\u6cd5\u4f7f\u7528\uff1f',
    'a5': 'A\uff1a\u8bf7\u68c0\u67e5 config.xlsx \u4e2d\u7684AI\u914d\u7f6e\uff1a',
    'a5_1': '\u2022 llm_api_base\uff1aAPI\u5730\u5740\u662f\u5426\u6b63\u786e',
    'a5_2': '\u2022 llm_api_key\uff1aAPI\u5bc6\u94a5\u662f\u5426\u6709\u6548',
    'a5_3': '\u2022 llm_model\uff1a\u6a21\u578b\u540d\u79f0\u662f\u5426\u6b63\u786e',
    'q6': 'Q6\uff1a\u7a0b\u5e8f\u8fd0\u884c\u65f6\u51fa\u73b0\u9519\u8bef\uff1f',
    'a6': 'A\uff1a\u8bf7\u68c0\u67e5\u63a7\u5236\u53f0\u7a97\u53e3\u7684\u9519\u8bef\u4fe1\u606f\uff0c\u5e38\u89c1\u539f\u56e0\uff1a',
    'a6_1': '\u2022 config.xlsx \u6587\u4ef6\u4e0d\u5b58\u5728\u6216\u683c\u5f0f\u9519\u8bef',
    'a6_2': '\u2022 \u5fae\u4fe1\u6570\u636e\u8def\u5f84\u914d\u7f6e\u9519\u8bef',
    'a6_3': '\u2022 \u7aef\u53e35000\u88ab\u5176\u4ed6\u7a0b\u5e8f\u5360\u7528',
    'support': '\u3010\u6280\u672f\u652f\u6301\u3011',
    'support_desc': '\u5982\u6709\u5176\u4ed6\u95ee\u9898\uff0c\u8bf7\u8054\u7cfb\u56fd\u6d77\u8bc1\u5238\u91d1\u878d\u5de5\u7a0b\u56e2\u961f\u3002',
}

pdf_path = 'D:/gh_wx/dist/user_guide_v1.2.pdf'
doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)

styles = getSampleStyleSheet()
title_style = ParagraphStyle('TitleStyle', parent=styles['Title'], fontName='ChineseFont', fontSize=24, alignment=TA_CENTER, textColor=colors.HexColor('#4a9fd8'))
h1_style = ParagraphStyle('H1Style', parent=styles['Heading1'], fontName='ChineseFont', fontSize=18, spaceBefore=20, spaceAfter=12, textColor=colors.HexColor('#3d8bc4'))
h2_style = ParagraphStyle('H2Style', parent=styles['Heading2'], fontName='ChineseFont', fontSize=14, spaceBefore=15, spaceAfter=8)
body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontName='ChineseFont', fontSize=11, leading=18, spaceBefore=6, spaceAfter=6)
list_style = ParagraphStyle('ListStyle', parent=styles['Normal'], fontName='ChineseFont', fontSize=11, leading=18, leftIndent=20)
tip_style = ParagraphStyle('TipStyle', parent=styles['Normal'], fontName='ChineseFont', fontSize=10, backColor=colors.HexColor('#e8f4f8'), leftIndent=10, spaceBefore=8, spaceAfter=8)
warn_style = ParagraphStyle('WarnStyle', parent=styles['Normal'], fontName='ChineseFont', fontSize=10, backColor=colors.HexColor('#fff3cd'), leftIndent=10, spaceBefore=8, spaceAfter=8)
code_style = ParagraphStyle('CodeStyle', parent=styles['Code'], fontName='ChineseFont', fontSize=10, backColor=colors.HexColor('#f5f5f5'), leftIndent=20)

story = []

# Cover
story.append(Spacer(1, 3*cm))
story.append(Paragraph(T['title'], title_style))
story.append(Spacer(1, 1*cm))
story.append(Paragraph(T['guide'], ParagraphStyle('SubTitle', parent=styles['Title'], fontName='ChineseFont', fontSize=18, alignment=TA_CENTER, textColor=colors.HexColor('#666666'))))
story.append(Spacer(1, 2*cm))
story.append(Paragraph(T['intro'], body_style))
story.append(Paragraph(T['step1'], list_style))
story.append(Paragraph(T['step2'], list_style))
story.append(Paragraph(T['step3'], list_style))
story.append(Spacer(1, 3*cm))
story.append(Paragraph(T['version'], body_style))
story.append(PageBreak())

# Chapter 1
story.append(Paragraph(T['ch1'], h1_style))
story.append(Paragraph(T['ch1_intro'], body_style))
file_data = [[T['file_name'], T['file_desc']], ['DbkeyHookUI.exe', T['file1_desc']], ['config.xlsx', T['file2_desc']], [T['file3_name'], T['file3_desc']]]
file_table = Table(file_data, colWidths=[6*cm, 9*cm])
file_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a9fd8')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), ('FONTNAME', (0, 0), (-1, -1), 'ChineseFont'), ('FONTSIZE', (0, 0), (-1, -1), 10), ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc')), ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8)]))
story.append(Spacer(1, 0.5*cm))
story.append(file_table)
story.append(Spacer(1, 0.5*cm))
story.append(Paragraph(T['tip_same_dir'], tip_style))
story.append(PageBreak())

# Chapter 2
story.append(Paragraph(T['ch2'], h1_style))
story.append(Paragraph(T['ch2_1'], h2_style))
story.append(Paragraph(T['ch2_1_1'], list_style))
story.append(Paragraph(T['ch2_2'], h2_style))
story.append(Paragraph(T['step1_title'], body_style))
story.append(Paragraph(T['step1_desc'], body_style))
story.append(Paragraph(T['step2_title'], body_style))
story.append(Paragraph(T['step2_desc'], body_style))
story.append(Paragraph(T['step3_title'], body_style))
story.append(Paragraph(T['step3_desc'], body_style))
story.append(Spacer(1, 0.5*cm))
story.append(Paragraph(T['key_example'], warn_style))
story.append(Paragraph(T['key_sample'], code_style))
story.append(Spacer(1, 0.5*cm))
story.append(Paragraph(T['ch2_3'], h2_style))
story.append(Paragraph(T['path_step1_title'], body_style))
story.append(Paragraph(T['path_step1_desc'], body_style))
story.append(Paragraph(T['path_step2_title'], body_style))
story.append(Paragraph(T['path_step2_desc'], body_style))
story.append(Paragraph(T['path_step3_title'], body_style))
story.append(Paragraph(T['path_step3_desc'], body_style))
story.append(Spacer(1, 0.3*cm))
story.append(Paragraph(T['path_example_title'], body_style))
# Add screenshot if exists
screenshot_path = 'D:/gh_wx/dist/db_storage_screenshot.png'
if os.path.exists(screenshot_path):
    img = Image(screenshot_path, width=14*cm, height=9*cm)
    story.append(img)
story.append(Spacer(1, 0.3*cm))
story.append(Paragraph(T['path_example'], warn_style))
story.append(Paragraph(T['path_sample'], code_style))
story.append(Spacer(1, 0.5*cm))
story.append(Paragraph(T['save_title'], body_style))
story.append(Paragraph(T['save_desc'], body_style))
story.append(Paragraph(T['save1'], list_style))
story.append(Paragraph(T['save2'], list_style))
story.append(Spacer(1, 0.5*cm))
story.append(Paragraph(T['notes'], warn_style))
story.append(Paragraph(T['note1'], list_style))
story.append(Paragraph(T['note2'], list_style))
story.append(Paragraph(T['note3'], list_style))
story.append(Paragraph(T['note4'], list_style))
story.append(PageBreak())

# Chapter 3
story.append(Paragraph(T['ch3'], h1_style))
story.append(Paragraph(T['ch3_1'], h2_style))
story.append(Paragraph(T['ch3_1_desc'], body_style))
story.append(Paragraph(T['ch3_2'], h2_style))
config_data = [[T['config_item'], T['config_desc'], T['config_example']], [T['cfg1'], T['cfg1_desc'], T['cfg1_ex']], [T['cfg2'], T['cfg2_desc'], T['cfg2_ex']], [T['cfg3'], T['cfg3_desc'], T['cfg3_ex']], [T['cfg4'], T['cfg4_desc'], T['cfg4_ex']], [T['cfg5'], T['cfg5_desc'], T['cfg5_ex']], [T['cfg6'], T['cfg6_desc'], T['cfg6_ex']], [T['cfg7'], T['cfg7_desc'], T['cfg7_ex']], [T['cfg8'], T['cfg8_desc'], T['cfg8_ex']], [T['cfg9'], T['cfg9_desc'], T['cfg9_ex']], [T['cfg10'], T['cfg10_desc'], T['cfg10_ex']]]
config_table = Table(config_data, colWidths=[4*cm, 6*cm, 5*cm])
config_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a9fd8')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), ('FONTNAME', (0, 0), (-1, -1), 'ChineseFont'), ('FONTSIZE', (0, 0), (-1, -1), 9), ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc')), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
story.append(Spacer(1, 0.3*cm))
story.append(config_table)
story.append(Paragraph(T['ch3_3'], h2_style))
story.append(Paragraph(T['ch3_3_desc'], body_style))
story.append(Paragraph(T['req1'], list_style))
story.append(Paragraph(T['req2'], list_style))
story.append(Paragraph(T['ch3_4'], h2_style))
story.append(Paragraph(T['ch3_4_desc'], body_style))
story.append(Paragraph(T['tip_config'], tip_style))
story.append(PageBreak())

# Chapter 4
story.append(Paragraph(T['ch4'], h1_style))
story.append(Paragraph(T['ch4_1'], h2_style))
story.append(Paragraph(T['ch4_1_desc1'], body_style))
story.append(Paragraph(T['ch4_1_desc2'], body_style))
story.append(Paragraph(T['ch4_1_url'], code_style))
story.append(Paragraph(T['ch4_2'], h2_style))
story.append(Paragraph(T['ch4_2_desc'], body_style))
module_data = [[T['module'], T['module_desc']], [T['mod1'], T['mod1_desc']], [T['mod2'], T['mod2_desc']], [T['mod3'], T['mod3_desc']]]
module_table = Table(module_data, colWidths=[4*cm, 11*cm])
module_table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a9fd8')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), ('FONTNAME', (0, 0), (-1, -1), 'ChineseFont'), ('FONTSIZE', (0, 0), (-1, -1), 10), ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc')), ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8)]))
story.append(Spacer(1, 0.3*cm))
story.append(module_table)
story.append(Paragraph(T['ch4_3'], h2_style))
story.append(Paragraph(T['op1_title'], body_style))
story.append(Paragraph(T['op1_desc'], body_style))
story.append(Paragraph(T['op2_title'], body_style))
story.append(Paragraph(T['op2_desc'], body_style))
story.append(Paragraph(T['op2_1'], list_style))
story.append(Paragraph(T['op2_2'], list_style))
story.append(Paragraph(T['op2_3'], list_style))
story.append(Paragraph(T['op3_title'], body_style))
story.append(Paragraph(T['op3_desc'], body_style))
story.append(Paragraph(T['op3_1'], list_style))
story.append(Paragraph(T['op3_2'], list_style))
story.append(Paragraph(T['op3_3'], list_style))
story.append(Paragraph(T['op3_4'], list_style))
story.append(Paragraph(T['op3_btn'], body_style))
story.append(Paragraph(T['ch4_4'], h2_style))
story.append(Paragraph(T['ch4_4_desc'], body_style))
story.append(Paragraph(T['stock1'], list_style))
story.append(Paragraph(T['stock2'], list_style))
story.append(Paragraph(T['stock3'], list_style))
story.append(Paragraph(T['stock4'], list_style))
story.append(Paragraph(T['stock_tip'], tip_style))
story.append(Paragraph(T['ch4_5'], h2_style))
story.append(Paragraph(T['ch4_5_desc'], body_style))
story.append(Paragraph(T['ai1'], list_style))
story.append(Paragraph(T['ai2'], list_style))
story.append(Paragraph(T['ai3'], list_style))
story.append(Paragraph(T['ch4_6'], h2_style))
story.append(Paragraph(T['ch4_6_desc'], body_style))
story.append(Paragraph(T['ch4_6_btn'], body_style))
story.append(PageBreak())

# Chapter 5
story.append(Paragraph(T['ch5'], h1_style))
story.append(Paragraph(T['q1'], h2_style))
story.append(Paragraph(T['a1'], body_style))
story.append(Paragraph(T['q2'], h2_style))
story.append(Paragraph(T['a2'], body_style))
story.append(Paragraph(T['a2_1'], list_style))
story.append(Paragraph(T['a2_2'], list_style))
story.append(Paragraph(T['a2_3'], list_style))
story.append(Paragraph(T['q3'], h2_style))
story.append(Paragraph(T['a3'], body_style))
story.append(Paragraph(T['a3_1'], list_style))
story.append(Paragraph(T['a3_2'], list_style))
story.append(Paragraph(T['a3_3'], list_style))
story.append(Paragraph(T['q4'], h2_style))
story.append(Paragraph(T['a4'], body_style))
story.append(Paragraph(T['q5'], h2_style))
story.append(Paragraph(T['a5'], body_style))
story.append(Paragraph(T['a5_1'], list_style))
story.append(Paragraph(T['a5_2'], list_style))
story.append(Paragraph(T['a5_3'], list_style))
story.append(Paragraph(T['q6'], h2_style))
story.append(Paragraph(T['a6'], body_style))
story.append(Paragraph(T['a6_1'], list_style))
story.append(Paragraph(T['a6_2'], list_style))
story.append(Paragraph(T['a6_3'], list_style))
story.append(Spacer(1, 1*cm))
story.append(Paragraph(T['support'], h2_style))
story.append(Paragraph(T['support_desc'], body_style))

doc.build(story)
print(f'PDF generated: {pdf_path}')

