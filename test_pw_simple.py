import sys
print("开始简单测试 Playwright...")

try:
    from playwright.sync_api import sync_playwright
    print("1. 成功导入 playwright.sync_api")
    
    with sync_playwright() as p:
        print("2. 成功创建 Playwright 上下文")
        
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-gpu',
                '--disable-dev-shm-usage',
                '--disable-software-rasterizer',
                '--disable-extensions',
            ]
        )
        print("3. 成功启动浏览器")
        
        page = browser.new_page()
        print("4. 成功创建页面")
        
        page.goto('https://www.baidu.com', timeout=30000)
        print("5. 成功访问页面")
        
        title = page.title()
        print(f"6. 页面标题: {title}")
        
        browser.close()
        print("7. 成功关闭浏览器")
        
    print("✅ Playwright 测试成功!")
    
except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()