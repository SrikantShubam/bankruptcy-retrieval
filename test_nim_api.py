#!/usr/bin/env python3
"""
Test NVIDIA NIM API directly
"""
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("NVIDIA_NIM_API_KEY")
print(f"API Key: {api_key[:10]}..." if api_key else "No API key")

url = "https://integrate.api.nvidia.com/v1/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}",
}

payload = {
    "model": "llama-3.1-8b-instruct",
    "messages": [
        {"role": "user", "content": "Say hello"}
    ],
    "temperature": 0.7,
    "max_tokens": 50,
}

print(f"\nTesting NVIDIA NIM API...")
print(f"URL: {url}")
print(f"Model: llama-3.1-8b-instruct")

try:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, json=payload, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
