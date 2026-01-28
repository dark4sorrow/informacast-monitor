def filter_device(device):
    """Broadened filter to ensure we catch all 78 AND speakers."""
    attrs = device.get('attributes', {})
    model = str(attrs.get('InformaCastDeviceType', '')).upper()
    desc = str(device.get('description', '')).upper()
    
    # Still strictly exclude Cisco Phones
    if "CISCO" in model or "SEP" in desc:
        return False
        
    # AND hardware often identifies as 'Advanced', 'IPSpeaker', 
    # or simply contains 'AND' in the description.
    is_speaker = any(term in model for term in ["ADVANCED", "IPSPEAKER", "SPEAKER"]) or \
                 any(term in desc for term in ["AND ", "SPEAKER", "CLOCK"])
                 
    if is_speaker:
        print(f">>> MATCH FOUND: {desc} | Model: {model}", file=sys.stderr)
        
    return is_speaker

def run_sync():
    """Background task with increased cap and improved exit logic."""
    global state
    with state_lock:
        state.update({"is_syncing": True, "offset": 0, "speakers_found": 0, "speakers": []})

    local_offset = 0
    local_speakers = []
    seen_ids = set()

    while True:
        url = f"{BASE_URL}/devices?limit=100&offset={local_offset}"
        try:
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
                        'name': d.get('description') or 'AND Device',
                        'ip': attrs.get('IPAddress', 'N/A'),
                        'model': attrs.get('InformaCastDeviceType', 'AND Hardware'),
                        'status': "Active" if not d.get('defunct') else "Defunct"
                    })
                    seen_ids.add(d['id'])

            local_offset += len(data)
            
            with state_lock:
                state["offset"] = local_offset
                state["speakers_found"] = len(local_speakers)
                state["speakers"] = local_speakers

            # Raised safety cap to 12,000 just in case
            if local_offset >= 12000: break
            time.sleep(0.02)
        except Exception as e:
            print(f">>> ERROR: {e}", file=sys.stderr); break

    with state_lock:
        state["is_syncing"] = False
        state["last_sync"] = datetime.now().strftime("%I:%M:%S %p")