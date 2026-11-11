"use strict";
// Image-only routing. Explicit profiles and existing projects remain pinned.
const fs = require("node:fs");
const path = require("node:path");

function fileLease(root) {
  return async (profile) => {
    if (!/^[A-Za-z0-9._-]+$/.test(profile)) throw new Error("Invalid profile");
    fs.mkdirSync(root, {recursive: true});
    const folder = path.join(root, profile + ".lock");
    try { fs.mkdirSync(folder); }
    catch (err) {
      if (err.code !== "EEXIST") throw err;
      let owner;
      try { owner = JSON.parse(fs.readFileSync(path.join(folder, "owner.json"), "utf8")); }
      catch { return null; } // Incomplete/unknown lock is never stolen.
      // Never steal a stale-looking lock: its owner may be changing between
      // inspection and deletion. Orphan locks require explicit host cleanup.
      return null;
    }
    const token = require("node:crypto").randomUUID();
    try { fs.writeFileSync(path.join(folder, "owner.json"), JSON.stringify({pid: process.pid, token})); }
    catch (err) { fs.rmSync(folder, {recursive:true, force:true}); throw err; }
    return async () => {
      try {
        const owner = JSON.parse(fs.readFileSync(path.join(folder, "owner.json"), "utf8"));
        if (owner.token === token) fs.rmSync(folder, {recursive: true});
      } catch { /* Never release a lock now owned by another job. */ }
    };
  };
}

function createImageDispatcher({listProfiles, preflight, generateSingle, acquire = async () => async () => {}, defaultProfile = () => "prod"}) {
  async function probe(profile, args) {
    try {
      const q = await preflight(profile, {...args, count: 1});
      const balance = Number(q.balance), budget = Number(q.budget_credits);
      if (!Number.isFinite(balance) || !Number.isFinite(budget) || budget < 0)
        return {profile, eligible:false, reason:"cost_unavailable"};
      return {profile, balance, budget_credits:budget, eligible:balance >= budget, quote:q.quote,
        reason:balance >= budget ? "eligible" : "insufficient_credits"};
    } catch (err) {
      return {profile, eligible:false, reason:"account_or_cost_unavailable", error:String(err.message).slice(0,300)};
    }
  }

  return async function dispatch(args) {
    if (!args.prompt || !String(args.prompt).trim()) throw new Error("prompt is required");
    const count = args.count === undefined ? 1 : args.count;
    if (!Number.isInteger(count) || count < 1 || count > 4) throw new Error("count must be 1..4");
    if (args.account_mode && !["auto","single"].includes(args.account_mode)) throw new Error("invalid account_mode");
    const explicit = typeof args.profile === "string" && args.profile.trim();
    if (args.project_id && !explicit)
      return {status:"profile_required", abort_generation:true, hint:"An existing project requires its owning profile; it cannot be moved between accounts."};
    const pinned = explicit || args.account_mode === "single";
    if (pinned) {
      const profile = explicit ? args.profile.trim() : defaultProfile();
      if (args.dry_run) {
        const q = await preflight(profile, {...args, count});
        return {status:"planned", routing:"pinned", profile, count, preflight:q, generation_started:false};
      }
      const release = await acquire(profile);
      if (!release) return {status:"account_busy", profile, abort_generation:true};
      try { return {...await generateSingle({...args, profile}), routing:"pinned"}; }
      finally { await release(); }
    }

    const profiles = [...new Set(await listProfiles())];
    const accounts = await Promise.all(profiles.map(p => probe(p, args)));
    const used = new Set(), images = [], jobs = [], plan = [];
    for (let index=0; index<count; index++) {
      const candidates = accounts.filter(a => a.eligible && a.balance >= a.budget_credits)
        .sort((a,b) => Number(used.has(a.profile))-Number(used.has(b.profile))
          || (a.balance-a.budget_credits)-(b.balance-b.budget_credits) || a.profile.localeCompare(b.profile));
      let selected, release;
      for (const candidate of candidates) {
        if (args.dry_run) { selected=candidate; break; }
        release = await acquire(candidate.profile);
        if (!release) { candidate.eligible=false; candidate.reason="account_busy"; continue; }
        const fresh = await probe(candidate.profile, args);
        Object.assign(candidate, fresh);
        if (fresh.eligible) { selected=candidate; break; }
        await release(); release=null;
      }
      if (!selected) {
        return {status:images.length ? "partial" : "insufficient_credits", routing:"image_pool",
          abort_generation:true, requested_count:count, count_returned:images.length, images, jobs, plan,
          profiles_considered:accounts, generation_started:jobs.length>0,
          hint:"No eligible idle account can fund the next whole image. No invites, registration or retries were performed."};
      }
      const profile=selected.profile;
      plan.push({index, profile, count:1, budget_credits:selected.budget_credits});
      used.add(profile);
      if (args.dry_run) { selected.balance -= selected.budget_credits; continue; }
      try {
        // Once submitted, errors stop the batch. Never spend again on another account.
        const result = await generateSingle({...args, profile, count:1});
        jobs.push({...result, profile, index});
        for (const item of result.images || []) images.push({...item, profile, project_id:result.project_id});
        if (result.status !== "completed" || !(result.images || []).length)
          return {status:images.length ? "partial" : "failed", routing:"image_pool",
            requested_count:count, count_returned:images.length, images, jobs, plan, generation_started:true};
        if (result.images.length !== 1)
          return {status:"partial", routing:"image_pool", requested_count:count, count_returned:images.length,
            images, jobs, plan, generation_started:true, hint:"Service returned an unexpected image count; stopped to avoid extra spending."};
        Object.assign(selected, await probe(profile, args));
      } catch (err) {
        return {status:images.length ? "partial" : "failed", routing:"image_pool",
          requested_count:count, count_returned:images.length, images, jobs, plan,
          generation_started:true, failed_profile:profile, error:String(err.message).slice(0,600),
          hint:"Submission may have consumed credits. No automatic retry on another account."};
      } finally { await release(); }
    }
    if (args.dry_run) return {status:"planned", routing:"image_pool", plan, requested_count:count, generation_started:false, profiles_considered:accounts};
    // Keep the established single-image fields for existing callers.
    const base = jobs.length===1 ? jobs[0] : {};
    return {...base, status:"completed", routing:"image_pool", requested_count:count,
      count_returned:images.length, images, jobs, plan, profiles_used:[...used],
      originals:images.every(i=>i.original), generation_started:true};
  };
}
module.exports = {createImageDispatcher, fileLease};
