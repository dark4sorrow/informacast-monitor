import os
import requests
import sys
import time
from datetime import datetime
from flask import Flask, render_template, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

# Status and Cache
sync_status = {"active": False, "offset": 0, "speakers_found": 0, "last_success": "Never"}
speaker_cache = []

FUSION_API_TOKEN = os.getenv('FUSION_API_TOKEN', 'FHIXRHKMSII6RPKVNXX5C733N5KRB4MQJSJBD2F5KUCWJYHHJKI4PJ4UZRUIQZGDDJPK7U7ACTMLNSHK2VHSZUFCFARTYFKDQTMQEQA=')
BASE_URL = "https://api.icmobile.singlewire.com/api/v1"

def is_actually_a_speaker(device):
    """STRICT FILTER: Excludes Cisco phones and hunts for AND hardware."""
    attrs = device.get('attributes', {})
    model = str(attrs.get('InformaCastDeviceType', '')).upper()
    desc = str(device.get('description', '')).upper()
    
    # KILL CISCO PHONES IMMEDIATELY
    if "CISCOIPPHONE" in model or "PHONE" in model:
        return False
    
    # LOOK FOR ADVANCED NETWORK DEVICES (AND)
    # Most AND speakers show up as 'AdvancedNetworkDevices' or have 'AND' in the desc
    return "ADVANCED" in model or "SPEAKER" in model or "AND " in desc

@app.route('/')
def index(): return render_template('dashboard.html')

@app.route('/api/status')
def get_status(): return jsonify(sync_status)

@app.route('/api/analytics')
def api_analytics():
    global speaker_cache, sync_status
    speaker_cache = []
    seen_ids = set()
    current_offset = 0
    sync_status.update({"active": True, "offset": 0, "speakers_found": 0})
    
    while True:
        url = f"{BASE_URL}/devices?limit=100&offset={current_offset}"
        try:
            print(f">>> [PROCESS {os.getpid()}] Filtering Offset {current_offset}", file=sys.stderr)
            response = requests.get(url, headers={"Authorization": f"Bearer {FUSION_API_TOKEN}"}, timeout=20)
            if response.status_code == 429:
                time.sleep(10); continue
            
            response.raise_for_status()
            payload = response.json()
            batch = payload.get('data', [])
            if not batch: break
            
            for d in batch:
                device_id = d.get('id')
                if device_id not in seen_ids and is_actually_a_speaker(d):
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
            
            # Auto-stop after your approx total count (around 5000-6000)
            if len(batch) < 100 or current_offset > 8000: break
            time.sleep(0.05)
            
        except Exception as e:
            print(f">>> ERROR: {e}", file=sys.stderr); break

    sync_status.update({"active": False, "last_success": datetime.now().strftime("%I:%M:%S %p")})
    return jsonify({
        'speaker_details': speaker_cache,
        'summary': {
            'total_scanned': current_offset,
            'speakers': len(speaker_cache),
            'online': sum(1 for s in speaker_cache if s['status'] == 'Active'),
            'defunct': sum(1 for s in speaker_cache if s['status'] == 'Defunct')
        }
    })

@app.route('/api/devices')
def api_devices(): return jsonify({'data': speaker_cache})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5082)