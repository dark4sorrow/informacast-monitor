import os
import requests
import json
import time
import sys

FUSION_API_TOKEN = os.getenv('FUSION_API_TOKEN')
BASE_URL = "https://api.icmobile.singlewire.com/api/v1"

# Adjusted paths based on Fusion's specific resource structure
ENDPOINTS = {
    'licenses': '/licenses',
    'system_health': '/system-health',
    'notifications': '/notifications',
    'devices': '/devices',
    'users': '/users'
}

def deep_audit():
    if not FUSION_API_TOKEN:
        print("ERROR: FUSION_API_TOKEN is not set.")
        return

    headers = {"Authorization": f"Bearer {FUSION_API_TOKEN}", "Content-Type": "application/json"}
    
    for key, path in ENDPOINTS.items():
        print(f"\n--- AUDITING: {key.upper()} ---")
        all_data = []
        current_offset = "0"

        while current_offset is not None:
            url = f"{BASE_URL}{path}?limit=100&offset={current_offset}"
            try:
                response = requests.get(url, headers=headers, timeout=20)
                
                if response.status_code == 429:
                    print(f"\n[429] Rate Limit Hit. Sleeping 30s...")
                    time.sleep(30)
                    continue
                
                if response.status_code == 404:
                    print(f"\n[404] Resource {path} not found. Skipping.")
                    break
                    
                response.raise_for_status()
                payload = response.json()
                
                data = payload.get('data', []) if 'data' in payload else [payload]
                if not data: break
                    
                all_data.extend(data)
                current_offset = payload.get('next')
                
                print(f"  [PROGRESS] {key}: {len(all_data)} items...", end='\r')
                sys.stdout.flush()
                
                # We found 23,400 devices, so let's set safety to 30,000
                if not current_offset or len(all_data) > 30000:
                    break
                
                # Small delay to prevent 429s
                time.sleep(0.1)
                    
            except Exception as e:
                print(f"\n  [ERROR] {key}: {e}")
                break

        with open(f"fusion_{key}.json", 'w') as f:
            json.dump(all_data, f, indent=4)
        print(f"\n  [SUCCESS] Written {len(all_data)} records to fusion_{key}.json")

if __name__ == "__main__":
    deep_audit()