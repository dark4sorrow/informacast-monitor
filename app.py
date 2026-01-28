import os
import requests
import sys
import time
from datetime import datetime
from flask import Flask, render_template, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from collections import Counter

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

# Global trackers
sync_status = {"active": False, "offset": 0, "speakers_found": 0, "last_success": "Never"}
# We store ONLY the speakers globally
speaker_cache = []

FUSION_API_TOKEN = os.getenv('FUSION_API_TOKEN', 'FHIXRHKMSII6RPKVNXX5C733N5KRB4MQJSJBD2F5KUCWJYHHJKI4PJ4UZRUIQZGDDJPK7U7ACTMLNSHK2VHSZUFCFARTYFKDQTMQEQA=')
BASE_URL = "https://api.icmobile.singlewire.com/api/v1"

def is_ip_speaker(device):
    """Business logic to identify your 78 IP Speakers."""
    attrs = device.get('attributes', {})
    model = str(attrs.get('InformaCastDeviceType', '')).upper()
    desc = str(device.get('description', '')).upper()
    # Looking specifically for Advanced Network Devices (AND) or Speaker tags
    return any(term in model for term in ['SPEAKER', 'AND']) or 'AND ' in desc

@app.route('/')
def index(): return render_template('dashboard.html')

@app.route('/api/status')
def get_status(): return jsonify(sync_status)

@app.route('/api/analytics')
def api_analytics():
    global speaker_cache, sync_status
    
    # Reset trackers for fresh run
    speaker_cache = []
    seen_ids = set()
    current_offset = 0
    sync_status.update({"active": True, "offset": 0, "speakers_found": 0})
    
    # We only care about the 'devices' endpoint for speakers
    while True:
        url = f"{BASE_URL}/devices?limit=100&offset={current_offset}"
        try:
            print(f">>> [STREAM] Fetching Offset {current_offset}", file=sys.stderr)
            response = requests.get(url, headers={"Authorization": f"Bearer {FUSION_API_TOKEN}"}, timeout=20)
            
            if response.status_code == 429:
                time.sleep(10); continue
            
            response.raise_for_status()
            payload = response.json()
            batch = payload.get('data', [])
            if not batch: break
            
            for d in batch:
                device_id = d.get('id')
                # DUPLICATE PROTECTION: Only process if we haven't seen this ID in this run
                if device_id not in seen_ids and is_ip_speaker(d):
                    attrs = d.get('attributes', {})
                    speaker_cache.append({
                        'name': d.get('description') or 'Unnamed Speaker',
                        'ip': attrs.get('IPAddress', 'N/A'),
                        'status': "Active" if not d.get('defunct') else "Defunct",
                        'model': attrs.get('InformaCastDeviceType', 'Speaker')
                    })
                    seen_ids.add(device_id)
            
            current_offset += len(batch)
            sync_status.update({"offset": current_offset, "speakers_found": len(speaker_cache)})
            
            # If batch is done or we reach your known limit (approx 4500-5000 devices total)
            if len(batch) < 100 or current_offset > 8000: break
            time.sleep(0.05)
            
        except Exception as e:
            print(f">>> ERROR: {e}", file=sys.stderr); break

    sync_status.update({"active": False, "last_success": datetime.now().strftime("%I:%M:%S %p")})
    
    # Build summary using ONLY the speakers we plucked out
    return jsonify({
        'speaker_details': speaker_cache,
        'summary': {
            'total_devices': current_offset, # Total devices scanned
            'speakers': len(speaker_cache),
            'online': sum(1 for s in speaker_cache if s['status'] == 'Active'),
            'defunct': sum(1 for s in speaker_cache if s['status'] == 'Defunct')
        }
    })

@app.route('/api/devices')
def api_devices():
    # Return just the speakers for the table to keep it fast
    return jsonify({'data': speaker_cache})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5082)