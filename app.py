import os, requests, sys, time, threading
from datetime import datetime
from flask import Flask, render_template, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

# The Persistent Master State
state = {
    "is_syncing": False,
    "offset": 0,
    "total": 0,
    "last_sync": "Never",
    "master_list": [] # This will hold all 4,000+ items cumulatively
}
state_lock = threading.Lock()

FUSION_API_TOKEN = os.getenv('FUSION_API_TOKEN', 'FHIXRHKMSII6RPKVNXX5C733N5KRB4MQJSJBD2F5KUCWJYHHJKI4PJ4UZRUIQZGDDJPK7U7ACTMLNSHK2VHSZUFCFARTYFKDQTMQEQA=')
BASE_URL = "https://api.icmobile.singlewire.com/api/v1"

def run_sync():
    global state
    with state_lock:
        state.update({"is_syncing": True, "offset": 0, "total": 0, "master_list": []})

    current_offset = 0
    limit = 100
    seen_ids = set()
    local_accumulation = [] # Temporary local buffer

    while True:
        url = f"{BASE_URL}/devices?limit={limit}&offset={current_offset}"
        try:
            print(f">>> [FETCH] Requesting Offset: {current_offset}", file=sys.stderr)
            sys.stderr.flush()
            
            resp = requests.get(url, headers={"Authorization": f"Bearer {FUSION_API_TOKEN}"}, timeout=20)
            if resp.status_code == 429:
                time.sleep(10); continue
            resp.raise_for_status()
            
            payload = resp.json()
            data = payload.get('data', [])
            if not data: break

            for d in data:
                if d['id'] not in seen_ids:
                    attrs = d.get('attributes', {})
                    local_accumulation.append({
                        'number': len(local_accumulation) + 1,
                        'name': d.get('description') or 'No Name',
                        'ip': attrs.get('IPAddress', 'N/A'),
                        'model': attrs.get('InformaCastDeviceType', 'N/A'),
                        'status': "Active" if not d.get('defunct') else "Defunct",
                        'raw': d
                    })
                    seen_ids.add(d['id'])

            # Advance the offset for the NEXT API call
            current_offset += len(data)
            
            # PUSH THE FULL GROWING LIST TO THE GLOBAL STATE
            with state_lock:
                state["offset"] = current_offset
                state["total"] = len(local_accumulation)
                state["master_list"] = list(local_accumulation) # Send the full growing list

            # Stop if we hit the end of the data
            if len(data) < limit: break
            time.sleep(0.01)
            
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
    return jsonify({"status": "sync_started"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5082)