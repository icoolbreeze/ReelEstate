"""Validate the shared map-hub overlay math before rendering (no model/API use)."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path
from workspace import stage_episode

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("episode")
    args = ap.parse_args()
    work = stage_episode(args.episode)
    node = shutil.which("node")
    if not node:
        raise SystemExit("Node is required for shared overlay checks")
    hook = """const ts=require('typescript'),fs=require('fs');
for(const e of ['.ts','.tsx']) require.extensions[e]=(m,f)=>m._compile(ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.React,esModuleInterop:true,target:ts.ScriptTarget.ES2020}}).outputText,f);
require('./src/overlayMotion.check.ts');
const {prepareTracking,sampleTracking}=require('./src/annotationMotion.ts');
const path='./src/episode/annotations.json';const anns=fs.existsSync(path)?JSON.parse(fs.readFileSync(path,'utf8')):{};
let count=0,maxCorrection=0;
for(const ann of Object.values(anns))for(const t of ann.targets||[]){
 if(!t.kf?.length)continue;count++;
 const p=prepareTracking(t.kf);
 for(let i=0;i<p.keys.length;i++)for(let c=1;c<5;c++)maxCorrection=Math.max(maxCorrection,Math.abs(p.keys[i][c]-t.kf[i][c])*(c%2?1440:1080));
 for(const k of p.keys){const a=JSON.stringify(sampleTracking(t.kf,k[0]));if(a!==JSON.stringify(sampleTracking(t.kf,k[0])))throw Error('non-deterministic track');}
}
if(maxCorrection>1.25001)throw Error('tracking correction exceeds limit');
console.log(JSON.stringify({ok:true,tracks:count,maxCorrectionPx:maxCorrection}));
"""
    p = subprocess.run([node, "-e", hook], cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [line for line in p.stdout.splitlines() if line.startswith("{")]
    report = {"pass":p.returncode == 0,"checks":[json.loads(line) for line in lines],"stderr":p.stderr}
    (work.parent.parent / "out/overlay_checks.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False),flush=True)
    raise SystemExit(p.returncode)

if __name__ == "__main__":
    main()
