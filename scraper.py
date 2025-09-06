import os
import sys
import json
import time
import hashlib
import urllib.parse
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import codecs
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading



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
    """获取北京时间 (UTC+8)"""
    return datetime.utcnow() + timedelta(hours=8)

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
        'mode': 'full'
    },
    '盘前解读': {
        'user_url': 'https://www.jiuyangongshe.com/u/97fc2a020e644adb89570e69ae35ec02',
        'user_name': '盘前解读',
        'save_dir_prefix': '韭研公社_盘前解读',
        'mode': 'full'
    },
    '优秀阿呆': {
        'user_url': 'https://www.jiuyangongshe.com/u/88cf268bc56c423c985b87d1b1ff5de4',
        'user_name': '优秀阿呆',
        'save_dir_prefix': '韭研公社_优秀阿呆',
        'mode': 'simple'
    }
}

JIUYAN_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
}

def get_target_article_url(user_url, date_str):
    """从用户主页获取指定日期的文章链接"""
    try:
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
    except Exception as e:
        print(f"获取文章列表失败: {e}")
    
    return None, None

def fetch_article_content(article_url):
    """获取文章详细内容"""
    try:
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
    except Exception as e:
        print(f"获取文章内容失败: {e}")
        return None, None, None

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
        processed_images = set()  # 用于跟踪已处理的图片URL，避免重复
        
        for img in soup.find_all('img'):
            src = img.get('src')
            if not src:
                continue
            if not src.startswith('http'):
                src = urljoin(article_url, src)
            
            # 跳过已经处理过的图片
            if src in processed_images:
                # 如果图片已经处理过，直接替换为已有的占位符
                existing_placeholder = None
                for img_data in images_data:
                    if img_data.get('original_src') == src:
                        existing_placeholder = img_data['placeholder']
                        break
                if existing_placeholder:
                    img.replace_with(existing_placeholder)
                continue
            
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
                    "caption": "",
                    "original_src": src  # 记录原始URL用于去重
                })
                
                # 替换当前img标签为占位符
                img.replace_with(placeholder)
                processed_images.add(src)
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

    # 去除重复的图片占位符
    def remove_duplicate_image_placeholders(text):
        import re
        pattern = r'\[图片:([^\]]+)\]'
        seen_images = set()
        
        def replace_func(match):
            img_name = match.group(1)
            if img_name in seen_images:
                return ''  # 移除重复的占位符
            else:
                seen_images.add(img_name)
                return match.group(0)  # 保留第一次出现的占位符
        
        # 先移除重复的占位符
        deduplicated = re.sub(pattern, replace_func, text)
        
        # 清理多余的空行
        lines = deduplicated.split('\n')
        cleaned_lines = []
        prev_empty = False
        
        for line in lines:
            is_empty = not line.strip()
            if is_empty and prev_empty:
                continue  # 跳过连续的空行
            cleaned_lines.append(line)
            prev_empty = is_empty
        
        return '\n'.join(cleaned_lines)

    content_text = remove_duplicate_image_placeholders(content_text)

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
            
            # 处理内容，将图片占位符替换为实际图片
            content_for_docx = content_text
            img_placeholder_pattern = r'(\[图片:[^\]]+\])'
            
            # 按段落和图片占位符分割内容
            parts = re.split(img_placeholder_pattern, content_for_docx)
            
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                
                # 检查是否是图片占位符
                img_match = re.fullmatch(r'\[图片:(.*?)\]', part)
                if img_match:
                    img_filename = img_match.group(1)
                    img_path = os.path.join(img_folder, img_filename)
                    if os.path.exists(img_path):
                        try:
                            # 检查图片尺寸，避免过大
                            from PIL import Image
                            with Image.open(img_path) as pil_img:
                                width, height = pil_img.size
                                # 限制最大宽度为6英寸
                                max_width = Inches(6)
                                if width > height:
                                    doc.add_picture(img_path, width=max_width)
                                else:
                                    # 对于高图，限制高度
                                    max_height = Inches(8)
                                    doc.add_picture(img_path, height=max_height)
                        except Exception as img_error:
                            print(f"插入图片到Word文档失败 {img_filename}: {img_error}")
                            doc.add_paragraph(f'[图片插入失败: {img_filename}]')
                    else:
                        doc.add_paragraph(f'[图片文件不存在: {img_filename}]')
                else:
                    # 普通文本段落
                    if part:
                        doc.add_paragraph(part)
            
            docx_path = os.path.join(save_dir, f"{base_fname}.docx")
            doc.save(docx_path)
            
        except ImportError:
            print("警告：未安装python-docx，跳过Word文档生成")
        except Exception as e:
            print(f"生成Word文档失败: {e}")

    # 清理images_data，移除用于去重的辅助字段
    for img_data in images_data:
        if 'original_src' in img_data:
            del img_data['original_src']

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

def crawl_jiuyan_article(user_key, date_str=None):
    """爬取单个用户的文章 - 移除重试逻辑，由GitHub Actions控制"""
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
        # 使用北京时区的当前日期
        target_date = get_beijing_time()
    
    date_str = target_date.strftime('%Y-%m-%d')
    
    try:
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
            "publish_time": get_beijing_time().strftime("%H:%M"),
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
    if date_str not in index_data:
        index_data[date_str] = {
            "date": date_str,
            "update_time": get_beijing_time().strftime("%Y-%m-%d %H:%M:%S"),
            "articles": []
        }
    
    # 更新或添加文章数据
    existing_articles = index_data[date_str].get("articles", [])
    
    for new_article in articles_data:
        # 检查是否已存在相同作者的文章
        updated = False
        for i, existing_article in enumerate(existing_articles):
            if existing_article.get("author") == new_article.get("author"):
                existing_articles[i] = new_article
                updated = True
                break
        
        # 如果不存在，添加新文章
        if not updated:
            existing_articles.append(new_article)
    
    index_data[date_str]["articles"] = existing_articles
    index_data[date_str]["update_time"] = get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")
    
    # 保存索引
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
    
    print(f"文章索引已更新: {date_str}")

def crawl_single_jiuyan_user(user_key, date_str=None):
    """爬取单个用户的文章"""
    print(f"开始爬取 {user_key} 的文章...")
    
    if user_key not in JIUYAN_USERS:
        print(f"错误：未找到用户 '{user_key}'")
        print(f"可用用户: {', '.join(JIUYAN_USERS.keys())}")
        return None
    
    article_data = crawl_jiuyan_article(user_key, date_str)
    
    if article_data:
        current_date = date_str or get_beijing_time().strftime('%Y-%m-%d')
        save_articles_index([article_data], current_date)
        print(f"成功爬取 {user_key} 的文章")
        return article_data
    else:
        print(f"未能获取 {user_key} 的文章")
        return None

def crawl_all_jiuyan_articles(date_str=None):
    """爬取所有韭研公社文章"""
    print("开始爬取所有韭研公社文章...")
    articles_data = []
    
    for user_key in JIUYAN_USERS.keys():
        print(f"\n处理: {user_key}")
        article_data = crawl_jiuyan_article(user_key, date_str)
        if article_data:
            articles_data.append(article_data)
        time.sleep(2)  # 避免请求过于频繁
    
    # 保存文章索引
    if articles_data:
        current_date = date_str or get_beijing_time().strftime('%Y-%m-%d')
        save_articles_index(articles_data, current_date)
    
    print(f"\n韭研公社文章爬取完成！成功: {len(articles_data)}/{len(JIUYAN_USERS)}")
    return articles_data    

# ========== 韭研公社异动解析相关函数 ==========

