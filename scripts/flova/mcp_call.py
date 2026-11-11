"""Call one flova-image MCP tool from a shell: python scripts/flova/mcp_call.py <tool> <args.json> | list
Importable: from mcp_call import call; call("generate_speech", {...}) -> parsed tool result (dict).
Images: omit profile/project_id for automatic pool routing; use dry_run=true to inspect a plan without generation."""
import json, subprocess, sys, os
SERVER = r"C:/Users/shipi/.flova-mcp/server.js"
NODE = r"C:/Program Files/nodejs/node.exe"


class _Client:
    def __init__(self):
        env = dict(os.environ, FLOVA_BIN=r"C:/Users/shipi/AppData/Local/Programs/flova/flova.exe")
        self.p = subprocess.Popen([NODE, SERVER], stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env, text=True, encoding="utf-8")
        self.rpc(1, "initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "box", "version": "1"}})
        self.rpc(None, "notifications/initialized")

    def rpc(self, i, m, params=None):
        msg = {"jsonrpc": "2.0", "method": m}
        if i is not None: msg["id"] = i
        if params is not None: msg["params"] = params
        self.p.stdin.write(json.dumps(msg) + "\n"); self.p.stdin.flush()
        if i is None: return None
        while True:
            line = self.p.stdout.readline()
            if not line: raise SystemExit("server closed")
            d = json.loads(line)
            if d.get("id") == i: return d

    def close(self):
        self.p.terminate()


def call(tool, args):
    """Run one tool; return the parsed JSON result (raises RuntimeError on MCP error)."""
    c = _Client()
    try:
        r = c.rpc(3, "tools/call", {"name": tool, "arguments": args})
    finally:
        c.close()
    if "error" in r:
        raise RuntimeError(json.dumps(r["error"], ensure_ascii=False))
    res = r["result"]
    text = "".join(x.get("text", "") for x in res.get("content", []))
    try:
        out = json.loads(text)
    except ValueError:
        out = {"status": "error", "text": text}
    if res.get("isError"):
        raise RuntimeError(text[:500])
    return out


if __name__ == "__main__":
    if sys.argv[1] == "list":
        c = _Client()
        for t in c.rpc(2, "tools/list")["result"]["tools"]:
            print("##", t["name"], "\n", t.get("description", "")[:600], "\n", json.dumps(t.get("inputSchema"), ensure_ascii=False)[:1500])
        c.close()
    else:
        args = json.load(open(sys.argv[2], encoding="utf-8"))
        c = _Client()
        r = c.rpc(3, "tools/call", {"name": sys.argv[1], "arguments": args})
        c.close()
        sys.stdout.reconfigure(encoding="utf-8"); print(json.dumps(r, ensure_ascii=False)[:6000])
