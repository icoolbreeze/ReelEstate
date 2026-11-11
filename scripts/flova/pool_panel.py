# -*- coding: utf-8 -*-
"""本机 Flova MCP 号池面板。只监听 127.0.0.1。

    python scripts/flova/pool_panel.py

启动只显示本地账本/CLI/网页目录结构，不做任何探测（不开浏览器、不查积分登录态）：
上次手动刷新的快照从 pool-probe-cache.json 读回，一直显示到用户自己再点刷新。
全部探测和单卡「刷新」都要在页面上点；任何有 profile 的卡片始终显示「刷新」。
做片流程不调用这里。网页登录/录入/补关联走仓库内 login_web.py（随机指纹
Virtual Browser）；注册仍走现有脚本，浏览器后端仍是 Virtual Browser。
"""
from __future__ import annotations

import atexit
import json
import os
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import flova_invite as fi
import pool_status as ps

ROOT = Path(__file__).resolve().parents[2]
PORTREG = Path.home() / ".config" / "port-registry" / "portreg.py"
FL_DIR = ROOT / "scripts" / "flova"
LOGIN_WEB_PY = FL_DIR / "login_web.py"
POOL_NAME = "flova-pool"
POOL_PROJECT = "ReelEstate"

# 母号非强制刷新的节流窗口；页面上的「刷新母号」带 force:true，不受它影响。
ACTIVE_PROBE_TTL = 300.0

PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Flova 号池</title>
<style>
  :root { color-scheme: light; --ink:#1c1915; --paper:#f4f1ea; --line:#e4dfd4;
          --ok:#1e6b34; --okbg:#d9ead3; --bad:#9c2f23; --badbg:#f4d6d2;
          --warn:#7a5b12; --warnbg:#f6e7c1; --muted:#6b645c; --accent:#23497d; }
  * { box-sizing: border-box; }
  body { margin: 0; font: 15px/1.45 "Segoe UI", sans-serif; background: var(--paper); color: var(--ink); }
  header { padding: 14px 20px; background: var(--ink); color: var(--paper); }
  header .top { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between; }
  h1 { font-size: 19px; margin: 0; }
  header .sub { font-size: 12.5px; opacity: .75; margin-top: 2px; }
  main { padding: 16px 20px 40px; }
  .controls { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
  button, input { font: inherit; }
  button { background: var(--ink); color: #fff; border: 0; border-radius: 6px; padding: 6px 12px; cursor: pointer; }
  button:disabled { opacity: .4; cursor: default; }
  button.ghost { background: #fff; color: var(--ink); border: 1px solid var(--ink); }
  button.small { padding: 3px 9px; font-size: 13px; }
  button.icon { display: inline-flex; align-items: center; justify-content: center;
                width: 28px; height: 26px; padding: 0; background: #fff;
                color: var(--muted); border: 1px solid var(--line); border-radius: 6px; cursor: pointer; }
  button.icon:disabled { opacity: .4; cursor: default; }
  button.icon.danger:hover { background: var(--badbg); color: var(--bad); border-color: var(--bad); }
  button.danger { background: #fff; color: var(--bad); border: 1px solid var(--bad); }
  button.danger:hover { background: var(--badbg); }
  input[type=text] { padding: 5px 8px; border: 1px solid #b9b2a4; border-radius: 6px; background:#fff; }
  .hint { color: var(--muted); font-size: 13px; }
  .progress { font-size: 13px; color: var(--muted); min-height: 18px; margin: 8px 0 4px; }
  .errors { color: var(--bad); font-size: 13px; margin: 4px 0 10px; white-space: pre-wrap; }
  section { margin: 18px 0 0; }
  h2 { font-size: 15px; margin: 0 0 8px; display: flex; align-items: baseline; gap: 8px; }
  h2 .count { font-weight: 400; color: var(--muted); font-size: 13px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 10px; }
  .card { background: #fff; border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; }
  .card.mother { border: 2px solid var(--ink); grid-column: 1 / -1; background: #fbfaf6; }
  .card .name { font-weight: 600; font-size: 15px; }
  .card .email { font-size: 13px; word-break: break-all; }
  .card .meta { font-size: 12.5px; color: var(--muted); margin-top: 2px; }
  .pills { margin: 7px 0; display: flex; flex-wrap: wrap; gap: 5px; }
  .pill { display: inline-block; border-radius: 99px; padding: 1px 9px; font-size: 12px; background: #ece7dc; }
  .pill.ok { background: var(--okbg); color: var(--ok); }
  .pill.bad { background: var(--badbg); color: var(--bad); }
  .pill.warn { background: var(--warnbg); color: var(--warn); }
  .pill.info { background: #dce6f5; color: var(--accent); }
  .credits { font-size: 22px; font-weight: 700; margin: 2px 0; }
  .credits.small { font-size: 16px; }
  .credsrc { font-size: 11px; font-weight: 400; color: var(--muted); }
  .invite { font-size: 13px; margin: 4px 0; }
  .actions { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
  .detail { margin-top: 12px; }
  .detail summary { cursor: pointer; font-size: 14px; color: var(--muted); user-select: none; }
  .detail[open] summary { color: var(--ink); }
  .dead { opacity: .85; background: #faf8f3; }
  .errline { font-size: 12px; color: var(--bad); margin-top: 5px; word-break: break-all; }
  pre.log { white-space: pre-wrap; background: var(--ink); color: var(--paper); padding: 12px;
            min-height: 90px; max-height: 260px; overflow: auto; border-radius: 8px; font-size: 12.5px; }
  .empty { color: var(--muted); font-size: 13px; }
</style>
</head>
<body>
<header>
  <div class="top">
    <div>
      <h1>Flova 号池 <span style="font-size:12px;font-weight:normal;opacity:.85;background:rgba(255,255,255,.2);padding:2px 8px;border-radius:4px;margin-left:6px">非可用已折叠</span></h1>
      <div class="sub">只读本机账本、CLI 登录、网页登录与积分；余额和邀请码不落盘。</div>
    </div>
    <div class="controls">
      <button id="refresh-active" type="button">刷新母号</button>
      <button id="refresh-all" class="ghost" type="button">全部刷新</button>
      <button id="onboard" class="ghost" type="button">录入已有账号</button>
      <button id="direct" class="ghost" type="button">独立注册（VB）</button>
    </div>
  </div>
</header>
<main>
  <div class="progress" id="progress"></div>
  <div class="errors" id="errors"></div>

  <section><h2>当前母号</h2><div class="grid" id="mother"></div></section>
  <section>
    <h2>号池账号 <span class="count" id="pool-count"></span></h2>
    <div class="grid" id="pool"></div>
    <details class="detail" id="pool-dead-details" style="margin-top:10px">
      <summary id="pool-dead-summary">号池不可用 / 积分耗尽（0）</summary>
      <div class="grid" style="margin-top:8px" id="pool-dead"></div>
    </details>
  </section>
  <details class="detail" id="addable-details">
    <summary id="addable-summary">可加入号池（0）</summary>
    <div class="controls" style="margin:8px 0">
      <button id="add-all" class="ghost small" type="button">全部加入号池</button>
    </div>
    <div class="grid" id="addable"></div>
  </details>
  <details class="detail" id="unknown-details">
    <summary id="unknown-summary">未检测账号（0）</summary>
    <div class="grid" style="margin-top:8px" id="unknown"></div>
  </details>
  <details class="detail" id="dead-details">
    <summary id="dead-summary">无效 / 休眠账号（0）</summary>
    <div class="grid" style="margin-top:8px" id="dead"></div>
  </details>

  <h2 style="margin-top:22px">任务日志</h2>
  <pre class="log" id="log">还没有任务。</pre>
</main>
<script>
const TRASH_SVG = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
  + 'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
  + '<polyline points="3 6 5 6 21 6"></polyline>'
  + '<path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>'
  + '<path d="M10 11v6M14 11v6"></path>'
  + '<path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"></path></svg>';
function esc(value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) {
    return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch];
  });
}
function pill(text, kind) {
  return '<span class="pill ' + (kind || "") + '">' + esc(text) + "</span>";
}
function rowKey(row) {
  return row.profile ? "p:" + row.profile : "e:" + (row.email || "");
}
let latest = { rows: [], mode: null, progress: {}, job: { running: false, log: [] } };

function statusPills(row) {
  if (!row.probed) return pill("未检测", "info");
  return [
    pill(row.cli_logged_in ? "CLI 已登录" : "CLI 未登录", row.cli_logged_in ? "ok" : "bad"),
    pill(row.web_logged_in ? "网页已登录" : "网页未登录", row.web_logged_in ? "ok" : "bad"),
    row.in_pool ? pill("在号池", "ok") : pill("未入账", "warn")
  ].join("");
}

function inviteBlock(row) {
  if (!row.probed) return '<div class="invite muted">检测后显示积分和邀请名额</div>';
  if (!row.web_logged_in) return '<div class="invite muted">网页未登录，没有邀请状态</div>';
  const reward = row.credit_reward_num == null ? "未知" : row.credit_reward_num;
  const badges = [
    row.invite_ready ? pill("可邀请", "ok") : "",
    row.successor_eligible ? pill("可接班", "ok") : ""
  ].join("");
  return '<div class="invite">剩余邀请 '
    + esc(row.remaining_invitees == null ? "未知" : row.remaining_invitees) + " / "
    + esc(row.max_invitees == null ? "未知" : row.max_invitees)
    + "，单次 " + esc(reward)
    + (row.invite_reward_disabled ? pill("已停奖", "bad") : "") + "</div>"
    + '<div class="pills">' + badges + "</div>";
}

function actionButtons(row, busy) {
  const profile = esc(row.profile);
  let html = "";
  // 自动邀请仍要求有剩余名额且资格齐全；手动注册是人工流程，
  // 网页已登录、未退休的号（含母号和不满足自动资格的子号）都能点。
  const canAuto = row.probed && row.invite_ready;
  const canManual = row.probed && row.web_logged_in && row.role !== "retired_mother";
  // 每次点击固定邀请 1 个（不再提供数量输入框）；要多个就多点几次。
  if (canAuto) {
    html += '<button class="small" type="button" data-act="invite_batch" data-profile="' + profile + '"'
      + (busy ? " disabled" : "") + ">自动邀请</button> ";
  }
  if (canManual) {
    const why = canAuto ? "" : ("该号不满足自动邀请条件（"
      + [(row.invite_reward_disabled ? "已停奖" : ""),
          ((row.successor_blockers || []).includes("account_age_7d") ? "账号未满 7 天" : ""),
          ((row.successor_blockers || []).includes("no_export") ? "无导出记录" : ""),
          (!row.remaining_invitees ? "无剩余名额" : "")].filter(Boolean).join("、")
      + "），仍可人工操作，但可能没有奖励");
    html += '<button class="small ghost" type="button" data-act="invite_manual" data-profile="' + profile + '"'
      + ' title="' + esc(why || "人工辅助注册一个被邀请号") + '"'
      + (busy ? " disabled" : "") + ">手动注册</button> ";
    // 手动邀请：脚本只开邀请链接，人自己用 Google/邮箱注册；成功后与手动注册一样自动入账。
    html += '<button class="small ghost" type="button" data-act="invite_hand" data-profile="' + profile + '"'
      + ' title="' + esc(why || "打开邀请链接，由人自己完成注册；成功的新号自动入账") + '"'
      + (busy ? " disabled" : "") + ">手动邀请</button>";
  }
  if (row.addable) {
    html += '<button class="small" type="button" data-act="add" data-profile="' + profile + '"'
      + (busy ? " disabled" : "") + ">加入号池</button>";
  }
  if (row.in_pool && !row.active_mother && row.role !== "mother" && row.role !== "retired_mother"
      && (row.profile || row.email)) {
    html += '<button class="icon danger" type="button" data-act="remove" data-profile="' + profile + '"'
      + ' data-email="' + esc(row.email || "") + '" title="移出号池（只删账本记录，保留本机登录）"'
      + (busy ? " disabled" : "") + ' aria-label="移出号池">' + TRASH_SVG + "</button>";
  }
  if (row.profile && (!row.probed || !row.web_logged_in)) {
    html += '<button class="small ghost" type="button" data-act="login_web" data-profile="' + profile + '"'
      + (busy ? " disabled" : "") + ">网页登录</button>";
  } else if (row.profile && row.web_logged_in) {
    html += '<button class="small ghost" type="button" data-act="open_browser" data-profile="' + profile + '"'
      + ' title="使用 Virtual Browser 打开已登录该账号的工作台后台">进入后台</button>';
  }
  // CLI 掉线但网页仍在线：用已采纳的网页会话换 token、补建 CLI profile。
  if (row.profile && row.probed && row.web_logged_in && !row.cli_logged_in) {
    html += '<button class="small ghost" type="button" data-act="repair_cli" data-profile="' + profile + '"'
      + (busy ? " disabled" : "") + ' title="用已保存的网页会话补建 CLI 登录">补 CLI</button>';
  }
  // 单卡刷新始终显示：只探测这一张卡（CLI/网页/积分/剩余邀请），
  // 不写账本、不邀请、不清号、不换母号；忙碌锁仍由后端统一拦。
  if (row.profile) {
    html += '<button class="small ghost" type="button" data-act="probe_one" data-profile="' + profile + '"'
      + (busy ? " disabled" : "") + ">刷新</button>";
  }
  if (!row.profile) {
    if (row.in_pool && row.email) {
      html += '<button class="small ghost" type="button" data-act="relink" data-email="'
        + esc(row.email) + '"' + (busy ? " disabled" : "") + ">补登录关联 profile</button>";
    } else {
      html += '<span class="hint">账本缺 profile 引用，无法检测或登录</span>';
    }
  }
  return html;
}

function card(row, busy, hero) {
  const blockers = (row.successor_blockers || []).join("、");
  const err = [row.cli_error, row.web_error].filter(Boolean).join(" ");
  return '<div class="card' + (hero ? " mother" : "") + (row._dead ? " dead" : "") + '">'
    + '<div class="name">' + esc(row.profile || "(无 profile)")
    + (row.active_mother ? pill("当前母号", "info") : "") + "</div>"
    + '<div class="email">' + esc(row.email || "读不到邮箱") + "</div>"
    + '<div class="meta">' + esc(row.role || "未入账") + " · " + esc(row.state || "-")
    + (!hero && blockers ? " · 接班受阻：" + esc(blockers) : "") + "</div>"
    + '<div class="pills">' + statusPills(row) + "</div>"
    + (row.probed && row.credits != null
        ? '<div class="credits' + (hero ? "" : " small") + '">' + esc(row.credits) + " 积分"
          + (row.credits_source === "web" ? ' <span class="credsrc">网页会话</span>' : "") + "</div>"
        : (row.probed && row.web_logged_in ? '<div class="credits small muted">读不到积分</div>' : ""))
    + inviteBlock(row)
    + '<div class="actions">' + actionButtons(row, busy) + "</div>"
    + (err ? '<div class="errline">' + esc(err) + "</div>" : "")
    + "</div>";
}

function classify(rows) {
  const groups = { mother: [], pool: [], poolDead: [], addable: [], unknown: [], dead: [] };
  rows.forEach(function (row) {
    if (row.active_mother || row.role === "mother" || row.role === "retired_mother") {
      groups.mother.push(row);
      return;
    }
    if (row.in_pool) {
      // 在号池中：已检测且（掉线或积分已耗尽/<=0）视为不可用，折叠收起。
      const notUsable = row.probed && (!row.cli_logged_in || !row.web_logged_in || (row.credits != null && row.credits <= 0));
      if (notUsable) {
        row._dead = true;
        groups.poolDead.push(row);
      } else {
        groups.pool.push(row);
      }
      return;
    }
    if (!row.probed) { groups.unknown.push(row); return; }
    // 已检测但读不到邮箱、CLI 和网页都掉登录：休眠/无效，折叠。
    row._dead = !row.email && !row.cli_logged_in && !row.web_logged_in;
    if (row._dead) groups.dead.push(row);
    else if (row.addable) groups.addable.push(row);
    else groups.unknown.push(row);
  });
  return groups;
}

function render(data) {
  latest = data;
  const busy = data.mode != null;
  document.getElementById("refresh-active").disabled = busy;
  document.getElementById("refresh-all").disabled = busy;
  document.getElementById("onboard").disabled = busy;
  document.getElementById("direct").disabled = busy;
  document.getElementById("add-all").disabled =
    busy || !(data.rows || []).some(function (row) { return row.addable; });

  const progress = data.progress || {};
  let text = data.refreshed_at ? ("更新于 " + data.refreshed_at) : "";
  if (data.mode === "refresh") {
    if (progress.total) {
      text = "正在检测 " + (progress.done || 0) + "/" + progress.total
        + (progress.current ? " · " + progress.current : "");
    } else {
      text = "正在准备检测…";
    }
  } else if (data.mode === "job") {
    text = "任务进行中：" + ((data.job || {}).action || "");
  }
  document.getElementById("progress").textContent = text;
  document.getElementById("errors").textContent = (data.errors || []).join("\\n");

  const groups = classify(data.rows || []);
  document.getElementById("mother").innerHTML =
    groups.mother.map(function (r) { return card(r, busy, true); }).join("")
    || '<span class="empty">账本里没有当前母号（registry.json 的 active_mother_profile）</span>';
  document.getElementById("pool").innerHTML =
    groups.pool.map(function (r) { return card(r, busy, false); }).join("")
    || '<span class="empty">暂无可用号池账号</span>';
  document.getElementById("pool-dead").innerHTML =
    groups.poolDead.map(function (r) { return card(r, busy, false); }).join("");
  document.getElementById("pool-dead-details").style.display = groups.poolDead.length ? "" : "none";
  document.getElementById("pool-dead-summary").textContent = "号池内不可用 / 积分耗尽（" + groups.poolDead.length + "）";
  document.getElementById("addable").innerHTML =
    groups.addable.map(function (r) { return card(r, busy, false); }).join("")
    || '<span class="empty">没有检测到可入账的账号</span>';
  document.getElementById("addable-details").style.display = groups.addable.length ? "" : "none";
  document.getElementById("addable-summary").textContent = "可加入号池（" + groups.addable.length + "）";
  document.getElementById("unknown").innerHTML =
    groups.unknown.map(function (r) { return card(r, busy, false); }).join("")
    || '<span class="empty">没有待检测账号</span>';
  document.getElementById("unknown-details").style.display = groups.unknown.length ? "" : "none";
  document.getElementById("unknown-summary").textContent = "未检测账号（" + groups.unknown.length + "）";
  document.getElementById("dead").innerHTML =
    groups.dead.map(function (r) { return card(r, busy, false); }).join("")
    || '<span class="empty">没有休眠账号</span>';
  document.getElementById("dead-details").style.display = groups.dead.length ? "" : "none";
  document.getElementById("dead-summary").textContent = "无效 / 休眠账号（" + groups.dead.length + "）";

  document.getElementById("pool-count").textContent =
    (groups.pool.length + groups.poolDead.length)
      ? "(" + groups.pool.length + " 可用" + (groups.poolDead.length ? " / " + groups.poolDead.length + " 待补" : "") + ")" : "";

  const job = data.job || {};
  const log = (job.log || []).join("\\n");
  document.getElementById("log").textContent = log || (job.running ? "任务已开始" : "还没有任务。");
}

async function tick() {
  const response = await fetch("/api/pool");
  render(await response.json());
}

async function post(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload || {})
  });
  const data = await response.json();
  if (!response.ok) alert(data.message || "请求失败");
  await tick();
  return data;
}

document.getElementById("refresh-active").onclick = function () {
  post("/api/pool/refresh", { scope: "active", force: true });
};
document.getElementById("refresh-all").onclick = function () {
  post("/api/pool/refresh", { scope: "all" });
};
document.getElementById("add-all").onclick = function () {
  if (confirm("把当前能读到邮箱的未入账账号全部写入号池？")) post("/api/pool/add", { all: true });
};
document.getElementById("direct").onclick = function () {
  if (confirm("用 Virtual Browser 直接注册一个号，不使用邀请码？")) {
    post("/api/jobs", { action: "register_direct" });
  }
};
document.getElementById("onboard").onclick = function () {
  if (confirm("将自动命名并打开浏览器登录，成功后入账。")) post("/api/pool/onboard", {});
};
document.body.addEventListener("click", function (event) {
  const button = event.target.closest("button");
  if (!button) return;
  const profile = button.getAttribute("data-profile");
  const action = button.getAttribute("data-act");
  if (!action) return;
  if (action === "add") { post("/api/pool/add", { profile: profile }); return; }
  if (action === "remove") {
    const email = button.getAttribute("data-email") || "";
    const who = profile || email;
    if (!confirm("把 " + who + " 从号池账本移除？\\n\\n只删除账本跟踪记录，本机 CLI 登录和网页会话保留，以后可以重新加入。")) return;
    post("/api/pool/remove", { profile: profile || null, email: email || null });
    return;
  }
  if (action === "relink") {
    const email = button.getAttribute("data-email") || "";
    const name = prompt("给 " + email + " 指定一个本机 profile 名（如 kid11）。\\n"
      + "确定后打开浏览器，请登录这个账号；登录邮箱必须与账本一致才会写入引用。");
    if (name == null) return;
    const p = name.trim();
    if (!/^[A-Za-z0-9._-]+$/.test(p)) { alert("profile 名不合法"); return; }
    post("/api/pool/relink", { profile: p, email: email });
    return;
  }
  if (action === "probe_one") { post("/api/pool/refresh", { scope: "one", profile: profile, force: true }); return; }
  if (action === "login_web") { post("/api/jobs", { action: "login_web", profile: profile }); return; }
  if (action === "open_browser") { post("/api/pool/open_browser", { profile: profile }); return; }
  if (action === "repair_cli") {
    if (!confirm("用 " + profile + " 已保存的网页会话补建 CLI 登录？只读取已采纳的 cookie，不打开浏览器。")) return;
    post("/api/jobs", { action: "repair_cli", profile: profile, n: 1 });
    return;
  }
  const count = 1;
  const labels = { invite_batch: "自动邀请", invite_manual: "手动注册", invite_hand: "手动邀请" };
  const label = labels[action] || action;
  if (!confirm(label + " 1 个，邀请人是 " + profile + "？")) return;
  post("/api/jobs", { action: action, profile: profile, n: count });
});
setInterval(tick, 2000);
tick();
</script>
</body>
</html>
"""


class State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.rows: list[dict[str, Any]] = []
        self.errors: list[str] = []
        self.progress = {"done": 0, "total": 0, "current": ""}
        self.refreshed_at: str | None = None
        self.mode: str | None = None
        # key -> (probed_at_epoch, probed row)，母号节流用。
        self.probe_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self.last_active_probe = 0.0
        self.job = {
            "action": None,
            "profile": None,
            "n": None,
            "running": False,
            "exit_code": None,
            "log": [],
        }


STATE = State()
BOUND = False


def row_key(row: dict[str, Any]) -> str:
    profile = str(row.get("profile") or "")
    if profile:
        return f"p:{profile}"
    return f"e:{row.get('email') or ''}"


# 这些是「账本/本地结构」事实，只由 list_structural() 当下决定，绝不能被旧探测
# 缓存覆盖——否则会出现「已加入号池、补完 CLI 却又退回可加入号池」的自强化脏缓存。
_STRUCTURAL_KEYS = ("profile", "in_pool", "active_mother", "role", "state", "sources")


def _overlay_probe(base: dict[str, Any], probed: dict[str, Any]) -> dict[str, Any]:
    # 动态探测值打底（cli/web 登录态、积分、邀请名额……），结构事实一律以最新 base 为准。
    merged = dict(probed)
    for key in _STRUCTURAL_KEYS:
        merged[key] = base.get(key)
    # 邮箱/user_id：账本里有就以账本为准，否则沿用探测读到的。
    if base.get("email"):
        merged["email"] = base.get("email")
    if base.get("user_id"):
        merged["user_id"] = base.get("user_id")
    # addable 必须由权威 in_pool 重算，不能信可能过期的缓存值。
    merged["addable"] = (not base.get("in_pool")) and bool(merged.get("email"))
    merged["add_block_reason"] = (
        None if merged["addable"]
        else ("读不到邮箱" if not merged.get("email") else None)
    )
    merged["probed"] = True
    return merged


def structural_rows() -> tuple[list[dict[str, Any]], list[str]]:
    """本地结构行：账本 + CLI profile + 网页目录。打上探测缓存覆盖，不访问网络。"""
    bases, errors = ps.list_structural()
    if not STATE.probe_cache:
        # 进程刚启动：把磁盘上的探测快照装回内存。快照不过期，启动也不重探，
        # 卡片一直显示上次手动刷新的结果，直到用户再点刷新。
        STATE.probe_cache.update(ps.load_probe_cache())
    out: list[dict[str, Any]] = []
    for base in bases:
        cached = STATE.probe_cache.get(row_key(base))
        if cached:
            out.append(_overlay_probe(base, cached[1]))
        else:
            row = dict(base)
            row["probed"] = False
            out.append(row)
    return out, errors


def build_job(action: str, profile: str | None, n: int, *,
              expect_email: str | None = None) -> list[str]:
    """拼子进程参数。独立注册不带 profile，也不带 refCode。

    网页登录/录入/补关联一律走仓库内 login_web.py（随机指纹 Virtual Browser），
    不再调用仓库外 login-web.js。relink 必须带账本邮箱 --expect-email。
    """
    python = sys.executable
    folder = FL_DIR
    if action == "register_direct":
        return [python, str(folder / "register_direct.py")]
    if not profile or not ps.profile_name_ok(profile):
        raise ValueError("invalid profile")
    if action == "invite_batch":
        return [python, str(folder / "invite_batch.py"), "--profile", profile, str(n)]
    if action == "invite_manual":
        return [python, str(folder / "invite_manual.py"), "--profile", profile, str(n)]
    if action == "invite_hand":
        return [python, str(folder / "invite_hand.py"), "--profile", profile, str(n)]
    if action == "repair_cli":
        return [python, str(folder / "repair_cli.py"), "--profile", profile]
    if action in ("login_web", "onboard"):
        return [python, str(LOGIN_WEB_PY), "--profile", profile]
    if action == "relink":
        expected = str(expect_email or "").strip().lower()
        if not expected or "@" not in expected:
            raise ValueError("relink requires expect_email")
        return [python, str(LOGIN_WEB_PY), "--profile", profile,
                "--expect-email", expected]
    raise ValueError("unknown action")


def invite_busy() -> bool:
    try:
        with fi._Lock(fi.LOCK_PATH):
            return False
    except RuntimeError:
        return True


def _count(value: Any, default: int = 1) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("人数必须是整数")
    if value < 1:
        raise ValueError("人数至少是 1")
    return value


def _snapshot() -> dict[str, Any]:
    with STATE.lock:
        return {
            "rows": STATE.rows,
            "errors": list(STATE.errors),
            "progress": dict(STATE.progress),
            "refreshed_at": STATE.refreshed_at,
            "mode": STATE.mode,
            "job": {
                "action": STATE.job["action"],
                "profile": STATE.job["profile"],
                "n": STATE.job["n"],
                "running": STATE.job["running"],
                "exit_code": STATE.job["exit_code"],
                "log": list(STATE.job["log"]),
            },
        }


def _busy_message() -> str | None:
    with STATE.lock:
        if STATE.mode == "refresh":
            return "正在检测，请等这一轮结束"
        if STATE.mode == "job":
            return "已有任务在跑"
    return None


def start_refresh(payload: dict[str, Any] | None = None) -> dict[str, Any] | tuple[int, dict[str, Any]]:
    payload = payload or {}
    scope = str(payload.get("scope") or "active")
    if scope not in ("active", "all", "one"):
        return 400, {"ok": False, "message": "不认识的刷新范围"}
    force = bool(payload.get("force"))
    one_profile = str(payload.get("profile") or "").strip()
    if scope == "one" and not ps.profile_name_ok(one_profile):
        return 400, {"ok": False, "message": "缺少合法 profile"}

    message = _busy_message()
    if message:
        return 409, {"ok": False, "message": message}

    now = time.time()
    with STATE.lock:
        registry = ps.load_pool_registry()
        active = str(registry.get("active_mother_profile") or ps.default_mother_profile())
        if scope == "active" and not force and now - STATE.last_active_probe < ACTIVE_PROBE_TTL:
            return {"ok": True, "message": "母号刚检测过", "skipped": True}
        STATE.mode = "refresh"
        STATE.errors = []
        bases, errors = structural_rows()
        STATE.rows = bases
        STATE.errors = errors

    def _run() -> None:
        try:
            if scope == "active":
                targets = [b for b in bases if str(b.get("profile")) == active]
                if not targets:
                    # 账本母号在本地没有任何痕迹：仍按活跃名构一行，至少把错误显示出来。
                    targets = [{
                        "profile": active, "email": None, "role": "mother", "state": None,
                        "in_pool": True, "active_mother": True, "sources": [],
                    }]
            elif scope == "one":
                targets = [b for b in bases if str(b.get("profile")) == one_profile]
                if not targets:
                    targets = [{
                        "profile": one_profile, "email": None, "role": None, "state": None,
                        "in_pool": False, "active_mother": one_profile == active,
                        "sources": [],
                    }]
            else:
                targets = bases
            total = len(targets)
            probed_by_key: dict[str, dict[str, Any]] = {}
            for index, base in enumerate(targets, start=1):
                with STATE.lock:
                    STATE.progress = {
                        "done": index - 1, "total": total,
                        "current": str(base.get("profile") or base.get("email") or ""),
                    }
                row = ps.probe_row(base)
                row["probed"] = True
                # 自动补全 CLI：若账号网页在线但 CLI 掉线或缺失，自动调用 repair 补建 CLI
                if row.get("web_logged_in") and not row.get("cli_logged_in") and row.get("profile"):
                    try:
                        import repair_cli
                        rep_res = repair_cli.repair(str(row["profile"]))
                        if rep_res.get("ok"):
                            bases_updated, _ = structural_rows()
                            new_base = next((b for b in bases_updated if str(b.get("profile")) == str(row["profile"])), base)
                            row = ps.probe_row(new_base)
                            row["probed"] = True
                    except Exception:
                        pass
                probed_by_key[row_key(base)] = row
                stamp = time.time()
                with STATE.lock:
                    STATE.probe_cache[row_key(base)] = (stamp, row)
                    disk_snapshot = dict(STATE.probe_cache)
                    fresh: list[dict[str, Any]] = []
                    for current in STATE.rows:
                        hit = probed_by_key.get(row_key(current))
                        fresh.append(hit if hit is not None else current)
                    # 单测一个尚未出现在结构里的 profile（新网页目录）时补进行尾。
                    present = {row_key(r) for r in fresh}
                    if row_key(base) not in present:
                        fresh.append(row)
                    STATE.rows = fresh
                    STATE.progress["done"] = index
                    if scope == "active":
                        STATE.last_active_probe = stamp
                try:
                    ps.save_probe_cache(disk_snapshot)
                except OSError:
                    pass
            with STATE.lock:
                STATE.refreshed_at = ps._now()
                STATE.progress = {"done": total, "total": total, "current": ""}
        except Exception as exc:
            with STATE.lock:
                STATE.errors.append(ps.redact(str(exc)[:200]))
        finally:
            with STATE.lock:
                if STATE.mode == "refresh":
                    STATE.mode = None

    threading.Thread(target=_run, name="flova-pool-refresh", daemon=True).start()
    return {"ok": True, "message": "开始检测"}


def _row_by_profile(profile: str) -> dict[str, Any] | None:
    with STATE.lock:
        for row in STATE.rows:
            if row.get("profile") == profile:
                return dict(row)
    return None


def _remember_add(profile: str, result: dict[str, Any]) -> None:
    if not result.get("ok"):
        return
    with STATE.lock:
        for row in STATE.rows:
            if row.get("profile") != profile:
                continue
            row["in_pool"] = True
            row["addable"] = False
            row["add_block_reason"] = None
            if result.get("role"):
                row["role"] = result["role"]
            if result.get("state"):
                row["state"] = result["state"]
            if result.get("email"):
                row["email"] = result["email"]


def add_profiles(payload: dict[str, Any]) -> dict[str, Any] | tuple[int, dict[str, Any]]:
    message = _busy_message()
    if message:
        return 409, {"ok": False, "message": message}
    if payload.get("all") is True:
        with STATE.lock:
            targets = [dict(row) for row in STATE.rows if row.get("addable")]
    else:
        profile = str(payload.get("profile") or "")
        row = _row_by_profile(profile)
        if row is None:
            return 404, {"ok": False, "message": "没有这个 profile，先检测"}
        if not row.get("addable"):
            return 409, {"ok": False, "message": row.get("add_block_reason") or "这个号已在号池或读不到邮箱"}
        targets = [row]
    results = []
    for row in targets:
        result = ps.add_to_pool(
            str(row.get("profile") or ""),
            email=row.get("email"),
            user_id=row.get("user_id"),
            cli_logged_in=bool(row.get("cli_logged_in")),
            cli_exists="cli" in (row.get("sources") or []) or bool(row.get("cli_logged_in")),
            web_dir_exists="web_dir" in (row.get("sources") or []),
        )
        results.append(result)
        _remember_add(str(row.get("profile") or ""), result)
    return {"ok": True, "results": results}


def remove_profile(payload: dict[str, Any]) -> dict[str, Any] | tuple[int, dict[str, Any]]:
    message = _busy_message()
    if message:
        return 409, {"ok": False, "message": message}
    raw_profile = str(payload.get("profile") or "").strip()
    profile = raw_profile if ps.profile_name_ok(raw_profile) else ""
    email = str(payload.get("email") or "").strip() or None
    if not profile and not email:
        return 400, {"ok": False, "message": "缺少要移除的 profile 或邮箱"}
    result = ps.remove_from_pool(profile=profile or None, email=email)
    if not result.get("ok"):
        return 409, result
    # 账本已变：丢掉该号的探测缓存（内存和磁盘），按本地结构重排行。
    with STATE.lock:
        if profile:
            STATE.probe_cache.pop(f"p:{profile}", None)
        disk_snapshot = dict(STATE.probe_cache)
        bases, errors = structural_rows()
        STATE.rows = bases
        STATE.errors = errors
    try:
        ps.save_probe_cache(disk_snapshot)
    except OSError:
        pass
    return result


def _start_web_login_job(
    *,
    action: str,
    profile: str,
    intro: str,
    finalize: "Callable[[], dict[str, Any] | None]",
    expect_email: str | None = None,
) -> dict[str, Any] | tuple[int, dict[str, Any]]:
    """打开 login_web.py（随机指纹 VB），成功后在后台线程跑 finalize（探测/入账/补登）。"""
    try:
        command = build_job(action, profile, 1, expect_email=expect_email)
    except ValueError:
        return 400, {"ok": False, "message": "不认识的任务或 profile"}
    with STATE.lock:
        STATE.mode = "job"
        STATE.job = {
            "action": action,
            "profile": profile,
            "n": None,
            "running": True,
            "exit_code": None,
            "log": ["$ " + " ".join(command), intro],
        }

    def _run() -> None:
        code = 1
        result: dict[str, Any] | None = None
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            proc = subprocess.Popen(
                command,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                clean = ps.redact(line.rstrip("\r\n"))[:500]
                with STATE.lock:
                    STATE.job["log"].append(clean)
                    if len(STATE.job["log"]) > 200:
                        del STATE.job["log"][:-200]
            code = proc.wait()
            if code == 0:
                result = finalize() or None
        except Exception as exc:
            code = 1
            with STATE.lock:
                STATE.job["log"].append(ps.redact(str(exc)[:200]))
        with STATE.lock:
            STATE.job["running"] = False
            STATE.job["exit_code"] = code
            if result is not None:
                STATE.job["log"].append("结果：" + ps.redact(json.dumps(
                    result, ensure_ascii=False))[:300])
            STATE.job["log"].append(f"exit {code}")
            if STATE.mode == "job":
                STATE.mode = None

    threading.Thread(target=_run, name=f"flova-pool-{action}", daemon=True).start()
    return {"ok": True, "message": "浏览器登录已启动"}


def _reload_rows_with_probe(profile: str) -> dict[str, Any]:
    """登录成功后重扫结构、探测该 profile，写缓存，返回探测行。"""
    bases, errors = structural_rows()
    with STATE.lock:
        STATE.rows = bases
        STATE.errors = errors
    base = next((b for b in bases if str(b.get("profile")) == profile), None)
    if base is None:
        raise RuntimeError("登录结束但没有发现该 profile 的网页目录")
    row = ps.probe_row(base)
    row["probed"] = True
    stamp = time.time()
    with STATE.lock:
        STATE.probe_cache[f"p:{profile}"] = (stamp, row)
        disk_snapshot = dict(STATE.probe_cache)
        STATE.rows = [row if row_key(r) == f"p:{profile}" else r for r in STATE.rows]
    try:
        ps.save_probe_cache(disk_snapshot)
    except OSError:
        pass
    return row


def start_onboard(payload: dict[str, Any]) -> dict[str, Any] | tuple[int, dict[str, Any]]:
    """引导录入一个本机已有账号：自动取下一个空的 kidN，打开网页登录，成功后探测并自动入账。

    旧页面可能仍在请求体里带 profile 名，但一律忽略，名字由服务端分配。
    """
    message = _busy_message()
    if message:
        return 409, {"ok": False, "message": message}
    if not LOGIN_WEB_PY.is_file():
        return 400, {"ok": False, "message": "找不到 login_web.py"}
    taken = ps.collect_onboard_taken(
        ps.load_pool_registry(), fi.known_profiles(), ps.web_profile_dirs())
    profile = ps.next_onboard_profile(taken)

    def _finalize() -> dict[str, Any]:
        profile = str(STATE.job.get("profile") or "")
        try:
            import repair_cli
            repair_cli.repair(profile)
        except Exception:
            pass
        row = _reload_rows_with_probe(profile)
        if not row.get("email"):
            raise RuntimeError("登录后仍读不到邮箱，没有入账；可稍后点该卡片的检测再试")
        result = ps.add_to_pool(
            profile,
            email=row.get("email"),
            user_id=row.get("user_id"),
            cli_logged_in=bool(row.get("cli_logged_in")),
            cli_exists="cli" in (row.get("sources") or []) or bool(row.get("cli_logged_in")),
            web_dir_exists="web_dir" in (row.get("sources") or []),
        )
        _remember_add(profile, result)
        bases, errors = structural_rows()
        with STATE.lock:
            STATE.rows = bases
            STATE.errors = errors
        return result

    return _start_web_login_job(
        action="onboard",
        profile=profile,
        intro=(f"本次 profile 是 {profile}。浏览器将打开，请登录要录入的已有账号，"
               "登录成功后自动检测并入账。"),
        finalize=_finalize,
    )


def start_relink(payload: dict[str, Any]) -> dict[str, Any] | tuple[int, dict[str, Any]]:
    """给账本里缺 profile 引用的行补登：打开网页登录，登录邮箱必须与账本一致才关联。"""
    message = _busy_message()
    if message:
        return 409, {"ok": False, "message": message}
    profile = str(payload.get("profile") or "").strip()
    expected = str(payload.get("email") or "").strip().lower()
    if not ps.profile_name_ok(profile):
        return 400, {"ok": False, "message": "profile 名不合法（字母数字 . _ -）"}
    if not expected or "@" not in expected:
        return 400, {"ok": False, "message": "缺少账本记录的邮箱"}
    if not LOGIN_WEB_PY.is_file():
        return 400, {"ok": False, "message": "找不到 login_web.py"}

    def _finalize() -> dict[str, Any]:
        job_profile = str(STATE.job.get("profile") or "")
        row = _reload_rows_with_probe(job_profile)
        actual = (row.get("email") or "").strip().lower()
        if not actual:
            raise RuntimeError("登录后读不到邮箱，没有补登")
        if actual != expected:
            raise RuntimeError(
                f"登录的是 {actual}，账本这条是 {expected}，邮箱不一致，未改动账本")
        result = ps.relink_registry_row(
            profile=job_profile, email=actual, user_id=row.get("user_id"))
        if not result.get("ok"):
            raise RuntimeError(result.get("message") or "补登失败")
        bases, errors = structural_rows()
        with STATE.lock:
            STATE.rows = bases
            STATE.errors = errors
        return result

    return _start_web_login_job(
        action="relink",
        profile=profile,
        intro=(f"浏览器将打开 profile「{profile}」。请登录账本里的账号（邮箱一致性由脚本校验）；"
               "登录邮箱与账本不一致时不会采纳会话，也不改动账本。"),
        finalize=_finalize,
        expect_email=expected,
    )


def start_job(payload: dict[str, Any]) -> dict[str, Any] | tuple[int, dict[str, Any]]:
    message = _busy_message()
    if message:
        return 409, {"ok": False, "message": message}
    action = str(payload.get("action") or "")
    profile = payload.get("profile")
    profile = str(profile).strip() if isinstance(profile, str) and profile.strip() else None
    try:
        count = _count(payload.get("n"), 1)
    except ValueError as exc:
        return 400, {"ok": False, "message": str(exc)}
    manual_actions = ("invite_manual", "invite_hand")
    locked_actions = ("invite_batch",) + manual_actions + ("register_direct",)
    if action in locked_actions and invite_busy():
        return 409, {"ok": False, "message": "已有邀请或注册在跑，没有抢锁"}
    if action == "invite_batch":
        row = _row_by_profile(profile or "")
        if row is None or not row.get("invite_ready"):
            return 409, {"ok": False, "message": "这个号当前不能自动邀请"}
        remaining = row.get("remaining_invitees")
        if not isinstance(remaining, int) or count > remaining:
            return 400, {"ok": False, "message": "人数超过剩余邀请名额"}
    if action in manual_actions:
        # 人工注册/人工邀请都是人工流程：只要网页登录在线、不是已退休母号即可，
        # 停奖/无名额不拦（可能没有奖励，由用户自负）；输入框上限放到前端提示。
        row = _row_by_profile(profile or "")
        if row is None:
            return 409, {"ok": False, "message": "没有这个 profile，先检测"}
        if row.get("role") == "retired_mother":
            return 409, {"ok": False, "message": "已退休母号不能再作为邀请人"}
        if not row.get("web_logged_in"):
            return 409, {"ok": False, "message": "网页未登录，先点网页登录或检测"}
    if action == "repair_cli":
        row = _row_by_profile(profile or "")
        if row is None:
            return 409, {"ok": False, "message": "没有这个 profile，先检测"}
        if not row.get("probed") or not row.get("web_logged_in"):
            return 409, {"ok": False, "message": "需要先检测且网页已登录才能补 CLI"}
        if row.get("cli_logged_in"):
            return 409, {"ok": False, "message": "CLI 已登录，不需要补"}
    if action == "login_web":
        if not profile:
            return 400, {"ok": False, "message": "缺少 profile"}
        if not LOGIN_WEB_PY.is_file():
            return 400, {"ok": False, "message": "找不到 login_web.py"}
    try:
        command = build_job(action, profile, count)
    except ValueError:
        return 400, {"ok": False, "message": "不认识的任务或 profile"}
    with STATE.lock:
        STATE.mode = "job"
        STATE.job = {
            "action": action,
            "profile": profile,
            "n": count,
            "running": True,
            "exit_code": None,
            "log": ["$ " + " ".join(command)],
        }

    def _run() -> None:
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            proc = subprocess.Popen(
                command,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                clean = ps.redact(line.rstrip("\r\n"))[:500]
                with STATE.lock:
                    STATE.job["log"].append(clean)
                    if len(STATE.job["log"]) > 200:
                        del STATE.job["log"][:-200]
            code = proc.wait()
        except Exception as exc:
            code = 1
            with STATE.lock:
                STATE.job["log"].append(ps.redact(str(exc)[:200]))
        # 注册/邀请类进程可能改了账本（_record_children）或 CLI profile 列表：
        # 进程退出后按本地结构重排（哪怕中途失败也可能有已入账的号），
        # 新入账的号不用重启面板就能出现。不在这里自动邀请或 prune；
        # 新行保持未探测，用户再点该卡「刷新」。
        if action in ("invite_hand", "invite_manual", "invite_batch",
                      "register_direct"):
            with STATE.lock:
                bases, errors = structural_rows()
                STATE.rows = bases
                STATE.errors = errors
        # 补 CLI 结束后探测这一张卡（CLI/网页/积分），再刷新结构；探测失败只记日志。
        if action == "repair_cli" and profile:
            try:
                _reload_rows_with_probe(profile)
            except Exception as exc:
                with STATE.lock:
                    STATE.job["log"].append(ps.redact(str(exc)[:200]))
            with STATE.lock:
                bases, errors = structural_rows()
                STATE.rows = bases
                STATE.errors = errors
        with STATE.lock:
            STATE.job["running"] = False
            STATE.job["exit_code"] = code
            STATE.job["log"].append(f"exit {code}")
            if STATE.mode == "job":
                STATE.mode = None

    threading.Thread(target=_run, name="flova-pool-job", daemon=True).start()
    return {"ok": True, "message": "任务已开始"}


def _profile_worker_id(profile: str) -> int:
    """给每个 profile 分配一个专用的稳定 worker-id（>=200，避开自动邀请/注册的 100/101）。"""
    if profile == "prod":
        return 200
    m = re.match(r"^kid(\d+)$", profile)
    if m:
        return 200 + int(m.group(1))
    return 500 + (abs(hash(profile)) % 400)


def _ensure_profile_fingerprint(profile_dir: Path, env_id: int, cc: str) -> Path:
    """确保 profile 目录下有该 worker-id 对应的 virtual.dat 指纹文件。"""
    dat = profile_dir / "virtual.dat"
    if dat.is_file():
        try:
            raw = json.loads(dat.read_text(encoding="utf-8"))
            users = raw.get("users") or []
            if any(isinstance(u, dict) and u.get("id") == env_id for u in users):
                return dat
        except Exception:
            pass
    import vb_fingerprint as vbf
    u = vbf.generate_fingerprint(env_id, cc, name=f"POOL-{env_id}")
    tmp = dat.with_suffix(".dat.tmp")
    tmp.write_text(json.dumps({"users": [u]}, ensure_ascii=False), encoding="utf-8", newline="\n")
    tmp.replace(dat)
    return dat


def open_browser(payload: dict[str, Any]) -> dict[str, Any] | tuple[int, dict[str, Any]]:
    """启动带指定 profile 持久化会话的 Virtual Browser（VB），直接进入 Flova 工作台后台。"""
    profile = str(payload.get("profile") or "").strip()
    if not ps.profile_name_ok(profile):
        return 400, {"ok": False, "message": "profile 名不合法"}

    if profile == "prod":
        profile_dir = Path.home() / ".flova-mcp" / "browser-profile"
        if not profile_dir.is_dir():
            alt = Path.home() / ".flova-mcp" / "browser-profiles" / "prod"
            if alt.is_dir():
                profile_dir = alt
    else:
        profile_dir = Path.home() / ".flova-mcp" / "browser-profiles" / profile

    if not profile_dir.is_dir():
        return 404, {"ok": False, "message": f"未找到 profile「{profile}」的网页会话目录，请先进行网页登录"}

    import vb_backend as vbb
    kernel_exe = vbb.kernel_path()
    if not kernel_exe.is_file():
        return 500, {"ok": False, "message": f"未找到 Virtual Browser 内核: {kernel_exe}"}

    env_id = _profile_worker_id(profile)
    if vbb.running_worker(env_id):
        return 409, {"ok": False, "message": f"{profile} 的 Virtual Browser 已在运行中，请检查桌面窗口"}

    cc = vbb.country()
    try:
        pinfo = vbb.ensure_proxy(cc, auto_start=True, verify_loc=False)
        proxy_url = pinfo["proxy"]
    except Exception as exc:
        return 500, {"ok": False, "message": f"代理自检失败: {exc}"}

    try:
        _ensure_profile_fingerprint(profile_dir, env_id, cc)
    except Exception as exc:
        return 500, {"ok": False, "message": f"准备指纹失败: {exc}"}

    cfg = vbb.COUNTRY_CFG.get(cc, vbb.COUNTRY_CFG["us"])
    target_url = str(payload.get("url") or "https://www.flova.ai/en/generator/").strip()
    cdp_port = vbb._free_port()

    cmd = [
        str(kernel_exe),
        f"--user-data-dir={profile_dir}",
        f"--worker-id={env_id}",
        "--no-first-run",
        "--no-default-browser-check",
        f"--remote-debugging-port={cdp_port}",
        "--remote-allow-origins=*",
        f"--proxy-server={proxy_url}",
        f"--lang={cfg['lang']}",
        f"--accept-lang={cfg['accept_lang']}",
    ]

    def _navigate_target() -> None:
        try:
            vbb.wait_cdp(cdp_port, timeout_s=25)
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{cdp_port}")
                ctx = b.contexts[0]
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                page.goto("https://www.flova.ai/en/", wait_until="domcontentloaded", timeout=30000)
                # 检查并自动水合前端 localStorage 鉴权（防止前端未水合时将子号跳出重定向到首页）
                try:
                    auth_raw = page.evaluate("() => localStorage.getItem('videoagent-auth-storage')")
                    needs_hydrate = True
                    if auth_raw:
                        try:
                            parsed = json.loads(auth_raw)
                            if (parsed.get("state") or {}).get("user"):
                                needs_hydrate = False
                        except Exception:
                            pass
                    if needs_hydrate:
                        raw_user = page.evaluate('''async () => {
                            try {
                                const r = await fetch('https://service.flova.ai/api/v2/user/get_user_info', {
                                    method: 'POST',
                                    headers: {'content-type': 'application/json'},
                                    body: '{}', credentials: 'include'
                                });
                                const j = await r.json().catch(() => ({}));
                                return (j && j.data) ? j.data : null;
                            } catch (e) { return null; }
                        }''')
                        if raw_user:
                            auth_val = json.dumps({"state": {"user": raw_user}, "version": 0})
                            page.evaluate(f'''(val) => {{ localStorage.setItem('videoagent-auth-storage', val); }}''', auth_val)
                except Exception:
                    pass
                # 导航到目标工作台页面
                page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                # 关闭其他多余的起始虚拟页
                for pg in list(ctx.pages):
                    if pg != page and ("virtual-worker" in str(pg.url) or pg.url == "about:blank"):
                        try:
                            pg.close()
                        except Exception:
                            pass
        except Exception:
            pass

    try:
        creationflags = 0
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen(
            cmd,
            cwd=str(kernel_exe.parent),
            creationflags=creationflags,
        )
        threading.Thread(target=_navigate_target, daemon=True).start()
        return {"ok": True, "message": f"已打开 {profile} 的 Virtual Browser 工作台窗口"}
    except Exception as exc:
        return 500, {"ok": False, "message": f"启动 Virtual Browser 失败: {exc}"}


class PanelServer(ThreadingHTTPServer):
    # 关掉窗口后端口会短暂留在 TIME_WAIT。不打开这项，马上再点快捷方式就会
    # WinError 10048（地址已被占用）。
    allow_reuse_address = True
    daemon_threads = True


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _host_ok(self) -> bool:
        host = self.headers.get("Host", "")
        return host.startswith("127.0.0.1:")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(ps.scrub_obj(payload), ensure_ascii=False).encode("utf-8")
        self._send(status, raw, "application/json; charset=utf-8")

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length < 0 or length > 8192:
            raise ValueError("请求体过大")
        raw = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("请求体必须是对象")
        return data

    def do_GET(self) -> None:  # noqa: N802
        if not self._host_ok():
            self._json(403, {"ok": False, "message": "只接受本机访问"})
            return
        path = urlparse(self.path).path
        if path == "/":
            body = PAGE.encode("utf-8")
            self._send(status=200, body=body, content_type="text/html; charset=utf-8")
            return
        if path == "/api/pool":
            self._json(200, _snapshot())
            return
        if path == "/api/jobs":
            snap = _snapshot()
            self._json(200, {"job": snap["job"], "mode": snap["mode"]})
            return
        self._json(404, {"ok": False, "message": "没有这个地址"})

    def do_POST(self) -> None:  # noqa: N802
        if not self._host_ok():
            self._json(403, {"ok": False, "message": "只接受本机访问"})
            return
        path = urlparse(self.path).path
        try:
            payload = self._read_json()
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"ok": False, "message": str(exc)})
            return
        if path == "/api/pool/refresh":
            result = start_refresh(payload)
        elif path == "/api/pool/add":
            result = add_profiles(payload)
        elif path == "/api/pool/remove":
            result = remove_profile(payload)
        elif path == "/api/pool/onboard":
            result = start_onboard(payload)
        elif path == "/api/pool/relink":
            result = start_relink(payload)
        elif path == "/api/pool/open_browser":
            result = open_browser(payload)
        elif path == "/api/jobs":
            result = start_job(payload)
        else:
            self._json(404, {"ok": False, "message": "没有这个地址"})
            return
        if isinstance(result, tuple):
            self._json(result[0], result[1])
            return
        self._json(200, result)


def allocate_port() -> int:
    out = subprocess.run(
        [sys.executable, str(PORTREG), "allocate",
         "--name", POOL_NAME, "--project", POOL_PROJECT,
         "--note", "Flova MCP account pool panel"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if out.returncode != 0:
        raise SystemExit(ps.redact((out.stderr or out.stdout or "port allocate failed")[:300]))
    match = re.search(r"port=(\d+)", out.stdout or "")
    if not match:
        raise SystemExit("port-registry 没有返回端口")
    return int(match.group(1))


def release_port() -> None:
    subprocess.run(
        [sys.executable, str(PORTREG), "release",
         "--name", POOL_NAME, "--project", POOL_PROJECT],
        capture_output=True, text=True, encoding="utf-8",
    )


def _release_if_bound() -> None:
    if BOUND:
        release_port()


def main() -> None:
    global BOUND
    rows, errors = structural_rows()
    with STATE.lock:
        STATE.rows = rows
        STATE.errors = errors
    port = allocate_port()
    try:
        server = PanelServer(("127.0.0.1", port), Handler)
    except OSError as exc:
        print(f"bind failed port={port} {exc}", flush=True)
        print(f"若面板已在运行，请手动打开 127.0.0.1:{port}", flush=True)
        raise SystemExit(1) from exc
    BOUND = True
    atexit.register(_release_if_bound)
    print(f"Flova 号池面板 http://127.0.0.1:{port}/", flush=True)
    # 启动不探测：不开浏览器、不查积分登录态；页面只叠磁盘快照。
    try:
        server.serve_forever()
    finally:
        server.server_close()
        release_port()
        BOUND = False


if __name__ == "__main__":
    main()
