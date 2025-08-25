import json
import requests
import urllib.parse
import hashlib
import os
import re
import codecs
import sys
import time
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

# ========== 财联社涨停池相关函数 ==========

def generate_sign(params_dict):
    sorted_data = sorted(params_dict.items(), key=lambda item: item[0])
    query_string = urllib.parse.urlencode(sorted_data)
    sha1_hash = hashlib.sha1(query_string.encode('utf-8')).hexdigest()
    sign = hashlib.md5(sha1_hash.encode('utf-8')).hexdigest()
    return sign

def get_headers():
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
    params = {
        "app": "CailianpressWeb",
        "os": "web",
        "rever": "1",
        "sv": "8.4.6",
        "type": "up_pool",
        "way": "last_px"
    }
    params["sign"] = generate_sign(params)
    return params

def convert_stock_code(code):
    if code.startswith('sh'):
        return code[2:] + '.SH'
    elif code.startswith('sz'):
        return code[2:] + '.SZ'
    return code

def format_plate_names(plates):
    if not plates:
        return ""
    return '|'.join([plate['secu_name'] for plate in plates])

def get_beijing_time():
    return datetime.now() 

def fetch_limit_up_data():
    url = "https://x-quote.cls.cn/quote/index/up_down_analysis"
    try:
        params = get_params()
        response = requests.get(url, params=params, headers=get_headers(), timeout=10)
        response.raise_for_status()
        data = response.json()
        if data['code'] != 200:
            print(f"API返回错误: {data['msg']}")
            return None
        return data['data']
    except Exception as e:
        print(f"获取涨停池数据失败: {e}")
        return None

def process_limit_up_data(data):
    if not data:
        return None
    
    current_time = get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")
    current_date = get_beijing_time().strftime("%Y-%m-%d")
    
    formatted_data = []
    for stock in data:
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
    
    result = {
        "date": current_date,
        "update_time": current_time,
        "count": len(formatted_data),
        "stocks": formatted_data
    }
    return result

def save_limit_up_data(data):
    if not data:
        return
    
    os.makedirs('data', exist_ok=True)
    current_date = data['date']
    
    with open(f'data/{current_date}.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    dates = [f.replace('.json', '') for f in os.listdir('data') if f.endswith('.json') and f != 'index.json']
    dates.sort(reverse=True)
    
    with open('data/index.json', 'w', encoding='utf-8') as f:
        json.dump(dates, f, ensure_ascii=False)
    
    print(f"涨停池数据已保存: {current_date}, 共{data['count']}只涨停股")

# ========== 韭研公社文章爬取相关函数 ==========

JIUYAN_USERS = {
    '盘前纪要': {
        'user_url': 'https://www.jiuyangongshe.com/u/4df747be1bf143a998171ef03559b517',
        'user_name': '盘前纪要',
        'save_dir_prefix': '韭研公社_盘前纪要',
        'default_time': '07:40',
        'retry_time': '08:00',
        'mode': 'full'
    },
    '盘前解读': {
        'user_url': 'https://www.jiuyangongshe.com/u/97fc2a020e644adb89570e69ae35ec02',
        'user_name': '盘前解读',
        'save_dir_prefix': '韭研公社_盘前解读',
        'default_time': '08:17',
        'retry_time': '08:27',
        'mode': 'full'
    },
    '优秀阿呆': {
        'user_url': 'https://www.jiuyangongshe.com/u/88cf268bc56c423c985b87d1b1ff5de4',
        'user_name': '优秀阿呆',
        'save_dir_prefix': '韭研公社_优秀阿呆',
        'default_time': '23:30',
        'retry_time': None,
        'mode': 'simple'
    }
}

JIUYAN_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
}

def get_target_article_url(user_url, date_str):
    resp = requests.get(user_url, headers=JIUYAN_HEADERS, timeout=15)
    resp.encoding = resp.apparent_encoding
    soup = BeautifulSoup(resp.text, "html.parser")
    for li in soup.find_all('li'):
        title_tag = li.select_one('.book-title span')
        time_tag = li.select_one('.fs13-ash')
        if not title_tag or not time_tag:
            continue
        title = title_tag.text.strip()
        pub_time = time_tag.text.strip()
        if pub_time.startswith(date_str):
            a_tag = li.select_one('a[href^="/a/"]')
            if a_tag:
                article_url = urljoin(user_url, a_tag['href'])
                return title, article_url
    return None, None

def fetch_article_content(article_url):
    resp = requests.get(article_url, headers=JIUYAN_HEADERS, timeout=15)
    html = resp.text

    pattern = r'content:"(.*?)",url:'
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        return None, None, None

    content_html = match.group(1)
    content_html = content_html.replace('\\\\u', '\\u')
    content_html = codecs.decode(content_html, 'unicode_escape')
    content_html = content_html.encode('latin1').decode('utf-8')
    content_html = content_html.replace('\\"', '"')

    soup = BeautifulSoup(content_html, "html.parser")
    return soup, article_url, html

