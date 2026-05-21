from playwright.sync_api import sync_playwright
import re
import json
import time
import random

def parse_with_playwright(url, timeout=45000):
    """使用Playwright解析抖音视频/图文链接"""
    result = None
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-gpu',
                    '--disable-dev-shm-usage',
                    '--disable-software-rasterizer',
                    '--disable-extensions',
                    '--disable-web-security',
                    '--allow-running-insecure-content',
                    '--window-size=414,736',
                ]
            )
            
            try:
                context = browser.new_context(
                    viewport={'width': 414, 'height': 736},
                    user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
                    accept_language='zh-CN,zh;q=0.9,en;q=0.8',
                    locale='zh-CN',
                )
                page = context.new_page()
                
                # 设置请求超时
                page.set_default_timeout(timeout)
                
                # 导航到页面
                print(f"Playwright: 开始访问 {url}")
                page.goto(url, timeout=timeout)
                
                # 等待页面加载
                try:
                    page.wait_for_load_state('networkidle', timeout=timeout)
                except:
                    print("Playwright: networkidle超时，继续执行")
                
                # 随机延迟
                time.sleep(random.uniform(2, 4))
                
                # 方法1：尝试从_ROUTER_DATA获取数据
                result = extract_from_router_data(page)
                if result:
                    print(f"Playwright: 从_ROUTER_DATA提取成功")
                    return result
                
                # 方法2：尝试从页面内容提取
                content = page.content()
                result = extract_data_from_content(content, url)
                if result:
                    print(f"Playwright: 从页面内容提取成功")
                    return result
                    
                print("Playwright: 未能提取数据")
                
            except Exception as e:
                print(f"Playwright解析错误: {e}")
            finally:
                try:
                    browser.close()
                except:
                    pass
    
    except Exception as e:
        print(f"Playwright初始化错误: {e}")
    
    return result

def extract_from_router_data(page):
    """从_ROUTER_DATA提取数据"""
    try:
        data = page.evaluate('''
            () => {
                const routerData = window._ROUTER_DATA;
                if (!routerData || !routerData.loaderData) return null;
                
                const loaderData = routerData.loaderData;
                for (const key of Object.keys(loaderData)) {
                    const value = loaderData[key];
                    if (value && value.videoInfoRes && value.videoInfoRes.item_list) {
                        const itemList = value.videoInfoRes.item_list;
                        if (itemList.length > 0) {
                            return itemList[0];
                        }
                    }
                    if (value && value.note) {
                        return value.note;
                    }
                }
                return null;
            }
        ''')
        
        if data:
            return parse_item_data(data)
        
        return None
    except Exception as e:
        print(f"从_ROUTER_DATA提取失败: {e}")
        return None

def parse_item_data(item):
    """解析单个视频/图文项"""
    try:
        aweme_type = item.get('aweme_type', 0)
        has_images = 'images' in item and isinstance(item['images'], list) and len(item['images']) > 0
        
        if has_images or aweme_type == 2:
            images = item.get('images', [])
            img_list = []
            for img in images:
                if isinstance(img, dict):
                    url_list = img.get('url_list', [])
                    if url_list:
                        img_list.append(url_list[0])
            
            if img_list:
                return {
                    'type': 'image',
                    'title': item.get('desc', ''),
                    'author': item.get('author', {}).get('nickname', ''),
                    'thumbnail': img_list[0],
                    'image_url_list': img_list,
                }
        
        if 'video' in item and isinstance(item['video'], dict):
            video = item['video']
            play_addr = video.get('play_addr', {})
            url_list = play_addr.get('url_list', [])
            
            if url_list:
                cover = video.get('cover', {})
                cover_urls = cover.get('url_list', [])
                
                return {
                    'type': 'video',
                    'title': item.get('desc', ''),
                    'author': item.get('author', {}).get('nickname', ''),
                    'thumbnail': cover_urls[0] if cover_urls else '',
                    'video_url': url_list[0],
                    'video_id': item.get('aweme_id', ''),
                }
        
        return None
    except Exception as e:
        print(f"解析item数据失败: {e}")
        return None

def extract_data_from_content(content, url):
    """从页面内容中提取视频/图片数据"""
    if '/note/' in url:
        return extract_note_data(content)
    
    return extract_video_data(content)

