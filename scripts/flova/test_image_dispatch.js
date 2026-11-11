"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs"), os = require("node:os"), path = require("node:path");
const {createImageDispatcher, fileLease} = require("./image_dispatch");

function fixture(balances, options={}) {
  const calls=[], probes=[];
  const dispatch=createImageDispatcher({
    listProfiles:async()=>Object.keys(balances),
    preflight:async(profile,args)=>{
      probes.push({profile,args});
      if (options.bad===profile) throw new Error("account unavailable");
      return {balance:balances[profile],budget_credits:12*(args.count||1)};
    },
    acquire:async(profile)=>options.busy===profile ? null : async()=>{},
    generateSingle:async(args)=>{
      calls.push(args);
      if (calls.length===options.failAt) throw new Error("submitted generation failed");
      balances[args.profile]-=12*(args.count||1);
      return {status:"completed",profile:args.profile,project_id:"project-"+args.profile,
        images:Array.from({length:args.count||1},(_,i)=>({path:args.profile+"-"+i+".png",original:true}))};
    },
    defaultProfile:()=>Object.keys(balances)[0],
  });
  return {dispatch,calls,probes};
}
test("a multi-image budget is split into independently funded images",async()=>{
  const f=fixture({a:20,b:20,c:20});
  const r=await f.dispatch({prompt:"room",count:3,reference_images:["ref.png"]});
  assert.equal(r.status,"completed");assert.equal(r.count_returned,3);
  assert.deepEqual(f.calls.map(a=>a.count),[1,1,1]);
  assert.equal(new Set(f.calls.map(a=>a.profile)).size,3);
  assert.ok(f.calls.every(a=>a.reference_images[0]==="ref.png"));
  assert.ok(r.images.every(i=>i.project_id==="project-"+i.profile));
});
test("pool credits cannot be combined to fund one indivisible image",async()=>{
  const f=fixture({a:7,b:7});const r=await f.dispatch({prompt:"room"});
  assert.equal(r.status,"insufficient_credits");assert.equal(f.calls.length,0);
});
test("explicit profile keeps the batch on that account",async()=>{
  const f=fixture({a:60,b:60});const r=await f.dispatch({prompt:"room",profile:"b",count:2});
  assert.equal(r.routing,"pinned");assert.equal(f.calls.length,1);
  assert.equal(f.calls[0].profile,"b");assert.equal(f.calls[0].count,2);
});
test("existing project without owner stops before account probing or generation",async()=>{
  const f=fixture({a:60});const r=await f.dispatch({prompt:"room",project_id:"old"});
  assert.equal(r.status,"profile_required");assert.equal(f.probes.length,0);assert.equal(f.calls.length,0);
});
test("existing project with owner is never moved",async()=>{
  const f=fixture({a:60,b:60});await f.dispatch({prompt:"room",project_id:"old",profile:"a"});
  assert.equal(f.calls[0].project_id,"old");assert.equal(f.calls[0].profile,"a");
});
test("a failed submitted image is never retried on another account",async()=>{
  const f=fixture({a:60,b:60},{failAt:1});const r=await f.dispatch({prompt:"room",count:2});
  assert.equal(r.status,"failed");assert.equal(r.generation_started,true);assert.equal(f.calls.length,1);
});
test("partial batch retains completed artifacts and stops at failure",async()=>{
  const f=fixture({a:60,b:60,c:60},{failAt:2});const r=await f.dispatch({prompt:"room",count:3});
  assert.equal(r.status,"partial");assert.equal(r.images.length,1);assert.equal(f.calls.length,2);
});
test("dry-run plans distinct accounts without generating or consuming balances",async()=>{
  const balances={a:20,b:20};const f=fixture(balances);
  const r=await f.dispatch({prompt:"room",count:2,dry_run:true});
  assert.equal(r.status,"planned");assert.equal(r.generation_started,false);
  assert.deepEqual(r.plan.map(p=>p.profile),["a","b"]);assert.equal(f.calls.length,0);
  assert.deepEqual(balances,{a:20,b:20});
});
test("accounts with unavailable prices/auth are excluded",async()=>{
  const f=fixture({a:20,b:20},{bad:"a"});const r=await f.dispatch({prompt:"room"});
  assert.equal(r.status,"completed");assert.equal(f.calls[0].profile,"b");
});
test("busy accounts are skipped before submission",async()=>{
  const f=fixture({a:20,b:20},{busy:"a"});await f.dispatch({prompt:"room"});
  assert.equal(f.calls[0].profile,"b");
});
test("cross-process lease excludes simultaneous use and releases cleanly",async()=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),"flova-lease-"));
  try {
    const acquire=fileLease(root);const release=await acquire("a");
    assert.equal(await acquire("a"),null);await release();
    const next=await acquire("a");assert.equal(typeof next,"function");await next();
  } finally {fs.rmSync(root,{recursive:true,force:true});}
});
test("count validation rejects empty or unlimited batches",async()=>{
  const f=fixture({a:60});
  await assert.rejects(()=>f.dispatch({prompt:"room",count:0}));
  await assert.rejects(()=>f.dispatch({prompt:"room",count:5}));
});
