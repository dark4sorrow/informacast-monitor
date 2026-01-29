import os, requests, sys, time, json
from flask import Flask, render_template, Response, stream_with_context
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

# --- CONFIGURATION ---
FUSION_API_TOKEN = os.getenv('FUSION_API_TOKEN', 'FHIXRHKMSII6RPKVNXX5C733N5KRB4MQJSJBD2F5KUCWJYHHJKI4PJ4UZRUIQZGDDJPK7U7ACTMLNSHK2VHSZUFCFARTYFKDQTMQEQA=')
BASE_URL = "https://api.icmobile.singlewire.com/api/v1"

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/stream_devices')
def stream_devices():
    def generate():
        current_offset = 0
        limit = 100
        total_sent = 0
        seen_ids = set()

        headers = {"Authorization": f"Bearer {FUSION_API_TOKEN}", "Content-Type": "application/json"}

        while True:
            url = f"{BASE_URL}/devices?limit={limit}&offset={current_offset}"
            try:
                print(f">>> [STREAMING] Requesting Offset: {current_offset}", file=sys.stderr)
                sys.stderr.flush()
                
                resp = requests.get(url, headers=headers, timeout=20)
                if resp.status_code == 429:
                    time.sleep(5)
                    continue
                resp.raise_for_status()
                
                data = resp.json().get('data', [])
                if not data:
                    break

                batch_to_send = []
                for d in data:
                    if d['id'] not in seen_ids:
                        attrs = d.get('attributes', {})
                        total_sent += 1
                        batch_to_send.append({
                            'number': total_sent,
                            'name': d.get('description') or 'No Name',
                            'ip': attrs.get('IPAddress', 'N/A'),
                            'model': attrs.get('InformaCastDeviceType', 'N/A'),
                            'status': "Active" if not d.get('defunct') else "Defunct",
                            'raw': d
                        })
                        seen_ids.add(d['id'])

                # Yield this batch as a Server-Sent Event (SSE)
                yield f"data: {json.dumps(batch_to_send)}\n\n"

                current_offset += len(data)
                if len(data) < limit or total_sent >= 16000:
                    break
                
                time.sleep(0.05)
            except Exception as e:
                print(f">>> ERROR: {e}", file=sys.stderr)
                break
        
        yield "event: close\ndata: done\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5082)