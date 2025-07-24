import os
from dotenv import load_dotenv
load_dotenv()

import requests, json

url = os.getenv("SPACEBIN_URL", None)
if not url:
    raise ValueError("SPACEBIN_URL environment variable is not set.")

content = "Hello World!"

print(f"Posting to {url} with content: {content}")
response = requests.request("POST", url, json={"content": content})
if response.status_code == 200:
    data = response.text
    print(data) 
else:
    print(f"Failed to post content. Status code: {response.status_code}")
    print(f"Response: {response.text}")