import urllib.request
import urllib.parse
import json

# Login First
login_data = json.dumps({'email': 'admin@eduguard.com', 'password': 'admin123', 'role': 'admin'}).encode('utf-8')
req = urllib.request.Request('http://127.0.0.1:8000/api/auth/login', data=login_data, headers={'Content-Type': 'application/json'})
response = urllib.request.urlopen(req)
res = json.loads(response.read().decode('utf-8'))
token = res['access_token']

# Test Chat
chat_data = json.dumps({'message': 'Who are the highest risk students?'}).encode('utf-8')
chat_req = urllib.request.Request('http://127.0.0.1:8000/api/ai/chat', data=chat_data, headers={
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {token}'
})
chat_res = urllib.request.urlopen(chat_req)
print(chat_res.read().decode('utf-8'))
