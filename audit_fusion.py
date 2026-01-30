import os
import requests
import csv
import sys
import time

# Configuration from your environment
FUSION_API_TOKEN = os.getenv('FUSION_API_TOKEN', 'FHIXRHKMSII6RPKVNXX5C733N5KRB4MQJSJBD2F5KUCWJYHHJKI4PJ4UZRUIQZGDDJPK7U7ACTMLNSHK2VHSZUFCFARTYFKDQTMQEQA=')
BASE_URL = "https://api.icmobile.singlewire.com/api/v1"

def run_unfiltered_audit():
    headers = {
        "Authorization": f"Bearer {FUSION_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    csv_file = "fusion_inventory.csv"
    current_offset = 0
    limit = 100
    total_processed = 0
    
    print(f"--- Starting Full Fusion Audit ---")
    print(f"Target: {BASE_URL}/devices")
    print(f"Output: {csv_file}\n")

    try:
        with open(csv_file, mode='w', newline='', encoding='utf-8') as f:
            writer = None # We'll initialize headers once we see the first record
            
            while True:
                url = f"{BASE_URL}/devices?limit={limit}&offset={current_offset}"
                print(f"[FETCHING] Offset {current_offset}...", end='\r')
                sys.stdout.flush()

                response = requests.get(url, headers=headers, timeout=30)
                
                if response.status_code == 429:
                    print("\n[RATE LIMIT] Throttled. Waiting 10s...")
                    time.sleep(10)
                    continue
                
                response.raise_for_status()
                payload = response.json()
                devices = payload.get('data', [])

                if not devices:
                    print(f"\n[COMPLETE] End of data reached at offset {current_offset}.")
                    break

                for dev in devices:
                    # Flatten the dictionary for CSV
                    # We pull top-level fields and the 'attributes' sub-dictionary
                    flat_record = {**dev}
                    attrs = flat_record.pop('attributes', {})
                    for k, v in attrs.items():
                        flat_record[f"attr_{k}"] = v
                    
                    # Initialize CSV headers based on the first record's keys
                    if writer is None:
                        headers_list = sorted(flat_record.keys())
                        writer = csv.DictWriter(f, fieldnames=headers_list)
                        writer.writeheader()

                    writer.writerow(flat_record)
                    total_processed += 1

                # Advance offset
                current_offset += len(devices)
                
                # Safety break to prevent infinite loops if the API behaves unexpectedly
                if current_offset > 20000:
                    print("\n[SAFETY STOP] Exceeded 20,000 records.")
                    break

        print(f"\n--- Audit Summary ---")
        print(f"Total Devices Written to CSV: {total_processed}")
        print(f"File Location: {os.path.abspath(csv_file)}")

    except Exception as e:
        print(f"\n[FATAL ERROR] {str(e)}")

if __name__ == "__main__":
    run_unfiltered_audit()