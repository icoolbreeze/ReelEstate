"""Run the existing image QA on one current episode/version, never on old output/."""
import argparse,re,subprocess,sys,json
from pathlib import Path
REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO))
from pipeline.common.workspace import episode_path
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('episode');ap.add_argument('--ver',required=True)
 a=ap.parse_args()
 if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',a.ver):ap.error('invalid version')
 ep=episode_path(a.episode);folder=ep/'out/drafts'/a.ver;frames={}
 for p in folder.glob('*.png'):
  match=re.search(r'_f(\d+)$',p.stem)
  if match:frames.setdefault(int(match.group(1)),p)
 if len(frames)<4:
  print('FAIL: provide at least four distinct rendered frames in '+str(folder));return 1
 argv=[sys.executable,str(REPO/'pipeline/check/harmony_check.py'),*[str(p) for p in frames.values()]]
 from pipeline.common.voice_config import read_yaml
 cfg=read_yaml(ep/'episode.yaml')
 if cfg.get('series')=='interview':
  layout=json.loads((ep/'data/layout.json').read_text(encoding='utf-8-sig'));boxes=layout['boxes']
  face,gesture=boxes['face'],boxes['gesture'];x=min(face['x'],gesture['x']);y=min(face['y'],gesture['y'])
  w=max(face['x']+face['w'],gesture['x']+gesture['w'])-x;h=max(face['y']+face['h'],gesture['y']+gesture['h'])-y
  argv += ['--focus-box',str(x/layout['width']),str(y/layout['height']),str(w/layout['width']),str(h/layout['height'])]
 return subprocess.call(argv,cwd=REPO)
if __name__=='__main__':raise SystemExit(main())