def save_article_and_generate_json(soup, article_url, save_dir, base_fname, user_info, date_str):
    """保存文章并生成JSON数据"""
    mode = user_info.get('mode', 'full')
    
    # 创建目录
    os.makedirs(save_dir, exist_ok=True)
    
    # 处理图片
    images_data = []
    if mode == 'full':
        img_folder = os.path.join(save_dir, "images")
        os.makedirs(img_folder, exist_ok=True)
        headers_with_referer = JIUYAN_HEADERS.copy()
        headers_with_referer['Referer'] = article_url

        img_counter = 1
        for img in soup.find_all('img'):
            src = img.get('src')
            if not src:
                continue
            if not src.startswith('http'):
                src = urljoin(article_url, src)
            
            try:
                r = requests.get(src, headers=headers_with_referer, timeout=10)
                if r.status_code != 200:
                    continue
                
                ext = os.path.splitext(urlparse(src).path)[-1]
                if not ext or len(ext) > 5:
                    ext = '.jpg'
                fname = f'img{img_counter}{ext}'
                img_path = os.path.join(img_folder, fname)
                
                with open(img_path, 'wb') as f:
                    f.write(r.content)
                
                # 验证图片
                try:
                    from PIL import Image
                    with Image.open(img_path) as im:
                        im.verify()
                except:
                    if os.path.exists(img_path):
                        os.remove(img_path)
                    continue
                
                # 记录图片信息
                placeholder = f"[图片:img{img_counter}{ext}]"
                images_data.append({
                    "placeholder": placeholder,
                    "filename": fname,
                    "src": f"articles/{user_info['save_dir_prefix']}/{date_str}/images/{fname}",
                    "alt": f"图片{img_counter}",
                    "caption": ""
                })
                
                img.replace_with(placeholder)
                img_counter += 1
                
            except Exception as e:
                print(f"下载图片失败: {e}")
                continue

    # 提取文本内容
    if mode == 'full':
        lines = []
        for block in soup.find_all(['p', 'div', 'li']):
            text = ''.join(block.stripped_strings)
            if text.strip():
                lines.append(text)
        content_text = '\n'.join(lines)
    else:
        lines = []
        for p in soup.find_all('p'):
            text = ''.join(p.stripped_strings)
            if text.strip():
                lines.append(text)
        content_text = '\n\n'.join(lines)

    # 保存文本文件
    txt_path = os.path.join(save_dir, f"{base_fname}.txt")
    with open(txt_path, 'w', encoding='utf-8-sig') as f:
        f.write(content_text)

    # 保存Word文档（如果是full模式）
    docx_path = None
    if mode == 'full':
        try:
            from docx import Document
            from docx.shared import Inches
            
            doc = Document()
            img_placeholder_pattern = r'(\[图片:[^\]]+\])'
            
            for para in content_text.split('\n'):
                if not para.strip():
                    continue
                    
                parts = re.split(img_placeholder_pattern, para)
                for part in parts:
                    if not part.strip():
                        continue
                    
                    img_match = re.fullmatch(r'\[图片:(.*?)\]', part.strip())
                    if img_match:
                        img_filename = img_match.group(1)
                        img_path = os.path.join(img_folder, img_filename)
                        if os.path.exists(img_path):
                            try:
                                doc.add_picture(img_path, width=Inches(4.5))
                            except:
                                doc.add_paragraph('[图片插入失败]')
                    else:
                        doc.add_paragraph(part)
            
            docx_path = os.path.join(save_dir, f"{base_fname}.docx")
            doc.save(docx_path)
            
        except ImportError:
            print("警告：未安装python-docx，跳过Word文档生成")
        except Exception as e:
            print(f"生成Word文档失败: {e}")

    return {
        "content": content_text,
        "images": images_data,
        "files": {
            "txt": f"articles/{user_info['save_dir_prefix']}/{date_str}/{base_fname}.txt",
            "docx": f"articles/{user_info['save_dir_prefix']}/{date_str}/{base_fname}.docx" if docx_path else None
        },
        "word_count": len(content_text.replace('\n', '').replace(' ', '')),
        "image_count": len(images_data)
    }

def crawl_jiuyan_article(user_key, date_str=None, try_second_time=True):
    if user_key not in JIUYAN_USERS:
        print(f"未找到用户配置: {user_key}")
        return None
    
    user_info = JIUYAN_USERS[user_key]
    
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d')
        except:
            print("日期格式错误")
            return None
    else:
        target_date = datetime.now()
    
    date_str = target_date.strftime('%Y-%m-%d')
    
    try:
        title, article_url = get_target_article_url(user_info['user_url'], date_str)
        
        if not title and try_second_time and user_info.get('retry_time'):
            now = datetime.now()
            retry_time_str = user_info['retry_time']
            retry_time = now.replace(hour=int(retry_time_str[:2]), minute=int(retry_time_str[3:]), second=0, microsecond=0)
            wait_sec = (retry_time - now).total_seconds()
            if wait_sec > 0:
                print(f"未找到今日文章，等待到{retry_time_str}再试一次（约{int(wait_sec)}秒）")
                time.sleep(wait_sec)
            title, article_url = get_target_article_url(user_info['user_url'], date_str)
        
        if not title:
            print(f"未找到{user_info['user_name']} {date_str}的文章")
            return None

        print(f"找到文章：{title}")
        
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)
        
        # 确定保存路径
        if user_key == '优秀阿呆':
            save_dir = os.path.join('articles', user_info['save_dir_prefix'])
        else:
            save_dir = os.path.join('articles', user_info['save_dir_prefix'], date_str)

        soup, article_url, _ = fetch_article_content(article_url)
        if soup is None:
            print("获取文章内容失败")
            return None

        # 保存文章并获取数据
        article_data = save_article_and_generate_json(soup, article_url, save_dir, safe_title, user_info, date_str)
        
        # 构建完整的文章信息
        result = {
            "author": user_info['user_name'],
            "title": title,
            "publish_time": user_info['default_time'],
            "date": date_str,
            "url": article_url,
            **article_data
        }
        
        print(f"成功保存 {user_info['user_name']} 的文章: {title}")
        return result
        
    except Exception as e:
        print(f"爬取 {user_info['user_name']} 文章时发生错误: {e}")
        return None

def save_articles_index(articles_data, date_str):
    """保存文章索引数据"""
    os.makedirs('articles', exist_ok=True)
    
    # 读取现有索引
    index_file = 'articles/index.json'
    if os.path.exists(index_file):
        with open(index_file, 'r', encoding='utf-8') as f:
            try:
                index_data = json.load(f)
                # 如果是旧格式，转换为新格式
                if 'users' in index_data or 'recent_articles' in index_data:
                    # 提取日期数据
                    new_index_data = {}
                    for key, value in index_data.items():
                        if key.startswith('20') and isinstance(value, dict) and 'articles' in value:
                            new_index_data[key] = value
                    index_data = new_index_data
            except:
                index_data = {}
    else:
        index_data = {}
    
    # 更新当日数据
    index_data[date_str] = {
        "date": date_str,
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "articles": articles_data
    }
    
    # 保存索引
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
    
    print(f"文章索引已更新: {date_str}")


def crawl_all_jiuyan_articles(date_str=None):
    print("开始爬取韭研公社文章...")
    articles_data = []
    
    for user_key in JIUYAN_USERS.keys():
        print(f"\n处理: {user_key}")
        article_data = crawl_jiuyan_article(user_key, date_str)
        if article_data:
            articles_data.append(article_data)
        time.sleep(2)
    
    # 保存文章索引
    if articles_data:
        current_date = date_str or datetime.now().strftime('%Y-%m-%d')
        save_articles_index(articles_data, current_date)
    
    print(f"\n韭研公社文章爬取完成！成功: {len(articles_data)}/{len(JIUYAN_USERS)}")
    return articles_data

