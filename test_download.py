import requests
import json

def test_download():
    url = 'http://localhost:8787/api/download'
    
    test_cases = [
        'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        'https://www.bilibili.com/video/BV1xx411c7mZ/',
    ]
    
    for video_url in test_cases:
        print(f"\n测试链接: {video_url}")
        try:
            data = {'url': video_url}
            response = requests.post(url, json=data)
            print(f"状态码: {response.status_code}")
            print(f"响应: {response.text}")
        except Exception as e:
            print(f"错误: {e}")

if __name__ == '__main__':
    test_download()