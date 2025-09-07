#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
涨停透视数据爬虫 - 完善版（支持历史数据查询）
使用方法：
  python ztts_crawler_enhanced.py              # 获取最新数据并推送
  python ztts_crawler_enhanced.py 2025-01-21   # 获取指定日期数据
"""

import os
import json
import time
import sys
import subprocess
import requests
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.options import Options

# 配置
TARGET_URL = "https://webrelease.dzh.com.cn/htmlweb/ztts/index.php"
DATA_DIR = "dzh_ztts"
WAIT_TIME = 25  # 增加等待时间确保数据完全加载

def get_latest_trading_day():
    """获取最新交易日"""
    current_date = datetime.now().date()
    while current_date.weekday() >= 5:  # 周末
        current_date -= timedelta(days=1)
    
    # 如果是今天但在9点前，返回前一个交易日
    if current_date == datetime.now().date() and datetime.now().hour < 9:
        current_date -= timedelta(days=1)
        while current_date.weekday() >= 5:
            current_date -= timedelta(days=1)
    
    return current_date

def parse_date(date_str):
    """解析日期字符串"""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except:
        return get_latest_trading_day()

def get_file_paths(date_obj):
    """获取文件路径"""
    year_month = date_obj.strftime('%Y-%m')
    date_str = date_obj.strftime('%Y-%m-%d')
    
    month_dir = os.path.join(DATA_DIR, year_month)
    os.makedirs(month_dir, exist_ok=True)
    
    return {
        'json': os.path.join(month_dir, f"{date_str}.json"),
        'txt': os.path.join(month_dir, f"{date_str}.txt"),
        'date_str': date_str
    }

def git_push_data(date_str):
    """推送数据到GitHub"""
    print(f"🚀 推送数据到GitHub...")
    
    try:
        # 先拉取远程更改
        subprocess.run(r'"D:\Git\cmd\git.exe" pull origin main', shell=True, check=True)
        
        # 添加文件
        subprocess.run(r'"D:\Git\cmd\git.exe" add dzh_ztts/', shell=True, check=True)
        
        # 提交更改
        subprocess.run(rf'"D:\Git\cmd\git.exe" commit -m "Update 涨停透视数据 {date_str}"', shell=True, check=True)
        
        # 推送
        subprocess.run(r'"D:\Git\cmd\git.exe" push', shell=True, check=True)
        
        print(f"✅ 推送成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 推送失败: {e}")
        print(f"💡 请稍后手动推送: git push")
        return False

def get_ladder_data_via_api(date_str):
    """通过API获取涨停梯队个股数据"""
    api_date = date_str.replace('-', '')  # 2025-01-21 -> 20250121
    
    url = "https://webrelease.dzh.com.cn/htmlweb/ztts/api.php"
    params = {'service': 'getZttdData', 'date': api_date}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Referer': 'https://webrelease.dzh.com.cn/htmlweb/ztts/index.php'
    }
    
    try:
        print(f"🌐 获取涨停梯队API数据...")
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        if data.get('code') == 0:
            print(f"✅ 涨停梯队数据获取成功，共 {len(data.get('data', []))} 只股票")
            return process_ladder_data(data['data'])
        else:
            print(f"❌ API返回错误: {data.get('msg', '未知错误')}")
            return {}
            
    except Exception as e:
        print(f"❌ API请求失败: {e}")
        return {}

def get_market_type(code):
    """根据股票代码判断市场类型"""
    if code.startswith('SH60'):
        return '沪市主板'
    elif code.startswith('SH68'):
        return '科创板'
    elif code.startswith('SZ00'):
        return '深市主板'
    elif code.startswith('SZ30'):
        return '创业板'
    elif code.startswith('BJ'):
        return '北交所'
    return '其他'

def process_ladder_data(api_data):
    """处理涨停梯队数据"""
    board_groups = {}
    market_count = {}
    
    for item in api_data:
        bnum = item['bnum']  # 板数
        market = get_market_type(item['code'])
        
        if bnum not in board_groups:
            board_groups[bnum] = []
        
        stock_data = {
            'code': item['code'],
            'name': item['name'],
            'close_price': item['close'],
            'change_rate': round(item['zf'] * 100, 2),
            'turnover_rate': round(item['fbrate'] * 100, 2),
            'dnum': item['dnum'],
            'bnum': item['bnum'],
            'board_label': f"{item['dnum']}天{item['bnum']}板",
            'market': market
        }
        
        board_groups[bnum].append(stock_data)
        market_count[market] = market_count.get(market, 0) + 1
    
    # 按板数从高到低排序
    sorted_board_groups = dict(sorted(board_groups.items(), key=lambda x: x[0], reverse=True))
    
    return {
        'ladder_stocks': {f"{k}板": v for k, v in sorted_board_groups.items()},
        'market_distribution': market_count,
        'board_distribution': {f"{k}板": len(v) for k, v in sorted_board_groups.items()}
    }

class ZTTSCrawler:
    def __init__(self, target_date):
        self.target_date = target_date
        self.actual_date = None
        self.driver = None
    
    def setup_driver(self):
        """设置浏览器"""
        print(f"🚀 设置浏览器...")
        
        options = Options()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        
        self.driver = webdriver.Edge(options=options)
    
    
    def navigate_to_date(self, target_date_str):
        """导航到指定日期"""
        print(f"📅 尝试导航到日期: {target_date_str}")
        
        # 获取当前页面日期
        current_date = self.get_current_date()
        
        if not current_date:
            print(f"❌ 无法获取当前日期")
            return False
        
        target_date_obj = datetime.strptime(target_date_str, '%Y%m%d').date()
        current_date_obj = datetime.strptime(current_date, '%Y%m%d').date()
        
        print(f"📅 当前页面日期: {current_date_obj}, 目标日期: {target_date_obj}")
        
        if current_date_obj == target_date_obj:
            print(f"✅ 已在目标日期")
            return True
        
        # 计算需要点击的次数和方向
        days_diff = (current_date_obj - target_date_obj).days
        
        if days_diff > 0:
            button_selector = '.prev'
            print(f"⬅️ 需要往前翻 {abs(days_diff)} 天")
        else:
            button_selector = '.next'
            print(f"➡️ 需要往后翻 {abs(days_diff)} 天")
        
        # 执行点击操作
        for i in range(abs(days_diff)):
            try:
                button = self.driver.find_element(By.CSS_SELECTOR, button_selector)
                if 'disable' in button.get_attribute('class'):
                    print(f"❌ 按钮已禁用，无法继续翻页")
                    break
                
                button.click()
                print(f"🔄 执行第 {i+1} 次点击...")
                
                # 等待更长时间确保数据更新
                time.sleep(20)  # 增加到8秒
                
                # 多次检查日期是否更新
                for check_attempt in range(5):
                    new_date = self.get_current_date()
                    if new_date != current_date:
                        print(f"📅 日期已更新: {new_date}")
                        current_date = new_date
                        break
                    time.sleep(1)
                
                # 检查是否到达目标日期
                if current_date == target_date_str:
                    print(f"✅ 成功导航到目标日期")
                    return True
                    
            except Exception as e:
                print(f"❌ 点击按钮失败: {e}")
                break
        
        print(f"⚠️ 导航完成，最终日期: {current_date}")
        return current_date == target_date_str


    def get_current_date(self):
        """获取当前页面显示的日期"""
        try:
            script = """
            try {
                var app = document.querySelector('#app').__vue__;
                // 修改：优先使用today，因为它更准确反映选中的日期
                return app.today || app.thisDay || null;
            } catch (error) {
                return null;
            }
            """
            
            result = self.driver.execute_script(script)
            return result
            
        except:
            return None

    
    def crawl_data(self):
        """爬取数据"""
        print(f"🕷️ 开始爬取数据（目标日期：{self.target_date}）...")
        
        self.setup_driver()
        
        try:
            # 访问页面
            self.driver.get(TARGET_URL)
            
            # 等待加载
            wait = WebDriverWait(self.driver, 30)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            print(f"⏳ 等待Vue应用加载 {WAIT_TIME} 秒...")
            time.sleep(WAIT_TIME)
            
            # 获取当前页面日期
            current_date = self.get_current_date()
            print(f"📅 页面加载完成，当前日期: {current_date}")
            
            # 如果需要，导航到目标日期
            target_date_str = self.target_date.strftime('%Y%m%d')
            if current_date != target_date_str:
                success = self.navigate_to_date(target_date_str)
                if not success:
                    print(f"❌ 无法导航到目标日期，使用当前页面数据")
                
                # 等待数据更新
                time.sleep(5)
            
            # 获取实际数据日期
            self.actual_date = self.get_actual_date()
            print(f"📅 实际数据日期: {self.actual_date}")
            
            # 提取基础数据
            base_data = self.extract_data()
            
            if base_data:
                print("✅ 基础数据爬取成功")
                
                # 获取涨停梯队数据（API）
                date_str = self.actual_date.strftime('%Y-%m-%d')
                ladder_data = get_ladder_data_via_api(date_str)
                
                # 合并数据
                base_data['涨停梯队数据'] = ladder_data
                
                return base_data
            else:
                print("❌ 基础数据爬取失败")
                return None
                
        finally:
            if self.driver:
                self.driver.quit()
    
    def get_actual_date(self):
        """获取页面实际数据日期"""
        try:
            current_date = self.get_current_date()
            if current_date and len(current_date) >= 8:
                return datetime.strptime(current_date, '%Y%m%d').date()
            
            return self.target_date
            
        except:
            return self.target_date
    
    def extract_data(self):
        """提取Vue数据和DOM文本"""
        script = """
        try {
            var app = document.querySelector('#app').__vue__;
            if (!app) return {error: 'Vue实例未找到'};
            
            // 从DOM获取解读文本
            var analysisElement = document.querySelector('.mod-introduction');
            var analysisText = analysisElement ? analysisElement.innerText.trim() : '';
            
            // 提取完整的解读段落
            var analysisLines = analysisText.split('\\n').filter(line => line.trim());
            var fullAnalysis = analysisLines.join('\\n\\n');
            
            return {
                爬取时间: new Date().toISOString(),
                实际数据日期: app.thisDay || app.today || null,
                
                // 解读文本（从DOM获取）
                完整解读文本: fullAnalysis,
                
                // 核心数据
                活跃资金情绪: app.todayMarketSense,
                封板率: app.todayStat ? app.todayStat.lufb : null,
                涨停数量: app.todayStat ? app.todayStat.lu : null,
                涨停打开数量: app.todayStat ? app.todayStat.luop : null,
                跌停数量: app.todayStat ? app.todayStat.ld : null,
                跌停封板率: app.todayStat ? app.todayStat.ldfb : null,
                跌停打开数量: app.todayStat ? app.todayStat.ldop : null,
                
                昨日涨停数量: app.yesterdayStat ? app.yesterdayStat.lu : null,
                昨日封板率: app.yesterdayStat ? app.yesterdayStat.lufb : null,
                昨日涨停打开数量: app.yesterdayStat ? app.yesterdayStat.luop : null,
                昨日跌停数量: app.yesterdayStat ? app.yesterdayStat.ld : null,
                昨日跌停封板率: app.yesterdayStat ? app.yesterdayStat.ldfb : null,
                昨日跌停打开数量: app.yesterdayStat ? app.yesterdayStat.ldop : null,
                
                // 连板统计
                最高板数: app.todayMaxban,
                连板家数: app.todayLbnum,
                自然板家数: app.todayZrb,
                触及涨停: app.todayCjzt,
                
                // 趋势分析数据（完整的todayWad对象）
                今日涨停数量: app.todayWad ? app.todayWad.num : null,
                百日排名: app.todayWad ? app.todayWad.rank100 : null,
                五日平均: app.todayWad ? app.todayWad.avg5 : null,
                趋势类型: app.todayWad ? app.todayWad.type : null,
                连续天数: app.todayWad ? app.todayWad.days : null,
                
                // 完整的todayWad对象用于分析
                todayWad完整数据: app.todayWad,
                
                // 其他实时数据
                昨日涨停今日表现: app.zrztRate || null,
                上证指数表现: app.shRate || null
            };
        } catch (error) {
            return {error: error.toString()};
        }
        """
        
        try:
            result = self.driver.execute_script(script)
            if 'error' in result:
                print(f"❌ 数据提取失败: {result['error']}")
                return None
            return result
        except Exception as e:
            print(f"❌ 数据提取异常: {e}")
            return None

class DataFormatter:
    def __init__(self, data, actual_date):
        self.data = data
        self.actual_date = actual_date
    
    def format_percent(self, value):
        """格式化百分比"""
        if value is None:
            return "暂无数据"
        try:
            float_value = float(value)
            if float_value > 1:
                return f"{float_value:.2f}%"
            else:
                return f"{float_value * 100:.2f}%"
        except:
            return str(value)
    
    def format_number(self, value):
        """格式化数字"""
        if value is None:
            return "暂无数据"
        try:
            return str(int(float(value)))
        except:
            return str(value)
    
    def generate_analysis_from_dom(self):
        """从DOM解读文本中提取分析信息"""
        full_text = self.data.get('完整解读文本', '')
        
        if not full_text:
            return self.generate_fallback_analysis()
        
        # 直接返回从DOM获取的完整解读文本
        return full_text
    
    def generate_fallback_analysis(self):
        """备用分析生成（当DOM文本获取失败时）"""
        todayWad = self.data.get('todayWad完整数据', {})
        
        if not todayWad:
            return "暂无分析数据"
        
        num = todayWad.get('num', 0)
        rank = todayWad.get('rank100', 0)
        avg5 = todayWad.get('avg5', 0)
        days = todayWad.get('days', 0)
        trend_type = todayWad.get('type', 0)
        
        # 趋势判断
        trend = "上升" if trend_type == 1 else "下降"
        
        # 情绪强度判断
        if rank <= 20:
            strength = "很强"
        elif rank <= 40:
            strength = "较强"
        elif rank <= 60:
            strength = "一般"
        elif rank <= 80:
            strength = "较弱"
        else:
            strength = "很弱"
        
        date_text = "今日" if self.actual_date == datetime.now().date() else f"{self.actual_date.strftime('%m月%d日')}"
        
        analysis_text = f"解读：{date_text}涨停数量{num}，在过去100个交易日中排名{rank}位，涨停数量连续{days}个交易日{trend}；\n\n"
        analysis_text += f"市场中线赚钱效应{strength}，赚钱效应有{trend}趋势。"
        
        return analysis_text
    
    def generate_txt(self):
        """生成TXT报告"""
        date_str = self.actual_date.strftime('%Y年%m月%d日')
        time_str = datetime.now().strftime('%H:%M:%S')
        
        lines = []
        lines.append("=" * 60)
        lines.append(f"大智慧涨停透视 - {date_str}")
        lines.append(f"更新时间：{time_str}")
        lines.append("=" * 60)
        lines.append("")
        
        # 添加完整的解读文本
        analysis_text = self.generate_analysis_from_dom()
        lines.append("【市场分析解读】")
        lines.append("-" * 40)
        lines.append(analysis_text)
        lines.append("")
        
        lines.append("【核心指标统计】")
        lines.append("-" * 40)
        lines.append(f"活跃资金情绪：{self.format_percent(self.data.get('活跃资金情绪'))}")
        lines.append(f"封板率：{self.format_percent(self.data.get('封板率'))}")
        lines.append(f"最高板数：{self.format_number(self.data.get('最高板数'))}板")
        lines.append(f"连板家数：{self.format_number(self.data.get('连板家数'))}家")
        lines.append(f"自然板家数：{self.format_number(self.data.get('自然板家数'))}家")
        lines.append(f"触及涨停：{self.format_number(self.data.get('触及涨停'))}家")
        lines.append("")
        
        date_prefix = "今日" if self.actual_date == datetime.now().date() else "当日"
        lines.append(f"【{date_prefix}vs前一日对比】")
        lines.append("-" * 40)
        
        comparisons = [
            ("涨停板", "涨停数量", "昨日涨停数量"),
            ("涨停封板率", "封板率", "昨日封板率"),
            ("涨停打开", "涨停打开数量", "昨日涨停打开数量"),
            ("跌停板", "跌停数量", "昨日跌停数量"),
            ("跌停封板率", "跌停封板率", "昨日跌停封板率"),
            ("跌停打开", "跌停打开数量", "昨日跌停打开数量")
        ]
        
        for name, today_key, yesterday_key in comparisons:
            lines.append(f"{name}：")
            if "率" in name:
                lines.append(f"  {date_prefix}：{self.format_percent(self.data.get(today_key))}")
                lines.append(f"  前一日：{self.format_percent(self.data.get(yesterday_key))}")
            else:
                lines.append(f"  {date_prefix}：{self.format_number(self.data.get(today_key))}")
                lines.append(f"  前一日：{self.format_number(self.data.get(yesterday_key))}")
            lines.append("")
        
        # 添加涨停梯队信息
        ladder_data = self.data.get('涨停梯队数据', {})
        if ladder_data.get('ladder_stocks'):
            lines.append("【涨停梯队详情】")
            lines.append("=" * 60)
            
            # 添加板数分布
            board_dist = ladder_data.get('board_distribution', {})
            if board_dist:
                lines.append("")
                lines.append("板数分布：")
                for board_type, count in board_dist.items():
                    if count > 0:
                        lines.append(f"  {board_type}: {count}只")
            
            # 添加市场分布
            market_dist = ladder_data.get('market_distribution', {})
            if market_dist:
                lines.append("")
                lines.append("市场分布：")
                for market, count in market_dist.items():
                    lines.append(f"  {market}: {count}只")
            
            # 添加详细个股信息
            ladder_stocks = ladder_data.get('ladder_stocks', {})
            if ladder_stocks:
                lines.append("")
                lines.append("详细个股：")
                # 按板数从高到低排序
                sorted_boards = sorted(ladder_stocks.keys(), key=lambda x: int(x.replace('板', '')), reverse=True)
                
                for board_type in sorted_boards:
                    stocks = ladder_stocks[board_type]
                    if stocks and len(stocks) > 0:
                        lines.append("")
                        lines.append(f"{board_type} ({len(stocks)}只)：")
                        lines.append("-" * 40)
                        for i, stock in enumerate(stocks, 1):
                            lines.append(f"{i}. {stock['name']} ({stock['code']}) - {stock['market']}")
                            lines.append(f"   收盘价: {stock['close_price']:.2f}元  涨幅: {stock['change_rate']:.2f}%")
                            lines.append(f"   连板标签: {stock['board_label']}")
                            lines.append("")
        
        lines.append("【数据说明】")
        lines.append("-" * 40)
        lines.append(f"数据来源：大智慧涨停透视")
        lines.append(f"数据日期：{self.actual_date}")
        lines.append(f"爬取时间：{self.data.get('爬取时间', '未知')}")
        lines.append("")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def generate_json(self):
        """生成JSON报告"""
        # 获取涨停梯队数据
        ladder_data = self.data.get('涨停梯队数据', {})
        
        return {
            "报告信息": {
                "生成时间": datetime.now().isoformat(),
                "数据日期": self.actual_date.strftime('%Y-%m-%d'),
                "数据来源": "大智慧涨停透视"
            },
            "市场分析": {
                "完整解读": self.generate_analysis_from_dom(),
                "分析来源": "页面DOM提取"
            },
            "核心指标": {
                "活跃资金情绪": self.data.get('活跃资金情绪'),
                "封板率": self.data.get('封板率'),
                "涨停数量": self.data.get('涨停数量'),
                "最高板数": self.data.get('最高板数'),
                "连板家数": self.data.get('连板家数'),
                "自然板家数": self.data.get('自然板家数'),
                "触及涨停": self.data.get('触及涨停')
            },
            "趋势分析": {
                "百日排名": self.data.get('百日排名'),
                "五日平均": self.data.get('五日平均'),
                "连续天数": self.data.get('连续天数'),
                "趋势类型": self.data.get('趋势类型'),
                "趋势描述": "上升" if self.data.get('趋势类型') == 1 else "下降"
            },
            "今日数据": {
                "涨停数量": self.data.get('涨停数量'),
                "封板率": self.data.get('封板率'),
                "涨停打开": self.data.get('涨停打开数量'),
                "跌停数量": self.data.get('跌停数量'),
                "跌停封板率": self.data.get('跌停封板率'),
                "跌停打开": self.data.get('跌停打开数量'),
                "活跃资金情绪": self.data.get('活跃资金情绪')
            },
            "前日数据": {
                "涨停数量": self.data.get('昨日涨停数量'),
                "封板率": self.data.get('昨日封板率'),
                "涨停打开": self.data.get('昨日涨停打开数量'),
                "跌停数量": self.data.get('昨日跌停数量'),
                "跌停封板率": self.data.get('昨日跌停封板率'),
                "跌停打开": self.data.get('昨日跌停打开数量')
            },
            "连板统计": {
                "最高板数": self.data.get('最高板数'),
                "连板家数": self.data.get('连板家数'),
                "自然板家数": self.data.get('自然板家数'),
                "触及涨停": self.data.get('触及涨停')
            },
            "市场表现": {
                "昨日涨停今日表现": self.data.get('昨日涨停今日表现'),
                "上证指数表现": self.data.get('上证指数表现')
            },
            "涨停梯队": ladder_data.get('ladder_stocks', {}),
            "市场分布": ladder_data.get('market_distribution', {}),
            "板数分布": ladder_data.get('board_distribution', {}),
            "原始数据": self.data
        }

def update_index():
    """更新索引文件"""
    try:
        index_path = os.path.join(DATA_DIR, 'index.json')
        dates_data = {}
        
        if os.path.exists(DATA_DIR):
            for year_month in os.listdir(DATA_DIR):
                month_path = os.path.join(DATA_DIR, year_month)
                if os.path.isdir(month_path):
                    for filename in os.listdir(month_path):
                        if filename.endswith('.json'):
                            date_str = filename.replace('.json', '')
                            try:
                                datetime.strptime(date_str, '%Y-%m-%d')
                                file_path = os.path.join(month_path, filename)
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                                
                                dates_data[date_str] = {
                                    "date": date_str,
                                    "update_time": data.get('报告信息', {}).get('生成时间', ''),
                                    "source": "大智慧涨停透视",
                                    "files": {
                                        "json": f"dzh_ztts/{year_month}/{filename}",
                                        "txt": f"dzh_ztts/{year_month}/{date_str}.txt"
                                    },
                                    "core_data": {
                                        "涨停数量": data.get('核心指标', {}).get('涨停数量'),
                                        "封板率": data.get('核心指标', {}).get('封板率'),
                                        "最高板数": data.get('核心指标', {}).get('最高板数'),
                                        "活跃资金情绪": data.get('核心指标', {}).get('活跃资金情绪')
                                    },
                                    "market_analysis": data.get('市场分析', {}).get('完整解读', '')[:200] + "..."
                                }
                            except:
                                continue
        
        with open(index_path, 'w', encoding='utf-8') as f:
            json.dump(dates_data, f, ensure_ascii=False, indent=2)
        
        print(f"📑 索引文件已更新: {len(dates_data)} 条记录")
        
    except Exception as e:
        print(f"❌ 更新索引文件失败: {e}")

def main():
    """主函数"""
    # 解析命令行参数
    if len(sys.argv) > 1:
        target_date = parse_date(sys.argv[1])
    else:
        target_date = get_latest_trading_day()
    
    print(f"🚀 涨停透视数据爬虫启动")
    print(f"📅 目标日期: {target_date}")
    
    # 爬取数据
    crawler = ZTTSCrawler(target_date)
    data = crawler.crawl_data()
    
    if not data:
        print("❌ 爬取失败")
        return False
    
    # 格式化数据
    actual_date = crawler.actual_date or target_date
    formatter = DataFormatter(data, actual_date)
    
    json_report = formatter.generate_json()
    txt_report = formatter.generate_txt()
    
    # 保存文件
    paths = get_file_paths(actual_date)
    
    try:
        with open(paths['json'], 'w', encoding='utf-8') as f:
            json.dump(json_report, f, ensure_ascii=False, indent=2)
        
        with open(paths['txt'], 'w', encoding='utf-8') as f:
            f.write(txt_report)
        
        print(f"📁 文件保存成功:")
        print(f"   JSON: {paths['json']}")
        print(f"   TXT:  {paths['txt']}")
        
        # 更新索引文件
        update_index()
        
        # 显示关键指标
        print(f"\n📈 关键指标:")
        print(f"   活跃资金情绪: {formatter.format_percent(data.get('活跃资金情绪'))}")
        print(f"   封板率: {formatter.format_percent(data.get('封板率'))}")
        print(f"   涨停数量: {formatter.format_number(data.get('涨停数量'))}")
        print(f"   最高板数: {formatter.format_number(data.get('最高板数'))}")
        print(f"   百日排名: {formatter.format_number(data.get('百日排名'))}")
        print(f"   五日平均: {formatter.format_number(data.get('五日平均'))}")
        
        # 显示解读文本预览
        analysis_preview = formatter.generate_analysis_from_dom()
        if analysis_preview and len(analysis_preview) > 10:
            preview_text = analysis_preview[:150] + "..." if len(analysis_preview) > 150 else analysis_preview
            print(f"\n📊 市场解读预览:")
            print(f"   {preview_text}")
        
        # 显示涨停梯队统计
        ladder_data = data.get('涨停梯队数据', {})
        if ladder_data.get('board_distribution'):
            print(f"\n🔥 板数分布:")
            for board_type, count in ladder_data['board_distribution'].items():
                if count > 0:
                    print(f"   {board_type}: {count}只")
        
        # 显示市场分布
        if ladder_data.get('market_distribution'):
            print(f"\n📊 市场分布:")
            for market, count in ladder_data['market_distribution'].items():
                print(f"   {market}: {count}只")
        
        # 推送到GitHub
        success = git_push_data(paths['date_str'])
        if success:
            print(f"\n✅ 程序执行完成，数据已推送到GitHub")
        else:
            print(f"\n⚠️ 程序执行完成，但GitHub推送失败")
        
        return True
        
    except Exception as e:
        print(f"❌ 文件保存失败: {e}")
        return False

if __name__ == "__main__":
    main()
