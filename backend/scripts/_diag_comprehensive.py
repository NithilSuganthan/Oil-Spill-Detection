"""Comprehensive AISStream diagnostic — tests all potential failure modes."""
import json
import sys
import time
import base64
import threading

# Load API key
api_key = None
with open("D:/Oil spill detection/backend/.env") as f:
    for line in f:
        if line.strip().startswith("AISSTREAM_API_KEY="):
            api_key = line.strip().split("=", 1)[1]
            break

if not api_key:
    print("ERROR: No AISSTREAM_API_KEY")
    sys.exit(1)

print(f"API key length: {len(api_key)}")
print(f"API key is JWT: {api_key.startswith('eyJ')}")

import websockets.sync.client as ws_sync

def test_connection(label, subscribe_msg, bbox_label, timeout_sec=30):
    """Test a single connection scenario."""
    print(f"\n{'='*60}")
    print(f"TEST: {label}")
    print(f"{'='*60}")

    url = f"wss://stream.aisstream.io/v0/stream?apikey={api_key}"
    try:
        with ws_sync.connect(url) as ws:
            print(f"CONNECTED (type={type(ws).__name__})")

            # Send subscription
            ws.send(subscribe_msg)
            print(f"SUBSCRIPTION SENT: {bbox_label}")

            total_frames = 0
            start = time.time()
            last_frame_time = start

            while time.time() - start < timeout_sec:
                try:
                    msg = ws.recv(timeout=5.0)
                    now = time.time()
                    total_frames += 1

                    if msg is None:
                        print(f"[{now-start:.1f}s] FRAME #{total_frames}: recv()=None — connection closed")
                        break

                    # Log Python type
                    py_type = type(msg).__name__
                    if isinstance(msg, bytes):
                        size = len(msg)
                        try:
                            text = msg.decode("utf-8")
                        except UnicodeDecodeError:
                            print(f"[{now-start:.1f}s] FRAME #{total_frames}: BINARY len={size} python_type={py_type} (not UTF-8)")
                            last_frame_time = now
                            continue
                    else:
                        text = msg
                        size = len(text.encode("utf-8")) if isinstance(text, str) else 0

                    # Parse JSON
                    try:
                        data = json.loads(text)
                    except json.JSONDecodeError:
                        print(f"[{now-start:.1f}s] FRAME #{total_frames}: NON-JSON python_type={py_type} size={size} preview={text[:100]}")
                        last_frame_time = now
                        continue

                    msg_type = data.get("MessageType", "unknown")

                    # Log all details for first 5 frames
                    if total_frames <= 5:
                        print(f"[{now-start:.1f}s] FRAME #{total_frames}: type={msg_type} python_type={py_type} size={size}")
                        if msg_type == "SubscriptionConfirmation":
                            comp = data.get("Message", {}).get("CompressionEnabled", "unknown")
                            print(f"  CompressionEnabled={comp}")
                        elif msg_type == "PositionReport":
                            m = data.get("Message", {})
                            print(f"  Message keys={list(m.keys()) if isinstance(m, dict) else type(m)}")
                            # Check MetaData
                            md = data.get("MetaData", {})
                            if md:
                                print(f"  MetaData keys={list(md.keys()) if isinstance(md, dict) else type(md)}")
                                print(f"  MetaData.MMSI={md.get('MMSI')} lat={md.get('Latitude')} lon={md.get('Longitude')}")
                        elif msg_type == "ShipStaticData":
                            m = data.get("Message", {})
                            print(f"  Message keys={list(m.keys()) if isinstance(m, dict) else type(m)}")
                    else:
                        # For frames after #5, just count types
                        pass

                    last_frame_time = now

                except TimeoutError:
                    elapsed = time.time() - start
                    idle = time.time() - last_frame_time
                    if total_frames > 0 and idle > 10:
                        print(f"[{elapsed:.1f}s] TIMEOUT (idle={idle:.1f}s, frames={total_frames})")
                    continue
                except Exception as e:
                    print(f"[{now-start:.1f}s] EXCEPTION: {type(e).__name__}: {e}")
                    break

            elapsed = time.time() - start
            print(f"\nRESULT: {total_frames} frames in {elapsed:.1f}s")
            return total_frames

    except Exception as e:
        print(f"CONNECTION ERROR: {type(e).__name__}: {e}")
        return 0


# TEST 1: Current config — FilterMessageTypes=["PositionReport"], large bbox
bbox_large = [[-5.0, 55.0], [25.0, 100.0]]
sub_with_filter = json.dumps({
    "APIKey": api_key,
    "BoundingBoxes": [bbox_large],
    "FilterMessageTypes": ["PositionReport"],
})
n1 = test_connection("FilterMessageTypes=[PositionReport], large bbox", sub_with_filter, "large bbox with filter", timeout_sec=30)

# TEST 2: NO FilterMessageTypes, large bbox
sub_no_filter = json.dumps({
    "APIKey": api_key,
    "BoundingBoxes": [bbox_large],
})
n2 = test_connection("No FilterMessageTypes, large bbox", sub_no_filter, "large bbox no filter", timeout_sec=30)

# TEST 3: FilterMessageTypes=["PositionReport"], small bbox (Arabian Sea)
bbox_small = [[5.0, 55.0], [25.0, 75.0]]
sub_small = json.dumps({
    "APIKey": api_key,
    "BoundingBoxes": [bbox_small],
    "FilterMessageTypes": ["PositionReport"],
})
n3 = test_connection("FilterMessageTypes=[PositionReport], small bbox", sub_small, "small bbox (55-75E, 5-25N)", timeout_sec=30)

# TEST 4: Global bbox, no filter
bbox_global = [[-90.0, -180.0], [90.0, 180.0]]
sub_global = json.dumps({
    "APIKey": api_key,
    "BoundingBoxes": [bbox_global],
})
n4 = test_connection("Global bbox, no filter", sub_global, "global", timeout_sec=30)

# TEST 5: Exact example from AISStream docs (Miami)
bbox_miami = [[25.835302, -80.207729], [25.602700, -79.879297]]
sub_miami = json.dumps({
    "APIKey": api_key,
    "BoundingBoxes": [bbox_miami],
})
n5 = test_connection("Miami example from docs, no filter", sub_miami, "Miami port", timeout_sec=20)

print(f"\n{'='*60}")
print(f"SUMMARY")
print(f"{'='*60}")
print(f"Test 1 (large+filter):     {n1} frames")
print(f"Test 2 (large+no filter):  {n2} frames")
print(f"Test 3 (small+filter):     {n3} frames")
print(f"Test 4 (global+no filter): {n4} frames")
print(f"Test 5 (Miami+no filter):  {n5} frames")
