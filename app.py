import os
import requests
import sys
from flask import Flask, render_template, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from collections import Counter

app = Flask(__name__)
# Configure ProxyFix for the /informacast/ sub-path on galacticbacon
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

# --- CONFIGURATION ---
FUSION_API_TOKEN = os.getenv('FUSION_API_TOKEN', 'FHIXRHKMSII6RPKVNXX5C733N5KRB4MQJSJBD2F5KUCWJYHHJKI4PJ4UZRUIQZGDDJPK7U7ACTMLNSHK2VHSZUFCFARTYFKDQTMQEQA=')
BASE_URL = "https://api.icmobile.singlewire.com/api/v1"

class FusionClient:
    def __init__(self, token):
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def fetch_all(self, endpoint):
        """Recursively follows the full URL provided in the 'next' field."""
        all_items = []
        # We start with the base endpoint
        current_url = f"{BASE_URL}/{endpoint}?limit=100"
        
        while current_url:
            try:
                # Log exactly what we are about to call
                print(f">>> DEBUG: Sending Request To: {current_url}", file=sys.stderr)
                
                response = requests.get(current_url, headers=self.headers, timeout=30)
                response.raise_for_status()
                payload = response.json()
                
                # Add current batch to list
                batch = payload.get('data', [])
                all_items.extend(batch)
                
                # Informacast returns a FULL URL in the 'next' field for the next page
                # We update current_url to this value. If it's None, the loop ends.
                current_url = payload.get('next')
                
                print(f">>> DEBUG: Batch Size: {len(batch)}. Total So Far: {len(all_items)}", file=sys.stderr)
                if current_url:
                    print(f">>> DEBUG: Next Link Found: {current_url}", file=sys.stderr)
                else:
                    print(f">>> DEBUG: No more pages found.", file=sys.stderr)
                    
            except Exception as e:
                print(f">>> ERROR: Pagination failed: {e}", file=sys.stderr)
                # Break the loop on error so we at least return what we have
                current_url = None
                
        return all_items

client = FusionClient(FUSION_API_TOKEN)

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/analytics')
def api_analytics():
    # Fetch ALL pages for both devices and notifications
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
        
        # Filter for your 78 IP Speakers
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
            'total_devices': len(devices),
            'online': active,
            'defunct': defunct,
            'speakers': len(speaker_details),
            'total_broadcasts': len(notifications)
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