# ========== 网页生成函数 ==========

def generate_main_page():
    """生成主页"""
    html_content = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📊 数据中心导航</title>
    <link rel="stylesheet" href="assets/css/style.css">
</head>
<body>
    <div class="container">
        <header class="main-header">
            <h1>📊 数据中心导航</h1>
            <p class="subtitle">Data Center Navigation</p>
        </header>
        
        <div class="navigation-cards">
            <div class="nav-card" onclick="location.href='limitup.html'">
                <div class="card-icon">💹</div>
                <h3>财联社涨停池</h3>
                <p>查看每日涨停数据</p>
                <div class="card-status" id="limitupStatus">最新更新: 加载中...</div>
                <div class="card-button">进入查看</div>
            </div>
            
            <div class="nav-card" onclick="location.href='jiuyan.html'">
                <div class="card-icon">📰</div>
                <h3>韭研公社文章</h3>
                <p>查看研报文章</p>
                <div class="card-status" id="articlesStatus">最新更新: 加载中...</div>
                <div class="card-button">进入查看</div>
            </div>
        </div>
        
        <div class="stats-panel">
            <h3>📈 快速统计</h3>
            <div class="stats-grid">
                <div class="stat-item">
                    <span class="stat-label">今日涨停</span>
                    <span class="stat-value" id="todayLimitUp">--</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">本周文章</span>
                    <span class="stat-value" id="weeklyArticles">--</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">数据状态</span>
                    <span class="stat-value" id="dataStatus">正常</span>
                </div>
            </div>
        </div>
        
        <div class="quick-links">
            <h3>🔗 快速链接</h3>
            <div class="links-grid">
                <a href="json_viewer.html" class="quick-link">JSON数据查看器</a>
                <a href="#" class="quick-link" onclick="showAbout()">关于项目</a>
                <a href="https://github.com" class="quick-link" target="_blank">GitHub仓库</a>
            </div>
        </div>
    </div>
    
    <script src="assets/js/common.js"></script>
    <script>
        // 加载统计数据
        loadMainPageStats();
    </script>
</body>
</html>'''
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html_content)

def generate_limitup_page():
    """生成涨停池页面"""
    html_content = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>💹 财联社涨停池数据</title>
    <link rel="stylesheet" href="assets/css/style.css">
</head>
<body>
    <div class="container">
        <header class="page-header">
            <div class="header-nav">
                <a href="index.html" class="back-link">← 返回首页</a>
                <h1>💹 财联社涨停池数据</h1>
            </div>
        </header>
        
        <div class="controls-panel">
            <div class="search-section">
                <input type="text" id="searchInput" placeholder="搜索股票代码或名称..." class="search-input">
            </div>
            <div class="date-section">
                <select id="dateSelect" class="date-select">
                    <option value="">选择日期...</option>
                </select>
                <button id="copyDataBtn" class="action-btn">📋 复制数据</button>
                <button id="viewJsonBtn" class="action-btn">📄 查看JSON</button>
            </div>
        </div>
        
        <div class="data-info" id="dataInfo" style="display: none;">
            <div class="info-item">
                <span class="info-label">更新时间:</span>
                <span id="updateTime">--</span>
            </div>
            <div class="info-item">
                <span class="info-label">涨停股数:</span>
                <span id="stockCount">--</span>
            </div>
        </div>
        
        <div class="stocks-container" id="stocksContainer">
            <div class="loading">请选择日期查看数据...</div>
        </div>
    </div>
    
    <script src="assets/js/common.js"></script>
    <script src="assets/js/limitup.js"></script>
</body>
</html>'''
    
    with open('limitup.html', 'w', encoding='utf-8') as f:
        f.write(html_content)

def generate_jiuyan_page():
    """生成韭研公社文章页面"""
    html_content = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📰 韭研公社研报文章</title>
    <link rel="stylesheet" href="assets/css/style.css">
</head>
<body>
    <div class="container">
        <header class="page-header">
            <div class="header-nav">
                <a href="index.html" class="back-link">← 返回首页</a>
                <h1>📰 韭研公社研报文章</h1>
            </div>
        </header>
        
        <div class="controls-panel">
            <div class="filter-section">
                <select id="authorFilter" class="filter-select">
                    <option value="">全部作者</option>
                    <option value="盘前纪要">盘前纪要</option>
                    <option value="盘前解读">盘前解读</option>
                    <option value="优秀阿呆">优秀阿呆</option>
                </select>
                <select id="dateFilter" class="filter-select">
                    <option value="">选择日期</option>
                </select>
                <button id="refreshBtn" class="action-btn">🔄 刷新</button>
            </div>
        </div>
        
        <div class="articles-container" id="articlesContainer">
            <div class="loading">加载中...</div>
        </div>
    </div>
    
    <!-- 文章详情模态框 -->
    <div id="articleModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <span class="close" onclick="closeArticleModal()">&times;</span>
                <h2 id="modalTitle">文章标题</h2>
                <div class="modal-actions">
                    <button onclick="copyArticleContent('full')" class="action-btn">📋 复制全文</button>
                    <button onclick="copyArticleContent('text')" class="action-btn">📄 纯文本</button>
                    <button onclick="downloadArticle()" class="action-btn">💾 下载</button>
                </div>
            </div>
            <div class="modal-body">
                <div class="article-meta" id="articleMeta"></div>
                <div class="article-content" id="articleContent"></div>
            </div>
        </div>
    </div>
    
    <!-- 图片查看器 -->
    <div id="imageViewer" class="image-viewer">
        <div class="viewer-content">
            <span class="viewer-close" onclick="closeImageViewer()">&times;</span>
            <img id="viewerImage" src="" alt="">
            <div class="viewer-controls">
                <button onclick="prevImage()" class="viewer-btn">← 上一张</button>
                <button onclick="downloadCurrentImage()" class="viewer-btn">💾 下载</button>
                <button onclick="nextImage()" class="viewer-btn">下一张 →</button>
            </div>
            <div class="viewer-info" id="viewerInfo">图片 1 / 1</div>
        </div>
    </div>
    
    <script src="assets/js/common.js"></script>
    <script src="assets/js/jiuyan.js"></script>
