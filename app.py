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
sync_status = {"active": False, "endpoint": "", "offset": 0, "count": 0, "last_success": "Never"}
cache = {"devices": [], "notifications": [], "timestamp": 0}

FUSION_API_TOKEN = os.getenv('FUSION_API_TOKEN', 'FHIXRHKMSII6RPKVNXX5C733N5KRB4MQJSJBD2F5KUCWJYHHJKI4PJ4UZRUIQZGDDJPK7U7ACTMLNSHK2VHSZUFCFARTYFKDQTMQEQA=')
BASE_URL = "https://api.icmobile.singlewire.com/api/v1"

class FusionClient:
    def __init__(self, token):
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def fetch_all(self, endpoint):
        global sync_status
        # Use cache if data is less than 5 minutes old
        if time.time() - cache["timestamp"] < 300 and cache[endpoint]:
            print(f">>> Using cached data for {endpoint}")
            return cache[endpoint]

        all_items = []
        limit = 100
        current_offset = 0
        sync_status.update({"active": True, "endpoint": endpoint, "offset": 0, "count": 0})
        
        while True:
            url = f"{BASE_URL}/{endpoint}?limit={limit}&offset={current_offset}"
            try:
                print(f">>> [FETCH] {endpoint} Offset {current_offset}", file=sys.stderr)
                response = requests.get(url, headers=self.headers, timeout=30)
                if response.status_code == 429:
                    time.sleep(10); continue
                response.raise_for_status()
                payload = response.json()
                batch = payload.get('data', [])
                if not batch: break
                    
                all_items.extend(batch)
                current_offset += len(batch)
                sync_status.update({"offset": current_offset, "count": len(all_items)})
                
                # Cap at 10,000 for your large notifier count
                if len(batch) < limit or len(all_items) > 10000: break
                time.sleep(0.05)
            except Exception as e:
                print(f">>> ERROR: {e}", file=sys.stderr); break
        
        cache[endpoint] = all_items
        cache["timestamp"] = time.time()
        sync_status.update({"active": False, "last_success": datetime.now().strftime("%I:%M:%S %p")})
        return all_items

client = FusionClient(FUSION_API_TOKEN)

@app.route('/')
def index(): return render_template('dashboard.html')

@app.route('/api/status')
def get_status(): return jsonify(sync_status)

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
        models.append(model_name)
        if d.get('defunct'): defunct += 1
        else: active += 1
        
        desc = (d.get('description') or '').upper()
        if any(x in model_name.upper() for x in ['SPEAKER', 'AND']) or 'AND ' in desc:
            speaker_details.append({
                'name': d.get('description') or 'Unnamed Speaker',
                'ip': attrs.get('IPAddress', 'N/A'),
                'status': "Active" if not d.get('defunct') else "Defunct"
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