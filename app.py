import os
import requests
import sys
from flask import Flask, render_template, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from collections import Counter

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

# --- CONFIGURATION ---
FUSION_API_TOKEN = os.getenv('FUSION_API_TOKEN', 'FHIXRHKMSII6RPKVNXX5C733N5KRB4MQJSJBD2F5KUCWJYHHJKI4PJ4UZRUIQZGDDJPK7U7ACTMLNSHK2VHSZUFCFARTYFKDQTMQEQA=')
BASE_URL = "https://api.icmobile.singlewire.com/api/v1"

class FusionClient:
    def __init__(self, token):
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def fetch_all(self, endpoint):
        all_items = []
        current_url = f"{BASE_URL}/{endpoint}?limit=100"
        
        while current_url:
            try:
                print(f">>> DEBUG: Requesting: {current_url}", file=sys.stderr)
                response = requests.get(current_url, headers=self.headers, timeout=30)
                response.raise_for_status()
                payload = response.json()
                
                # Pull the data batch
                batch = payload.get('data', [])
                all_items.extend(batch)
                
                # CORRECT PATH: Singlewire usually puts pagination in a 'paging' or 'links' object
                # If 'next' is at the root and returning '100', it's the wrong key.
                # We will check both 'next' and 'paging.next' to be safe.
                paging = payload.get('paging', {})
                next_link = paging.get('next') or payload.get('next')
                
                # Check if the captured 'next' is a valid URL or just a number
                if next_link and isinstance(next_link, str) and next_link.startswith('http'):
                    current_url = next_link
                else:
                    current_url = None
                
                print(f">>> DEBUG: Batch: {len(batch)}. Total: {len(all_items)}", file=sys.stderr)
            except Exception as e:
                print(f">>> ERROR: {e}", file=sys.stderr)
                current_url = None
                
        return all_items

client = FusionClient(FUSION_API_TOKEN)

@app.route('/')
def index():
    return render_template('dashboard.html')

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
        
        if any(term in model_name.upper() for term in ['SPEAKER', 'AND', 'ADVANCED']) or \
           any(term in desc for term in ['SPEAKER', 'AND']):
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