</body>
</html>'''
    
    with open('jiuyan.html', 'w', encoding='utf-8') as f:
        f.write(html_content)

def generate_json_viewer():
    """生成JSON查看器页面"""
    html_content = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📄 JSON数据查看器</title>
    <link rel="stylesheet" href="assets/css/style.css">
</head>
<body>
    <div class="container">
        <header class="page-header">
            <div class="header-nav">
                <a href="index.html" class="back-link">← 返回首页</a>
                <h1>📄 JSON数据查看器</h1>
            </div>
        </header>
        
        <div class="controls-panel">
            <div class="json-controls">
                <select id="dataTypeSelect" class="filter-select">
                    <option value="limitup">涨停池数据</option>
                    <option value="articles">文章数据</option>
                </select>
                <select id="dateSelect" class="filter-select">
                    <option value="">选择日期</option>
                </select>
                <button id="copyJsonBtn" class="action-btn">📋 复制JSON</button>
            </div>
        </div>
        
        <div class="json-container">
            <pre><code id="jsonContent">请选择数据类型和日期...</code></pre>
        </div>
    </div>
    
    <script src="assets/js/common.js"></script>
    <script>
        loadJsonViewer();
    </script>
</body>
</html>'''
    
    with open('json_viewer.html', 'w', encoding='utf-8') as f:
        f.write(html_content)

