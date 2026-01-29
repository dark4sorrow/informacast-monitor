import os, requests, sys, time, threading
from datetime import datetime
from flask import Flask, render_template, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

state = {"is_syncing": False, "offset": 0, "total": 0, "last_sync": "Never", "devices": []}
state_lock = threading.Lock()

FUSION_API_TOKEN = os.getenv('FUSION_API_TOKEN', 'FHIXRHKMSII6RPKVNXX5C733N5KRB4MQJSJBD2F5KUCWJYHHJKI4PJ4UZRUIQZGDDJPK7U7ACTMLNSHK2VHSZUFCFARTYFKDQTMQEQA=')
BASE_URL = "https://api.icmobile.singlewire.com/api/v1"

def run_sync():
    global state
    with state_lock:
        state.update({"is_syncing": True, "offset": 0, "total": 0, "devices": []})

    current_offset = 0
    limit = 100
    accumulated_devices = [] # Use this to store everything across all pages
    seen_ids = set()

    while True:
        # Explicitly pass limit and offset
        url = f"{BASE_URL}/devices?limit={limit}&offset={current_offset}"
        try:
            print(f">>> [FETCHING PAGE] Offset: {current_offset}", file=sys.stderr)
            sys.stderr.flush()
            
            resp = requests.get(url, headers={"Authorization": f"Bearer {FUSION_API_TOKEN}"}, timeout=20)
            if resp.status_code == 429:
                time.sleep(10); continue
            resp.raise_for_status()
            
            payload = resp.json()
            data = payload.get('data', [])
            
            if not data: 
                print(">>> No more data returned from API.", file=sys.stderr)
                break

            for d in data:
                if d['id'] not in seen_ids:
                    attrs = d.get('attributes', {})
                    accumulated_devices.append({
                        'number': len(accumulated_devices) + 1,
                        'name': d.get('description') or 'No Name',
                        'ip': attrs.get('IPAddress', 'N/A'),
                        'model': attrs.get('InformaCastDeviceType', 'N/A'),
                        'status': "Active" if not d.get('defunct') else "Defunct",
                        'raw': d
                    })
                    seen_ids.add(d['id'])

            # THE FIX: Advance offset by the number of items received
            current_offset += len(data)
            
            with state_lock:
                state["offset"] = current_offset
                state["total"] = len(accumulated_devices)
                state["devices"] = accumulated_devices # Push the whole list to UI

            # If we got fewer than 100 items, we are on the last page
            if len(data) < limit: break
            time.sleep(0.01)
        except Exception as e:
            print(f">>> ERROR during fetch: {e}", file=sys.stderr); break

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
    return jsonify({"status": "sync_started"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5082)