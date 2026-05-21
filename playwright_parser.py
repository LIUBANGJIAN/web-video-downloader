from playwright.sync_api import sync_playwright
import re
import json
import time

def parse_with_playwright(url, timeout=30000):
    """使用Playwright解析抖音视频/图文链接"""
    result = None
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-gpu',
                '--disable-dev-shm-usage',
                '--window-size=1280,720',
                '--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
            ]
        )
        
        try:
            context = browser.new_context(
                viewport={'width': 414, 'height': 736},
                user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
            )
            page = context.new_page()
            
            # 导航到页面
            page.goto(url, timeout=timeout)
            
            # 等待页面加载
            page.wait_for_load_state('networkidle', timeout=timeout)
            time.sleep(2)  # 额外等待确保JS加载完成
            
            # 方法1：尝试从_ROUTER_DATA获取数据（通过evaluate）
            result = extract_from_router_data(page)
            
            # 方法2：如果方法1失败，尝试从页面内容提取
            if not result:
                content = page.content()
                result = extract_data_from_content(content, url)
            
        except Exception as e:
            print(f"Playwright解析错误: {e}")
        finally:
            browser.close()
    
    return result

def extract_from_router_data(page):
    """从_ROUTER_DATA提取数据"""
    try:
        # 获取loaderData中的视频/图文数据
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
        # 检查是否是图文（aweme_type == 2 通常是图文）
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
        
        # 否则视为视频
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
    # 检查是否是图文链接
    if '/note/' in url:
        return extract_note_data(content)
    
    # 检查是否是视频链接
    return extract_video_data(content)

def extract_note_data(content):
    """提取图文数据"""
    try:
        # 尝试解析__NEXT_DATA__
        next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', content)
        if next_data_match:
            try:
                data = json.loads(next_data_match.group(1))
                return parse_next_data_for_note(data)
            except:
                pass
        
        # 尝试解析__INIT_PROPS__
        init_props_match = re.search(r'window\.__INIT_PROPS__\s*=\s*([^<]+);', content)
        if init_props_match:
            try:
                data = json.loads(init_props_match.group(1))
                return parse_init_props_for_note(data)
            except:
                pass
        
        # 尝试直接提取图片URL
        img_pattern = r'"url_list":\["(https://[^"]+douyinpic[^"]+)"'
        matches = re.findall(img_pattern, content)
        if matches:
            # 过滤重复和缩略图
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

# 测试函数
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