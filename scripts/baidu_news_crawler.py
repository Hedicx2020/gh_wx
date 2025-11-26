#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度新闻爬虫 - 抓取百度搜索结果中的新闻内容
"""

import re
import json
import time
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, parse_qs, unquote
from typing import Optional, Dict, List

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("请先安装依赖: pip install requests beautifulsoup4 lxml")
    exit(1)


class BaiduNewsCrawler:
    """百度新闻爬虫类"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def extract_news_links(self, search_url: str) -> List[Dict[str, str]]:
        """
        从百度搜索结果页面提取新闻链接
        
        Args:
            search_url: 百度搜索URL
            
        Returns:
            新闻链接列表，每个包含title和url
        """
        try:
            print(f"正在访问搜索页面: {search_url}")
            response = self.session.get(search_url, timeout=10)
            response.encoding = 'utf-8'
            
            if response.status_code != 200:
                print(f"访问失败，状态码: {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'lxml')
            news_links = []
            
            # 查找所有新闻结果
            # 百度搜索结果通常在 class 包含 "result" 或 "c-container" 的div中
            results = soup.find_all('div', class_=re.compile(r'result|c-container|news-item'))
            
            for result in results:
                # 查找标题链接
                title_elem = result.find('a', href=True)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    url = title_elem.get('href', '')
                    
                    # 处理百度跳转链接
                    if url.startswith('/link?url='):
                        # 提取真实URL
                        parsed = parse_qs(urlparse(url).query)
                        if 'url' in parsed:
                            url = unquote(parsed['url'][0])
                    
                    if title and url:
                        news_links.append({
                            'title': title,
                            'url': url
                        })
            
            # 如果上面的方法没找到，尝试其他选择器
            if not news_links:
                # 尝试查找所有链接
                all_links = soup.find_all('a', href=True)
                for link in all_links:
                    title = link.get_text(strip=True)
                    url = link.get('href', '')
                    
                    # 过滤掉无关链接
                    if title and len(title) > 10 and ('习近平' in title or '特朗普' in title or '电话' in title):
                        if url.startswith('http'):
                            news_links.append({
                                'title': title,
                                'url': url
                            })
            
            print(f"找到 {len(news_links)} 个新闻链接")
            return news_links[:10]  # 返回前10个结果
            
        except Exception as e:
            print(f"提取新闻链接时出错: {e}")
            return []
    
    def crawl_news_content(self, url: str) -> Optional[Dict[str, str]]:
        """
        爬取单个新闻页面的内容
        
        Args:
            url: 新闻URL
            
        Returns:
            包含标题、内容、来源等的字典
        """
        try:
            # 处理相对URL
            if url.startswith('/'):
                url = 'https://www.baidu.com' + url
            elif not url.startswith('http'):
                print(f"跳过无效URL: {url}")
                return None
            
            # 处理百度跳转链接
            if 'baidu.com/link' in url:
                # 尝试跟随重定向获取真实URL
                try:
                    response = self.session.get(url, timeout=10, allow_redirects=True)
                    url = response.url
                except:
                    pass
            
            print(f"正在爬取: {url}")
            response = self.session.get(url, timeout=10, allow_redirects=True)
            response.encoding = 'utf-8'
            
            if response.status_code != 200:
                print(f"访问失败，状态码: {response.status_code}")
                return None
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # 提取标题
            title = None
            title_selectors = ['h1', '.title', '.article-title', 'title']
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    if title and len(title) > 5:
                        break
            
            # 提取正文内容
            content = None
            content_selectors = [
                '.article-content',
                '.content',
                '.article-body',
                '.news-content',
                '#article',
                'article',
                '.text',
                '.main-content'
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    # 移除脚本和样式标签
                    for script in content_elem(['script', 'style', 'iframe']):
                        script.decompose()
                    content = content_elem.get_text(separator='\n', strip=True)
                    if content and len(content) > 100:
                        break
            
            # 如果没找到，尝试查找所有段落
            if not content:
                paragraphs = soup.find_all('p')
                content_parts = []
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if text and len(text) > 20:
                        content_parts.append(text)
                if content_parts:
                    content = '\n\n'.join(content_parts)
            
            # 提取来源
            source = None
            source_selectors = ['.source', '.author', '.origin', '.media-name']
            for selector in source_selectors:
                source_elem = soup.select_one(selector)
                if source_elem:
                    source = source_elem.get_text(strip=True)
                    if source:
                        break
            
            # 提取发布时间
            publish_time = None
            time_selectors = ['.time', '.publish-time', '.date', 'time']
            for selector in time_selectors:
                time_elem = soup.select_one(selector)
                if time_elem:
                    publish_time = time_elem.get_text(strip=True)
                    if publish_time:
                        break
            
            result = {
                'url': url,
                'title': title or '未找到标题',
                'content': content or '未找到内容',
                'source': source or '未知来源',
                'publish_time': publish_time or '未知时间',
                'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return result
            
        except Exception as e:
            print(f"爬取内容时出错: {e}")
            return None
    
    def crawl_from_search_url(self, search_url: str) -> List[Dict[str, str]]:
        """
        从百度搜索URL开始，爬取所有新闻内容
        
        Args:
            search_url: 百度搜索URL
            
        Returns:
            新闻内容列表
        """
        # 提取新闻链接
        news_links = self.extract_news_links(search_url)
        
        if not news_links:
            print("未找到新闻链接")
            return []
        
        # 爬取每个新闻的内容
        results = []
        for i, news in enumerate(news_links, 1):
            print(f"\n[{i}/{len(news_links)}] 处理: {news['title']}")
            content = self.crawl_news_content(news['url'])
            if content:
                content['title'] = news['title']  # 使用搜索结果中的标题
                results.append(content)
            time.sleep(1)  # 避免请求过快
        
        return results
    
    def save_results(self, results: List[Dict[str, str]], output_file: Optional[str] = None):
        """
        保存爬取结果到文件
        
        Args:
            results: 爬取结果列表
            output_file: 输出文件路径，如果为None则自动生成
        """
        if not results:
            print("没有结果可保存")
            return
        
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = Path(__file__).parent.parent / 'output' / 'news'
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f'新闻_{timestamp}.json'
        
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 保存为JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\n结果已保存到: {output_path}")
        
        # 同时保存为文本格式
        txt_path = output_path.with_suffix('.txt')
        with open(txt_path, 'w', encoding='utf-8') as f:
            for i, result in enumerate(results, 1):
                f.write(f"{'='*80}\n")
                f.write(f"新闻 {i}\n")
                f.write(f"{'='*80}\n")
                f.write(f"标题: {result['title']}\n")
                f.write(f"来源: {result['source']}\n")
                f.write(f"发布时间: {result['publish_time']}\n")
                f.write(f"URL: {result['url']}\n")
                f.write(f"爬取时间: {result['crawl_time']}\n")
                f.write(f"\n内容:\n{result['content']}\n\n")
        
        print(f"文本格式已保存到: {txt_path}")


def main():
    """主函数"""
    # 百度搜索URL
    search_url = "https://www.baidu.com/s?wd=%E4%B9%A0%E8%BF%91%E5%B9%B3%E5%90%8C%E7%89%B9%E6%9C%97%E6%99%AE%E9%80%9A%E7%94%B5%E8%AF%9D&sa=fyb_n_homepage&rsv_dl=fyb_n_homepage&from=super&cl=3&tn=baidutop10&fr=top1000"
    
    crawler = BaiduNewsCrawler()
    
    print("="*80)
    print("百度新闻爬虫")
    print("="*80)
    print(f"搜索关键词: 习近平同特朗普通电话")
    print()
    
    # 爬取新闻
    results = crawler.crawl_from_search_url(search_url)
    
    if results:
        # 保存结果
        crawler.save_results(results)
        
        # 打印摘要
        print("\n" + "="*80)
        print("爬取摘要")
        print("="*80)
        for i, result in enumerate(results, 1):
            print(f"\n[{i}] {result['title']}")
            print(f"    来源: {result['source']}")
            print(f"    时间: {result['publish_time']}")
            print(f"    内容长度: {len(result['content'])} 字符")
            print(f"    预览: {result['content'][:100]}...")
    else:
        print("\n未爬取到任何内容")


if __name__ == '__main__':
    main()