def fetch_stock_analysis_data(date_str=None):
    """获取韭研公社异动解析数据"""
    if not date_str:
        date_str = get_beijing_time().strftime('%Y-%m-%d')
    
    url = "https://app.jiuyangongshe.com/jystock-app/api/v1/action/field"
    
    headers = {
        "Host": "app.jiuyangongshe.com",
        "Connection": "keep-alive",
        "sec-ch-ua": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
        "sec-ch-ua-mobile": "?0",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "timestamp": str(int(time.time() * 1000)),
        "platform": "3",
        "token": "c9f25f21829e88387639723f4f98272a",
        "sec-ch-ua-platform": '"Windows"',
        "Origin": "https://www.jiuyangongshe.com",
        "Sec-Fetch-Site": "same-site",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://www.jiuyangongshe.com/",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Cookie": "SESSION=Njk3YTRhNTUtZjFkMi00NzNiLTk2NGYtNTVlNDU5NTRmNWU3; Hm_lvt_58aa18061df7855800f2a1b32d6da7f4=1754989369,1755050145; Hm_lpvt_58aa18061df7855800f2a1b32d6da7f4=1755052203"
    }
    
    payload = {
        "date": date_str,
        "pc": 1
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if data.get("errCode") == "0" and "data" in data:
            return data["data"]
        else:
            print(f"异动解析API返回错误: {data.get('errCode', '未知错误')}")
            return None
            
    except Exception as e:
        print(f"获取异动解析数据失败: {e}")
        return None

def process_stock_analysis_data(raw_data, date_str):
    """处理异动解析数据"""
    if not raw_data:
        return None
    
    current_time = get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")
    
    categories = []
    total_stocks = 0
    
    for category in raw_data:
        category_name = category.get("name", "")
        category_reason = category.get("reason", "")
        stock_list = category.get("list", [])
        
        if stock_list:  # 只处理有股票数据的分类
            processed_stocks = []
            
            for stock in stock_list:
                stock_code = stock.get("code", "")
                stock_name = stock.get("name", "")
                
                # 获取异动信息
                action_info = stock.get("article", {}).get("action_info", {})
                limit_time = action_info.get("time", "")
                analysis = action_info.get("expound", "")
                
                processed_stock = {
                    "code": stock_code,
                    "name": stock_name,
                    "limit_time": limit_time,
                    "analysis": analysis
                }
                processed_stocks.append(processed_stock)
                total_stocks += 1
            
            category_data = {
                "name": category_name,
                "reason": category_reason,
                "stock_count": len(processed_stocks),
                "stocks": processed_stocks
            }
            categories.append(category_data)
    
    result = {
        "date": date_str,
        "update_time": current_time,
        "category_count": len(categories),
        "total_stocks": total_stocks,
        "categories": categories
    }
    
    return result

def generate_analysis_text_content(data):
    """生成异动解析的文本内容"""
    content = f"韭研公社异动解析 - {data['date']}\n"
    content += f"更新时间: {data['update_time']}\n"
    content += f"板块数量: {data['category_count']} 个\n"
    content += f"股票数量: {data['total_stocks']} 只\n"
    content += "=" * 80 + "\n\n"
    
    for category in data['categories']:
        content += f"=== {category['name']} ===\n"
        if category['reason']:
            content += f"板块异动解析: {category['reason']}\n"
        content += f"涉及股票: {category['stock_count']} 只\n\n"
        
        for stock in category['stocks']:
            content += f"{stock['name']}（{stock['code']}）\n"
            if stock['limit_time']:
                content += f"涨停时间: {stock['limit_time']}\n"
            content += f"个股异动解析: {stock['analysis']}\n"
            content += "\n" + "-" * 80 + "\n\n"
    
    return content

def save_stock_analysis_data(data):
    """保存异动解析数据"""
    if not data:
        return
    
    # 创建数据目录
    os.makedirs('analysis', exist_ok=True)
    current_date = data['date']
    
    # 保存JSON数据
    json_path = f'analysis/{current_date}.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # 保存文本格式
    text_content = generate_analysis_text_content(data)
    txt_path = f'analysis/{current_date}.txt'
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(text_content)
    
    # 更新索引文件
    index_path = 'analysis/index.json'
    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8') as f:
            try:
                index_data = json.load(f)
                if not isinstance(index_data, dict):
                    index_data = {}
            except:
                index_data = {}
    else:
        index_data = {}
    
    # 更新索引
    index_data[current_date] = {
        "date": current_date,
        "update_time": data['update_time'],
        "category_count": data['category_count'],
        "total_stocks": data['total_stocks'],
        "files": {
            "json": f"analysis/{current_date}.json",
            "txt": f"analysis/{current_date}.txt"
        }
    }
    
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
    
    print(f"异动解析数据已保存: {current_date}, 共{data['category_count']}个板块，{data['total_stocks']}只股票")

def crawl_stock_analysis(date_str=None):
    """爬取异动解析数据"""
    print("开始获取韭研公社异动解析数据...")
    
    if not date_str:
        date_str = get_beijing_time().strftime('%Y-%m-%d')
    
    try:
        raw_data = fetch_stock_analysis_data(date_str)
        processed_data = process_stock_analysis_data(raw_data, date_str)
        
        if processed_data:
            save_stock_analysis_data(processed_data)
            print(f"异动解析数据获取成功: {date_str}")
            return processed_data
        else:
            print(f"未获取到 {date_str} 的异动解析数据")
            return None
            
    except Exception as e:
        print(f"获取异动解析数据时发生错误: {e}")
        return None

# ========== 通达信龙虎榜相关函数 ==========

def get_tdx_lhb_overview():
    """获取通达信龙虎榜总览数据"""
    url = "https://fk.tdx.com.cn/TQLEX?Entry=CWServ.tdxsj_lhbd_lhbzl"
    
    headers = {
        "Host": "fk.tdx.com.cn",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Origin": "https://fk.tdx.com.cn",
        "Referer": "https://fk.tdx.com.cn/site/tdxsj/html/tdxsj_lhbd.html?from=www&webfrom=1&pc=0",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept": "text/plain, */*; q=0.01",
        "sec-ch-ua": "\"Not A(Brand\";v=\"99\", \"Google Chrome\";v=\"121\", \"Chromium\";v=\"121\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\""
    }
    
    data = {"Params": ["0", "0", "0"]}
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data), timeout=15)
        response.raise_for_status()
        
        result = response.json()
        if result.get('ErrorCode') == 0:
            return result
        else:
            print(f"龙虎榜API返回错误: {result.get('ErrorCode')}")
            return None
    except Exception as e:
        print(f"获取龙虎榜总览失败: {e}")
        return None

def parse_lhb_overview(overview_data):
    """解析龙虎榜总览数据"""
    if not overview_data or not overview_data.get('ResultSets'):
        return None
    
    result_sets = overview_data['ResultSets']
    stocks_info = []
    trading_date = None
    
    # 解析股票列表
    if len(result_sets) > 0 and result_sets[0].get('Count', 0) > 0:
        table0 = result_sets[0]
        for row in table0['Content']:
            stock_info = {
                "code": row[0],
                "name": row[1],
                "market_code": row[2],
                "change_percent": float(row[3]) if row[3] else 0,
                "close_price": float(row[4]) if row[4] else 0,
                "market_name": row[5]
            }
            stocks_info.append(stock_info)
    
    # 解析交易日期
    if len(result_sets) > 1 and result_sets[1].get('Count', 0) > 0:
        table1 = result_sets[1]
        if table1['Content']:
            trading_date = table1['Content'][0][2]
    
    return {
        "trading_date": trading_date,
        "total_count": len(stocks_info),
        "stocks": stocks_info
    }

def get_single_dragon_tiger_detail(stock_code, date):
    """获取单只股票的龙虎榜详细信息"""
    url = "https://fk.tdx.com.cn/TQLEX?Entry=CWServ.tdxsj_lhbd_ggxq"
    
    headers = {
        'Host': 'fk.tdx.com.cn',
        'Connection': 'keep-alive',
        'sec-ch-ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
        'Accept': 'text/plain, */*; q=0.01',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'sec-ch-ua-mobile': '?0',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'sec-ch-ua-platform': '"Windows"',
        'Origin': 'https://fk.tdx.com.cn',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Dest': 'empty',
        'Referer': f'https://fk.tdx.com.cn/site/tdxsj/html/tdxsj_lhbd_ggxq.html?back=tdxsj_lhbd,%E9%BE%99%E8%99%8E%E6%A6%9C%E4%B8%AA%E8%82%A1,{stock_code}&pc=0&webfrom=1',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'zh-CN,zh;q=0.9'
    }
    
    payload = json.dumps({"Params": ["1", stock_code, date]})
    
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        
        raw_data = response.json()
        
        if raw_data.get('ErrorCode') != 0:
            return {"code": stock_code, "status": "api_error", "error_code": raw_data.get('ErrorCode')}
        
        result_sets = raw_data.get('ResultSets', [])
        
        structured_data = {
            "code": stock_code,
            "query_date": date,
            "status": "success"
        }
        
        # 解析基本信息
        if len(result_sets) > 0 and result_sets[0].get('Count', 0) > 0:
            table0 = result_sets[0]
            basic_info = table0['Content'][0]
            
            structured_data["lhb_info"] = {
                "list_code": basic_info[0],
                "list_reason": basic_info[1],
                "volume": float(basic_info[2]) if basic_info[2] else 0,
                "amount": float(basic_info[3]) if basic_info[3] else 0,
                "close_price": float(basic_info[4]) if basic_info[4] else 0,
                "change_percent": float(basic_info[5]) if basic_info[5] else 0
            }
        else:
            structured_data["status"] = "no_detail_data"
            return structured_data
        
        # 解析席位信息
        if len(result_sets) > 1 and result_sets[1].get('Count', 0) > 0:
            table1 = result_sets[1]
            
            buy_seats = []
            sell_seats = []
            
            for row in table1['Content']:
                seat_info = {
                    "rank": int(row[0]) if row[0] else 0,
                    "department_name": row[2],
                    "buy_amount": float(row[3]) if row[3] else 0,
                    "sell_amount": float(row[4]) if row[4] else 0,
                    "net_amount": float(row[5]) if row[5] else 0,
                    "direction": row[7],
                    "label": row[12] if row[12] else ""
                }
                
                # 计算占比
                total_amount = basic_info[3] if basic_info[3] > 0 else 1
                seat_info["amount_ratio"] = round(abs(row[5]) / total_amount * 100, 2)
                
                if row[7] == "B":
                    buy_seats.append(seat_info)
                else:
                    sell_seats.append(seat_info)
            
            structured_data["buy_seats"] = buy_seats
            structured_data["sell_seats"] = sell_seats
            
            # 计算资金流向
            buy_total = sum([seat.get("buy_amount", 0) for seat in buy_seats])
            sell_total = sum([seat.get("sell_amount", 0) for seat in sell_seats])
            
            structured_data["capital_flow"] = {
                "buy_total": buy_total,
                "sell_total": sell_total,
                "net_inflow": buy_total - sell_total,
                "buy_ratio": round(buy_total / total_amount * 100, 2),
                "sell_ratio": round(sell_total / total_amount * 100, 2)
            }
        
        return structured_data
        
    except Exception as e:
        return {"code": stock_code, "status": "query_failed", "error": str(e)}

def crawl_dragon_tiger_data(date_str=None, max_workers=5, delay=0.1):
    """爬取龙虎榜数据"""
    print("开始获取通达信龙虎榜数据...")
    
    if not date_str:
        date_str = get_beijing_time().strftime('%Y-%m-%d')
    
    try:
        # 获取总览数据
        print("1. 获取龙虎榜总览...")
        overview_data = get_tdx_lhb_overview()
        if not overview_data:
            print("获取龙虎榜总览失败")
            return None
        
        # 解析总览数据
        print("2. 解析总览数据...")
        parsed_overview = parse_lhb_overview(overview_data)
        if not parsed_overview:
            print("解析龙虎榜总览失败")
            return None
        
        trading_date = parsed_overview["trading_date"]
        stocks_list = parsed_overview["stocks"]
        
        print(f"发现 {len(stocks_list)} 只龙虎榜股票，交易日期: {trading_date}")
        
        # 并发获取详细数据
        print(f"3. 并发获取详细数据（线程数: {max_workers}）...")
        
        all_detailed_data = {
            "date": trading_date,
            "update_time": get_beijing_time().strftime("%Y-%m-%d %H:%M:%S"),
            "total_count": len(stocks_list),
            "overview": parsed_overview,
            "details": {},
            "statistics": {
                "success_count": 0,
                "failed_count": 0,
                "no_detail_count": 0
            }
        }
        
        completed_count = 0
        lock = threading.Lock()
        
        def query_with_delay(stock_info):
            nonlocal completed_count
            
            time.sleep(delay)
            detail_data = get_single_dragon_tiger_detail(stock_info["code"], trading_date)
            
            # 合并总览信息
            detail_data.update({
                "name": stock_info["name"],
                "market_name": stock_info["market_name"],
                "overview_change_percent": stock_info["change_percent"],
                "overview_close_price": stock_info["close_price"]
            })
            
            with lock:
                completed_count += 1
                all_detailed_data["details"][stock_info["code"]] = detail_data
                
                status = detail_data.get("status", "unknown")
                if status == "success":
                    all_detailed_data["statistics"]["success_count"] += 1
                    lhb_info = detail_data.get("lhb_info", {})
                    flow_info = detail_data.get("capital_flow", {})
                    print(f"[{completed_count:2d}/{len(stocks_list)}] ✓ {stock_info['code']} {stock_info['name'][:8]} - "
                          f"{lhb_info.get('list_reason', 'N/A')[:15]} - 净流入: {flow_info.get('net_inflow', 0):>8.2f}万元")
                elif status == "no_detail_data":
                    all_detailed_data["statistics"]["no_detail_count"] += 1
                    print(f"[{completed_count:2d}/{len(stocks_list)}] - {stock_info['code']} {stock_info['name'][:8]} - 无详细数据")
                else:
                    all_detailed_data["statistics"]["failed_count"] += 1
                    print(f"[{completed_count:2d}/{len(stocks_list)}] ✗ {stock_info['code']} {stock_info['name'][:8]} - 查询失败")
            
            return detail_data
        
        # 使用线程池并发执行
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_stock = {
                executor.submit(query_with_delay, stock): stock 
                for stock in stocks_list
            }
            
            for future in as_completed(future_to_stock):
                try:
                    future.result()
                except Exception as e:
                    stock = future_to_stock[future]
                    print(f"✗ {stock['code']} 查询异常: {e}")
        
        # 保存数据
        save_dragon_tiger_data(all_detailed_data)
        
        success_rate = all_detailed_data["statistics"]["success_count"] / len(stocks_list) * 100
        print(f"龙虎榜数据获取完成: {trading_date}, 成功率: {success_rate:.1f}%")
        
        return all_detailed_data
        
    except Exception as e:
        print(f"获取龙虎榜数据时发生错误: {e}")
        return None

def save_dragon_tiger_data(data):
    """保存龙虎榜数据"""
    if not data:
        return
    
    # 创建数据目录
    os.makedirs('dragon_tiger', exist_ok=True)
    current_date = data['date']
    
    # 保存JSON数据
    json_path = f'dragon_tiger/{current_date}.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # 生成文本格式
    text_content = generate_dragon_tiger_text_content(data)
    txt_path = f'dragon_tiger/{current_date}.txt'
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(text_content)
    
    # 更新索引文件
    index_path = 'dragon_tiger/index.json'
    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8') as f:
            try:
                index_data = json.load(f)
                if not isinstance(index_data, dict):
                    index_data = {}
            except:
                index_data = {}
    else:
        index_data = {}
    
    # 更新索引
    index_data[current_date] = {
        "date": current_date,
        "update_time": data['update_time'],
        "total_count": data['total_count'],
        "success_count": data['statistics']['success_count'],
        "success_rate": round(data['statistics']['success_count'] / data['total_count'] * 100, 1),
        "files": {
            "json": f"dragon_tiger/{current_date}.json",
            "txt": f"dragon_tiger/{current_date}.txt"
        }
    }
    
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
    
    print(f"龙虎榜数据已保存: {current_date}, 共{data['total_count']}只股票，成功{data['statistics']['success_count']}只")

def generate_dragon_tiger_text_content(data):
    """生成龙虎榜的文本内容"""
    content = f"通达信龙虎榜数据 - {data['date']}\n"
    content += f"更新时间: {data['update_time']}\n"
    content += f"股票总数: {data['total_count']} 只\n"
    content += f"查询成功: {data['statistics']['success_count']} 只\n"
    content += f"成功率: {data['statistics']['success_count']/data['total_count']*100:.1f}%\n"
    content += "=" * 80 + "\n\n"
    
    # 市场分布统计
    market_stats = {}
    for stock in data['overview']['stocks']:
        market = stock['market_name']
        if market not in market_stats:
            market_stats[market] = 0
        market_stats[market] += 1
    
    content += "=== 市场分布 ===\n"
    for market, count in market_stats.items():
        content += f"{market}: {count}只\n"
    content += "\n"
    
    # 详细数据
    content += "=== 龙虎榜详细数据 ===\n\n"
    
    for stock_code, detail in data['details'].items():
        if detail.get('status') != 'success':
            continue
            
        content += f"股票代码: {stock_code}\n"
        content += f"股票名称: {detail.get('name', 'N/A')}\n"
        content += f"市场: {detail.get('market_name', 'N/A')}\n"
        
        lhb_info = detail.get('lhb_info', {})
        content += f"收盘价: {lhb_info.get('close_price', 0):.2f}元\n"
        content += f"涨跌幅: {lhb_info.get('change_percent', 0):.2f}%\n"
        content += f"上榜原因: {lhb_info.get('list_reason', 'N/A')}\n"
        content += f"成交额: {lhb_info.get('amount', 0):.2f}万元\n"
        content += f"成交量: {lhb_info.get('volume', 0):.2f}万股\n"
        
        # 资金流向
        flow_info = detail.get('capital_flow', {})
        if flow_info:
            content += f"买入合计: {flow_info.get('buy_total', 0):.2f}万元\n"
            content += f"卖出合计: {flow_info.get('sell_total', 0):.2f}万元\n"
            content += f"净流入: {flow_info.get('net_inflow', 0):.2f}万元\n"
        
        # 买入席位
        buy_seats = detail.get('buy_seats', [])
        if buy_seats:
            content += "\n买入席位TOP5:\n"
            for i, seat in enumerate(buy_seats[:5], 1):
                content += f"  {i}. {seat.get('department_name', 'N/A')} - "
                content += f"买入: {seat.get('buy_amount', 0):.2f}万元 "
                content += f"占比: {seat.get('amount_ratio', 0):.2f}% "
                content += f"{seat.get('label', '')}\n"
        
        # 卖出席位
        sell_seats = detail.get('sell_seats', [])
        if sell_seats:
            content += "\n卖出席位TOP5:\n"
            for i, seat in enumerate(sell_seats[:5], 1):
                content += f"  {i}. {seat.get('department_name', 'N/A')} - "
                content += f"卖出: {seat.get('sell_amount', 0):.2f}万元 "
                content += f"占比: {seat.get('amount_ratio', 0):.2f}% "
                content += f"{seat.get('label', '')}\n"
        
        content += "\n" + "-" * 80 + "\n\n"
    
    return content



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
            
            <div class="nav-card" onclick="location.href='analysis.html'">
                <div class="card-icon">📈</div>
                <h3>异动解析数据</h3>
                <p>查看股票异动解析</p>
                <div class="card-status" id="analysisStatus">最新更新: 加载中...</div>
                <div class="card-button">进入查看</div>
            </div>
            
            <div class="nav-card" onclick="location.href='dragon_tiger.html'">
                <div class="card-icon">🐉</div>
                <h3>通达信龙虎榜</h3>
                <p>查看龙虎榜数据</p>
                <div class="card-status" id="dragonTigerStatus">最新更新: 加载中...</div>
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
                    <span class="stat-label">龙虎榜股票</span>
                    <span class="stat-value" id="todayDragonTiger">--</span>
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

def generate_analysis_page():
    """生成异动解析页面"""
    html_content = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📈 韭研公社异动解析</title>
    <link rel="stylesheet" href="assets/css/style.css">
</head>
<body>
    <div class="container">
        <header class="page-header">
            <div class="header-nav">
                <a href="index.html" class="back-link">← 返回首页</a>
                <h1>📈 韭研公社异动解析</h1>
            </div>
        </header>
        
        <div class="controls-panel">
            <div class="filter-section">
                <select id="dateFilter" class="filter-select">
                    <option value="">选择日期</option>
                </select>
                <input type="text" id="searchInput" placeholder="搜索股票代码或名称..." class="search-input">
                <button id="copyDataBtn" class="action-btn">📋 复制数据</button>
                <button id="viewJsonBtn" class="action-btn">📄 查看JSON</button>
                <button id="refreshBtn" class="action-btn">🔄 刷新</button>
            </div>
        </div>
        
        <div class="data-info" id="dataInfo" style="display: none;">
            <div class="info-item">
                <span class="info-label">更新时间:</span>
                <span id="updateTime">--</span>
            </div>
            <div class="info-item">
                <span class="info-label">板块数量:</span>
                <span id="categoryCount">--</span>
            </div>
            <div class="info-item">
                <span class="info-label">股票数量:</span>
                <span id="stockCount">--</span>
            </div>
        </div>
        
        <div class="analysis-container" id="analysisContainer">
            <div class="loading">请选择日期查看数据...</div>
        </div>
    </div>
    
    <script src="assets/js/common.js"></script>
    <script src="assets/js/analysis.js"></script>
</body>
</html>'''
    
    with open('analysis.html', 'w', encoding='utf-8') as f:
        f.write(html_content)


def generate_dragon_tiger_page():
    """生成龙虎榜页面"""
    html_content = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🐉 通达信龙虎榜数据</title>
    <link rel="stylesheet" href="assets/css/style.css">
</head>
<body>
    <div class="container">
        <header class="page-header">
            <div class="header-nav">
                <a href="index.html" class="back-link">← 返回首页</a>
                <h1>🐉 通达信龙虎榜数据</h1>
            </div>
        </header>
        
        <div class="controls-panel">
            <div class="filter-section">
                <select id="dateFilter" class="filter-select">
                    <option value="">选择日期</option>
                </select>
                <input type="text" id="searchInput" placeholder="搜索股票代码或名称..." class="search-input">
                <button id="copyDataBtn" class="action-btn">📋 复制数据</button>
                <button id="viewJsonBtn" class="action-btn">📄 查看JSON</button>
                <button id="refreshBtn" class="action-btn">🔄 刷新</button>
            </div>
        </div>
        
        <div class="data-info" id="dataInfo" style="display: none;">
            <div class="info-item">
                <span class="info-label">更新时间:</span>
                <span id="updateTime">--</span>
            </div>
            <div class="info-item">
                <span class="info-label">龙虎榜股票:</span>
                <span id="stockCount">--</span>
            </div>
            <div class="info-item">
                <span class="info-label">查询成功率:</span>
                <span id="successRate">--</span>
            </div>
        </div>
        
        <div class="market-stats" id="marketStats" style="display: none;">
            <h3>📊 市场分布</h3>
            <div class="stats-grid" id="marketStatsGrid">
            </div>
        </div>
        
        <div class="dragon-tiger-container" id="dragonTigerContainer">
            <div class="loading">请选择日期查看数据...</div>
        </div>
    </div>
    
    <!-- 详情模态框 -->
    <div id="detailModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <span class="close" onclick="closeDetailModal()">&times;</span>
                <h2 id="modalTitle">股票详情</h2>
                <div class="modal-actions">
                    <button onclick="copyDetailContent('full')" class="action-btn">📋 复制全部</button>
                    <button onclick="copyDetailContent('seats')" class="action-btn">📋 复制席位</button>
                    <button onclick="downloadDetail()" class="action-btn">💾 下载详情</button>
                </div>
            </div>
            <div class="modal-body">
                <div id="detailContent"></div>
            </div>
        </div>
    </div>
    
    <script src="assets/js/common.js"></script>
    <script src="assets/js/dragon_tiger.js"></script>
</body>
</html>'''
    
    with open('dragon_tiger.html', 'w', encoding='utf-8') as f:
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
                    <option value="analysis">异动解析数据</option>
                    <option value="dragon_tiger">龙虎榜数据</option>
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
/* 龙虎榜相关样式 */
.market-stats {
    background: white;
    border-radius: 15px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 5px 20px rgba(0,0,0,0.1);
}

.market-stats h3 {
    margin-bottom: 15px;
    color: #2d3748;
}

.dragon-tiger-container {
    background: white;
    border-radius: 15px;
    padding: 20px;
    box-shadow: 0 5px 20px rgba(0,0,0,0.1);
}

.dragon-tiger-card {
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 15px;
    transition: all 0.3s;
}

.dragon-tiger-card:hover {
    border-color: #667eea;
    box-shadow: 0 5px 15px rgba(102, 126, 234, 0.1);
}

.dragon-tiger-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 15px;
}

