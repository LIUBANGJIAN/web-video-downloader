from playwright.sync_api import sync_playwright
import base64

print("Testing Playwright...")
try:
    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch(
            headless=True, 
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
        )
        print("Browser launched")
        
        context = browser.new_context(viewport={'width': 800, 'height': 600})
        page = context.new_page()
        
        print("Navigating to douyin.com...")
        page.goto('https://www.douyin.com', timeout=60000)
        print("Page loaded")
        
        page.wait_for_timeout(2000)
        
        print("Capturing screenshot...")
        screenshot = page.screenshot()
        screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')
        print(f"Screenshot captured, size: {len(screenshot_b64)} bytes")
        
        browser.close()
        print("Browser closed")
        print("Test passed!")
except Exception as e:
    print(f"Test failed: {str(e)}")
    import traceback
    traceback.print_exc()