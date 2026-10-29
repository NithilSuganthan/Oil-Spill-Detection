"""Direct AISStream diagnostic — tests WebSocket connection with full logging."""
import json
import sys
import os
import time
import base64

# Load API key
api_key = None
with open("D:/Oil spill detection/backend/.env") as f:
    for line in f:
        if line.strip().startswith("AISSTREAM_API_KEY="):
            api_key = line.strip().split("=", 1)[1]
            break

if not api_key:
    print("ERROR: No AISSTREAM_API_KEY found")
    sys.exit(1)

print(f"API key length: {len(api_key)}")
print(f"API key is JWT: {api_key.startswith('eyJ')}")

# Decode JWT to check audience
try:
    parts = api_key.split(".")
    if len(parts) >= 2:
        payload = parts[1]
        payload += "=" * (4 - len(payload) % 4)
        decoded = json.loads(base64.b64decode(payload))
        print(f"JWT aud: {decoded.get('aud')}")
        print(f"JWT iss: {decoded.get('iss')}")
except Exception as e:
    print(f"JWT decode error: {e}")

import websockets.sync.client as ws_sync

url = f"wss://stream.aisstream.io/v0/stream?apikey={api_key}"
print(f"\nConnecting to wss://stream.aisstream.io/v0/stream")

try:
    with ws_sync.connect(url) as ws:
        print("CONNECTED")

        # Test 1: Without FilterMessageTypes
        subscribe_msg = json.dumps({
            "APIKey": api_key,
            "BoundingBoxes": [[[-5.0, 55.0], [25.0, 100.0]]],
        })
        print(f"\n--- TEST 1: No FilterMessageTypes ---")
        print(f"Subscription: BoundingBoxes=[[[-5.0, 55.0], [25.0, 100.0]]]")
        ws.send(subscribe_msg)
        print("SENT")

        total_frames = 0
        start = time.time()
        msg_types = {}
        while time.time() - start < 30:
            try:
                msg = ws.recv(timeout=5.0)
                if msg is None:
                    print(f"[{time.time()-start:.1f}s] recv() returned None — connection closed")
                    break
                total_frames += 1
                if isinstance(msg, bytes):
                    msg = msg.decode("utf-8", errors="replace")
                data = json.loads(msg)
                mt = data.get("MessageType", "unknown")
                msg_types[mt] = msg_types.get(mt, 0) + 1
                if total_frames <= 10:
                    print(f"[{time.time()-start:.1f}s] FRAME #{total_frames} type={mt} keys={list(data.keys())}")
                    if mt == "PositionReport":
                        m = data.get("Message", {})
                        print(f"  MMSI={m.get('MMSI')} lat={m.get('Latitude')} lon={m.get('Longitude')}")
                elif total_frames == 11:
                    print(f"[{time.time()-start:.1f}s] ... (continuing)")
            except TimeoutError:
                continue
            except Exception as e:
                print(f"[{time.time()-start:.1f}s] ERROR: {type(e).__name__}: {e}")
                break

        print(f"\n--- RESULTS (no filter) ---")
        print(f"Total frames: {total_frames}")
        print(f"Message types: {msg_types}")
        print(f"Duration: {time.time()-start:.1f}s")

except Exception as e:
    print(f"CONNECTION ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
