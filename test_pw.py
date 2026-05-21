import sys
print("开始测试 Playwright...")

try:
    from playwright_parser import parse_with_playwright
    print("成功导入 Playwright parser")
    
    url = 'https://v.douyin.com/MpeyIZyxMTA/'
    print(f"开始解析: {url}")
    
    result = parse_with_playwright(url)
    print(f"解析结果: {result}")
    
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()