def extract_note_data(content):
    """提取图文数据"""
    try:
        next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', content)
        if next_data_match:
            try:
                data = json.loads(next_data_match.group(1))
                return parse_next_data_for_note(data)
            except:
                pass
        
        init_props_match = re.search(r'window\.__INIT_PROPS__\s*=\s*([^<]+);', content)
        if init_props_match:
            try:
                data = json.loads(init_props_match.group(1))
                return parse_init_props_for_note(data)
            except:
                pass
        
        img_pattern = r'"url_list":\["(https://[^"]+douyinpic[^"]+)"'
        matches = re.findall(img_pattern, content)
        if matches:
            unique_urls = []
            seen = set()
            for url in matches:
                clean_url = url.replace('\\/', '/').replace('\\\\u002F', '/')
                if '/100x100/' not in clean_url and '/720x720/' not in clean_url:
                    if clean_url not in seen:
                        seen.add(clean_url)
                        unique_urls.append(clean_url)
            
            if unique_urls:
                title_match = re.search(r'"desc":\s*"([^"]+)"', content)
                title = title_match.group(1) if title_match else ''
                
                author_match = re.search(r'"nickname":\s*"([^"]+)"', content)
                author = author_match.group(1) if author_match else ''
                
                return {
                    'type': 'image',
                    'title': title,
                    'author': author,
                    'thumbnail': unique_urls[0],
                    'image_url_list': unique_urls,
                }
        
        return None
    except Exception as e:
        print(f"提取图文数据错误: {e}")
        return None

def extract_video_data(content):
    """提取视频数据"""
    try:
        video_url_pattern = r'"play_addr":\s*{"uri":"[^"]+","url_list":\["([^"]+)"'
        match = re.search(video_url_pattern, content)
        if match:
            video_url = match.group(1).replace('\\/', '/')
            
            title_match = re.search(r'"desc":\s*"([^"]+)"', content)
            title = title_match.group(1) if title_match else ''
            
            author_match = re.search(r'"nickname":\s*"([^"]+)"', content)
            author = author_match.group(1) if author_match else ''
            
            cover_match = re.search(r'"cover":\s*{"uri":"[^"]+","url_list":\["([^"]+)"', content)
            thumbnail = cover_match.group(1).replace('\\/', '/') if cover_match else ''
            
            return {
                'type': 'video',
                'title': title,
                'author': author,
                'thumbnail': thumbnail,
                'video_url': video_url,
                'video_id': '',
            }
        
        return None
    except Exception as e:
        print(f"提取视频数据错误: {e}")
        return None

def parse_next_data_for_note(data):
    """从__NEXT_DATA__解析图文数据"""
    try:
        props = data.get('props', {})
        pageProps = props.get('pageProps', {})
        note = pageProps.get('note', {})
        
        if note:
            images = note.get('images', [])
            if images:
                img_list = []
                for img in images:
                    if isinstance(img, dict) and img.get('url'):
                        img_list.append(img['url'])
                    elif isinstance(img, dict) and img.get('url_list'):
                        url_list = img['url_list']
                        if url_list:
                            img_list.append(url_list[0])
                
                if img_list:
                    return {
                        'type': 'image',
                        'title': note.get('title', '') or note.get('desc', ''),
                        'author': note.get('author', {}).get('nickname', ''),
                        'thumbnail': img_list[0],
                        'image_url_list': img_list,
                    }
        
        return None
    except:
        return None

def parse_init_props_for_note(data):
    """从__INIT_PROPS__解析图文数据"""
    try:
        paths = [
            ['note', 'images'],
            ['data', 'note', 'images'],
            ['result', 'note', 'images'],
            ['aweme', 'images'],
        ]
        
        for path in paths:
            current = data
            valid = True
            for key in path:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    valid = False
                    break
            
            if valid and isinstance(current, list) and len(current) > 0:
                img_list = []
                for img in current:
                    if isinstance(img, dict):
                        if img.get('url'):
                            img_list.append(img['url'])
                        elif img.get('url_list'):
                            url_list = img['url_list']
                            if url_list:
                                img_list.append(url_list[0])
                
                if img_list:
                    return {
                        'type': 'image',
                        'title': data.get('note', {}).get('title', '') or data.get('desc', ''),
                        'author': data.get('note', {}).get('author', {}).get('nickname', ''),
                        'thumbnail': img_list[0],
                        'image_url_list': img_list,
                    }
        
        return None
    except:
        return None

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = 'https://v.douyin.com/0zEjCbwAWNo/'
    
    print(f"解析链接: {url}")
    result = parse_with_playwright(url)
    
    if result:
        print("\n解析成功!")
        print(f"类型: {result.get('type')}")
        print(f"标题: {result.get('title', '')[:50]}")
        print(f"作者: {result.get('author', '')[:30]}")
        
        if result['type'] == 'image':
            images = result.get('image_url_list', [])
            print(f"图片数量: {len(images)}")
            for i, img in enumerate(images[:3]):
                print(f"  {i+1}: {img[:80]}...")
        else:
            print(f"视频URL: {result.get('video_url', '')[:80]}...")
    else:
        print("\n解析失败!")