def generate_css():
    """生成CSS样式文件"""
    os.makedirs('assets/css', exist_ok=True)
    
    css_content = '''/* 基础样式 */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
    background-color: #f8f9fa;
    color: #333;
    line-height: 1.6;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

/* 头部样式 */
.main-header {
    text-align: center;
    margin-bottom: 40px;
    padding: 40px 0;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-radius: 15px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.1);
}

.main-header h1 {
    font-size: 2.5rem;
    margin-bottom: 10px;
}

.subtitle {
    font-size: 1.1rem;
    opacity: 0.9;
}

.page-header {
    margin-bottom: 30px;
}

.header-nav {
    display: flex;
    align-items: center;
    gap: 20px;
    margin-bottom: 20px;
}

.back-link {
    color: #667eea;
    text-decoration: none;
    font-weight: 500;
    transition: color 0.3s;
}

.back-link:hover {
    color: #5a67d8;
}

/* 导航卡片 */
.navigation-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 30px;
    margin-bottom: 40px;
}

.nav-card {
    background: white;
    border-radius: 15px;
    padding: 30px;
    text-align: center;
    box-shadow: 0 5px 20px rgba(0,0,0,0.1);
    cursor: pointer;
    transition: transform 0.3s, box-shadow 0.3s;
}

.nav-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 10px 30px rgba(0,0,0,0.15);
}

.card-icon {
    font-size: 3rem;
    margin-bottom: 20px;
}

.nav-card h3 {
    font-size: 1.5rem;
    margin-bottom: 10px;
    color: #2d3748;
}

.nav-card p {
    color: #718096;
    margin-bottom: 20px;
}

.card-status {
    font-size: 0.9rem;
    color: #667eea;
    margin-bottom: 20px;
}

.card-button {
    background: #667eea;
    color: white;
    padding: 12px 24px;
    border-radius: 25px;
    font-weight: 500;
    transition: background 0.3s;
}

.nav-card:hover .card-button {
    background: #5a67d8;
}

/* 统计面板 */
.stats-panel {
    background: white;
    border-radius: 15px;
    padding: 30px;
    margin-bottom: 30px;
    box-shadow: 0 5px 20px rgba(0,0,0,0.1);
}

.stats-panel h3 {
    margin-bottom: 20px;
    color: #2d3748;
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 20px;
}

.stat-item {
    text-align: center;
    padding: 20px;
    background: #f7fafc;
    border-radius: 10px;
}

.stat-label {
    display: block;
    font-size: 0.9rem;
    color: #718096;
    margin-bottom: 5px;
}

.stat-value {
    display: block;
    font-size: 1.5rem;
    font-weight: bold;
    color: #667eea;
}

/* 快速链接 */
.quick-links {
    background: white;
    border-radius: 15px;
    padding: 30px;
    box-shadow: 0 5px 20px rgba(0,0,0,0.1);
}

.quick-links h3 {
    margin-bottom: 20px;
    color: #2d3748;
}

.links-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 15px;
}

.quick-link {
    display: block;
    padding: 15px 20px;
    background: #f7fafc;
    color: #667eea;
    text-decoration: none;
    border-radius: 10px;
    text-align: center;
    transition: all 0.3s;
}

.quick-link:hover {
    background: #667eea;
    color: white;
}

/* 控制面板 */
.controls-panel {
    background: white;
    border-radius: 15px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 5px 20px rgba(0,0,0,0.1);
}

.search-section, .date-section, .filter-section {
    display: flex;
    gap: 15px;
    align-items: center;
    flex-wrap: wrap;
}

.search-input, .date-select, .filter-select {
    padding: 12px 15px;
    border: 2px solid #e2e8f0;
    border-radius: 8px;
    font-size: 1rem;
    transition: border-color 0.3s;
}

.search-input:focus, .date-select:focus, .filter-select:focus {
    outline: none;
    border-color: #667eea;
}

.search-input {
    flex: 1;
    min-width: 250px;
}

.action-btn {
    padding: 12px 20px;
    background: #667eea;
    color: white;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 0.9rem;
    transition: background 0.3s;
}

.action-btn:hover {
    background: #5a67d8;
}

/* 数据信息 */
.data-info {
    background: white;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
    display: flex;
    gap: 30px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

.info-item {
    display: flex;
    flex-direction: column;
}

.info-label {
    font-size: 0.9rem;
    color: #718096;
    margin-bottom: 5px;
}

.info-item span:last-child {
    font-weight: bold;
    color: #2d3748;
}

/* 股票容器 */
.stocks-container {
    background: white;
    border-radius: 15px;
    padding: 20px;
    box-shadow: 0 5px 20px rgba(0,0,0,0.1);
}

.stock-card {
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 15px;
    transition: all 0.3s;
}

.stock-card:hover {
    border-color: #667eea;
    box-shadow: 0 5px 15px rgba(102, 126, 234, 0.1);
}

.stock-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
}

.stock-code {
    font-weight: bold;
    color: #667eea;
}

.stock-name {
    font-size: 1.1rem;
    font-weight: 600;
    color: #2d3748;
}

.stock-price {
    font-size: 1.2rem;
    font-weight: bold;
    color: #e53e3e;
}

.stock-change {
    background: #e53e3e;
    color: white;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.9rem;
}

.stock-details {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 10px;
    font-size: 0.9rem;
    color: #718096;
}

/* 文章容器 */
.articles-container {
    background: white;
    border-radius: 15px;
    padding: 20px;
    box-shadow: 0 5px 20px rgba(0,0,0,0.1);
}

.article-card {
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 25px;
    margin-bottom: 20px;
    transition: all 0.3s;
}

.article-card:hover {
    border-color: #667eea;
    box-shadow: 0 5px 15px rgba(102, 126, 234, 0.1);
}

.article-header {
    margin-bottom: 15px;
}

.article-title {
    font-size: 1.3rem;
    font-weight: 600;
    color: #2d3748;
    margin-bottom: 8px;
}

.article-meta {
    display: flex;
    gap: 20px;
    font-size: 0.9rem;
    color: #718096;
    margin-bottom: 15px;
}

.article-preview {
    color: #4a5568;
    margin-bottom: 15px;
    line-height: 1.6;
}

.article-stats {
    display: flex;
    gap: 15px;
    font-size: 0.85rem;
    color: #718096;
    margin-bottom: 15px;
}

.article-actions {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
}

.article-btn {
    padding: 8px 16px;
    border: 1px solid #667eea;
    background: transparent;
    color: #667eea;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.9rem;
    transition: all 0.3s;
}

.article-btn:hover {
    background: #667eea;
    color: white;
}

.article-btn.primary {
    background: #667eea;
    color: white;
}

.article-btn.primary:hover {
    background: #5a67d8;
}

/* 模态框 */
.modal {
    display: none;
    position: fixed;
    z-index: 1000;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0,0,0,0.5);
}

.modal-content {
    background-color: white;
    margin: 2% auto;
    padding: 0;
    border-radius: 15px;
    width: 90%;
    max-width: 800px;
    max-height: 90vh;
    overflow: hidden;
    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
}

.modal-header {
    padding: 20px 25px;
    border-bottom: 1px solid #e2e8f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #f7fafc;
}

.modal-header h2 {
    margin: 0;
    color: #2d3748;
    flex: 1;
}

.close {
    color: #718096;
    float: right;
    font-size: 28px;
    font-weight: bold;
    cursor: pointer;
    margin-left: 20px;
}

.close:hover {
    color: #2d3748;
}

.modal-actions {
    display: flex;
    gap: 10px;
}

.modal-body {
    padding: 25px;
    max-height: 70vh;
    overflow-y: auto;
}

.article-content {
    line-height: 1.8;
    color: #2d3748;
}

.article-content h1, .article-content h2, .article-content h3 {
    margin: 20px 0 10px 0;
    color: #1a202c;
}

.article-content p {
    margin-bottom: 15px;
}

.article-image {
    max-width: 100%;
    height: auto;
    border-radius: 8px;
    margin: 20px 0;
    cursor: pointer;
    transition: transform 0.3s;
}

.article-image:hover {
    transform: scale(1.02);
}

.image-caption {
    text-align: center;
    font-size: 0.9rem;
    color: #718096;
    margin-top: 5px;
}

/* 图片查看器 */
.image-viewer {
    display: none;
    position: fixed;
    z-index: 2000;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0,0,0,0.9);
}

.viewer-content {
    position: relative;
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}

.viewer-close {
    position: absolute;
    top: 20px;
    right: 30px;
    color: white;
    font-size: 40px;
    font-weight: bold;
    cursor: pointer;
    z-index: 2001;
}

.viewer-close:hover {
    opacity: 0.7;
}

#viewerImage {
    max-width: 90%;
    max-height: 80%;
    object-fit: contain;
}

.viewer-controls {
    position: absolute;
    bottom: 80px;
    display: flex;
    gap: 20px;
}

.viewer-btn {
    padding: 12px 20px;
    background: rgba(255,255,255,0.2);
    color: white;
    border: 1px solid rgba(255,255,255,0.3);
    border-radius: 6px;
    cursor: pointer;
    transition: background 0.3s;
}

.viewer-btn:hover {
    background: rgba(255,255,255,0.3);
}

.viewer-info {
    position: absolute;
    bottom: 30px;
    color: white;
    font-size: 1.1rem;
}

/* JSON容器 */
.json-container {
    background: white;
    border-radius: 15px;
    padding: 20px;
    box-shadow: 0 5px 20px rgba(0,0,0,0.1);
}

.json-container pre {
    background: #f8f9fa;
    border: 1px solid #e9ecef;
    border-radius: 8px;
    padding: 20px;
    overflow-x: auto;
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 0.9rem;
    line-height: 1.5;
    max-height: 70vh;
}

.json-container code {
    color: #495057;
}

.json-controls {
    display: flex;
    gap: 15px;
    align-items: center;
    flex-wrap: wrap;
}

/* 加载状态 */
.loading {
    text-align: center;
    padding: 40px;
    color: #718096;
    font-size: 1.1rem;
}

/* Toast 提示样式 */
.toast {
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 12px 20px;
    border-radius: 6px;
    color: white;
    font-weight: 500;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    z-index: 10000;
    max-width: 300px;
}

.toast-success {
    background-color: #48bb78;
}

.toast-error {
    background-color: #f56565;
}

/* 响应式设计 */
@media (max-width: 768px) {
    .container {
        padding: 15px;
    }
    
    .main-header {
        padding: 30px 20px;
    }
    
    .main-header h1 {
        font-size: 2rem;
    }
    
    .navigation-cards {
        grid-template-columns: 1fr;
    }
    
    .nav-card {
        padding: 20px;
    }
    
    .header-nav {
        flex-direction: column;
        align-items: flex-start;
        gap: 10px;
    }
    
    .search-section, .date-section, .filter-section {
        flex-direction: column;
        align-items: stretch;
    }
    
    .search-input {
        min-width: auto;
    }
    
    .data-info {
        flex-direction: column;
        gap: 15px;
    }
    
    .stock-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 10px;
    }
    
    .stock-details {
        grid-template-columns: 1fr;
    }
    
    .article-actions {
        justify-content: center;
    }
    
    .modal-content {
        width: 95%;
        margin: 5% auto;
    }
    
    .modal-header {
        flex-direction: column;
        gap: 15px;
        align-items: flex-start;
    }
    
    .modal-actions {
        align-self: stretch;
        justify-content: center;
    }
    
    .viewer-controls {
        bottom: 120px;
        flex-direction: column;
        gap: 10px;
    }
    
    .json-controls {
        flex-direction: column;
        align-items: stretch;
    }
    
    .stats-grid {
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    }
    
    .article-meta {
        flex-direction: column;
        gap: 8px;
    }
}

@media (max-width: 480px) {
    .main-header {
        padding: 25px 15px;
    }
    
    .main-header h1 {
        font-size: 1.8rem;
    }
    
    .subtitle {
        font-size: 1rem;
    }
    
    .stats-grid {
        grid-template-columns: 1fr;
    }
    
    .links-grid {
        grid-template-columns: 1fr;
    }
    
    .modal-body {
        padding: 20px;
    }
    
    #viewerImage {
        max-width: 95%;
        max-height: 70%;
    }
    
    .viewer-close {
        top: 10px;
        right: 15px;
        font-size: 30px;
    }
    
    .viewer-controls {
        bottom: 100px;
    }
    
    .viewer-btn {
        padding: 10px 15px;
        font-size: 0.9rem;
    }
    
    .article-card {
        padding: 20px;
    }
    
    .stock-card {
        padding: 15px;
    }
    
    .nav-card {
        padding: 20px 15px;
    }
    
    .card-icon {
        font-size: 2.5rem;
    }
}

/* 动画效果 */
@keyframes fadeIn {
    from { 
        opacity: 0; 
        transform: translateY(20px); 
    }
    to { 
        opacity: 1; 
        transform: translateY(0); 
    }
}

@keyframes slideIn {
    from { 
        transform: translateX(100%); 
        opacity: 0; 
    }
    to { 
        transform: translateX(0); 
        opacity: 1; 
    }
}

@keyframes slideOut {
    from { 
        transform: translateX(0); 
        opacity: 1; 
    }
    to { 
        transform: translateX(100%); 
        opacity: 0; 
    }
}

@keyframes pulse {
    0% { 
        transform: scale(1); 
    }
    50% { 
        transform: scale(1.05); 
    }
    100% { 
        transform: scale(1); 
    }
}

.article-card, .stock-card {
    animation: fadeIn 0.5s ease-out;
}

.nav-card:hover {
    animation: pulse 0.6s ease-in-out;
}

/* 滚动条样式 */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 4px;
}

::-webkit-scrollbar-thumb {
    background: #c1c1c1;
    border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
    background: #a8a8a8;
}

/* Firefox滚动条 */
* {
    scrollbar-width: thin;
    scrollbar-color: #c1c1c1 #f1f1f1;
}

/* 选择文本样式 */
::selection {
    background-color: #667eea;
    color: white;
}

::-moz-selection {
    background-color: #667eea;
    color: white;
}

/* 焦点样式 */
button:focus, input:focus, select:focus {
    outline: 2px solid #667eea;
    outline-offset: 2px;
}

/* 禁用状态 */
.action-btn:disabled {
    background-color: #e2e8f0;
    color: #a0aec0;
    cursor: not-allowed;
}

.action-btn:disabled:hover {
    background-color: #e2e8f0;
}

/* 加载动画 */
.loading::after {
    content: '';
    display: inline-block;
    width: 20px;
    height: 20px;
    border: 3px solid #f3f3f3;
    border-top: 3px solid #667eea;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-left: 10px;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

/* 暗色主题支持 */
@media (prefers-color-scheme: dark) {
    body {
        background-color: #1a202c;
        color: #e2e8f0;
    }
    
    .nav-card, .stats-panel, .quick-links, .controls-panel, 
    .stocks-container, .articles-container, .json-container,
    .modal-content {
        background-color: #2d3748;
        color: #e2e8f0;
    }
    
    .stock-card, .article-card {
        background-color: #4a5568;
        border-color: #718096;
    }
    
    .search-input, .date-select, .filter-select {
        background-color: #4a5568;
        border-color: #718096;
        color: #e2e8f0;
    }
    
    .json-container pre {
        background-color: #4a5568;
        border-color: #718096;
    }
    
    .stat-item {
        background-color: #4a5568;
    }
    
    .quick-link {
        background-color: #4a5568;
    }
}

/* 打印样式 */
@media print {
    .controls-panel, .modal-actions, .article-actions,
    .viewer-controls, .back-link {
        display: none !important;
    }
    
    .container {
        max-width: none;
        padding: 0;
    }
    
    .article-card, .stock-card {
        break-inside: avoid;
        box-shadow: none;
        border: 1px solid #ccc;
    }
    
    .main-header {
        background: none !important;
        color: #000 !important;
    }
}'''
    
    with open('assets/css/style.css', 'w', encoding='utf-8') as f:
        f.write(css_content)
    
    print("CSS文件生成完成: assets/css/style.css")

