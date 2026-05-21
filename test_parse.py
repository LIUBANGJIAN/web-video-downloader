import requests

url = 'https://v.douyin.com/0zEjCbwAWNo/'
r = requests.post('http://127.0.0.1:8787/api/info', json={'url': url})
print('状态码:', r.status_code)
print('响应:', r.text)