.stock-basic-info {
    display: flex;
    flex-direction: column;
    gap: 5px;
}

.stock-code-dt {
    font-weight: bold;
    color: #667eea;
    font-size: 1rem;
}

.stock-name-dt {
    font-size: 1.1rem;
    font-weight: 600;
    color: #2d3748;
}

.stock-market {
    font-size: 0.9rem;
    color: #718096;
}

.stock-price-info {
    text-align: right;
    display: flex;
    flex-direction: column;
    gap: 5px;
}

.stock-price-dt {
    font-size: 1.2rem;
    font-weight: bold;
    color: #2d3748;
}

.stock-change-dt {
    background: #e53e3e;
    color: white;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.9rem;
    text-align: center;
}

.stock-change-dt.positive {
    background: #e53e3e;
}

.stock-change-dt.negative {
    background: #38a169;
}

.dragon-tiger-details {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 15px;
    margin-bottom: 15px;
    font-size: 0.9rem;
    color: #4a5568;
}

.detail-item {
    display: flex;
    justify-content: space-between;
    padding: 8px 12px;
    background: #f7fafc;
    border-radius: 6px;
}

.detail-label {
    font-weight: 500;
    color: #2d3748;
}

.detail-value {
    font-weight: 600;
    color: #667eea;
}

.capital-flow-summary {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 10px;
    margin-bottom: 15px;
    padding: 15px;
    background: #f8f9fa;
    border-radius: 8px;
    border-left: 4px solid #667eea;
}

.flow-item {
    text-align: center;
}

.flow-label {
    display: block;
    font-size: 0.8rem;
    color: #718096;
    margin-bottom: 3px;
}

.flow-value {
    display: block;
    font-weight: bold;
    font-size: 0.95rem;
}

.flow-value.positive {
    color: #e53e3e;
}

.flow-value.negative {
    color: #38a169;
}

.dragon-tiger-actions {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
}

.dt-btn {
    padding: 8px 16px;
    border: 1px solid #667eea;
    background: transparent;
    color: #667eea;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.9rem;
    transition: all 0.3s;
}

.dt-btn:hover {
    background: #667eea;
    color: white;
}

.dt-btn.primary {
    background: #667eea;
    color: white;
}

.dt-btn.primary:hover {
    background: #5a67d8;
}

/* 详情模态框内容 */
.detail-modal-content {
    max-height: 70vh;
    overflow-y: auto;
}

.basic-info-section {
    margin-bottom: 25px;
    padding: 20px;
    background: #f8f9fa;
    border-radius: 10px;
}

.basic-info-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 15px;
}

.info-pair {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid #e2e8f0;
}

.info-pair:last-child {
    border-bottom: none;
}

.seats-section {
    margin-bottom: 25px;
}

.seats-section h4 {
    margin-bottom: 15px;
    color: #2d3748;
    font-size: 1.1rem;
    display: flex;
    align-items: center;
    gap: 8px;
}

.seats-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 20px;
}

.seats-table th,
.seats-table td {
    padding: 12px 8px;
    text-align: left;
    border-bottom: 1px solid #e2e8f0;
}

.seats-table th {
    background: #f7fafc;
    font-weight: 600;
    color: #2d3748;
    font-size: 0.9rem;
}

.seats-table td {
    font-size: 0.85rem;
    color: #4a5568;
}

.seat-rank {
    font-weight: bold;
    color: #667eea;
    text-align: center;
}

.seat-amount {
    font-weight: 600;
    text-align: right;
}

.seat-label {
    display: inline-block;
    padding: 2px 6px;
    background: #667eea;
    color: white;
    border-radius: 3px;
    font-size: 0.7rem;
}

.seat-label.institution {
    background: #38a169;
}

.seat-label.hot-money {
    background: #e53e3e;
}

/* 响应式设计 */
@media (max-width: 768px) {
    .dragon-tiger-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 10px;
    }
    
    .stock-price-info {
        align-self: stretch;
        text-align: left;
    }
    
    .dragon-tiger-details {
        grid-template-columns: 1fr;
    }
    
    .capital-flow-summary {
        grid-template-columns: repeat(2, 1fr);
    }
    
    .dragon-tiger-actions {
        justify-content: center;
    }
    
    .seats-table {
        font-size: 0.8rem;
    }
    
    .seats-table th,
    .seats-table td {
        padding: 8px 4px;
    }
}

@media (max-width: 480px) {
    .capital-flow-summary {
        grid-template-columns: 1fr;
    }
    
    .basic-info-grid {
        grid-template-columns: 1fr;
    }
    
    .seats-table th,
    .seats-table td {
        padding: 6px 3px;
        font-size: 0.75rem;
    }
}
/* 异动解析样式 */
.analysis-container {
    background: white;
    border-radius: 15px;
    padding: 20px;
    box-shadow: 0 5px 20px rgba(0,0,0,0.1);
}

.category-card {
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
    transition: all 0.3s;
}

.category-card:hover {
    border-color: #667eea;
    box-shadow: 0 5px 15px rgba(102, 126, 234, 0.1);
}

.category-header {
    margin-bottom: 15px;
    padding-bottom: 10px;
    border-bottom: 1px solid #e2e8f0;
}

.category-title {
    font-size: 1.3rem;
    font-weight: 600;
    color: #2d3748;
    margin-bottom: 8px;
}

.category-reason {
    color: #4a5568;
    margin-bottom: 10px;
    line-height: 1.6;
}

.category-stats {
    font-size: 0.9rem;
    color: #718096;
}

.stocks-list {
    margin-top: 15px;
}

.analysis-stock-card {
    background: #f7fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 15px;
    margin-bottom: 10px;
    transition: all 0.3s;
}

.analysis-stock-card:hover {
    background: #edf2f7;
    border-color: #cbd5e0;
}

.stock-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
}

.stock-basic {
    display: flex;
    align-items: center;
    gap: 10px;
}

.stock-code-analysis {
    font-weight: bold;
    color: #667eea;
}

.stock-name-analysis {
    font-weight: 600;
    color: #2d3748;
}

.limit-time {
    font-size: 0.9rem;
    color: #e53e3e;
    font-weight: 500;
}

.stock-analysis {
    color: #4a5568;
    line-height: 1.6;
    margin-top: 10px;
    padding: 10px;
    background: white;
    border-radius: 6px;
    border-left: 3px solid #667eea;
}

