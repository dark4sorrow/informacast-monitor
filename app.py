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

# Persistent state for the live progress bar
state = {
    "is_syncing": False,
    "offset": 0,
    "speakers_found": 0,
    "last_sync": "Never",
    "speakers": []
}
state_lock = threading.Lock()

FUSION_API_TOKEN = os.getenv('FUSION_API_TOKEN', 'FHIXRHKMSII6RPKVNXX5C733N5KRB4MQJSJBD2F5KUCWJYHHJKI4PJ4UZRUIQZGDDJPK7U7ACTMLNSHK2VHSZUFCFARTYFKDQTMQEQA=')
BASE_URL = "https://api.icmobile.singlewire.com/api/v1"

def filter_device(device):
    """Refined filter for Advanced Network Devices (AND)."""
    attrs = device.get('attributes', {})
    model = str(attrs.get('InformaCastDeviceType', '')).upper()
    desc = str(device.get('description', '')).upper()
    
    # Exclude Cisco Phones strictly
    if "CISCO" in model:
        return False
        
    # Standard labels for AND hardware in InformaCast Fusion
    return any(term in model for term in ["ADVANCED", "IPSPEAKER"]) or "AND " in desc

def run_sync():
    """Background task to pull and filter data page by page."""
    global state
    with state_lock:
        state["is_syncing"] = True
        state["offset"] = 0
        state["speakers"] = []
        state["speakers_found"] = 0

    local_offset = 0
    local_speakers = []
    seen_ids = set()

    while True:
        url = f"{BASE_URL}/devices?limit=100&offset={local_offset}"
        try:
            print(f">>> SCANNING: Offset {local_offset}", file=sys.stderr)
            resp = requests.get(url, headers={"Authorization": f"Bearer {FUSION_API_TOKEN}"}, timeout=15)
            if resp.status_code == 429:
                time.sleep(5); continue
            resp.raise_for_status()
            data = resp.json().get('data', [])
            if not data: break

            for d in data:
                if d['id'] not in seen_ids and filter_device(d):
                    attrs = d.get('attributes', {})
                    local_speakers.append({
                        'name': d.get('description') or 'AND Speaker',
                        'ip': attrs.get('IPAddress', 'N/A'),
                        'model': attrs.get('InformaCastDeviceType', 'AND Device'),
                        'status': "Active" if not d.get('defunct') else "Defunct"
                    })
                    seen_ids.add(d['id'])

            local_offset += len(data)
            
            # PUSH UPDATE TO GLOBAL STATE FOR UI
            with state_lock:
                state["offset"] = local_offset
                state["speakers_found"] = len(local_speakers)
                state["speakers"] = local_speakers

            if len(data) < 100 or local_offset > 10000: break
            time.sleep(0.05)
        except Exception as e:
            print(f">>> ERROR: {e}", file=sys.stderr); break

    with state_lock:
        state["is_syncing"] = False
        state["last_sync"] = datetime.now().strftime("%I:%M:%S %p")

@app.route('/')
def index(): return render_template('dashboard.html')

@app.route('/api/status')
def get_status():
    with state_lock: return jsonify(state)

@app.route('/api/trigger_sync')
def trigger():
    if not state["is_syncing"]:
        threading.Thread(target=run_sync).start()
        return jsonify({"status": "started"})
    return jsonify({"status": "already_running"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5082)