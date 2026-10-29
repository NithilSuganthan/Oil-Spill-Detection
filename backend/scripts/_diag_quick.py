"""Minimal AISStream diagnostic — 20 second test."""
import json, sys, time, base64

api_key = None
with open("D:/Oil spill detection/backend/.env") as f:
    for line in f:
        if line.strip().startswith("AISSTREAM_API_KEY="):
            api_key = line.strip().split("=", 1)[1]
            break

import websockets.sync.client as ws_sync

url = f"wss://stream.aisstream.io/v0/stream?apikey={api_key}"
print("CONNECTING...", flush=True)

with ws_sync.connect(url) as ws:
    print("CONNECTED", flush=True)

    # Subscribe WITHOUT FilterMessageTypes, small bbox
    sub = json.dumps({
        "APIKey": api_key,
        "BoundingBoxes": [[[5.0, 55.0], [25.0, 75.0]]],
    })
    ws.send(sub)
    print("SUBSCRIPTION SENT (small bbox, no filter)", flush=True)

    start = time.time()
    frames = 0
    while time.time() - start < 20:
        try:
            msg = ws.recv(timeout=5.0)
            frames += 1
            elapsed = time.time() - start
            if msg is None:
                print(f"[{elapsed:.1f}s] FRAME #{frames}: None (closed)", flush=True)
                break
            pytype = type(msg).__name__
            if isinstance(msg, bytes):
                print(f"[{elapsed:.1f}s] FRAME #{frames}: BINARY len={len(msg)} python_type={pytype}", flush=True)
                try:
                    text = msg.decode("utf-8")
                    data = json.loads(text)
                    print(f"  MessageType={data.get('MessageType','?')}", flush=True)
                except:
                    print(f"  raw[:100]={msg[:100]}", flush=True)
            else:
                data = json.loads(msg)
                mt = data.get("MessageType", "?")
                print(f"[{elapsed:.1f}s] FRAME #{frames}: type={mt} python_type={pytype} len={len(msg)}", flush=True)
                if mt == "PositionReport":
                    m = data.get("Message", data)
                    md = data.get("MetaData", {})
                    print(f"  MMSI={md.get('MMSI', m.get('MMSI','?'))} lat={md.get('Latitude', m.get('Latitude','?'))} lon={md.get('Longitude', m.get('Longitude','?'))}", flush=True)
        except TimeoutError:
            continue
        except Exception as e:
            print(f"[{time.time()-start:.1f}s] ERROR: {type(e).__name__}: {e}", flush=True)
            break

    print(f"\nTOTAL: {frames} frames in {time.time()-start:.1f}s", flush=True)