/* 响应式设计 */
@media (max-width: 768px) {
    .stock-info {
        flex-direction: column;
        align-items: flex-start;
        gap: 8px;
    }
    
    .stock-basic {
        flex-direction: column;
        align-items: flex-start;
        gap: 5px;
    }
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

    # dragon_tiger.js - 修复后的版本
    dragon_tiger_js = '''// assets/js/dragon_tiger.js - 龙虎榜页面功能

let currentDragonTigerData = null;
let currentDetailStock = null;

document.addEventListener('DOMContentLoaded', function() {
    initDragonTigerPage();
});

async function initDragonTigerPage() {
    await loadDragonTigerDateOptions();
    setupDragonTigerEventListeners();
}

// 加载日期选项
async function loadDragonTigerDateOptions() {
    try {
        const response = await fetch('dragon_tiger/index.json');
        if (!response.ok) throw new Error('无法加载龙虎榜日期数据');
        
        const indexData = await response.json();
        const dates = Object.keys(indexData).sort().reverse();
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
        
        // 默认选择最新日期
        if (dates.length > 0) {
            dateFilter.value = dates[0];
            await loadDragonTigerData(dates[0]);
        }
    } catch (error) {
        console.error('加载龙虎榜日期选项失败:', error);
        const container = document.getElementById('dragonTigerContainer');
        if (container) {
            showError(container, '加载日期数据失败');
        }
    }
}

// 设置事件监听器
function setupDragonTigerEventListeners() {
    const dateFilter = document.getElementById('dateFilter');
    const searchInput = document.getElementById('searchInput');
    const copyDataBtn = document.getElementById('copyDataBtn');
    const viewJsonBtn = document.getElementById('viewJsonBtn');
    const refreshBtn = document.getElementById('refreshBtn');
    
    if (dateFilter) {
        dateFilter.addEventListener('change', (e) => {
            if (e.target.value) {
                loadDragonTigerData(e.target.value);
            }
        });
    }
    
    if (searchInput) {
        searchInput.addEventListener('input', debounce(filterDragonTigerStocks, 300));
    }
    
    if (copyDataBtn) {
        copyDataBtn.addEventListener('click', copyDragonTigerData);
    }
    
    if (viewJsonBtn) {
        viewJsonBtn.addEventListener('click', viewDragonTigerJsonData);
    }
    
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            location.reload();
        });
    }
}

// 加载龙虎榜数据
async function loadDragonTigerData(date) {
    const container = document.getElementById('dragonTigerContainer');
    const dataInfo = document.getElementById('dataInfo');
    const marketStats = document.getElementById('marketStats');
    
    if (!container) {
        console.error('dragonTigerContainer元素未找到');
        return;
    }
    
    showLoading(container);
    if (dataInfo) {
        dataInfo.style.display = 'none';
    }
    if (marketStats) {
        marketStats.style.display = 'none';
    }
    
    try {
        const response = await fetch(`dragon_tiger/${date}.json`);
        if (!response.ok) throw new Error('龙虎榜数据加载失败');
        
        currentDragonTigerData = await response.json();
        
        // 更新数据信息
        const updateTimeEl = document.getElementById('updateTime');
        const stockCountEl = document.getElementById('stockCount');
        const successRateEl = document.getElementById('successRate');
        
        if (updateTimeEl) {
            updateTimeEl.textContent = currentDragonTigerData.update_time;
        }
        if (stockCountEl) {
            stockCountEl.textContent = currentDragonTigerData.total_count + '只';
        }
        if (successRateEl) {
            const successRate = (currentDragonTigerData.statistics.success_count / currentDragonTigerData.total_count * 100).toFixed(1);
            successRateEl.textContent = successRate + '%';
        }
        if (dataInfo) {
            dataInfo.style.display = 'flex';
        }
        
        // 显示市场分布
        renderMarketStats(currentDragonTigerData.overview.stocks);
        
        // 渲染股票列表
        renderDragonTigerStocks(currentDragonTigerData.details);
        
    } catch (error) {
        console.error('加载龙虎榜数据失败:', error);
        showError(container, '加载数据失败');
    }
}

// 渲染市场分布统计
function renderMarketStats(stocks) {
    const marketStats = document.getElementById('marketStats');
    const marketStatsGrid = document.getElementById('marketStatsGrid');
    
    if (!marketStats || !marketStatsGrid) return;
    
    // 统计市场分布
    const marketCounts = {};
    stocks.forEach(stock => {
        const market = stock.market_name;
        marketCounts[market] = (marketCounts[market] || 0) + 1;
    });
    
    const statsHtml = Object.entries(marketCounts).map(([market, count]) => 
        '<div class="stat-item"><span class="stat-label">' + market + '</span><span class="stat-value">' + count + '只</span></div>'
    ).join('');
    
    marketStatsGrid.innerHTML = statsHtml;
    marketStats.style.display = 'block';
}

// 渲染龙虎榜股票列表
function renderDragonTigerStocks(details) {
    const container = document.getElementById('dragonTigerContainer');
    
    if (!container) {
        console.error('dragonTigerContainer元素未找到');
        return;
    }
    
    // 只显示查询成功的股票
    const successfulStocks = Object.entries(details).filter(([code, data]) => 
        data.status === 'success'
    );
    
    if (successfulStocks.length === 0) {
        container.innerHTML = '<div class="loading">暂无成功查询的龙虎榜数据</div>';
        return;
    }
    
    const stocksHtml = successfulStocks.map(([code, data]) => {
        const lhbInfo = data.lhb_info || {};
        const capitalFlow = data.capital_flow || {};
        const changePercent = lhbInfo.change_percent || 0;
        const changeClass = changePercent >= 0 ? 'positive' : 'negative';
        const changeSign = changePercent >= 0 ? '+' : '';
        const closePrice = lhbInfo.close_price ? lhbInfo.close_price.toFixed(2) : '0.00';
        
        const capitalFlowHtml = capitalFlow.net_inflow !== undefined ? 
            '<div class="capital-flow-summary">' +
                '<div class="flow-item">' +
                    '<span class="flow-label">买入合计</span>' +
                    '<span class="flow-value">' + formatAmount(capitalFlow.buy_total) + '万</span>' +
                '</div>' +
                '<div class="flow-item">' +
                    '<span class="flow-label">卖出合计</span>' +
                    '<span class="flow-value">' + formatAmount(capitalFlow.sell_total) + '万</span>' +
                '</div>' +
                '<div class="flow-item">' +
                    '<span class="flow-label">净流入</span>' +
                    '<span class="flow-value ' + (capitalFlow.net_inflow >= 0 ? 'positive' : 'negative') + '">' +
                        (capitalFlow.net_inflow >= 0 ? '+' : '') + formatAmount(capitalFlow.net_inflow) + '万' +
                    '</span>' +
                '</div>' +
                '<div class="flow-item">' +
                    '<span class="flow-label">主力席位</span>' +
                    '<span class="flow-value">' + ((data.buy_seats ? data.buy_seats.length : 0) + (data.sell_seats ? data.sell_seats.length : 0)) + '个</span>' +
                '</div>' +
            '</div>' : '';
        
        return '<div class="dragon-tiger-card" data-code="' + code + '" data-name="' + data.name + '">' +
            '<div class="dragon-tiger-header">' +
                '<div class="stock-basic-info">' +
                    '<div class="stock-code-dt">' + code + '</div>' +
                    '<div class="stock-name-dt">' + data.name + '</div>' +
                    '<div class="stock-market">🏢 ' + data.market_name + '</div>' +
                '</div>' +
                '<div class="stock-price-info">' +
                    '<div class="stock-price-dt">¥' + closePrice + '</div>' +
                    '<div class="stock-change-dt ' + changeClass + '">' + changeSign + changePercent.toFixed(2) + '%</div>' +
                '</div>' +
            '</div>' +
            '<div class="dragon-tiger-details">' +
                '<div class="detail-item">' +
                    '<span class="detail-label">上榜原因:</span>' +
                    '<span class="detail-value">' + (lhbInfo.list_reason || 'N/A') + '</span>' +
                '</div>' +
                '<div class="detail-item">' +
                    '<span class="detail-label">成交额:</span>' +
                    '<span class="detail-value">' + formatAmount(lhbInfo.amount) + '万元</span>' +
                '</div>' +
                '<div class="detail-item">' +
                    '<span class="detail-label">成交量:</span>' +
                    '<span class="detail-value">' + formatAmount(lhbInfo.volume) + '万股</span>' +
                '</div>' +
            '</div>' +
            capitalFlowHtml +
            '<div class="dragon-tiger-actions">' +
                '<button class="dt-btn primary" onclick="viewDragonTigerDetail(\\'' + code + '\\')">📖 查看详情</button>' +
                '<button class="dt-btn" onclick="copyStockData(\\'' + code + '\\')">📋 复制数据</button>' +
                '<button class="dt-btn" onclick="exportStockData(\\'' + code + '\\')">💾 导出</button>' +
            '</div>' +
        '</div>';
    }).join('');
    
    container.innerHTML = stocksHtml;
}

// 格式化金额
function formatAmount(amount) {
    if (!amount && amount !== 0) return '0.00';
    return parseFloat(amount).toFixed(2);
}

// 筛选股票
function filterDragonTigerStocks() {
    const searchInput = document.getElementById('searchInput');
    if (!searchInput) return;
    
    const searchTerm = searchInput.value.toLowerCase();
    const stockCards = document.querySelectorAll('.dragon-tiger-card');
    
    stockCards.forEach(card => {
        const code = card.dataset.code.toLowerCase();
        const name = card.dataset.name.toLowerCase();
        
        if (code.includes(searchTerm) || name.includes(searchTerm)) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
}

// 复制龙虎榜数据
function copyDragonTigerData() {
    if (!currentDragonTigerData) {
        showToast('暂无数据可复制', 'error');
        return;
    }
    
    // 生成表格格式数据
    const successfulStocks = Object.entries(currentDragonTigerData.details).filter(([code, data]) => 
        data.status === 'success'
    );
    
    let textData = '股票代码\\t股票名称\\t市场\\t收盘价\\t涨跌幅\\t上榜原因\\t成交额(万元)\\t成交量(万股)\\t净流入(万元)\\n';
    
    successfulStocks.forEach(([code, data]) => {
        const lhbInfo = data.lhb_info || {};
        const capitalFlow = data.capital_flow || {};
        
        textData += code + '\\t';
        textData += data.name + '\\t';
        textData += data.market_name + '\\t';
        textData += (lhbInfo.close_price ? lhbInfo.close_price.toFixed(2) : '0.00') + '\\t';
        textData += (lhbInfo.change_percent ? lhbInfo.change_percent.toFixed(2) : '0.00') + '%\\t';
        textData += (lhbInfo.list_reason || 'N/A') + '\\t';
        textData += formatAmount(lhbInfo.amount) + '\\t';
        textData += formatAmount(lhbInfo.volume) + '\\t';
        textData += formatAmount(capitalFlow.net_inflow || 0) + '\\n';
    });
    
    copyToClipboard(textData);
}

// 查看股票详情
function viewDragonTigerDetail(stockCode) {
    if (!currentDragonTigerData || !currentDragonTigerData.details[stockCode]) {
        showToast('股票数据未找到', 'error');
        return;
    }
    
    const stockData = currentDragonTigerData.details[stockCode];
    currentDetailStock = stockData;
    
    // 填充模态框内容
    const modalTitle = document.getElementById('modalTitle');
    const detailContent = document.getElementById('detailContent');
    const modal = document.getElementById('detailModal');
    
    if (!modalTitle || !detailContent || !modal) {
        console.error('详情模态框元素未找到');
        return;
    }
    
    modalTitle.textContent = stockCode + ' ' + stockData.name + ' - 龙虎榜详情';
    
    // 生成详情内容
    const detailHtml = generateDetailContent(stockData);
    detailContent.innerHTML = detailHtml;
    
    // 显示模态框
    modal.style.display = 'block';
}

// 生成详情内容
function generateDetailContent(stockData) {
    const lhbInfo = stockData.lhb_info || {};
    const capitalFlow = stockData.capital_flow || {};
    const buySeats = stockData.buy_seats || [];
    const sellSeats = stockData.sell_seats || [];
    
    let html = '<div class="basic-info-section">' +
        '<h4>📊 基本信息</h4>' +
        '<div class="basic-info-grid">' +
            '<div class="info-pair"><span>交易日期:</span><span>' + stockData.query_date + '</span></div>' +
            '<div class="info-pair"><span>收盘价:</span><span>¥' + (lhbInfo.close_price ? lhbInfo.close_price.toFixed(2) : '0.00') + '</span></div>' +
            '<div class="info-pair"><span>涨跌幅:</span><span class="' + ((lhbInfo.change_percent || 0) >= 0 ? 'positive' : 'negative') + '">' +
                ((lhbInfo.change_percent || 0) >= 0 ? '+' : '') + (lhbInfo.change_percent ? lhbInfo.change_percent.toFixed(2) : '0.00') + '%</span></div>' +
            '<div class="info-pair"><span>市场:</span><span>' + stockData.market_name + '</span></div>' +
            '<div class="info-pair"><span>上榜原因:</span><span>' + (lhbInfo.list_reason || 'N/A') + '</span></div>' +
            '<div class="info-pair"><span>成交额:</span><span>' + formatAmount(lhbInfo.amount) + '万元</span></div>' +
            '<div class="info-pair"><span>成交量:</span><span>' + formatAmount(lhbInfo.volume) + '万股</span></div>' +
        '</div>' +
    '</div>';
    
    // 资金流向
    if (capitalFlow.net_inflow !== undefined) {
        html += '<div class="capital-flow-summary">' +
            '<div class="flow-item"><span class="flow-label">💹 总买入</span><span class="flow-value">' + formatAmount(capitalFlow.buy_total) + '万元</span></div>' +
            '<div class="flow-item"><span class="flow-label">💸 总卖出</span><span class="flow-value">' + formatAmount(capitalFlow.sell_total) + '万元</span></div>' +
            '<div class="flow-item"><span class="flow-label">📈 净流入</span><span class="flow-value ' + (capitalFlow.net_inflow >= 0 ? 'positive' : 'negative') + '">' +
                (capitalFlow.net_inflow >= 0 ? '+' : '') + formatAmount(capitalFlow.net_inflow) + '万元</span></div>' +
            '<div class="flow-item"><span class="flow-label">📊 净流入占比</span><span class="flow-value">' +
                ((capitalFlow.net_inflow / lhbInfo.amount) * 100).toFixed(1) + '%</span></div>' +
        '</div>';
    }
    
    // 买入席位
    if (buySeats.length > 0) {
        html += '<div class="seats-section">' +
            '<h4>🔴 买入席位 TOP' + Math.min(buySeats.length, 5) + '</h4>' +
            '<table class="seats-table">' +
                '<thead><tr><th>排名</th><th>营业部名称</th><th>买入金额(万元)</th><th>占比(%)</th><th>标签</th></tr></thead>' +
                '<tbody>';
        
        buySeats.slice(0, 5).forEach(seat => {
            html += '<tr>' +
                '<td class="seat-rank">' + seat.rank + '</td>' +
                '<td>' + seat.department_name + '</td>' +
                '<td class="seat-amount">' + formatAmount(seat.buy_amount) + '</td>' +
                '<td class="seat-amount">' + seat.amount_ratio + '%</td>' +
                '<td>' + (seat.label ? '<span class="seat-label ' + getSeatLabelClass(seat.label) + '">' + seat.label + '</span>' : '') + '</td>' +
            '</tr>';
        });
        
        html += '</tbody></table></div>';
    }
    
    // 卖出席位
    if (sellSeats.length > 0) {
        html += '<div class="seats-section">' +
            '<h4>🟢 卖出席位 TOP' + Math.min(sellSeats.length, 5) + '</h4>' +
            '<table class="seats-table">' +
                '<thead><tr><th>排名</th><th>营业部名称</th><th>卖出金额(万元)</th><th>占比(%)</th><th>标签</th></tr></thead>' +
                '<tbody>';
        
        sellSeats.slice(0, 5).forEach(seat => {
            html += '<tr>' +
                '<td class="seat-rank">' + seat.rank + '</td>' +
                '<td>' + seat.department_name + '</td>' +
                '<td class="seat-amount">' + formatAmount(seat.sell_amount) + '</td>' +
                '<td class="seat-amount">' + seat.amount_ratio + '%</td>' +
                '<td>' + (seat.label ? '<span class="seat-label ' + getSeatLabelClass(seat.label) + '">' + seat.label + '</span>' : '') + '</td>' +
            '</tr>';
        });
        
        html += '</tbody></table></div>';
    }
    
    return html;
}

// 获取席位标签样式类
function getSeatLabelClass(label) {
    if (label.includes('机构')) return 'institution';
    if (label.includes('游资')) return 'hot-money';
    return '';
}

// 关闭详情模态框
function closeDetailModal() {
    const modal = document.getElementById('detailModal');
    if (modal) {
        modal.style.display = 'none';
    }
    currentDetailStock = null;
}

// 复制详情内容
function copyDetailContent(type) {
    if (!currentDetailStock) {
        showToast('未选择股票', 'error');
        return;
    }
    
    let content = '';
    
    switch (type) {
        case 'full':
            content = generateDetailTextContent(currentDetailStock);
            break;
        case 'seats':
            content = generateSeatsTextContent(currentDetailStock);
            break;
        default:
            content = generateDetailTextContent(currentDetailStock);
    }
    
    copyToClipboard(content);
}

// 生成详情文本内容
function generateDetailTextContent(stockData) {
    const lhbInfo = stockData.lhb_info || {};
    const capitalFlow = stockData.capital_flow || {};
    const buySeats = stockData.buy_seats || [];
    const sellSeats = stockData.sell_seats || [];
    
    let content = stockData.code + ' ' + stockData.name + ' - 龙虎榜详情\\n\\n';
    content += '交易日期: ' + stockData.query_date + '\\n';
    content += '收盘价: ¥' + (lhbInfo.close_price ? lhbInfo.close_price.toFixed(2) : '0.00') + '\\n';
    content += '涨跌幅: ' + ((lhbInfo.change_percent || 0) >= 0 ? '+' : '') + (lhbInfo.change_percent ? lhbInfo.change_percent.toFixed(2) : '0.00') + '%\\n';
    content += '市场: ' + stockData.market_name + '\\n';
    content += '上榜原因: ' + (lhbInfo.list_reason || 'N/A') + '\\n';
    content += '成交额: ' + formatAmount(lhbInfo.amount) + '万元\\n';
    content += '成交量: ' + formatAmount(lhbInfo.volume) + '万股\\n\\n';
    
    // 资金流向
    if (capitalFlow.net_inflow !== undefined) {
        content += '=== 资金流向 ===\\n';
        content += '总买入: ' + formatAmount(capitalFlow.buy_total) + '万元\\n';
        content += '总卖出: ' + formatAmount(capitalFlow.sell_total) + '万元\\n';
        content += '净流入: ' + (capitalFlow.net_inflow >= 0 ? '+' : '') + formatAmount(capitalFlow.net_inflow) + '万元\\n';
        content += '净流入占比: ' + ((capitalFlow.net_inflow / lhbInfo.amount) * 100).toFixed(1) + '%\\n\\n';
    }
    
    // 买入席位
    if (buySeats.length > 0) {
        content += '=== 买入席位 TOP5 ===\\n';
        buySeats.slice(0, 5).forEach((seat, index) => {
            content += (index + 1) + '. ' + seat.department_name + '\\n';
            content += '   买入: ' + formatAmount(seat.buy_amount) + '万元  占比: ' + seat.amount_ratio + '%';
            if (seat.label) content += '  ' + seat.label;
            content += '\\n';
        });
        content += '\\n';
    }
    
    // 卖出席位
    if (sellSeats.length > 0) {
        content += '=== 卖出席位 TOP5 ===\\n';
        sellSeats.slice(0, 5).forEach((seat, index) => {
            content += (index + 1) + '. ' + seat.department_name + '\\n';
            content += '   卖出: ' + formatAmount(seat.sell_amount) + '万元  占比: ' + seat.amount_ratio + '%';
            if (seat.label) content += '  ' + seat.label;
            content += '\\n';
        });
    }
    
    return content;
}

// 生成席位文本内容
function generateSeatsTextContent(stockData) {
    const buySeats = stockData.buy_seats || [];
    const sellSeats = stockData.sell_seats || [];
    
    let content = stockData.code + ' ' + stockData.name + ' - 席位信息\\n\\n';
    
    if (buySeats.length > 0) {
        content += '买入席位:\\n';
        buySeats.forEach((seat, index) => {
            content += (index + 1) + '. ' + seat.department_name + '\\t' + formatAmount(seat.buy_amount) + '万元\\t' + seat.amount_ratio + '%';
            if (seat.label) content += '\\t' + seat.label;
            content += '\\n';
        });
        content += '\\n';
    }
    
    if (sellSeats.length > 0) {
        content += '卖出席位:\\n';
        sellSeats.forEach((seat, index) => {
            content += (index + 1) + '. ' + seat.department_name + '\\t' + formatAmount(seat.sell_amount) + '万元\\t' + seat.amount_ratio + '%';
            if (seat.label) content += '\\t' + seat.label;
            content += '\\n';
        });
    }
    
    return content;
}

// 下载详情
function downloadDetail() {
    if (!currentDetailStock) {
        showToast('未选择股票', 'error');
        return;
    }
    
    const content = generateDetailTextContent(currentDetailStock);
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = '龙虎榜详情_' + currentDetailStock.code + '_' + currentDetailStock.name + '_' + currentDetailStock.query_date + '.txt';
    link.click();
    URL.revokeObjectURL(url);
    showToast('详情下载中...');
}

// 复制单只股票数据
function copyStockData(stockCode) {
    if (!currentDragonTigerData || !currentDragonTigerData.details[stockCode]) {
        showToast('股票数据未找到', 'error');
        return;
    }
    
    const stockData = currentDragonTigerData.details[stockCode];
    const content = generateDetailTextContent(stockData);
    copyToClipboard(content);
}

// 导出单只股票数据
function exportStockData(stockCode) {
    if (!currentDragonTigerData || !currentDragonTigerData.details[stockCode]) {
        showToast('股票数据未找到', 'error');
        return;
    }
    
    const stockData = currentDragonTigerData.details[stockCode];
    const content = generateDetailTextContent(stockData);
    
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = '龙虎榜_' + stockCode + '_' + stockData.name + '_' + stockData.query_date + '.txt';
    link.click();
    URL.revokeObjectURL(url);
    showToast('数据导出中...');
}

// 查看JSON数据
function viewDragonTigerJsonData() {
    const dateFilter = document.getElementById('dateFilter');
    if (!dateFilter) {
        showToast('页面元素异常', 'error');
        return;
    }
    
    const date = dateFilter.value;
    if (date) {
        window.open('json_viewer.html?type=dragon_tiger&date=' + date, '_blank');
    } else {
        showToast('请先选择日期', 'error');
    }
}

// 模态框外部点击关闭
document.addEventListener('click', (e) => {
    const modal = document.getElementById('detailModal');
    if (modal && e.target === modal) {
        closeDetailModal();
    }
});

// 键盘事件
document.addEventListener('keydown', (e) => {
    const modal = document.getElementById('detailModal');
    if (modal && modal.style.display === 'block' && e.key === 'Escape') {
        closeDetailModal();
    }
});
'''
    
    with open('assets/js/dragon_tiger.js', 'w', encoding='utf-8') as f:
        f.write(dragon_tiger_js)
 


    
    # common.js
    common_js = '''// assets/js/common.js - 通用功能

// 全局变量
let currentImageIndex = 0;
let currentImages = [];

// 通用工具函数
function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN');
}

function formatTime(timeStr) {
    return timeStr || '--';
}

function showLoading(container) {
    container.innerHTML = '<div class="loading">加载中...</div>';
}

function showError(container, message) {
    container.innerHTML = '<div class="loading">错误: ' + message + '</div>';
}

// 复制到剪贴板
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast('复制成功！');
        return true;
    } catch (err) {
        console.error('复制失败:', err);
        // 降级方案
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
    toast.className = 'toast toast-' + type;
    toast.textContent = message;
    toast.style.cssText = 'position: fixed; top: 20px; right: 20px; background: ' + (type === 'success' ? '#48bb78' : '#f56565') + '; color: white; padding: 12px 20px; border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); z-index: 10000; animation: slideIn 0.3s ease-out;';
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-out forwards';
        setTimeout(() => {
            if (document.body.contains(toast)) {
                document.body.removeChild(toast);
            }
        }, 300);
    }, 3000);
}

// 添加CSS动画
if (!document.querySelector('#toast-styles')) {
    const style = document.createElement('style');
    style.id = 'toast-styles';
    style.textContent = '@keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } } @keyframes slideOut { from { transform: translateX(0); opacity: 1; } to { transform: translateX(100%); opacity: 0; } }';
    document.head.appendChild(style);
}

// 加载主页统计数据
async function loadMainPageStats() {
    try {
        // 加载涨停池数据状态
        await loadLimitUpStatus();
        
        // 加载文章数据状态
        await loadArticlesStatus();
        
        // 加载异动解析数据状态
        await loadAnalysisStatus();
        
        // 加载龙虎榜数据状态
        await loadDragonTigerStatus();
        
    } catch (error) {
        console.error('加载统计数据失败:', error);
        const dataStatusEl = document.getElementById('dataStatus');
        if (dataStatusEl) {
            dataStatusEl.textContent = '异常';
        }
    }
}


// 加载龙虎榜状态
async function loadDragonTigerStatus() {
    try {
        const response = await fetch('dragon_tiger/index.json');
        if (response.ok) {
            const indexData = await response.json();
            const dates = Object.keys(indexData).sort().reverse();
            if (dates.length > 0) {
                const latestDate = dates[0];
                const dragonTigerStatusEl = document.getElementById('dragonTigerStatus');
                if (dragonTigerStatusEl) {
                    dragonTigerStatusEl.textContent = '最新更新: ' + latestDate;
                }
                
                // 加载最新数据获取股票数量
                const dataResponse = await fetch('dragon_tiger/' + latestDate + '.json');
                if (dataResponse.ok) {
                    const data = await dataResponse.json();
                    const todayDragonTigerEl = document.getElementById('todayDragonTiger');
                    if (todayDragonTigerEl) {
                        const stockCount = data.statistics?.success_count || 0;
                        todayDragonTigerEl.textContent = stockCount + '只';
                    }
                }
            }
        }
    } catch (error) {
        console.error('加载龙虎榜状态失败:', error);
        const dragonTigerStatusEl = document.getElementById('dragonTigerStatus');
        const todayDragonTigerEl = document.getElementById('todayDragonTiger');
        if (dragonTigerStatusEl) {
            dragonTigerStatusEl.textContent = '最新更新: 加载失败';
        }
        if (todayDragonTigerEl) {
            todayDragonTigerEl.textContent = '加载失败';
        }
    }
}
// 加载涨停池状态
async function loadLimitUpStatus() {
    try {
        const response = await fetch('data/index.json');
        if (response.ok) {
            const dates = await response.json();
            if (dates.length > 0) {
                const latestDate = dates[0];
                const limitupStatusEl = document.getElementById('limitupStatus');
                if (limitupStatusEl) {
                    limitupStatusEl.textContent = '最新更新: ' + latestDate;
                }
                
                // 加载最新数据获取股票数量
                const dataResponse = await fetch('data/' + latestDate + '.json');
                if (dataResponse.ok) {
                    const data = await dataResponse.json();
                    const todayLimitUpEl = document.getElementById('todayLimitUp');
                    if (todayLimitUpEl) {
                        const stockCount = data.count || data.total_stocks || data.stocks?.length || 0;
                        todayLimitUpEl.textContent = stockCount + '只';
                    }
                }
            }
        }
    } catch (error) {
        console.error('加载涨停池状态失败:', error);
        const limitupStatusEl = document.getElementById('limitupStatus');
        const todayLimitUpEl = document.getElementById('todayLimitUp');
        if (limitupStatusEl) {
            limitupStatusEl.textContent = '最新更新: 加载失败';
        }
        if (todayLimitUpEl) {
            todayLimitUpEl.textContent = '加载失败';
        }
    }
}

// 加载文章状态
async function loadArticlesStatus() {
    try {
        const articlesResponse = await fetch('articles/index.json');
        if (articlesResponse.ok) {
            const articlesData = await articlesResponse.json();
            const dates = Object.keys(articlesData).sort().reverse();
            if (dates.length > 0) {
                const latestDate = dates[0];
                const articlesStatusEl = document.getElementById('articlesStatus');
                if (articlesStatusEl) {
                    articlesStatusEl.textContent = '最新更新: ' + latestDate;
                }
                
                // 计算本周文章数量
                const weekAgo = new Date();
                weekAgo.setDate(weekAgo.getDate() - 7);
                const weekAgoStr = weekAgo.toISOString().split('T')[0];
                
                let weeklyCount = 0;
                dates.forEach(date => {
                    if (date >= weekAgoStr && articlesData[date].articles) {
                        weeklyCount += articlesData[date].articles.length;
                    }
                });
                const weeklyArticlesEl = document.getElementById('weeklyArticles');
                if (weeklyArticlesEl) {
                    weeklyArticlesEl.textContent = weeklyCount + '篇';
                }
            }
        }
    } catch (error) {
        console.error('加载文章状态失败:', error);
        const articlesStatusEl = document.getElementById('articlesStatus');
        if (articlesStatusEl) {
            articlesStatusEl.textContent = '最新更新: 加载失败';
        }
    }
}

// 加载异动解析状态
async function loadAnalysisStatus() {
    try {
        const analysisResponse = await fetch('analysis/index.json');
        if (analysisResponse.ok) {
            const analysisData = await analysisResponse.json();
            const dates = Object.keys(analysisData).sort().reverse();
            if (dates.length > 0) {
                const latestDate = dates[0];
                const analysisStatusEl = document.getElementById('analysisStatus');
                if (analysisStatusEl) {
                    analysisStatusEl.textContent = '最新更新: ' + latestDate;
                }
            }
        }
    } catch (error) {
        console.error('加载异动解析状态失败:', error);
        const analysisStatusEl = document.getElementById('analysisStatus');
        if (analysisStatusEl) {
            analysisStatusEl.textContent = '最新更新: 加载失败';
        }
    }
}

// 显示关于信息
function showAbout() {
    const aboutContent = '<div style="text-align: center; padding: 20px;"><h2>📊 数据中心</h2><p style="margin: 20px 0; color: #666;">这是一个股票数据和研报文章的收集展示平台<br>自动收集财联社涨停池数据和韭研公社研报文章</p><p style="color: #999; font-size: 0.9rem;">数据仅供参考，投资有风险，入市需谨慎</p></div>';
    
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.style.display = 'block';
    modal.innerHTML = '<div class="modal-content" style="max-width: 400px;"><div class="modal-header"><span class="close" onclick="this.closest(\\'.modal\\').remove()">&times;</span></div><div class="modal-body">' + aboutContent + '</div></div>';
    
    document.body.appendChild(modal);
    
    // 点击外部关闭
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
}

// JSON查看器功能
async function loadJsonViewer() {
    const dataTypeSelect = document.getElementById('dataTypeSelect');
    const dateSelect = document.getElementById('dateSelect');
    const jsonContent = document.getElementById('jsonContent');
    const copyJsonBtn = document.getElementById('copyJsonBtn');
    
    if (!dataTypeSelect || !dateSelect || !jsonContent || !copyJsonBtn) {
        console.error('JSON查看器元素未找到');
        return;
    }
    
    // 加载日期选项
    async function loadDates() {
        const dataType = dataTypeSelect.value;
        dateSelect.innerHTML = '<option value="">选择日期</option>';
        
        try {
            let dates = [];
            if (dataType === 'limitup') {
                const response = await fetch('data/index.json');
                if (response.ok) {
                    dates = await response.json();
                }
            } else if (dataType === 'articles') {
                const response = await fetch('articles/index.json');
                if (response.ok) {
                    const articlesData = await response.json();
                    dates = Object.keys(articlesData).sort().reverse();
                }
            } else if (dataType === 'analysis') {
                const response = await fetch('analysis/index.json');
                if (response.ok) {
                    const analysisData = await response.json();
                    dates = Object.keys(analysisData).sort().reverse();
                }
            } else if (dataType === 'dragon_tiger') {
                const response = await fetch('dragon_tiger/index.json');
                if (response.ok) {
                    const dragonTigerData = await response.json();
                    dates = Object.keys(dragonTigerData).sort().reverse();
                }
            }
            
            dates.forEach(date => {
                const option = document.createElement('option');
                option.value = date;
                option.textContent = date;
                dateSelect.appendChild(option);
            });
            
            if (dates.length > 0) {
                dateSelect.value = dates[0];
                loadJsonData();
            }
        } catch (error) {
            jsonContent.textContent = '加载日期失败';
        }
    }
    
    // 加载JSON数据
    async function loadJsonData() {
        const dataType = dataTypeSelect.value;
        const date = dateSelect.value;
        
        if (!date) {
            jsonContent.textContent = '请选择日期';
            return;
        }
        
        try {
            let response;
            if (dataType === 'limitup') {
                response = await fetch('data/' + date + '.json');
            } else if (dataType === 'articles') {
                response = await fetch('articles/index.json');
            } else if (dataType === 'analysis') {
                response = await fetch('analysis/' + date + '.json');
            } else if (dataType === 'dragon_tiger') {
                response = await fetch('dragon_tiger/' + date + '.json');
            }
            
            if (response && response.ok) {
                let data = await response.json();
                if (dataType === 'articles') {
                    data = data[date] || {};
                }
                jsonContent.textContent = JSON.stringify(data, null, 2);
            } else {
                jsonContent.textContent = '加载数据失败';
            }
        } catch (error) {
            jsonContent.textContent = '加载失败: ' + error.message;
        }
    }
    
    // 复制JSON
    copyJsonBtn.addEventListener('click', () => {
        copyToClipboard(jsonContent.textContent);
    });
    
    // 事件监听
    dataTypeSelect.addEventListener('change', loadDates);
    dateSelect.addEventListener('change', loadJsonData);
    
    // 初始加载
    loadDates();
}

// 格式化数字
function formatNumber(num) {
    if (num >= 10000) {
        return (num / 10000).toFixed(1) + '万';
    }
    return num.toString();
}

// 获取URL参数
function getUrlParameter(name) {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(name);
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

// 节流函数
function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    }
}'''
    
    with open('assets/js/common.js', 'w', encoding='utf-8') as f:
        f.write(common_js)


    
    # limitup.js
    limitup_js = '''// assets/js/limitup.js - 涨停池页面功能

let currentLimitUpData = null;

document.addEventListener('DOMContentLoaded', function() {
    initLimitUpPage();
});

async function initLimitUpPage() {
    await loadDateOptions();
    setupEventListeners();
}

// 加载日期选项
async function loadDateOptions() {
    try {
        const response = await fetch('data/index.json');
        if (!response.ok) throw new Error('无法加载日期数据');
        
        const dates = await response.json();
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
    const copyDataBtn = document.getElementById('copyDataBtn');
    const viewJsonBtn = document.getElementById('viewJsonBtn');
    
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
    
    if (copyDataBtn) {
        copyDataBtn.addEventListener('click', copyLimitUpData);
    }
    
    if (viewJsonBtn) {
        viewJsonBtn.addEventListener('click', viewJsonData);
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
        const response = await fetch(`data/${date}.json`);
        if (!response.ok) throw new Error('数据加载失败');
        
        currentLimitUpData = await response.json();
        
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
}

// 复制涨停池数据
function copyLimitUpData() {
    if (!currentLimitUpData) {
        showToast('暂无数据可复制', 'error');
        return;
    }
    
    const textData = currentLimitUpData.stocks.map(stock => 
        `${stock.code}\\t${stock.name}\\t${stock.price}\\t${stock.change_percent}\\t${stock.limit_up_time}\\t${stock.reason}\\t${stock.plates}`
    ).join('\\n');
    
    const header = '股票代码\\t股票名称\\t最新价格\\t涨幅\\t涨停时间\\t涨停原因\\t所属板块\\n';
    const fullText = header + textData;
    
    copyToClipboard(fullText);
}

// 查看JSON数据
function viewJsonData() {
    const dateSelect = document.getElementById('dateSelect');
    if (!dateSelect) {
        showToast('页面元素异常', 'error');
        return;
    }
    
    const date = dateSelect.value;
    if (date) {
        window.open(`json_viewer.html?type=limitup&date=${date}`, '_blank');
    } else {
        showToast('请先选择日期', 'error');
    }
}

// 导出Excel格式数据
function exportToExcel() {
    if (!currentLimitUpData) {
        showToast('暂无数据可导出', 'error');
        return;
    }
    
    const csvContent = "data:text/csv;charset=utf-8," 
        + "股票代码,股票名称,最新价格,涨幅,涨停时间,涨停原因,所属板块\\n"
        + currentLimitUpData.stocks.map(stock => 
            `${stock.code},${stock.name},${stock.price},${stock.change_percent},${stock.limit_up_time},"${stock.reason}","${stock.plates}"`
        ).join('\\n');
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `涨停池数据_${currentLimitUpData.date}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showToast('数据导出成功！');
}'''
    
    with open('assets/js/limitup.js', 'w', encoding='utf-8') as f:
        f.write(limitup_js)
    
    # jiuyan.js
    jiuyan_js = '''// assets/js/jiuyan.js - 韭研公社文章页面功能

let currentArticlesData = {};
let currentArticle = null;

document.addEventListener('DOMContentLoaded', function() {
    initJiuyanPage();
});

async function initJiuyanPage() {
    await loadArticlesData();
    setupEventListeners();
}

// 加载文章数据
async function loadArticlesData() {
    try {
        const response = await fetch('articles/index.json');
        if (!response.ok) throw new Error('无法加载文章数据');
        
        currentArticlesData = await response.json();
        
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
                <span>💾 ${article.files && article.files.docx ? '可下载' : '仅文本'}</span>
            </div>
            <div class="article-actions">
                <button class="article-btn primary" onclick="viewArticle('${article.date}', '${article.author}')">
                    📖 查看全文
                </button>
                <button class="article-btn" onclick="copyArticleText('${article.date}', '${article.author}')">
                    📋 复制内容
                </button>
                <button class="article-btn" onclick="downloadArticleFile('${article.date}', '${article.author}')">
                    💾 下载文件
                </button>
            </div>
        </div>
    `).join('');
    
    container.innerHTML = articlesHtml;
}

// 获取文章预览
function getArticlePreview(content, maxLength = 200) {
    if (!content) return '暂无预览';
    
    // 移除图片占位符 - 使用正确的正则表达式
    const imgRegex = new RegExp('\\\\[图片:[^\\\\]]+\\\\]', 'g');
    const textOnly = content.replace(imgRegex, '');
    
    if (textOnly.length <= maxLength) {
        return textOnly;
    }
    
    return textOnly.substring(0, maxLength) + '...';
}

// 查看文章详情
function viewArticle(date, author) {
    const article = findArticle(date, author);
    if (!article) {
        showToast('文章未找到', 'error');
        return;
    }
    
    currentArticle = article;
    
    // 填充模态框内容
    const modalTitle = document.getElementById('modalTitle');
    const articleMeta = document.getElementById('articleMeta');
    const articleContent = document.getElementById('articleContent');
    const modal = document.getElementById('articleModal');
    
    if (!modalTitle || !articleMeta || !articleContent || !modal) {
        console.error('模态框元素未找到');
        return;
    }
    
    modalTitle.textContent = article.title;
    articleMeta.innerHTML = `
        <div style="display: flex; gap: 20px; margin-bottom: 20px; font-size: 0.9rem; color: #666;">
            <span>📅 ${article.date} ${article.publish_time}</span>
            <span>👤 ${article.author}</span>
            <span>📊 ${article.word_count}字</span>
            <span>📷 ${article.image_count}图</span>
        </div>
    `;
    
    // 处理文章内容（包含图片）
    const processedContent = processArticleContent(article);
    articleContent.innerHTML = processedContent;
    
    // 显示模态框
    modal.style.display = 'block';
    
    // 设置图片点击事件
    setupImageViewer(article.images || []);
}

// 处理文章内容
function processArticleContent(article) {
    let content = article.content;
    
    // 替换图片占位符为实际图片
    if (article.images && article.images.length > 0) {
        article.images.forEach((image, index) => {
            const placeholder = image.placeholder;
            const imgHtml = `
                <div style="text-align: center; margin: 20px 0;">
                    <img src="${image.src}" 
                         alt="${image.alt}" 
                         class="article-image" 
                         data-index="${index}"
                         style="max-width: 100%; height: auto; border-radius: 8px; cursor: pointer;"
                         onerror="this.style.display='none'; this.nextElementSibling.style.display='block';">
                    <div style="display: none; padding: 20px; background: #f5f5f5; border-radius: 8px; color: #666;">
                        图片加载失败: ${image.filename}
                    </div>
                    ${image.caption ? `<div class="image-caption">${image.caption}</div>` : ''}
                </div>
            `;
            content = content.replace(placeholder, imgHtml);
        });
    }
    
    // 处理段落
    const lines = content.split('\\n');
    const processedLines = lines.map(line => {
        if (line.trim()) {
            return `<p>${line}</p>`;
        }
        return '';
    });
    
    return processedLines.join('');
}

// 设置图片查看器
function setupImageViewer(images) {
    currentImages = images;
    
    // 移除之前的事件监听器
    document.querySelectorAll('.article-image').forEach(img => {
        img.removeEventListener('click', handleImageClick);
        img.addEventListener('click', handleImageClick);
    });
}

function handleImageClick(e) {
    const index = parseInt(e.target.dataset.index);
    openImageViewer(index);
}

// 打开图片查看器
function openImageViewer(index) {
    if (!currentImages || currentImages.length === 0) return;
    
    currentImageIndex = index;
    const image = currentImages[index];
    
    const viewerImage = document.getElementById('viewerImage');
    const viewerInfo = document.getElementById('viewerInfo');
    const imageViewer = document.getElementById('imageViewer');
    
    if (!viewerImage || !viewerInfo || !imageViewer) {
        console.error('图片查看器元素未找到');
        return;
    }
    
    viewerImage.src = image.src;
    viewerInfo.textContent = `图片 ${index + 1} / ${currentImages.length}`;
    imageViewer.style.display = 'block';
}

// 关闭图片查看器
function closeImageViewer() {
    const imageViewer = document.getElementById('imageViewer');
    if (imageViewer) {
        imageViewer.style.display = 'none';
    }
}

// 上一张图片
function prevImage() {
    if (currentImageIndex > 0) {
        openImageViewer(currentImageIndex - 1);
    }
}

// 下一张图片
function nextImage() {
    if (currentImageIndex < currentImages.length - 1) {
        openImageViewer(currentImageIndex + 1);
    }
}

// 下载当前图片
function downloadCurrentImage() {
    if (currentImages && currentImages[currentImageIndex]) {
        const image = currentImages[currentImageIndex];
        const link = document.createElement('a');
        link.href = image.src;
        link.download = image.filename || `image_${currentImageIndex + 1}.jpg`;
        link.click();
        showToast('图片下载中...');
    }
}

// 关闭文章模态框
function closeArticleModal() {
    const modal = document.getElementById('articleModal');
    if (modal) {
        modal.style.display = 'none';
    }
    currentArticle = null;
}

// 复制文章内容
function copyArticleContent(type) {
    if (!currentArticle) {
        showToast('未选择文章', 'error');
        return;
    }
    
    let content = '';
    
    switch (type) {
        case 'full':
            // 包含格式的完整内容
            content = `${currentArticle.title}\\n\\n`;
            content += `作者: ${currentArticle.author}\\n`;
            content += `时间: ${currentArticle.date} ${currentArticle.publish_time}\\n\\n`;
            content += currentArticle.content;
            break;
        case 'text':
            // 纯文本（移除图片占位符）
            const imgRegex = new RegExp('\\\\[图片:[^\\\\]]+\\\\]', 'g');
            content = currentArticle.content.replace(imgRegex, '');
            break;
        case 'html':
            // HTML格式
            content = processArticleContent(currentArticle);
            break;
        case 'markdown':
            // Markdown格式
            content = convertToMarkdown(currentArticle);
            break;
        default:
            content = currentArticle.content;
    }
    
    copyToClipboard(content);
}

// 转换为Markdown格式
function convertToMarkdown(article) {
    let content = `# ${article.title}\\n\\n`;
    content += `**作者**: ${article.author}  \\n`;
    content += `**时间**: ${article.date} ${article.publish_time}\\n\\n`;
    
    let articleContent = article.content;
    
    // 替换图片占位符为Markdown图片语法
    if (article.images && article.images.length > 0) {
        article.images.forEach((image, index) => {
            const placeholder = image.placeholder;
            const markdownImg = `![${image.alt}](${image.src})`;
            articleContent = articleContent.replace(placeholder, markdownImg);
        });
    }
    
    // 处理段落
    const lines = articleContent.split('\\n');
    const processedLines = lines.map(line => {
        if (line.trim()) {
            return line;
        }
        return '';
    });
    const finalContent = processedLines.join('\\n\\n');
    
    content += finalContent;
    return content;
}

// 复制文章文本（从列表调用）
function copyArticleText(date, author) {
    const article = findArticle(date, author);
    if (article) {
        const imgRegex = new RegExp('\\\\[图片:[^\\\\]]+\\\\]', 'g');
        const content = article.content.replace(imgRegex, '');
        copyToClipboard(content);
    } else {
        showToast('文章未找到', 'error');
    }
}

// 下载文章文件
function downloadArticle() {
    if (!currentArticle) {
        showToast('未选择文章', 'error');
        return;
    }
    
    if (!currentArticle.files || !currentArticle.files.txt) {
        showToast('文件不可用', 'error');
        return;
    }
    
    const link = document.createElement('a');
    link.href = currentArticle.files.txt;
    link.download = `${currentArticle.title}.txt`;
    link.click();
    showToast('文件下载中...');
}

// 下载文章文件（从列表调用）
function downloadArticleFile(date, author) {
    const article = findArticle(date, author);
    if (article && article.files && article.files.txt) {
        const link = document.createElement('a');
        link.href = article.files.txt;
        link.download = `${article.title}.txt`;
        link.click();
        showToast('文件下载中...');
    } else {
        showToast('文件不可用', 'error');
    }
}

// 查找文章
function findArticle(date, author) {
    if (currentArticlesData[date] && currentArticlesData[date].articles) {
        return currentArticlesData[date].articles.find(article => article.author === author);
    }
    return null;
}

// 批量下载文章
function batchDownloadArticles() {
    const authorFilter = document.getElementById('authorFilter');
    const dateFilter = document.getElementById('dateFilter');
    
    if (!authorFilter || !dateFilter) return;
    
    const authorValue = authorFilter.value;
    const dateValue = dateFilter.value;
    
    let articles = [];
    
    // 根据筛选条件获取文章
    if (dateValue && currentArticlesData[dateValue]) {
        articles = currentArticlesData[dateValue].articles || [];
    } else {
        Object.values(currentArticlesData).forEach(dayData => {
            if (dayData.articles) {
                articles = articles.concat(dayData.articles);
            }
        });
    }
    
    if (authorValue) {
        articles = articles.filter(article => article.author === authorValue);
    }
    
    if (articles.length === 0) {
        showToast('没有可下载的文章', 'error');
        return;
    }
    
    // 创建批量下载内容
    let batchContent = '';
    articles.forEach((article, index) => {
        batchContent += `\\n${'='.repeat(50)}\\n`;
        batchContent += `文章 ${index + 1}: ${article.title}\\n`;
        batchContent += `作者: ${article.author}\\n`;
        batchContent += `时间: ${article.date} ${article.publish_time}\\n`;
        batchContent += `${'='.repeat(50)}\\n\\n`;
        const imgRegex = new RegExp('\\\\[图片:[^\\\\]]+\\\\]', 'g');
        batchContent += article.content.replace(imgRegex, '[图片]');
        batchContent += '\\n\\n';
    });
    
    // 创建下载链接
    const blob = new Blob([batchContent], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `批量文章_${new Date().toISOString().split('T')[0]}.txt`;
    link.click();
    URL.revokeObjectURL(url);
    
    showToast(`已下载 ${articles.length} 篇文章`);
}

// 搜索文章
function searchArticles(keyword) {
    if (!keyword.trim()) {
        filterAndRenderArticles();
        return;
    }
    
    let allArticles = [];
    Object.values(currentArticlesData).forEach(dayData => {
        if (dayData.articles) {
            allArticles = allArticles.concat(dayData.articles);
        }
    });
    
    const filteredArticles = allArticles.filter(article => {
        return article.title.toLowerCase().includes(keyword.toLowerCase()) ||
               article.content.toLowerCase().includes(keyword.toLowerCase()) ||
               article.author.toLowerCase().includes(keyword.toLowerCase());
    });
    
    renderArticles(filteredArticles);
    showToast(`找到 ${filteredArticles.length} 篇相关文章`);
}

// 模态框外部点击关闭
document.addEventListener('click', (e) => {
    const modal = document.getElementById('articleModal');
    const imageViewer = document.getElementById('imageViewer');
    
    if (modal && e.target === modal) {
        closeArticleModal();
    }
    
    if (imageViewer && e.target === imageViewer) {
        closeImageViewer();
    }
});

// 键盘事件
document.addEventListener('keydown', (e) => {
    const imageViewer = document.getElementById('imageViewer');
    const modal = document.getElementById('articleModal');
    
    if (imageViewer && imageViewer.style.display === 'block') {
        switch (e.key) {
            case 'Escape':
                closeImageViewer();
                break;
            case 'ArrowLeft':
                prevImage();
                break;
            case 'ArrowRight':
                nextImage();
                break;
            case ' ':
                e.preventDefault();
                nextImage();
                break;
        }
    }
    
    if (modal && modal.style.display === 'block' && e.key === 'Escape') {
        closeArticleModal();
    }
});

// 添加搜索功能到页面
function addSearchFeature() {
    const controlsPanel = document.querySelector('.controls-panel .filter-section');
    if (controlsPanel) {
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.placeholder = '搜索文章标题或内容...';
        searchInput.className = 'search-input';
        searchInput.style.flex = '1';
        searchInput.style.minWidth = '200px';
        
        searchInput.addEventListener('input', debounce((e) => {
            searchArticles(e.target.value);
        }, 500));
        
        controlsPanel.appendChild(searchInput);
    }
}

// 初始化时添加搜索功能
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(addSearchFeature, 100);
});

// 文章统计功能
function getArticleStats() {
    let totalArticles = 0;
    let totalWords = 0;
    let totalImages = 0;
    const authorStats = {};
    
    Object.values(currentArticlesData).forEach(dayData => {
        if (dayData.articles) {
            dayData.articles.forEach(article => {
                totalArticles++;
                totalWords += article.word_count || 0;
                totalImages += article.image_count || 0;
                
                if (!authorStats[article.author]) {
                    authorStats[article.author] = 0;
                }
                authorStats[article.author]++;
            });
        }
    });
    
    return {
        totalArticles,
        totalWords,
        totalImages,
        authorStats
    };
}

// 显示统计信息
function showStats() {
    const stats = getArticleStats();
    const statsContent = `
        <div style="padding: 20px;">
            <h3>📊 文章统计</h3>
            <div style="margin: 20px 0;">
                <p><strong>总文章数:</strong> ${stats.totalArticles} 篇</p>
                <p><strong>总字数:</strong> ${formatNumber(stats.totalWords)} 字</p>
                <p><strong>总图片数:</strong> ${stats.totalImages} 张</p>
            </div>
            <h4>📝 作者统计:</h4>
            <div style="margin: 10px 0;">
                ${Object.entries(stats.authorStats).map(([author, count]) => 
                    `<p><strong>${author}:</strong> ${count} 篇</p>`
                ).join('')}
            </div>
        </div>
    `;
    
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.style.display = 'block';
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 400px;">
            <div class="modal-header">
                <span class="close" onclick="this.closest('.modal').remove()">&times;</span>
                <h2>统计信息</h2>
            </div>
            <div class="modal-body">
                ${statsContent}
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
}'''
    
    with open('assets/js/jiuyan.js', 'w', encoding='utf-8') as f:
        f.write(jiuyan_js)
   
    # analysis.js
    analysis_js = '''// assets/js/analysis.js - 异动解析页面功能

let currentAnalysisData = null;

document.addEventListener('DOMContentLoaded', function() {
    initAnalysisPage();
});

async function initAnalysisPage() {
    await loadAnalysisDateOptions();
    setupAnalysisEventListeners();
}

// 加载日期选项
async function loadAnalysisDateOptions() {
    try {
        const response = await fetch('analysis/index.json');
        if (!response.ok) throw new Error('无法加载异动解析日期数据');
        
        const indexData = await response.json();
        const dates = Object.keys(indexData).sort().reverse();
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
        
        // 默认选择最新日期
        if (dates.length > 0) {
            dateFilter.value = dates[0];
            await loadAnalysisData(dates[0]);
        }
    } catch (error) {
        console.error('加载异动解析日期选项失败:', error);
        const container = document.getElementById('analysisContainer');
        if (container) {
            showError(container, '加载日期数据失败');
        }
    }
}

// 设置事件监听器
function setupAnalysisEventListeners() {
    const dateFilter = document.getElementById('dateFilter');
    const searchInput = document.getElementById('searchInput');
    const copyDataBtn = document.getElementById('copyDataBtn');
    const viewJsonBtn = document.getElementById('viewJsonBtn');
    const refreshBtn = document.getElementById('refreshBtn');
    
    if (dateFilter) {
        dateFilter.addEventListener('change', (e) => {
            if (e.target.value) {
                loadAnalysisData(e.target.value);
            }
        });
    }
    
    if (searchInput) {
        searchInput.addEventListener('input', debounce(filterAnalysisStocks, 300));
    }
    
    if (copyDataBtn) {
        copyDataBtn.addEventListener('click', copyAnalysisData);
    }
    
    if (viewJsonBtn) {
        viewJsonBtn.addEventListener('click', viewAnalysisJsonData);
    }
    
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            location.reload();
        });
    }
}

// 加载异动解析数据
async function loadAnalysisData(date) {
    const container = document.getElementById('analysisContainer');
    const dataInfo = document.getElementById('dataInfo');
    
    if (!container) {
        console.error('analysisContainer元素未找到');
        return;
    }
    
    showLoading(container);
    if (dataInfo) {
        dataInfo.style.display = 'none';
    }
    
    try {
        const response = await fetch('analysis/' + date + '.json');
        if (!response.ok) throw new Error('异动解析数据加载失败');
        
        currentAnalysisData = await response.json();
        
        // 更新数据信息
        const updateTimeEl = document.getElementById('updateTime');
        const categoryCountEl = document.getElementById('categoryCount');
        const stockCountEl = document.getElementById('stockCount');
        
        if (updateTimeEl) {
            updateTimeEl.textContent = currentAnalysisData.update_time;
        }
        if (categoryCountEl) {
            categoryCountEl.textContent = currentAnalysisData.category_count + '个';
        }
        if (stockCountEl) {
            stockCountEl.textContent = currentAnalysisData.total_stocks + '只';
        }
        if (dataInfo) {
            dataInfo.style.display = 'flex';
        }
        
        // 渲染异动解析数据
        renderAnalysisData(currentAnalysisData.categories);
        
    } catch (error) {
        console.error('加载异动解析数据失败:', error);
        showError(container, '加载数据失败');
    }
}

// 渲染异动解析数据
function renderAnalysisData(categories) {
    const container = document.getElementById('analysisContainer');
    
    if (!container) {
        console.error('analysisContainer元素未找到');
        return;
    }
    
    if (!categories || categories.length === 0) {
        container.innerHTML = '<div class="loading">暂无异动解析数据</div>';
        return;
    }
    
    const categoriesHtml = categories.map(category => {
        const reasonHtml = category.reason ? '<div class="category-reason">' + category.reason + '</div>' : '';
        const stocksHtml = category.stocks.map(stock => {
            const limitTimeHtml = stock.limit_time ? '<div class="limit-time">涨停时间: ' + stock.limit_time + '</div>' : '';
            const analysisHtml = stock.analysis ? '<div class="stock-analysis">' + stock.analysis + '</div>' : '';
            return '<div class="analysis-stock-card" data-code="' + stock.code + '" data-name="' + stock.name + '">' +
                   '<div class="stock-info">' +
                   '<div class="stock-basic">' +
                   '<span class="stock-code-analysis">' + stock.code + '</span>' +
                   '<span class="stock-name-analysis">' + stock.name + '</span>' +
                   '</div>' +
                   limitTimeHtml +
                   '</div>' +
                   analysisHtml +
                   '</div>';
        }).join('');
        
        return '<div class="category-card" data-category="' + category.name + '">' +
               '<div class="category-header">' +
               '<div class="category-title">' + category.name + '</div>' +
               reasonHtml +
               '<div class="category-stats">涉及股票: ' + category.stock_count + ' 只</div>' +
               '</div>' +
               '<div class="stocks-list">' +
               stocksHtml +
               '</div>' +
               '</div>';
    }).join('');
    
    container.innerHTML = categoriesHtml;
}

// 筛选股票
function filterAnalysisStocks() {
    const searchInput = document.getElementById('searchInput');
    if (!searchInput) return;
    
    const searchTerm = searchInput.value.toLowerCase();
    const categoryCards = document.querySelectorAll('.category-card');
    
    categoryCards.forEach(categoryCard => {
        const stockCards = categoryCard.querySelectorAll('.analysis-stock-card');
        let hasVisibleStocks = false;
        
        stockCards.forEach(stockCard => {
            const code = stockCard.dataset.code.toLowerCase();
            const name = stockCard.dataset.name.toLowerCase();
            
            if (code.includes(searchTerm) || name.includes(searchTerm)) {
                stockCard.style.display = 'block';
                hasVisibleStocks = true;
            } else {
                stockCard.style.display = 'none';
            }
        });
        
        // 如果板块下没有匹配的股票，隐藏整个板块
        if (searchTerm && !hasVisibleStocks) {
            categoryCard.style.display = 'none';
        } else {
            categoryCard.style.display = 'block';
        }
    });
}

// 复制异动解析数据
function copyAnalysisData() {
    if (!currentAnalysisData) {
        showToast('暂无数据可复制', 'error');
        return;
    }
    
    let textData = '韭研公社异动解析 - ' + currentAnalysisData.date + '\\n';
    textData += '更新时间: ' + currentAnalysisData.update_time + '\\n';
    textData += '板块数量: ' + currentAnalysisData.category_count + ' 个\\n';
    textData += '股票数量: ' + currentAnalysisData.total_stocks + ' 只\\n';
    textData += "=" + "=".repeat(80) + "\\n\\n";
    
    currentAnalysisData.categories.forEach(category => {
        textData += '=== ' + category.name + ' ===\\n';
        if (category.reason) {
            textData += '板块异动解析: ' + category.reason + '\\n';
        }
        textData += '涉及股票: ' + category.stock_count + ' 只\\n\\n';
        
        category.stocks.forEach(stock => {
            textData += stock.name + '（' + stock.code + '）\\n';
            if (stock.limit_time) {
                textData += '涨停时间: ' + stock.limit_time + '\\n';
            }
            textData += '个股异动解析: ' + stock.analysis + '\\n';
            textData += "\\n" + "-".repeat(80) + "\\n\\n";
        });
    });
    
    copyToClipboard(textData);
}

// 查看JSON数据
function viewAnalysisJsonData() {
    const dateFilter = document.getElementById('dateFilter');
    if (!dateFilter) {
        showToast('页面元素异常', 'error');
        return;
    }
    
    const date = dateFilter.value;
    if (date) {
        window.open('json_viewer.html?type=analysis&date=' + date, '_blank');
    } else {
        showToast('请先选择日期', 'error');
    }
}

// 导出Excel格式数据
function exportAnalysisToExcel() {
    if (!currentAnalysisData) {
        showToast('暂无数据可导出', 'error');
        return;
    }
    
    let csvContent = "data:text/csv;charset=utf-8,";
    csvContent += "板块名称,板块解析,股票代码,股票名称,涨停时间,个股解析\\n";
    
    currentAnalysisData.categories.forEach(category => {
        category.stocks.forEach(stock => {
            const categoryName = category.name || "";
            const categoryReason = category.reason || "";
            const stockCode = stock.code || "";
            const stockName = stock.name || "";
            const limitTime = stock.limit_time || "";
            const analysis = stock.analysis || "";
            
            csvContent += '"' + categoryName + '","' + categoryReason + '","' + stockCode + '","' + stockName + '","' + limitTime + '","' + analysis + '"\\n';
        });
    });
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', '异动解析_' + currentAnalysisData.date + '.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showToast('数据导出成功！');
}

// 获取异动解析统计信息
function getAnalysisStats() {
    if (!currentAnalysisData) return null;
    
    const stats = {
        totalCategories: currentAnalysisData.category_count,
        totalStocks: currentAnalysisData.total_stocks,
        categoriesWithReason: 0,
        stocksWithLimitTime: 0,
        avgStocksPerCategory: 0
    };
    
    currentAnalysisData.categories.forEach(category => {
        if (category.reason) {
            stats.categoriesWithReason++;
        }
        
        category.stocks.forEach(stock => {
            if (stock.limit_time) {
                stats.stocksWithLimitTime++;
            }
        });
    });
    
    stats.avgStocksPerCategory = (stats.totalStocks / stats.totalCategories).toFixed(1);
    
    return stats;
}

// 显示统计信息
function showAnalysisStats() {
    const stats = getAnalysisStats();
    if (!stats) {
        showToast('暂无统计数据', 'error');
        return;
    }
    
    const statsContent = '<div style="padding: 20px;">' +
        '<h3>📊 异动解析统计</h3>' +
        '<div style="margin: 20px 0;">' +
        '<p><strong>总板块数:</strong> ' + stats.totalCategories + ' 个</p>' +
        '<p><strong>总股票数:</strong> ' + stats.totalStocks + ' 只</p>' +
        '<p><strong>有解析的板块:</strong> ' + stats.categoriesWithReason + ' 个</p>' +
        '<p><strong>有涨停时间的股票:</strong> ' + stats.stocksWithLimitTime + ' 只</p>' +
        '<p><strong>平均每板块股票数:</strong> ' + stats.avgStocksPerCategory + ' 只</p>' +
        '</div>' +
        '<p style="color: #999; font-size: 0.9rem;">' +
        '数据更新时间: ' + currentAnalysisData.update_time +
        '</p>' +
        '</div>';
    
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.style.display = 'block';
    modal.innerHTML = '<div class="modal-content" style="max-width: 400px;">' +
        '<div class="modal-header">' +
        '<span class="close" onclick="this.closest(\\'.modal\\').remove()">&times;</span>' +
        '<h2>统计信息</h2>' +
        '</div>' +
        '<div class="modal-body">' +
        statsContent +
        '</div>' +
        '</div>';
    
    document.body.appendChild(modal);
    
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
}'''

    with open('assets/js/analysis.js', 'w', encoding='utf-8') as f:
        f.write(analysis_js)


    
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
    generate_analysis_page()
    generate_dragon_tiger_page()  # 添加这行
    generate_json_viewer()
    generate_css()
    generate_js_files()
    
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
                crawl_single_jiuyan_user(user_key)
            elif len(sys.argv) == 4:
                user_key = sys.argv[2]
                date_str = sys.argv[3]
                crawl_single_jiuyan_user(user_key, date_str)
            generate_all_pages()
        
        elif command == 'analysis':
            if len(sys.argv) == 2:
                crawl_stock_analysis()
            elif len(sys.argv) == 3:
                date_str = sys.argv[2]
                crawl_stock_analysis(date_str)
            generate_all_pages()
        
        elif command == 'dragon_tiger':  # 添加龙虎榜命令
            if len(sys.argv) == 2:
                crawl_dragon_tiger_data()
            elif len(sys.argv) == 3:
                date_str = sys.argv[2]
                crawl_dragon_tiger_data(date_str)
            generate_all_pages()
                
        elif command == 'all':
            print("执行所有功能...")
            main_limit_up()
            print("\n" + "="*60 + "\n")
            crawl_all_jiuyan_articles()
            print("\n" + "="*60 + "\n")
            crawl_stock_analysis()
            print("\n" + "="*60 + "\n")
            crawl_dragon_tiger_data()  # 添加龙虎榜
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
            print("  python script.py analysis                  # 获取异动解析数据")
            print("  python script.py analysis 2025-01-21       # 获取指定日期异动解析数据")
            print("  python script.py dragon_tiger              # 获取龙虎榜数据")
            print("  python script.py dragon_tiger 2025-01-21   # 获取指定日期龙虎榜数据")
            print("  python script.py all                       # 执行所有功能")
            print("  python script.py generate                  # 只生成网页文件")
            print("\n可用的韭研公社用户:")
            for key, info in JIUYAN_USERS.items():
                print(f"  {key} - {info['user_name']}")

if __name__ == "__main__":
    main()






