def generate_js_files():
    """生成JavaScript文件"""
    os.makedirs('assets/js', exist_ok=True)
    
    # common.js
    common_js = '''// assets/js/common.js - 通用功能

// 复制到剪贴板
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast('复制成功！');
        return true;
    } catch (err) {
        console.error('复制失败:', err);
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            showToast('复制成功！');
            return true;
        } catch (e) {
            showToast('复制失败，请手动复制');
            return false;
        } finally {
            document.body.removeChild(textArea);
        }
    }
}

// 显示提示消息
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'success' ? '#48bb78' : '#f56565'};
        color: white;
        padding: 12px 20px;
        border-radius: 6px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        if (document.body.contains(toast)) {
            document.body.removeChild(toast);
        }
    }, 3000);
}

// 防抖函数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 显示加载状态
function showLoading(container) {
    container.innerHTML = '<div class="loading">加载中...</div>';
}

// 显示错误
function showError(container, message) {
    container.innerHTML = `<div class="loading">错误: ${message}</div>`;
}'''
    
    with open('assets/js/common.js', 'w', encoding='utf-8') as f:
        f.write(common_js)
    
    # limitup.js
    limitup_js = '''// assets/js/limitup.js - 涨停池页面功能

let currentLimitUpData = null;

document.addEventListener('DOMContentLoaded', function() {
    console.log('涨停池页面初始化...');
    initLimitUpPage();
});

async function initLimitUpPage() {
    await loadDateOptions();
    setupEventListeners();
}

// 加载日期选项
async function loadDateOptions() {
    try {
        console.log('正在加载日期选项...');
        const response = await fetch('data/index.json');
        if (!response.ok) throw new Error('无法加载日期数据');
        
        const dates = await response.json();
        console.log('日期数据:', dates);
        
        const dateSelect = document.getElementById('dateSelect');
        if (!dateSelect) {
            console.error('dateSelect元素未找到');
            return;
        }
        
        dateSelect.innerHTML = '<option value="">选择日期...</option>';
        dates.forEach(date => {
            const option = document.createElement('option');
            option.value = date;
            option.textContent = date;
            dateSelect.appendChild(option);
        });
        
        // 默认选择最新日期
        if (dates.length > 0) {
            dateSelect.value = dates[0];
            await loadLimitUpData(dates[0]);
        }
    } catch (error) {
        console.error('加载日期选项失败:', error);
        const container = document.getElementById('stocksContainer');
        if (container) {
            showError(container, '加载日期数据失败');
        }
    }
}

// 设置事件监听器
function setupEventListeners() {
    const dateSelect = document.getElementById('dateSelect');
    const searchInput = document.getElementById('searchInput');
    
    if (dateSelect) {
        dateSelect.addEventListener('change', (e) => {
            if (e.target.value) {
                loadLimitUpData(e.target.value);
            }
        });
    }
    
    if (searchInput) {
        searchInput.addEventListener('input', debounce(filterStocks, 300));
    }
}

// 加载涨停池数据
async function loadLimitUpData(date) {
    const container = document.getElementById('stocksContainer');
    const dataInfo = document.getElementById('dataInfo');
    
    if (!container) {
        console.error('stocksContainer元素未找到');
        return;
    }
    
    showLoading(container);
    if (dataInfo) {
        dataInfo.style.display = 'none';
    }
    
    try {
        console.log('正在加载涨停池数据:', date);
        const response = await fetch(`data/${date}.json`);
        if (!response.ok) throw new Error('数据加载失败');
        
        currentLimitUpData = await response.json();
        console.log('涨停池数据:', currentLimitUpData);
        
        // 更新数据信息
        const updateTimeEl = document.getElementById('updateTime');
        const stockCountEl = document.getElementById('stockCount');
        
        if (updateTimeEl) {
            updateTimeEl.textContent = currentLimitUpData.update_time;
        }
        if (stockCountEl) {
            stockCountEl.textContent = `${currentLimitUpData.count}只`;
        }
        if (dataInfo) {
            dataInfo.style.display = 'flex';
        }
        
        // 渲染股票列表
        renderStocks(currentLimitUpData.stocks);
        
    } catch (error) {
        console.error('加载涨停池数据失败:', error);
        showError(container, '加载数据失败');
    }
}

// 渲染股票列表
function renderStocks(stocks) {
    const container = document.getElementById('stocksContainer');
    
    if (!container) {
        console.error('stocksContainer元素未找到');
        return;
    }
    
    if (!stocks || stocks.length === 0) {
        container.innerHTML = '<div class="loading">暂无数据</div>';
        return;
    }
    
    const stocksHtml = stocks.map(stock => `
        <div class="stock-card" data-code="${stock.code}" data-name="${stock.name}">
            <div class="stock-header">
                <div>
                    <div class="stock-code">${stock.code}</div>
                    <div class="stock-name">${stock.name}</div>
                </div>
                <div>
                    <div class="stock-price">¥${stock.price}</div>
                    <div class="stock-change">${stock.change_percent}</div>
                </div>
            </div>
            <div class="stock-details">
                <div><strong>涨停时间:</strong> ${stock.limit_up_time}</div>
                <div><strong>涨停原因:</strong> ${stock.reason}</div>
                <div><strong>所属板块:</strong> ${stock.plates || '暂无'}</div>
            </div>
        </div>
    `).join('');
    
    container.innerHTML = stocksHtml;
}

// 筛选股票
function filterStocks() {
    const searchInput = document.getElementById('searchInput');
    if (!searchInput) return;
    
    const searchTerm = searchInput.value.toLowerCase();
    const stockCards = document.querySelectorAll('.stock-card');
    
    stockCards.forEach(card => {
        const code = card.dataset.code.toLowerCase();
        const name = card.dataset.name.toLowerCase();
        
        if (code.includes(searchTerm) || name.includes(searchTerm)) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
}'''
    
    with open('assets/js/limitup.js', 'w', encoding='utf-8') as f:
        f.write(limitup_js)
    
    # jiuyan.js
    jiuyan_js = '''// assets/js/jiuyan.js - 韭研公社文章页面功能

let currentArticlesData = {};

document.addEventListener('DOMContentLoaded', function() {
    console.log('韭研公社页面初始化...');
    initJiuyanPage();
});

async function initJiuyanPage() {
    await loadArticlesData();
    setupEventListeners();
}

// 加载文章数据
async function loadArticlesData() {
    try {
        console.log('正在加载文章数据...');
        const response = await fetch('articles/index.json');
        if (!response.ok) throw new Error('无法加载文章数据');
        
        currentArticlesData = await response.json();
        console.log('文章数据:', currentArticlesData);
        
        // 填充日期选项
        const dates = Object.keys(currentArticlesData).sort().reverse();
        const dateFilter = document.getElementById('dateFilter');
        
        if (!dateFilter) {
            console.error('dateFilter元素未找到');
            return;
        }
        
        dateFilter.innerHTML = '<option value="">选择日期</option>';
        dates.forEach(date => {
            const option = document.createElement('option');
            option.value = date;
            option.textContent = date;
            dateFilter.appendChild(option);
        });
        
        // 默认加载最新日期
        if (dates.length > 0) {
            dateFilter.value = dates[0];
            filterAndRenderArticles();
        }
        
    } catch (error) {
        console.error('加载文章数据失败:', error);
        const container = document.getElementById('articlesContainer');
        if (container) {
            showError(container, '加载文章数据失败');
        }
    }
}

// 设置事件监听器
function setupEventListeners() {
    const authorFilter = document.getElementById('authorFilter');
    const dateFilter = document.getElementById('dateFilter');
    const refreshBtn = document.getElementById('refreshBtn');
    
    if (authorFilter) {
        authorFilter.addEventListener('change', filterAndRenderArticles);
    }
    
    if (dateFilter) {
        dateFilter.addEventListener('change', filterAndRenderArticles);
    }
    
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            location.reload();
        });
    }
}

// 筛选并渲染文章
function filterAndRenderArticles() {
    const authorFilter = document.getElementById('authorFilter');
    const dateFilter = document.getElementById('dateFilter');
    const container = document.getElementById('articlesContainer');
    
    if (!authorFilter || !dateFilter || !container) {
        console.error('筛选元素未找到');
        return;
    }
    
    const authorValue = authorFilter.value;
    const dateValue = dateFilter.value;
    
    let articles = [];
    
    // 根据日期筛选
    if (dateValue && currentArticlesData[dateValue]) {
        articles = currentArticlesData[dateValue].articles || [];
    } else {
        // 显示所有文章
        Object.values(currentArticlesData).forEach(dayData => {
            if (dayData.articles) {
                articles = articles.concat(dayData.articles);
            }
        });
    }
    
    // 根据作者筛选
    if (authorValue) {
        articles = articles.filter(article => article.author === authorValue);
    }
    
    // 按日期排序（最新在前）
    articles.sort((a, b) => new Date(b.date) - new Date(a.date));
    
    renderArticles(articles);
}

// 渲染文章列表
function renderArticles(articles) {
    const container = document.getElementById('articlesContainer');
    
    if (!container) {
        console.error('articlesContainer元素未找到');
        return;
    }
    
    if (!articles || articles.length === 0) {
        container.innerHTML = '<div class="loading">暂无文章数据</div>';
        return;
    }
    
    const articlesHtml = articles.map((article, index) => `
        <div class="article-card">
            <div class="article-header">
                <h3 class="article-title">${article.title}</h3>
                <div class="article-meta">
                    <span>📝 ${article.author}</span>
                    <span>📅 ${article.date} ${article.publish_time}</span>
                </div>
            </div>
            <div class="article-preview">
                ${getArticlePreview(article.content)}
            </div>
            <div class="article-stats">
                <span>📊 ${article.word_count || 0}字</span>
                <span>📷 ${article.image_count || 0}张图片</span>
            </div>
        </div>
    `).join('');
    
    container.innerHTML = articlesHtml;
}

// 获取文章预览
function getArticlePreview(content, maxLength = 200) {
    if (!content) return '暂无预览';
    
    // 移除图片占位符
    const textOnly = content.replace(/\\[图片:[^\\]]+\\]/g, '');
    
    if (textOnly.length <= maxLength) {
        return textOnly;
    }
    
    return textOnly.substring(0, maxLength) + '...';
}'''
    
    with open('assets/js/jiuyan.js', 'w', encoding='utf-8') as f:
        f.write(jiuyan_js)
    
    print("JavaScript文件生成完成:")
    print("- assets/js/common.js")
    print("- assets/js/limitup.js") 
    print("- assets/js/jiuyan.js")



