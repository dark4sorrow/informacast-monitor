import os, requests, sys, time, threading, json
from datetime import datetime
from flask import Flask, render_template, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

# The Persistent Master State - Ensures data accumulates and never resets mid-sync
state = {
    "is_syncing": False,
    "offset": 0,
    "total": 0,
    "last_sync": "Never",
    "master_list": [] # This holds all 4,000+ items cumulatively
}
state_lock = threading.Lock()

FUSION_API_TOKEN = os.getenv('FUSION_API_TOKEN', 'FHIXRHKMSII6RPKVNXX5C733N5KRB4MQJSJBD2F5KUCWJYHHJKI4PJ4UZRUIQZGDDJPK7U7ACTMLNSHK2VHSZUFCFARTYFKDQTMQEQA=')
BASE_URL = "https://api.icmobile.singlewire.com/api/v1"

def run_sync():
    global state
    # Reset state for a brand new full scan
    with state_lock:
        state.update({
            "is_syncing": True, 
            "offset": 0, 
            "total": 0, 
            "master_list": []
        })

    current_offset = 0
    limit = 100
    seen_ids = set()
    local_accumulation = [] # Temporary local buffer to build the list

    while True:
        url = f"{BASE_URL}/devices?limit={limit}&offset={current_offset}"
        try:
            print(f">>> [FETCH] Requesting Offset: {current_offset}", file=sys.stderr)
            sys.stderr.flush()
            
            resp = requests.get(url, headers={"Authorization": f"Bearer {FUSION_API_TOKEN}"}, timeout=20)
            if resp.status_code == 429:
                print(">>> Rate Limit Hit. Waiting 10s...", file=sys.stderr)
                time.sleep(10)
                continue
            resp.raise_for_status()
            
            payload = resp.json()
            data = payload.get('data', [])
            if not data: 
                print(">>> End of API data reached.", file=sys.stderr)
                break

            for d in data:
                # Deduplication check
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

            # Manually increment the offset based on the number of items received
            current_offset += len(data)
            
            # PUSH THE FULL GROWING LIST TO THE GLOBAL STATE FOR THE UI TO PULL
            with state_lock:
                state["offset"] = current_offset
                state["total"] = len(local_accumulation)
                state["master_list"] = list(local_accumulation)

            # Exit if we've reached the last page or hit a reasonable limit
            if len(data) < limit or current_offset >= 16000: 
                break
                
            time.sleep(0.01) # Small throttle to keep the API happy
            
        except Exception as e:
            print(f">>> ERROR during background sync: {e}", file=sys.stderr)
            sys.stderr.flush()
            break

    with state_lock:
        state["is_syncing"] = False
        state["last_sync"] = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    print(f">>> [FINISH] Total items captured: {len(local_accumulation)}", file=sys.stderr)

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/status')
def get_status():
    with state_lock:
        return jsonify(state)

@app.route('/api/trigger_sync')
def trigger():
    if not state["is_syncing"]:
        threading.Thread(target=run_sync).start()
        return jsonify({"status": "sync_started"})
    return jsonify({"status": "already_running"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5082)