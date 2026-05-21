import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 测试 Playwright 导入
try:
    from playwright_parser import parse_with_playwright
    print("✓ Playwright 导入成功")
    PLAYWRIGHT_AVAILABLE = True
except Exception as e:
    print(f"✗ Playwright 导入失败：{e}")
    PLAYWRIGHT_AVAILABLE = False

# 测试 app 导入
try:
    from app import _parse_douyin_url, APP_VERSION
    print(f"✓ App 导入成功，版本：{APP_VERSION}")
except Exception as e:
    print(f"✗ App 导入失败：{e}")

# 测试解析
if PLAYWRIGHT_AVAILABLE:
    print("\n测试解析图文链接...")
    try:
        result = parse_with_playwright('https://v.douyin.com/0zEjCbwAWNo/')
        if result:
            print(f"✓ 解析成功")
            print(f"  类型：{result.get('type')}")
            print(f"  图片数量：{len(result.get('image_url_list', []))}")
        else:
            print("✗ 解析失败")
    except Exception as e:
        print(f"✗ 解析错误：{e}")
