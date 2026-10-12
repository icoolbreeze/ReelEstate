"""Call one flova-image MCP tool from a shell: python scripts/flova/mcp_call.py <tool> <args.json> | list"""
import json, subprocess, sys, os
env = dict(os.environ, FLOVA_BIN=r"C:/Users/shipi/AppData/Local/Programs/flova/flova.exe")
p = subprocess.Popen([r"C:/Program Files/nodejs/node.exe", r"C:/Users/shipi/.flova-mcp/server.js"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env, text=True, encoding="utf-8")
def rpc(i, m, params=None):
    msg = {"jsonrpc": "2.0", "method": m}
    if i is not None: msg["id"] = i
    if params is not None: msg["params"] = params
    p.stdin.write(json.dumps(msg) + "\n"); p.stdin.flush()
    if i is None: return None
    while True:
        line = p.stdout.readline()
        if not line: raise SystemExit("server closed")
        d = json.loads(line)
        if d.get("id") == i: return d
rpc(1, "initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "box", "version": "1"}})
rpc(None, "notifications/initialized")
if sys.argv[1] == "list":
    for t in rpc(2, "tools/list")["result"]["tools"]:
        print("##", t["name"], "\n", t.get("description","")[:600], "\n", json.dumps(t.get("inputSchema"), ensure_ascii=False)[:1500])
else:
    args = json.load(open(sys.argv[2], encoding="utf-8"))
    r = rpc(3, "tools/call", {"name": sys.argv[1], "arguments": args})
    sys.stdout.reconfigure(encoding="utf-8"); print(json.dumps(r, ensure_ascii=False)[:6000])
p.terminate()
