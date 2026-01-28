import os
import requests
import sys
import time
import threading
from datetime import datetime
from flask import Flask, render_template, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

state = {"is_syncing": False, "offset": 0, "speakers_found": 0, "last_sync": "Never", "speakers": []}
state_lock = threading.Lock()

FUSION_API_TOKEN = os.getenv('FUSION_API_TOKEN', 'FHIXRHKMSII6RPKVNXX5C733N5KRB4MQJSJBD2F5KUCWJYHHJKI4PJ4UZRUIQZGDDJPK7U7ACTMLNSHK2VHSZUFCFARTYFKDQTMQEQA=')
BASE_URL = "https://api.icmobile.singlewire.com/api/v1"

def filter_device(device):
    attrs = device.get('attributes', {})
    model = str(attrs.get('InformaCastDeviceType', '')).upper()
    desc = str(device.get('description', '')).upper()
    
    # Strictly ignore Cisco and Desktop Notifiers
    if any(x in model for x in ["CISCO", "DESKTOP"]):
        return False
        
    # Broadened search for AND hardware
    is_match = any(x in model for x in ["ADVANCED", "IPSPEAKER", "NETWORK", "GENERIC"]) or \
               any(x in desc for x in ["AND ", "SPEAKER", "CLOCK", "ZONE"])
    
    if is_match:
        print(f">>> [MATCH] {desc} | Model: {model}", file=sys.stderr)
        sys.stderr.flush()
    return is_match

def run_sync():
    global state
    with state_lock:
        state.update({"is_syncing": True, "offset": 0, "speakers_found": 0, "speakers": []})

    local_offset = 0
    local_speakers = []
    seen_ids = set()

    while True:
        url = f"{BASE_URL}/devices?limit=100&offset={local_offset}"
        try:
            # Force print to terminal
            print(f">>> [SCANNING] Offset: {local_offset}...", file=sys.stderr)
            sys.stderr.flush()
            
            resp = requests.get(url, headers={"Authorization": f"Bearer {FUSION_API_TOKEN}"}, timeout=15)
            if resp.status_code == 429:
                time.sleep(10); continue
            resp.raise_for_status()
            data = resp.json().get('data', [])
            if not data: break

            for d in data:
                if d['id'] not in seen_ids and filter_device(d):
                    attrs = d.get('attributes', {})
                    local_speakers.append({
                        'name': d.get('description') or 'Unknown Device',
                        'ip': attrs.get('IPAddress', 'N/A'),
                        'model': attrs.get('InformaCastDeviceType', 'Other'),
                        'status': "Active" if not d.get('defunct') else "Defunct"
                    })
                    seen_ids.add(d['id'])

            local_offset += len(data)
            
            with state_lock:
                state["offset"] = local_offset
                state["speakers_found"] = len(local_speakers)
                state["speakers"] = local_speakers

            if len(data) < 100 or local_offset >= 15000: break
            time.sleep(0.01)
        except Exception as e:
            print(f">>> ERROR: {e}", file=sys.stderr); sys.stderr.flush()
            break

    with state_lock:
        state["is_syncing"] = False
        state["last_sync"] = datetime.now().strftime("%I:%M:%S %p")
    print(f">>> [FINISHED] Found {len(local_speakers)} items.", file=sys.stderr)
    sys.stderr.flush()

@app.route('/')
def index(): return render_template('dashboard.html')

@app.route('/api/status')
def get_status():
    with state_lock: return jsonify(state)

@app.route('/api/trigger_sync')
def trigger():
    if not state["is_syncing"]:
        threading.Thread(target=run_sync).start()
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5082)