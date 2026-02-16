#!/usr/bin/env python3
"""Test authentication with the API."""
import time
import hmac
import hashlib
import json
import urllib.request
import urllib.error

BOT_TOKEN = '63919582:zGmwIFir-JfC,aIkM-fhl#SEeU-QBgvloc~-I5VBWhtV-YM.j1nYJ-6xCbuolW-4!1YM0}P-4uLFt$i$-V0ZPqf8x-NbAzd23o-U8MsL&eS-K]6OEsDR-GX3?e8j5-k#K,xqDq-%N[S3Ltg-kPct99p2-ZY2r'

auth_date = int(time.time())

user_data = {
    "id": 27538424011,
    "first_name": "Mr",
    "last_name": "Hyde 795 7 ",
    "language_code": "en",
    "allows_write_to_pm": True
}

data_dict = {
    "auth_date": auth_date,
    "chat_instance": "-5574797810339889514",
    "chat_type": "private",
    "device_id": "40bc8e64956ded3c94755c22382408e1",
    "query_id": "4510310816288634",
    "start_param": "feed_rooznegar",
    "user": user_data
}

# Create check string
check_string_parts = []
for key, value in sorted(data_dict.items()):
    if isinstance(value, dict):
        json_value = json.dumps(value, ensure_ascii=True, separators=(',', ':'))
        check_string_parts.append(f"{key}={json_value}")
    else:
        check_string_parts.append(f"{key}={value}")

check_string = "\n".join(check_string_parts)
secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
hash_value = hmac.new(secret_key, check_string.encode(), hashlib.sha256).digest().hex()

user_json = json.dumps(user_data, separators=(',', ':'))
init_data = f"auth_date={auth_date}&chat_instance=-5574797810339889514&chat_type=private&device_id=40bc8e64956ded3c94755c22382408e1&query_id=4510310816288634&start_param=feed_rooznegar&user={user_json}&hash={hash_value}"

token = f"peyda:eitaa:{init_data}"

print(f"Auth date: {auth_date}")
print(f"Hash: {hash_value}")
print(f"Token length: {len(token)}")

# Make request
url = "http://localhost:8060/api/v1/lessons/1/questions/"
req = urllib.request.Request(url)
req.add_header("Authorization", f"Bearer {token}")
req.add_header("Content-Type", "application/json")

try:
    with urllib.request.urlopen(req) as response:
        print(f"Status: {response.status}")
        print(f"Response: {response.read().decode()[:500]}")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    print(f"Response: {e.read().decode()}")
except Exception as e:
    print(f"Error: {e}")
