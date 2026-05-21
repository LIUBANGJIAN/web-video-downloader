import requests

url = 'https://v.douyin.com/MpeyIZyxMTA/'

print(f"测试解析抖音链接: {url}")
print("=" * 50)

try:
    r = requests.post('http://127.0.0.1:8787/api/info', json={'url': url})
    print(f"状态码: {r.status_code}")
    print(f"响应: {r.text}")
    
    if r.status_code == 200:
        data = r.json()
        print("\n解析结果:")
        print(f"  成功: {data.get('success')}")
        print(f"  视频URL: {data.get('videoUrl')}")
        print(f"  图片数量: {data.get('imageCount')}")
        print(f"  消息: {data.get('msg')}")
except Exception as e:
    print(f"请求失败: {e}")