def generate_all_pages():
    """生成所有网页"""
    print("生成网页文件...")
    
    generate_main_page()
    generate_limitup_page()
    generate_jiuyan_page()
    generate_json_viewer()
    generate_css()        # 修改这行
    generate_js_files()   # 添加这行
    
    print("网页文件生成完成！")

    

# ========== 主函数和统一接口 ==========

def main_limit_up():
    """主函数 - 财联社涨停池数据"""
    try:
        print("开始获取财联社涨停池数据...")
        raw_data = fetch_limit_up_data()
        processed_data = process_limit_up_data(raw_data)
        
        if processed_data:
            save_limit_up_data(processed_data)
            print("财联社涨停池数据处理完成！")
        else:
            print("没有获取到有效数据")
    except Exception as e:
        print(f"处理涨停池数据时发生错误: {e}")

def main():
    """主函数 - 根据命令行参数决定执行哪个功能"""
    if len(sys.argv) == 1:
        # 默认执行涨停池数据获取
        main_limit_up()
        generate_all_pages()
    elif len(sys.argv) >= 2:
        command = sys.argv[1].lower()
        
        if command == 'limitup':
            main_limit_up()
            generate_all_pages()
            
        elif command == 'jiuyan':
            if len(sys.argv) == 2:
                crawl_all_jiuyan_articles()
            elif len(sys.argv) == 3:
                user_key = sys.argv[2]
                crawl_jiuyan_article(user_key)
            elif len(sys.argv) == 4:
                user_key = sys.argv[2]
                date_str = sys.argv[3]
                crawl_jiuyan_article(user_key, date_str)
            generate_all_pages()
                
        elif command == 'all':
            print("执行所有功能...")
            main_limit_up()
            print("\n" + "="*60 + "\n")
            crawl_all_jiuyan_articles()
            generate_all_pages()
            
        elif command == 'generate':
            # 只生成网页，不获取数据
            generate_all_pages()
            
        else:
            print("使用说明:")
            print("  python script.py                           # 默认获取涨停池数据并生成网页")
            print("  python script.py limitup                   # 获取涨停池数据")
            print("  python script.py jiuyan                    # 爬取韭研公社所有用户文章")
            print("  python script.py jiuyan 盘前纪要           # 爬取韭研公社指定用户文章")
            print("  python script.py jiuyan 盘前纪要 2025-01-21 # 爬取韭研公社指定用户指定日期文章")
            print("  python script.py all                       # 执行所有功能")
            print("  python script.py generate                  # 只生成网页文件")
            print("\n可用的韭研公社用户:")
            for key, info in JIUYAN_USERS.items():
                print(f"  {key} - {info['user_name']}")

if __name__ == "__main__":
    main()



