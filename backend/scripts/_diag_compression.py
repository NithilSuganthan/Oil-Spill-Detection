"""Test AISStream with compression disabled."""
import json, sys, time

api_key = None
with open("D:/Oil spill detection/backend/.env") as f:
    for line in f:
        if line.strip().startswith("AISSTREAM_API_KEY="):
            api_key = line.strip().split("=", 1)[1]
            break

import websockets
import websockets.sync.client as ws_sync

url = f"wss://stream.aisstream.io/v0/stream?apikey={api_key}"

# TEST A: Default (compression enabled by server)
print("=== TEST A: Default connection ===", flush=True)
with ws_sync.connect(url) as ws:
    sub = json.dumps({"APIKey": api_key, "BoundingBoxes": [[[5.0, 55.0], [25.0, 75.0]]]})
    ws.send(sub)
    start = time.time()
    frames = 0
    while time.time() - start < 15:
        try:
            msg = ws.recv(timeout=5.0)
            frames += 1
            if msg is None:
                print(f"  Frame #{frames}: None (closed)", flush=True)
                break
            data = json.loads(msg) if isinstance(msg, (str, bytes)) and len(msg) < 10000 else msg
            if isinstance(data, dict):
                print(f"  Frame #{frames}: type={data.get('MessageType','?')} py={type(msg).__name__}", flush=True)
            else:
                print(f"  Frame #{frames}: py={type(msg).__name__} len={len(str(msg))}", flush=True)
        except TimeoutError:
            continue
        except Exception as e:
            print(f"  Frame #{frames}: ERROR {type(e).__name__}: {e}", flush=True)
            break
    print(f"  Result: {frames} frames in {time.time()-start:.1f}s\n", flush=True)

# TEST B: Disable permessage-deflate compression
print("=== TEST B: Compression disabled ===", flush=True)
try:
    with ws_sync.connect(url, compression=None) as ws:
        sub = json.dumps({"APIKey": api_key, "BoundingBoxes": [[[5.0, 55.0], [25.0, 75.0]]]})
        ws.send(sub)
        start = time.time()
        frames = 0
        while time.time() - start < 15:
            try:
                msg = ws.recv(timeout=5.0)
                frames += 1
                if msg is None:
                    print(f"  Frame #{frames}: None (closed)", flush=True)
                    break
                data = json.loads(msg) if isinstance(msg, (str, bytes)) and len(msg) < 10000 else msg
                if isinstance(data, dict):
                    print(f"  Frame #{frames}: type={data.get('MessageType','?')} py={type(msg).__name__}", flush=True)
                else:
                    print(f"  Frame #{frames}: py={type(msg).__name__} len={len(str(msg))}", flush=True)
            except TimeoutError:
                continue
            except Exception as e:
                print(f"  Frame #{frames}: ERROR {type(e).__name__}: {e}", flush=True)
                break
        print(f"  Result: {frames} frames in {time.time()-start:.1f}s\n", flush=True)
except Exception as e:
    print(f"  Connection failed: {type(e).__name__}: {e}\n", flush=True)

# TEST C: Check what the server actually negotiates
print("=== TEST C: Connection details ===", flush=True)
try:
    with ws_sync.connect(url) as ws:
        print(f"  Subprotocol: {ws.subprotocol}", flush=True)
        print(f"  Extensions: {ws.extensions}", flush=True)
        print(f"  Response headers:", flush=True)
        if hasattr(ws, 'response'):
            print(f"    {ws.response}", flush=True)
except Exception as e:
    print(f"  Error: {type(e).__name__}: {e}", flush=True)
