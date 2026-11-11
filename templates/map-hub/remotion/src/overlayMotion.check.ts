import { prepareTracking, sampleTracking } from "./annotationMotion";
import { planLeader, leaderPathJump, segmentHits, rectanglePorts, type Obstacle } from "./leaderRouting";
const fails: string[] = [];
const check = (ok: boolean, label: string) => { if (!ok) fails.push(label); };
const jitter = Array.from({ length: 80 }, (_, i) => [i / 15, .2 + .003 * i + ((i % 2) ? .0007 : -.0007), .3 + .002 * i, .2, .1]);
const smooth = prepareTracking(jitter).keys;
const rms = (xs: number[]) => Math.sqrt(xs.reduce((a, b) => a + b * b, 0) / xs.length);
const before = rms(jitter.slice(3, -3).map((k, n) => k[1] - (.2 + .003 * (n + 3))));
const after = rms(smooth.slice(3, -3).map((k, n) => k[1] - (.2 + .003 * (n + 3))));
check(after < before * .6, "tracking noise not reduced");
check(smooth.every((k, i) => Math.abs(k[1] - jitter[i][1]) * 1440 <= 1.250001), "tracking correction exceeded bound");
const linear = [0,.08,.19,.31,.49,.62,.8,1].map((t) => [t,.1 + .12*t,.2 + .06*t,.3,.2]);
for(let t=.01;t<.99;t+=.013) check(Math.abs(sampleTracking(linear,t)![0]-(.1+.12*t))<1e-8,"linear motion distorted");
const ordered = Array.from({length:70},(_,i)=>sampleTracking(jitter,i/30));
for(let i=69;i>=0;i--)check(JSON.stringify(ordered[i])===JSON.stringify(sampleTracking(jitter,i/30)),"seek changed track");
for(let i=3;i<50;i++){
  const t=jitter[i][0], e=1e-6;
  const a=sampleTracking(jitter,t-e)![0],b=sampleTracking(jitter,t)![0],c=sampleTracking(jitter,t+e)![0];
  check(Math.abs((b-a)/e-(c-b)/e)<.001,"track velocity discontinuity");
}
const obstacles:Obstacle[]=[{id:"avatar",kind:"circle",x:300,y:350,r:52},{id:"text",kind:"rect",x:345,y:280,w:150,h:42}];
const anchor={x:252,y:312},box={x:385,y:400,w:64,h:64},ports=rectanglePorts(box);
const route=planLeader(anchor,ports,obstacles);
check(route.clear&&route.points.length>2,"leader did not route around avatar");
for(let i=1;i<route.points.length;i++)for(const o of obstacles){
  check(!segmentHits(route.points[i-1],route.points[i],o),"routed segment intersects obstacle");
  for(let j=0;j<=100;j++){
    const u=j/100,p={x:route.points[i-1].x*(1-u)+route.points[i].x*u,y:route.points[i-1].y*(1-u)+route.points[i].y*u};
    check(o.kind==="circle"?Math.hypot(p.x-o.x,p.y-o.y)>=o.r-.1:!(p.x>o.x+.1&&p.x<o.x+o.w-.1&&p.y>o.y+.1&&p.y<o.y+o.h-.1),"independent route sampling hit obstacle");
  }
}
const shift=.37;
const moved=obstacles.map(o=>({...o,x:o.x+shift,y:o.y+shift})) as Obstacle[];
const translated=planLeader({x:anchor.x+shift,y:anchor.y+shift},ports.map(p=>({x:p.x+shift,y:p.y+shift})),moved,route);
check(JSON.stringify(route.nodes)===JSON.stringify(translated.nodes),"preferred route flipped under slow translation");
check(translated.points.every((p,i)=>Math.abs(p.x-route.points[i].x-shift)<1e-7&&Math.abs(p.y-route.points[i].y-shift)<1e-7),"route translation was not smooth");
check(!leaderPathJump(route,translated),"camera translation mistaken for route jump");
check(leaderPathJump(route,{...route,port:(route.port+1)%4}),"port change was not detected");
const hiddenAnchor = { x:300, y:350 };
const hiddenRoute = planLeader(hiddenAnchor, ports, obstacles);
check(hiddenRoute.clear && hiddenRoute.points[0].x === hiddenAnchor.x && hiddenRoute.points[0].y === hiddenAnchor.y, "occluded geographic anchor was moved");
for(let i=1;i<hiddenRoute.points.length;i++)for(const o of obstacles)
  if(!(i===1 && o.id==="avatar"))check(!segmentHits(hiddenRoute.points[i-1],hiddenRoute.points[i],o),"occluded-start route hit another foreground");
console.log(JSON.stringify({ok:fails.length===0,fails:[...new Set(fails)],trackingBeforeRmsPx:before*1440,trackingAfterRmsPx:after*1440,route:route.points}));
if(fails.length)throw new Error([...new Set(fails)].join(";"));
