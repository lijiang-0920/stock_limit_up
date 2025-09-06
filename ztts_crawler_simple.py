#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
涨停透视数据爬虫 - 混合版（Selenium + API）
使用方法：
  python ztts_crawler_simple.py              # 获取最新数据并推送
  python ztts_crawler_simple.py 2025-01-21   # 获取指定日期数据
"""

import os
import json
import time
import sys
import subprocess
import requests  # 新增：用于API调用
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.options import Options

# 配置
TARGET_URL = "https://webrelease.dzh.com.cn/htmlweb/ztts/index.php"
DATA_DIR = "dzh_ztts"
WAIT_TIME = 20

def get_latest_trading_day():
    """获取最新交易日"""
    current_date = datetime.now().date()
    while current_date.weekday() >= 5:  # 周末
        current_date -= timedelta(days=1)
    
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
        # 直接使用完整路径
        subprocess.run(r'"D:\Git\cmd\git.exe" add dzh_ztts/', shell=True, check=True)
        subprocess.run(rf'"D:\Git\cmd\git.exe" commit -m "Update 涨停透视数据 {date_str}"', shell=True, check=True)
        subprocess.run(r'"D:\Git\cmd\git.exe" push', shell=True, check=True)
        
        print(f"✅ 推送成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 推送失败: {e}")
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
        print(f"🚀 启动浏览器...")
        
        options = Options()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        
        self.driver = webdriver.Edge(options=options)
    
    def crawl_data(self):
        """爬取数据"""
        print(f"🕷️ 开始爬取基础数据（目标日期：{self.target_date}）...")
        
        self.setup_driver()
        
        try:
            self.driver.get(TARGET_URL)
            
            wait = WebDriverWait(self.driver, 30)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            print(f"⏳ 等待页面加载 {WAIT_TIME} 秒...")
            time.sleep(WAIT_TIME)
            
            self.actual_date = self.get_actual_date()
            print(f"📅 实际数据日期: {self.actual_date}")
            
            # 获取基础数据（Selenium）
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
            script = """
            try {
                var app = document.querySelector('#app').__vue__;
                if (app && (app.thisDay || app.today)) {
                    return app.thisDay || app.today;
                }
                return null;
            } catch (error) {
                return null;
            }
            """
            
            result = self.driver.execute_script(script)
            if result and len(result) >= 10:
                return datetime.strptime(result[:10], '%Y-%m-%d').date()
            
            return self.target_date
            
        except:
            return self.target_date
    
    def extract_data(self):
        """提取Vue基础数据"""
        script = """
        try {
            var app = document.querySelector('#app').__vue__;
            if (!app) return {error: 'Vue实例未找到'};
            
            return {
                爬取时间: new Date().toISOString(),
                实际数据日期: app.thisDay || app.today || null,
                
                活跃资金情绪: app.todayMarketSense || null,
                封板率: app.todayStat ? app.todayStat.lufb : null,
                涨停数量: app.todayStat ? app.todayStat.lu : null,
                涨停打开数量: app.todayStat ? app.todayStat.luop : null,
                跌停数量: app.todayStat ? app.todayStat.ld : null,
                跌停封板率: app.todayStat ? app.todayStat.ldfb : null,
                跌停打开数量: app.todayStat ? app.todayStat.ldop : null,
                
                最高板数: app.todayMaxban || null,
                连板家数: app.todayLbnum || null,
                自然板家数: app.todayZrb || null,
                触及涨停: app.todayCjzt || null,
                
                昨日封板率: app.yesterdayStat ? app.yesterdayStat.lufb : null,
                昨日涨停数量: app.yesterdayStat ? app.yesterdayStat.lu : null,
                昨日涨停打开数量: app.yesterdayStat ? app.yesterdayStat.luop : null,
                昨日跌停数量: app.yesterdayStat ? app.yesterdayStat.ld : null,
                昨日跌停封板率: app.yesterdayStat ? app.yesterdayStat.ldfb : null,
                昨日跌停打开数量: app.yesterdayStat ? app.yesterdayStat.ldop : null
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

def format_data(data, actual_date):
    """格式化数据（增强版，包含涨停梯队）"""
    def format_percent(value):
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
    
    def format_number(value):
        if value is None:
            return "暂无数据"
        try:
            return str(int(float(value)))
        except:
            return str(value)
    
    # 生成分析文本
    num = data.get('涨停数量', 0)
    封板率 = data.get('封板率', 0)
    情绪 = data.get('活跃资金情绪', 0)
    最高板数 = data.get('最高板数', 0)
    连板家数 = data.get('连板家数', 0)
    自然板家数 = data.get('自然板家数', 0)
    
    date_text = "今日" if actual_date == datetime.now().date() else f"{actual_date.strftime('%m月%d日')}"
    analysis = f"{date_text}涨停数量{format_number(num)}只，封板率{format_percent(封板率)}，活跃资金情绪{format_percent(情绪)}"
    
    if 最高板数:
        analysis += f"，最高板数达到{format_number(最高板数)}板"
    if 连板家数:
        analysis += f"，连板家数{format_number(连板家数)}家"
    if 自然板家数:
        analysis += f"，自然板家数{format_number(自然板家数)}家"
    
    # 获取涨停梯队数据
    ladder_data = data.get('涨停梯队数据', {})
    
    # 生成JSON数据
    json_data = {
        "报告信息": {
            "生成时间": datetime.now().isoformat(),
            "数据日期": actual_date.strftime('%Y-%m-%d'),
            "数据来源": "大智慧涨停透视(Selenium+API)",
            "更新时间": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        "核心指标": {
            "活跃资金情绪": data.get('活跃资金情绪'),
            "封板率": data.get('封板率'),
            "涨停数量": data.get('涨停数量'),
            "最高板数": data.get('最高板数')
        },
        "市场分析": {
            "分析文本": analysis
        },
        "今日数据": {
            "涨停数量": data.get('涨停数量'),
            "封板率": data.get('封板率'),
            "涨停打开": data.get('涨停打开数量'),
            "跌停数量": data.get('跌停数量'),
            "跌停封板率": data.get('跌停封板率'),
            "跌停打开": data.get('跌停打开数量'),
            "活跃资金情绪": data.get('活跃资金情绪')
        },
        "前日数据": {
            "涨停数量": data.get('昨日涨停数量'),
            "封板率": data.get('昨日封板率'),
            "涨停打开": data.get('昨日涨停打开数量'),
            "跌停数量": data.get('昨日跌停数量'),
            "跌停封板率": data.get('昨日跌停封板率'),
            "跌停打开": data.get('昨日跌停打开数量')
        },
        "连板统计": {
            "最高板数": data.get('最高板数'),
            "连板家数": data.get('连板家数'),
            "自然板家数": data.get('自然板家数'),
            "触及涨停": data.get('触及涨停')
        },
        # 新增：涨停梯队数据
        "涨停梯队": ladder_data.get('ladder_stocks', {}),
        "市场分布": ladder_data.get('market_distribution', {}),
        "板数分布": ladder_data.get('board_distribution', {}),
        "原始数据": data
    }
    
    # 生成TXT文本（增强版）
    txt_data = f"""大智慧涨停透视 - {actual_date.strftime('%Y年%m月%d日')}
更新时间：{datetime.now().strftime('%H:%M:%S')}
{'=' * 60}

【核心指标】
活跃资金情绪：{format_percent(data.get('活跃资金情绪'))}
封板率：{format_percent(data.get('封板率'))}
涨停数量：{format_number(data.get('涨停数量'))}只
最高板数：{format_number(data.get('最高板数'))}板

【市场分析】
{analysis}

【连板统计】
最高板数：{format_number(data.get('最高板数'))}板
连板家数：{format_number(data.get('连板家数'))}家
自然板家数：{format_number(data.get('自然板家数'))}家
触及涨停：{format_number(data.get('触及涨停'))}只

【今日 vs 前日对比】
涨停板数量：今日 {format_number(data.get('涨停数量'))}只 / 前日 {format_number(data.get('昨日涨停数量'))}只
涨停封板率：今日 {format_percent(data.get('封板率'))} / 前日 {format_percent(data.get('昨日封板率'))}
跌停板数量：今日 {format_number(data.get('跌停数量'))}只 / 前日 {format_number(data.get('昨日跌停数量'))}只

【板数分布】"""
    
    # 添加板数分布
    board_dist = ladder_data.get('board_distribution', {})
    if board_dist:
        for board_type, count in board_dist.items():
            txt_data += f"\n{board_type}: {count}只"
    
    txt_data += "\n\n【市场分布】"
    # 添加市场分布
    market_dist = ladder_data.get('market_distribution', {})
    if market_dist:
        for market, count in market_dist.items():
            txt_data += f"\n{market}: {count}只"
    
    # 添加涨停梯队详情
    txt_data += "\n\n【涨停梯队详情】\n" + "=" * 60
    ladder_stocks = ladder_data.get('ladder_stocks', {})
    if ladder_stocks:
        for board_type, stocks in ladder_stocks.items():
            if stocks:  # 只显示有股票的板数
                txt_data += f"\n\n{board_type} ({len(stocks)}只)\n" + "-" * 40
                for i, stock in enumerate(stocks, 1):
                    txt_data += f"\n{i}. {stock['name']} ({stock['code']}) - {stock['market']}"
                    txt_data += f"\n   收盘价: {stock['close_price']:.2f}元  涨幅: {stock['change_rate']:.2f}%"
                    txt_data += f"\n   连板标签: {stock['board_label']}\n"
    
    txt_data += "\n" + "=" * 60
    
    return json_data, txt_data

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
                                    "update_time": data.get('报告信息', {}).get('更新时间', ''),
                                    "source": "大智慧涨停透视(Selenium+API)",
                                    "files": {
                                        "json": f"dzh_ztts/{year_month}/{filename}",
                                        "txt": f"dzh_ztts/{year_month}/{date_str}.txt"
                                    },
                                    "core_data": {
                                        "涨停数量": data.get('核心指标', {}).get('涨停数量'),
                                        "封板率": data.get('核心指标', {}).get('封板率'),
                                        "最高板数": data.get('核心指标', {}).get('最高板数'),
                                        "活跃资金情绪": data.get('核心指标', {}).get('活跃资金情绪')
                                    }
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
    
    print(f"🚀 涨停透视数据爬虫启动（混合版本）")
    print(f"📅 目标日期: {target_date}")
    
    # 爬取数据
    crawler = ZTTSCrawler(target_date)
    data = crawler.crawl_data()
    
    if not data:
        print("❌ 爬取失败")
        return False
    
    # 格式化数据
    actual_date = crawler.actual_date or target_date
    json_data, txt_data = format_data(data, actual_date)
    
    # 保存文件
    paths = get_file_paths(actual_date)
    
    try:
        with open(paths['json'], 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        with open(paths['txt'], 'w', encoding='utf-8') as f:
            f.write(txt_data)
        
        print(f"📁 文件保存成功:")
        print(f"   JSON: {paths['json']}")
        print(f"   TXT:  {paths['txt']}")
        
        # 更新索引文件
        update_index()
        
        # 显示关键指标
        print(f"\n📈 关键指标:")
        print(f"   活跃资金情绪: {json_data['核心指标']['活跃资金情绪']}")
        print(f"   封板率: {json_data['核心指标']['封板率']}")
        print(f"   涨停数量: {json_data['核心指标']['涨停数量']}")
        print(f"   最高板数: {json_data['核心指标']['最高板数']}")
        
        # 显示涨停梯队统计
        if json_data.get('板数分布'):
            print(f"\n🔥 板数分布:")
            for board_type, count in json_data['板数分布'].items():
                if count > 0:
                    print(f"   {board_type}: {count}只")
        
        # 显示市场分布
        if json_data.get('市场分布'):
            print(f"\n📊 市场分布:")
            for market, count in json_data['市场分布'].items():
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
        