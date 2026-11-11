"""Smoke test for the davinci-resolve MCP stdio server over the in-app bridge."""
import json, os, subprocess, sys

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
                     stderr=subprocess.PIPE, env=env, text=True, encoding="utf-8", bufsize=1)

def send(method, params=None, msg_id=1):
    msg = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None: msg["params"] = params
    p.stdin.write(json.dumps(msg) + "\n"); p.stdin.flush()

def recv():
    line = p.stdout.readline()
    if not line:
        err = p.stderr.read()
        raise SystemExit(f"server closed; stderr:\n{err[-3000:]}")
    return json.loads(line)

send("initialize", {"protocolVersion":"2024-11-05","capabilities":{},
                    "clientInfo":{"name":"smoke","version":"0"}}, 1)
r = recv(); print("INIT:", r.get("result",{}).get("serverInfo"), "| tools cap:",
                  list(r.get("result",{}).get("capabilities",{}).get("tools",{}).keys()))
p.stdin.write(json.dumps({"jsonrpc":"2.0","method":"notifications/initialized"})+"\n"); p.stdin.flush()
send("tools/list", {}, 2)
tools = recv()["result"]["tools"]
print("TOOL COUNT:", len(tools))
for t in tools: print(" -", t["name"])

def call(name, args, mid):
    send("tools/call", {"name": name, "arguments": args}, mid)
    r = recv()
    if "error" in r: return "ERROR: " + json.dumps(r["error"])[:500]
    c = r["result"]["content"]
    return "".join(b.get("text","") for b in c if b.get("type")=="text")[:1500]

print("\n== resolve_control ==")
print(call("resolve_control", {"action": "status"}, 3)[:1200])
p.terminate()
