import sys
import time
print("开始测试访问抖音...")

try:
    from playwright.sync_api import sync_playwright
    print("1. 成功导入 playwright.sync_api")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-gpu',
                '--disable-dev-shm-usage',
                '--disable-software-rasterizer',
            ]
        )
        print("2. 成功启动浏览器")
        
        context = browser.new_context(
            viewport={'width': 414, 'height': 736},
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
        )
        page = context.new_page()
        print("3. 成功创建页面")
        
        url = 'https://v.douyin.com/MpeyIZyxMTA/'
        print(f"4. 开始访问: {url}")
        
        page.goto(url, timeout=60000)
        print("5. 成功访问页面")
        
        time.sleep(3)
        print("6. 等待页面加载完成")
        
        title = page.title()
        print(f"7. 页面标题: {title}")
        
        # 检查页面内容
        content = page.content()
        print(f"8. 页面内容长度: {len(content)}")
        
        # 检查是否有 _ROUTER_DATA
        has_router_data = '_ROUTER_DATA' in content
        print(f"9. 包含 _ROUTER_DATA: {has_router_data}")
        
        browser.close()
        print("10. 成功关闭浏览器")
        
    print("✅ 抖音访问测试成功!")
    
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()