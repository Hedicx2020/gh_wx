#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票K线复盘模块
使用 baostock 获取A股历史数据，pyecharts 生成带聊天标注的K线图
"""

import baostock as bs
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from pyecharts import options as opts
from pyecharts.charts import Kline, Bar, Grid, Line
from pyecharts.commons.utils import JsCode


class StockKlineReview:
    """股票K线复盘类"""
    
    def __init__(self):
        self._logged_in = False
        
    def _ensure_login(self):
        """确保已登录 baostock"""
        if not self._logged_in:
            lg = bs.login()
            if lg.error_code != '0':
                raise Exception(f"baostock登录失败: {lg.error_msg}")
            self._logged_in = True
    
    def _logout(self):
        """登出 baostock"""
        if self._logged_in:
            bs.logout()
            self._logged_in = False
    
    def get_stock_info(self, code: str) -> Dict:
        """
        获取股票基本信息
        
        Args:
            code: 股票代码，支持格式: 000001, sh.000001, 600000, sz.000001
            
        Returns:
            {'code': 'sh.600000', 'name': '浦发银行', 'market': 'sh'}
        """
        self._ensure_login()
        
        # 标准化股票代码
        normalized_code = self._normalize_code(code)
        
        # 查询股票基本信息
        rs = bs.query_stock_basic(code=normalized_code)
        if rs.error_code != '0':
            raise Exception(f"查询股票信息失败: {rs.error_msg}")
        
        data_list = []
        while rs.next():
            data_list.append(rs.get_row_data())
        
        if not data_list:
            raise Exception(f"未找到股票: {code}")
        
        # 返回第一条记录
        fields = rs.fields
        row = data_list[0]
        info = dict(zip(fields, row))
        
        return {
            'code': normalized_code,
            'name': info.get('code_name', ''),
            'market': 'sh' if normalized_code.startswith('sh') else 'sz',
            'industry': info.get('industry', ''),
            'ipoDate': info.get('ipoDate', '')
        }
    
    def _normalize_code(self, code: str) -> str:
        """
        标准化股票代码为 baostock 格式
        
        Args:
            code: 输入代码，如 000001, sh000001, 600000 等
            
        Returns:
            标准格式如 sh.600000, sz.000001
        """
        code = code.strip().lower()
        
        # 如果已经是标准格式
        if '.' in code and (code.startswith('sh.') or code.startswith('sz.')):
            return code
        
        # 移除可能的前缀
        if code.startswith('sh') or code.startswith('sz'):
            market = code[:2]
            code_num = code[2:]
            if code_num.startswith('.'):
                code_num = code_num[1:]
            return f"{market}.{code_num}"
        
        # 根据代码规则判断市场
        # 6开头为上海，0/3开头为深圳
        if code.startswith('6'):
            return f"sh.{code}"
        elif code.startswith('0') or code.startswith('3'):
            return f"sz.{code}"
        else:
            # 默认尝试上海
            return f"sh.{code}"
    
    def get_kline_data(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取股票日K线数据
        
        Args:
            code: 股票代码
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            
        Returns:
            DataFrame with columns: date, open, high, low, close, volume, amount, turn
        """
        self._ensure_login()
        
        normalized_code = self._normalize_code(code)
        
        rs = bs.query_history_k_data_plus(
            normalized_code,
            "date,open,high,low,close,volume,amount,turn,pctChg",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="2"  # 前复权
        )
        
        if rs.error_code != '0':
            raise Exception(f"获取K线数据失败: {rs.error_msg}")
        
        data_list = []
        while rs.next():
            data_list.append(rs.get_row_data())
        
        if not data_list:
            raise Exception(f"未获取到K线数据，请检查日期范围")
        
        df = pd.DataFrame(data_list, columns=rs.fields)
        
        # 转换数据类型
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn', 'pctChg']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    
    def generate_kline_chart(
        self,
        kline_data: pd.DataFrame,
        messages: List[Dict],
        stock_name: str = "",
        stock_code: str = ""
    ) -> str:
        """
        生成带聊天标注的K线图
        
        Args:
            kline_data: K线数据 DataFrame
            messages: 聊天记录列表 [{'time': 'YYYY-MM-DD HH:MM:SS', 'content': '...', ...}]
            stock_name: 股票名称
            stock_code: 股票代码
            
        Returns:
            HTML字符串
        """
        if kline_data.empty:
            return "<div style='text-align:center;padding:50px;color:#999;'>无K线数据</div>"
        
        # 准备K线数据
        dates = kline_data['date'].tolist()
        kline_values = kline_data[['open', 'close', 'low', 'high']].values.tolist()
        volumes = kline_data['volume'].tolist()
        
        # 按日期聚合聊天记录
        msg_by_date = self._aggregate_messages_by_date(messages)
        
        # 准备标记点数据
        mark_points = []
        for date, msgs in msg_by_date.items():
            if date in dates:
                idx = dates.index(date)
                # 获取当日最高价作为标记位置
                high_price = kline_data.iloc[idx]['high']
                # 汇总当日消息
                summary = self._format_message_summary(msgs)
                mark_points.append({
                    'coord': [date, float(high_price)],
                    'value': len(msgs),
                    'name': date,
                    'itemStyle': {'color': '#ff6b6b'},
                    'label': {
                        'show': True,
                        'formatter': str(len(msgs)),
                        'color': '#fff',
                        'fontSize': 10
                    },
                    'summary': summary,
                    'messages': msgs
                })
        
        # 计算涨跌颜色
        def get_item_style(idx):
            if idx == 0:
                return '#ec0000' if kline_values[idx][1] >= kline_values[idx][0] else '#00da3c'
            return '#ec0000' if kline_values[idx][1] >= kline_values[idx - 1][1] else '#00da3c'
        
        # 创建K线图
        kline = (
            Kline()
            .add_xaxis(dates)
            .add_yaxis(
                series_name=f"{stock_name}",
                y_axis=kline_values,
                itemstyle_opts=opts.ItemStyleOpts(
                    color="#ec0000",
                    color0="#00da3c",
                    border_color="#ec0000",
                    border_color0="#00da3c",
                ),
                markpoint_opts=opts.MarkPointOpts(
                    data=[
                        opts.MarkPointItem(
                            coord=mp['coord'],
                            value=mp['value'],
                            symbol='circle',
                            symbol_size=20,
                            itemstyle_opts=opts.ItemStyleOpts(color='#4a9fd8'),
                            label_opts=opts.LabelOpts(
                                is_show=True,
                                formatter=JsCode("function(params){return params.value;}"),
                                color='#fff',
                                font_size=10
                            )
                        )
                        for mp in mark_points
                    ]
                ) if mark_points else None
            )
            .set_global_opts(
                title_opts=opts.TitleOpts(
                    title=f"{stock_name} ({stock_code}) K线复盘",
                    subtitle=f"数据区间: {dates[0]} ~ {dates[-1]}" if dates else "",
                    title_textstyle_opts=opts.TextStyleOpts(
                        font_family="Courier New, monospace",
                        font_size=16,
                        color="#4a9fd8"
                    ),
                    subtitle_textstyle_opts=opts.TextStyleOpts(
                        font_family="Courier New, monospace",
                        font_size=12,
                        color="#666"
                    )
                ),
                xaxis_opts=opts.AxisOpts(
                    type_="category",
                    is_scale=True,
                    boundary_gap=False,
                    axisline_opts=opts.AxisLineOpts(is_on_zero=False),
                    splitline_opts=opts.SplitLineOpts(is_show=False),
                    split_number=20,
                    min_="dataMin",
                    max_="dataMax",
                ),
                yaxis_opts=opts.AxisOpts(
                    is_scale=True,
                    splitarea_opts=opts.SplitAreaOpts(
                        is_show=True,
                        areastyle_opts=opts.AreaStyleOpts(opacity=1)
                    ),
                ),
                tooltip_opts=opts.TooltipOpts(
                    trigger="axis",
                    axis_pointer_type="cross",
                    background_color="rgba(255,255,255,0.95)",
                    border_color="#4a9fd8",
                    border_width=1,
                    textstyle_opts=opts.TextStyleOpts(color="#333"),
                    formatter=JsCode(
                        """function(params){
                            var date = params[0].axisValue;
                            var res = '<div style="font-family: Courier New, monospace; max-width: 400px;">';
                            res += '<div style="font-weight:bold; color:#4a9fd8; border-bottom:1px dashed #ccc; padding-bottom:5px; margin-bottom:8px;">[' + date + ']</div>';
                            if(params[0] && params[0].data){
                                var d = params[0].data;
                                var change = ((d[2] - d[1]) / d[1] * 100).toFixed(2);
                                var changeColor = change >= 0 ? '#ec0000' : '#00da3c';
                                res += '<div style="display:flex; flex-wrap:wrap; gap:8px; margin-bottom:8px;">';
                                res += '<span>开: ' + d[1] + '</span>';
                                res += '<span>收: <span style="color:'+changeColor+'">' + d[2] + '</span></span>';
                                res += '<span>低: ' + d[3] + '</span>';
                                res += '<span>高: ' + d[4] + '</span>';
                                res += '<span style="color:'+changeColor+'">(' + (change >= 0 ? '+' : '') + change + '%)</span>';
                                res += '</div>';
                            }
                            // 显示当天聊天记录
                            if(window.KLINE_MESSAGES && window.KLINE_MESSAGES[date]){
                                var msgs = window.KLINE_MESSAGES[date];
                                res += '<div style="border-top:1px solid #eee; padding-top:8px; margin-top:5px;">';
                                res += '<div style="color:#4a9fd8; font-size:11px; margin-bottom:5px;">📝 聊天记录 (' + msgs.length + '条)</div>';
                                var showCount = Math.min(msgs.length, 5);
                                for(var i=0; i<showCount; i++){
                                    var m = msgs[i];
                                    var content = m.content.length > 60 ? m.content.substring(0,60)+'...' : m.content;
                                    res += '<div style="font-size:11px; padding:4px 0; border-bottom:1px dotted #eee;">';
                                    res += '<span style="color:#666;">[' + m.sender + ']</span> ';
                                    res += '<span style="color:#333;">' + content + '</span>';
                                    res += '</div>';
                                }
                                if(msgs.length > 5){
                                    res += '<div style="font-size:10px; color:#999; text-align:center; padding-top:5px;">... 还有 ' + (msgs.length - 5) + ' 条消息</div>';
                                }
                                res += '</div>';
                            }
                            return res + '</div>';
                        }"""
                    )
                ),
                datazoom_opts=[
                    opts.DataZoomOpts(
                        is_show=True,
                        type_="inside",
                        xaxis_index=[0, 1],
                        range_start=0,
                        range_end=100,
                    ),
                    opts.DataZoomOpts(
                        is_show=True,
                        xaxis_index=[0, 1],
                        type_="slider",
                        pos_top="90%",
                        range_start=0,
                        range_end=100,
                    ),
                ],
                toolbox_opts=opts.ToolboxOpts(
                    is_show=True,
                    feature={
                        "dataZoom": {"yAxisIndex": "none"},
                        "restore": {},
                        "saveAsImage": {}
                    }
                ),
            )
        )
        
        # 创建成交量柱状图
        bar = (
            Bar()
            .add_xaxis(dates)
            .add_yaxis(
                series_name="成交量",
                y_axis=volumes,
                xaxis_index=1,
                yaxis_index=1,
                label_opts=opts.LabelOpts(is_show=False),
                itemstyle_opts=opts.ItemStyleOpts(
                    color=JsCode(
                        """function(params) {
                            var colorList;
                            if (params.data >= 0) {
                                colorList = '#ec0000';
                            } else {
                                colorList = '#00da3c';
                            }
                            return colorList;
                        }"""
                    )
                ),
            )
            .set_global_opts(
                xaxis_opts=opts.AxisOpts(
                    type_="category",
                    grid_index=1,
                    axislabel_opts=opts.LabelOpts(is_show=False),
                ),
                yaxis_opts=opts.AxisOpts(
                    grid_index=1,
                    split_number=2,
                    axislabel_opts=opts.LabelOpts(is_show=False),
                    axisline_opts=opts.AxisLineOpts(is_show=False),
                    axistick_opts=opts.AxisTickOpts(is_show=False),
                    splitline_opts=opts.SplitLineOpts(is_show=False),
                ),
                legend_opts=opts.LegendOpts(is_show=False),
            )
        )
        
        # 组合图表
        grid = (
            Grid(init_opts=opts.InitOpts(
                width="100%",
                height="500px",
                bg_color="#fff"
            ))
            .add(
                kline,
                grid_opts=opts.GridOpts(
                    pos_left="10%",
                    pos_right="8%",
                    pos_top="10%",
                    height="55%"
                ),
            )
            .add(
                bar,
                grid_opts=opts.GridOpts(
                    pos_left="10%",
                    pos_right="8%",
                    pos_top="70%",
                    height="15%"
                ),
            )
        )
        
        # 渲染为HTML
        html = grid.render_embed()
        
        # 添加聊天记录标注的交互脚本
        if mark_points:
            msg_data_js = self._generate_message_data_js(msg_by_date, dates)
            html = html.replace('</body>', f'{msg_data_js}</body>')
        
        return html
    
    def _aggregate_messages_by_date(self, messages: List[Dict]) -> Dict[str, List[Dict]]:
        """
        按日期聚合聊天记录（已去重）
        
        Args:
            messages: 聊天记录列表
            
        Returns:
            {date: [messages]}
        """
        msg_by_date = {}
        seen = set()
        
        for msg in messages:
            time_str = msg.get('time', '')
            if not time_str:
                continue
            
            # 提取日期部分
            date = time_str.split(' ')[0]
            
            # 去重: 同一日+聊天对象+发送者+内容
            dedup_key = f"{date}|{msg.get('chat_name', '')}|{msg.get('sender', '')}|{msg.get('content', '')}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            
            if date not in msg_by_date:
                msg_by_date[date] = []
            msg_by_date[date].append(msg)
        
        return msg_by_date
    
    def _format_message_summary(self, messages: List[Dict], max_chars: int = 100) -> str:
        """格式化消息摘要"""
        if not messages:
            return ""
        
        summaries = []
        for msg in messages[:3]:  # 最多显示3条
            sender = msg.get('sender', '未知')
            content = msg.get('content', '')[:50]
            if len(msg.get('content', '')) > 50:
                content += '...'
            summaries.append(f"[{sender}] {content}")
        
        result = '\n'.join(summaries)
        if len(messages) > 3:
            result += f"\n... 还有 {len(messages) - 3} 条"
        
        return result
    
    def _generate_message_data_js(self, msg_by_date: Dict, dates: List[str]) -> str:
        """生成消息数据的JavaScript代码"""
        import json
        
        # 转换为JSON安全格式
        safe_data = {}
        for date, msgs in msg_by_date.items():
            if date in dates:
                safe_data[date] = [
                    {
                        'time': m.get('time', ''),
                        'chat_name': m.get('chat_name', ''),
                        'sender': m.get('sender', ''),
                        'content': m.get('content', '')[:200]
                    }
                    for m in msgs
                ]
        
        js_code = f"""
        <script>
        window.KLINE_MESSAGES = {json.dumps(safe_data, ensure_ascii=False)};
        </script>
        """
        return js_code
    
    def __del__(self):
        """析构时登出"""
        self._logout()


# 模块级便捷函数
_instance: Optional[StockKlineReview] = None


def get_kline_reviewer() -> StockKlineReview:
    """获取全局K线复盘实例"""
    global _instance
    if _instance is None:
        _instance = StockKlineReview()
    return _instance


def get_stock_info(code: str) -> Dict:
    """获取股票信息"""
    return get_kline_reviewer().get_stock_info(code)


def get_kline_data(code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """获取K线数据"""
    return get_kline_reviewer().get_kline_data(code, start_date, end_date)


def generate_kline_chart(
    kline_data: pd.DataFrame,
    messages: List[Dict],
    stock_name: str = "",
    stock_code: str = ""
) -> str:
    """生成K线图HTML"""
    return get_kline_reviewer().generate_kline_chart(
        kline_data, messages, stock_name, stock_code
    )


