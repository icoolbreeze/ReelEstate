"""E2E stabilization test through davinci-resolve MCP (free-edition bridge)."""
import json, os, subprocess, sys, time

PY = r"C:\Users\shipi\vswp\ReelEstate\tools\davinci-resolve-mcp\runtime\venv\Scripts\python.exe"
SERVER = r"C:\Users\shipi\vswp\ReelEstate\tools\davinci-resolve-mcp\node_modules\davinci-resolve-mcp\src\server.py"
env = os.environ.copy()
env.update({
    "RESOLVE_SCRIPT_API": r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting",
    "RESOLVE_SCRIPT_LIB": r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll",
    "PYTHONPATH": r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules",
    "DAVINCI_RESOLVE_BRIDGE": "1",
})
p = subprocess.Popen([PY, SERVER], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.DEVNULL, env=env, text=True, encoding="utf-8", bufsize=1)
_id = 0
def send(method, params=None):
    global _id; _id += 1
    msg = {"jsonrpc":"2.0","id":_id,"method":method}
    if params is not None: msg["params"] = params
    p.stdin.write(json.dumps(msg)+"\n"); p.stdin.flush()
    line = p.stdout.readline()
    if not line: raise SystemExit("server closed")
    return json.loads(line)
def call(name, **args):
    r = send("tools/call", {"name":name, "arguments":args})
    if "error" in r: return {"_rpc_error": r["error"]}
    txt = "".join(b.get("text","") for b in r["result"]["content"] if b.get("type")=="text")
    try: return json.loads(txt)
    except Exception: return {"_text": txt}
def show(label, obj, n=600):
    print(f"-- {label}")
    print(json.dumps(obj, ensure_ascii=False)[:n])

send("initialize", {"protocolVersion":"2024-11-05","capabilities":{},
                    "clientInfo":{"name":"stab-test","version":"0"}})
p.stdin.write(json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"})+"\n"); p.stdin.flush()

ITEM = {"track_type":"video","track_index":1,"item_index":0}

# Stabilizer analysis runs on the Color page
show("open_page color", call("resolve_control", action="open_page", params={"page":"color"}))

show("get_property StabilizationEnable (before)",
     call("timeline_item", action="get_property", params={**ITEM,"key":"StabilizationEnable"}))
show("get_property StabilizationMethod (before)",
     call("timeline_item", action="get_property", params={**ITEM,"key":"StabilizationMethod"}))

# 1) run the tracker analysis (this is the expensive step)
show("stabilize() analyze", call("timeline_item_color", action="stabilize", params=ITEM))

# Stabilize may be async; give Resolve a moment
time.sleep(3)

# 2) enable + configure (Perspective, strength 0.8)
show("set StabilizationEnable=1",
     call("timeline_item", action="set_property", params={**ITEM,"key":"StabilizationEnable","value":1}))
show("set StabilizationMethod=Perspective",
     call("timeline_item", action="set_property", params={**ITEM,"key":"StabilizationMethod","value":"Perspective"}))
show("set StabilizationStrength=0.8",
     call("timeline_item", action="set_property", params={**ITEM,"key":"StabilizationStrength","value":0.8}))

# 3) read back
show("AFTER enable",
     call("timeline_item", action="get_property", params={**ITEM,"key":"StabilizationEnable"}))
show("AFTER method",
     call("timeline_item", action="get_property", params={**ITEM,"key":"StabilizationMethod"}))
show("AFTER strength",
     call("timeline_item", action="get_property", params={**ITEM,"key":"StabilizationStrength"}))

# 4) snapshot via the color probe to confirm
show("probe_grade_item",
     call("timeline_item_color", action="probe_grade_item", params=ITEM), 900)
p.terminate()
