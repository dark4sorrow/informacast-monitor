import os
import requests
import sys
import time
from flask import Flask, render_template, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from collections import Counter

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

# Global status tracker for the UI
sync_status = {"active": False, "endpoint": "", "offset": 0, "count": 0}

# --- CONFIGURATION ---
FUSION_API_TOKEN = os.getenv('FUSION_API_TOKEN', 'FHIXRHKMSII6RPKVNXX5C733N5KRB4MQJSJBD2F5KUCWJYHHJKI4PJ4UZRUIQZGDDJPK7U7ACTMLNSHK2VHSZUFCFARTYFKDQTMQEQA=')
BASE_URL = "https://api.icmobile.singlewire.com/api/v1"

class FusionClient:
    def __init__(self, token):
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def fetch_all(self, endpoint):
        global sync_status
        all_items = []
        limit = 100
        current_offset = 0
        
        sync_status.update({"active": True, "endpoint": endpoint, "offset": 0, "count": 0})
        
        while True:
            url = f"{BASE_URL}/{endpoint}?limit={limit}&offset={current_offset}"
            try:
                print(f">>> [PROCESS {os.getpid()}] Fetching {endpoint} - Offset {current_offset}", file=sys.stderr)
                response = requests.get(url, headers=self.headers, timeout=30)
                
                if response.status_code == 429:
                    time.sleep(10)
                    continue
                
                response.raise_for_status()
                payload = response.json()
                
                batch = payload.get('data', [])
                if not batch: break
                    
                all_items.extend(batch)
                current_offset += len(batch)
                
                # Update status for the UI progress bar
                sync_status["offset"] = current_offset
                sync_status["count"] = len(all_items)
                
                if len(batch) < limit or len(all_items) > 7000:
                    break
                
                time.sleep(0.1)
            except Exception as e:
                print(f">>> ERROR: {e}", file=sys.stderr)
                break
        
        sync_status["active"] = False
        return all_items

client = FusionClient(FUSION_API_TOKEN)

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/status')
def get_status():
    return jsonify(sync_status)

@app.route('/api/analytics')
def api_analytics():
    devices = client.fetch_all("devices")
    notifications = client.fetch_all("notifications")
    
    models = []
    speaker_details = []
    active = 0
    defunct = 0
    
    for d in devices:
        attrs = d.get('attributes', {})
        model_name = attrs.get('InformaCastDeviceType', 'Unknown')
        desc = (d.get('description') or '').upper()
        is_defunct = d.get('defunct', False)
        
        if is_defunct: defunct += 1
        else: active += 1
        
        models.append(model_name)
        
        if any(x in model_name.upper() for x in ['SPEAKER', 'AND']) or 'AND ' in desc:
            speaker_details.append({
                'name': d.get('description') or 'Unnamed Speaker',
                'ip': attrs.get('IPAddress', 'N/A'),
                'status': "Active" if not is_defunct else "Defunct"
            })
            
    return jsonify({
        'device_models': dict(Counter(models)),
        'activity_trend': dict(Counter([n.get('createdAt')[:10] for n in notifications if n.get('createdAt')])),
        'speaker_details': speaker_details,
        'summary': {
            'total_devices': len(devices), 'online': active, 'defunct': defunct,
            'speakers': len(speaker_details), 'total_broadcasts': len(notifications)
        }
    })

@app.route('/api/devices')
def api_devices():
    data = client.fetch_all("devices")
    return jsonify({'data': [{
        'name': d.get('description') or 'Unnamed Device',
        'model': d.get('attributes', {}).get('InformaCastDeviceType', 'Generic'),
        'ip': d.get('attributes', {}).get('IPAddress', 'N/A'),
        'mac': d.get('attributes', {}).get('Name', 'N/A'),
        'status': "Active" if not d.get('defunct') else "Defunct"
    } for d in data]})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5082)