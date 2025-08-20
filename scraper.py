import json
import requests
import urllib.parse
import hashlib
import os
from datetime import datetime, timedelta

def generate_sign(params_dict):
    """
    生成财联社API请求的签名
    """
    # 对字典的键进行排序，并生成排序后的查询字符串
    sorted_data = sorted(params_dict.items(), key=lambda item: item[0])  # 按key排序
    query_string = urllib.parse.urlencode(sorted_data)  # 转换为URL编码的字符串
    
    # 使用SHA1加密
    sha1_hash = hashlib.sha1(query_string.encode('utf-8')).hexdigest()
    
    # 对SHA1加密的结果再进行MD5加密
    sign = hashlib.md5(sha1_hash.encode('utf-8')).hexdigest()
    
    return sign

def get_headers():
    """
    获取请求头
    """
    return {
        "Host": "x-quote.cls.cn",
        "Connection": "keep-alive",
        "sec-ch-ua": "\"Not A(Brand\";v=\"99\", \"Google Chrome\";v=\"121\", \"Chromium\";v=\"121\"",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded",
        "sec-ch-ua-mobile": "?0",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "sec-ch-ua-platform": "\"Windows\"",
        "Origin": "https://www.cls.cn",
        "Sec-Fetch-Site": "same-site",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://www.cls.cn/",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }

def get_params():
    """
    获取请求参数并动态生成签名
    """
    params = {
        "app": "CailianpressWeb",
        "os": "web",
        "rever": "1",
        "sv": "8.4.6",
        "type": "up_pool",
        "way": "last_px"
    }
    
    # 动态生成签名
    params["sign"] = generate_sign(params)
    
    return params

def convert_stock_code(code):
    """
    转换股票代码为指定格式
    上交所股票格式为：XXX.SH
    深交所股票格式为：XXX.SZ
    """
    if code.startswith('sh'):
        return code[2:] + '.SH'
    elif code.startswith('sz'):
        return code[2:] + '.SZ'
    return code

def format_plate_names(plates):
    """
    格式化板块名称为字符串
    """
    if not plates:
        return ""
    return '|'.join([plate['secu_name'] for plate in plates])

def get_beijing_time():
    """
    获取北京时间（系统时间+8小时）
    """
    # 获取系统时间并加上8小时偏移
    return datetime.now() 

def fetch_limit_up_data():
    """
    获取涨停池数据
    """
    url = "https://x-quote.cls.cn/quote/index/up_down_analysis"
    
    try:
        params = get_params()
        
        response = requests.get(url, params=params, headers=get_headers(), timeout=10)
        response.raise_for_status()  # 检查请求是否成功
        
        data = response.json()
        if data['code'] != 200:
            print(f"API返回错误: {data['msg']}")
            return None
            
        return data['data']
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"JSON解析失败: {e}")
        return None
    except Exception as e:
        print(f"未知错误: {e}")
        return None

def process_data(data):
    """
    处理涨停池数据并返回格式化数据
    """
    if not data:
        print("没有数据可处理")
        return None
    
    # 获取当前时间作为记录时间
    current_time = get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")
    current_date = get_beijing_time().strftime("%Y-%m-%d")
    
    # 转换数据格式
    formatted_data = []
    for stock in data:
        # 将涨幅从小数转换为百分比格式（例如：0.2 -> 20%）
        change_value = float(stock['change']) * 100
        change_percent = f"{change_value:.2f}%"
        
        formatted_stock = {
            "code": convert_stock_code(stock['secu_code']),
            "name": stock['secu_name'].strip(),
            "change_percent": change_percent,
            "price": stock['last_px'],
            "limit_up_time": stock['time'],
            "reason": stock['up_reason'],
            "plates": format_plate_names(stock['plate'])
        }
        formatted_data.append(formatted_stock)
    
    # 构建结果对象
    result = {
        "date": current_date,
        "update_time": current_time,
        "count": len(formatted_data),
        "stocks": formatted_data
    }
    
    return result

def save_data(data):
    """
    保存数据到文件并更新HTML页面
    """
    if not data:
        print("没有数据可保存")
        return
    
    # 确保data目录存在
    os.makedirs('data', exist_ok=True)
    
    # 获取当前日期作为文件名
    current_date = data['date']
    
    # 保存今日数据
    with open(f'data/{current_date}.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # 更新索引文件 - 获取所有日期文件
    dates = [f.replace('.json', '') for f in os.listdir('data') if f.endswith('.json') and f != 'index.json']
    dates.sort(reverse=True)  # 按日期降序排序
    
    with open('data/index.json', 'w', encoding='utf-8') as f:
        json.dump(dates, f, ensure_ascii=False)
    
    # 生成HTML
    generate_html(dates)
    
    # 生成JSON查看页面
    generate_json_viewer()
    
    print(f"数据已保存: {current_date}, 共{data['count']}只涨停股")

def generate_json_viewer():
    """
    生成JSON查看页面
    """
    html_content = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>财联社涨停池 JSON 数据查看器</title>
        <style>
            body { font-family: "Microsoft YaHei", Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; background-color: white; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
            h1 { color: #333; text-align: center; margin-top: 0; }
            .info { text-align: center; color: #666; margin-bottom: 20px; }
            .date-select { width: 100%; padding: 10px; margin-bottom: 20px; font-size: 16px; }
            pre { background-color: #f8f8f8; padding: 15px; border-radius: 5px; overflow-x: auto; white-space: pre-wrap; }
            code { font-family: Consolas, Monaco, 'Andale Mono', monospace; }
            .back-link { display: block; margin-bottom: 20px; text-decoration: none; color: #4CAF50; }
            .back-link:hover { text-decoration: underline; }
            .copy-btn { background-color: #4CAF50; color: white; border: none; padding: 8px 15px; cursor: pointer; float: right; margin-bottom: 10px; }
            .copy-btn:hover { background-color: #45a049; }
        </style>
    </head>
    <body>
        <div class="container">
            <a href="index.html" class="back-link">← 返回数据表格视图</a>
            <h1>财联社涨停池 JSON 数据查看器</h1>
            <p class="info">查看原始 JSON 数据</p>
            
            <select id="dateSelect" class="date-select" onchange="loadJsonData()">
                <option value="">-- 选择日期 --</option>
            </select>
            
            <button id="copyBtn" class="copy-btn" onclick="copyToClipboard()">复制 JSON</button>
            
            <pre><code id="jsonContent">请选择一个日期查看数据...</code></pre>
        </div>
        
        <script>
            // 加载可用日期
            async function loadDates() {
                try {
                    const response = await fetch('data/index.json');
                    const dates = await response.json();
                    
                    const select = document.getElementById('dateSelect');
                    dates.forEach(date => {
                        const option = document.createElement('option');
                        option.value = date;
                        option.textContent = date;
                        select.appendChild(option);
                    });
                    
                    // 如果有日期，默认加载第一个
                    if (dates.length > 0) {
                        select.value = dates[0];
                        loadJsonData();
                    }
                } catch (error) {
                    console.error('加载日期失败:', error);
                    document.getElementById('jsonContent').textContent = '加载日期数据失败，请稍后再试。';
                }
            }
            
            // 加载选定日期的JSON数据
            async function loadJsonData() {
                const date = document.getElementById('dateSelect').value;
                if (!date) {
                    document.getElementById('jsonContent').textContent = '请选择一个日期查看数据...';
                    return;
                }
                
                try {
                    const response = await fetch(`data/${date}.json`);
                    const data = await response.json();
                    
                    // 格式化JSON并显示
                    document.getElementById('jsonContent').textContent = JSON.stringify(data, null, 2);
                } catch (error) {
                    console.error('加载JSON数据失败:', error);
                    document.getElementById('jsonContent').textContent = `加载 ${date} 的数据失败，请稍后再试。`;
                }
            }
            
            // 复制JSON到剪贴板
            function copyToClipboard() {
                const jsonContent = document.getElementById('jsonContent').textContent;
                
                navigator.clipboard.writeText(jsonContent)
                    .then(() => {
                        const btn = document.getElementById('copyBtn');
                        btn.textContent = '已复制!';
                        setTimeout(() => {
                            btn.textContent = '复制 JSON';
                        }, 2000);
                    })
                    .catch(err => {
                        console.error('复制失败:', err);
                        alert('复制失败，请手动选择并复制。');
                    });
            }
            
            // 页面加载时执行
            document.addEventListener('DOMContentLoaded', loadDates);
        </script>
    </body>
    </html>
    """
    
    with open('json_viewer.html', 'w', encoding='utf-8') as f:
        f.write(html_content)

def generate_html(dates):
    """
    生成HTML页面展示所有历史数据
    """
    html_start = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>财联社涨停池数据</title>
        <style>
            body { font-family: "Microsoft YaHei", Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; background-color: white; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
            h1 { color: #333; text-align: center; margin-top: 0; }
            .info { text-align: center; color: #666; margin-bottom: 20px; }
            .date-tabs { display: flex; flex-wrap: wrap; margin-bottom: 20px; border-bottom: 1px solid #ddd; }
            .date-tab { padding: 10px 15px; cursor: pointer; background-color: #f1f1f1; margin-right: 5px; margin-bottom: 5px; border-radius: 5px 5px 0 0; }
            .date-tab:hover { background-color: #ddd; }
            .date-tab.active { background-color: #4CAF50; color: white; }
            .tab-content { display: none; }
            .tab-content.active { display: block; }
            table { border-collapse: collapse; width: 100%; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 12px 8px; text-align: left; }
            th { background-color: #f2f2f2; position: sticky; top: 0; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            tr:hover { background-color: #f1f1f1; }
            .search-box { margin-bottom: 20px; padding: 10px; }
            .search-box input { width: 100%; padding: 10px; font-size: 16px; border: 1px solid #ddd; border-radius: 4px; }
            .stock-count { margin: 10px 0; font-weight: bold; color: #333; }
            .update-time { color: #666; font-style: italic; margin-bottom: 15px; }
            .json-link { display: inline-block; margin-top: 10px; text-decoration: none; color: #4CAF50; }
            .json-link:hover { text-decoration: underline; }
            .header-actions { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
            .view-json-btn { background-color: #4CAF50; color: white; border: none; padding: 8px 15px; cursor: pointer; }
            .view-json-btn:hover { background-color: #45a049; }
            @media (max-width: 768px) {
                .container { padding: 10px; }
                th, td { padding: 8px 4px; font-size: 14px; }
                .date-tab { padding: 8px 12px; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>财联社涨停池数据</h1>
            <p class="info">每日15:30自动更新，点击日期查看对应数据</p>
            
            <div class="header-actions">
                <div class="search-box">
                    <input type="text" id="searchInput" placeholder="搜索股票代码或名称..." onkeyup="searchStocks()">
                </div>
                <a href="json_viewer.html" class="view-json-btn">查看原始JSON数据</a>
            </div>
            
            <div class="date-tabs" id="dateTabs">
    """
    
    html_tabs = ""
    html_content = ""
    
    for i, date in enumerate(dates):
        active = " active" if i == 0 else ""
        html_tabs += f'<div class="date-tab{active}" onclick="openTab(\'{date}\')">{date}</div>\n'
        
        # 读取该日期的数据
        try:
            with open(f'data/{date}.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            stocks = data['stocks']
            
            html_content += f'<div id="{date}" class="tab-content{active}">\n'
            html_content += f'<div class="update-time">更新时间: {data["update_time"]}</div>\n'
            html_content += f'<div class="stock-count">涨停股数量: {data["count"]}</div>\n'
            html_content += f'<a href="data/{date}.json" target="_blank" class="json-link">查看此日期的JSON数据</a>\n'
            html_content += '<table>\n'
            html_content += '<tr><th>股票代码</th><th>股票名称</th><th>最新价格</th><th>涨幅</th><th>涨停时间</th><th>涨停原因</th><th>所属板块</th></tr>\n'
            
            for stock in stocks:
                html_content += f'<tr class="stock-row">'
                html_content += f'<td>{stock["code"]}</td>'
                html_content += f'<td>{stock["name"]}</td>'
                html_content += f'<td>{stock["price"]}</td>'
                html_content += f'<td>{stock["change_percent"]}</td>'
                html_content += f'<td>{stock["limit_up_time"]}</td>'
                html_content += f'<td>{stock["reason"]}</td>'
                html_content += f'<td>{stock["plates"]}</td>'
                html_content += '</tr>\n'
            
            html_content += '</table>\n</div>\n'
        except Exception as e:
            print(f"处理{date}数据时出错: {e}")
            html_content += f'<div id="{date}" class="tab-content{active}">\n'
            html_content += f'<p>数据加载失败</p>\n</div>\n'
    
    html_end = """
            </div>
            
            <script>
            function openTab(dateId) {
                // 隐藏所有内容
                var tabContents = document.getElementsByClassName("tab-content");
                for (var i = 0; i < tabContents.length; i++) {
                    tabContents[i].classList.remove("active");
                }
                
                // 取消所有标签页的激活状态
                var tabs = document.getElementsByClassName("date-tab");
                for (var i = 0; i < tabs.length; i++) {
                    tabs[i].classList.remove("active");
                }
                
                // 显示选中的内容并激活标签页
                document.getElementById(dateId).classList.add("active");
                
                // 找到并激活对应的标签
                var tabs = document.getElementsByClassName("date-tab");
                for (var i = 0; i < tabs.length; i++) {
                    if (tabs[i].textContent.trim() === dateId) {
                        tabs[i].classList.add("active");
                        break;
                    }
                }
                
                // 清除搜索框
                document.getElementById("searchInput").value = "";
                
                // 重置所有行的显示
                var rows = document.querySelectorAll("#" + dateId + " .stock-row");
                for (var i = 0; i < rows.length; i++) {
                    rows[i].style.display = "";
                }
            }
            
            function searchStocks() {
                // 获取搜索输入
                var input = document.getElementById("searchInput");
                var filter = input.value.toUpperCase();
                
                // 获取当前活动的标签内容
                var activeTab = document.querySelector(".tab-content.active");
                if (!activeTab) return;
                
                // 获取当前标签中的所有股票行
                var rows = activeTab.querySelectorAll(".stock-row");
                
                // 遍历所有行，隐藏不匹配的
                for (var i = 0; i < rows.length; i++) {
                    var codeCell = rows[i].getElementsByTagName("td")[0];
                    var nameCell = rows[i].getElementsByTagName("td")[1];
                    
                    if (codeCell || nameCell) {
                        var codeText = codeCell ? codeCell.textContent || codeCell.innerText : "";
                        var nameText = nameCell ? nameCell.textContent || nameCell.innerText : "";
                        
                        if (codeText.toUpperCase().indexOf(filter) > -1 || nameText.toUpperCase().indexOf(filter) > -1) {
                            rows[i].style.display = "";
                        } else {
                            rows[i].style.display = "none";
                        }
                    }
                }
            }
            </script>
        </div>
    </body>
    </html>
    """
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html_start + html_tabs + '</div>' + html_content + html_end)

def main():
    """
    主函数
    """
    try:
        # 获取涨停池数据
        raw_data = fetch_limit_up_data()
        
        # 处理数据
        processed_data = process_data(raw_data)
        
        # 保存数据并生成HTML
        if processed_data:
            save_data(processed_data)
        else:
            print("没有获取到有效数据，无法保存")
    except Exception as e:
        print(f"执行过程中发生错误: {e}")

if __name__ == "__main__":
    main()

