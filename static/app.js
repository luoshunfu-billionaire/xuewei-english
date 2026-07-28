/* 学位英语学习系统 — 前端（同域本地服务器） */
'use strict';

let VOCAB = [];
let QUESTIONS = [];
let STUDY = { modules: [] };
let studyView = null;   // 当前打开的复习模块 id
let studyMask = true;   // 对照类默认遮挡中文

const START_DATE = '2026-07-27';
const EXAM_DATE = '2026-09-26';
const REVIEW_IV = [1, 3, 7, 15];

const WEEK_PLANS = [
  '第1周：语法资料（上）每天5-6页；每天精读1篇阅读；感受2022真题完成对话',
  '第2周：语法（上）收尾；每天1篇阅读精读；复习生词本',
  '第3周：语法（下）每天2页；周末限时做《考试试题（一）》摸底并分析错题',
  '第4周：《选择题核心》+《同位词300》；做《考试试题（二）》',
  '第5周：《英汉互译句法》每天2-3页；每两天练1段英译汉；做《湖南模拟一》',
  '第6周：作文模板/句型/金句背熟；精读真题范文9篇，手写3篇；做《湖南模拟二》',
  '第7周：2021、2022真题各限时120分钟；模拟三、四；选背6篇范文',
  '第8周：模拟五、六+试题（三）（四）限时；错题复盘；考前3天只看错题和模板'
];

let S = emptyState();
let CURRENT = '';
let ready = false;
let visBound = false;
let SERVER = false;   // true=连本机/局域网服务器同步；false=纯本地模式（App 未配置或离线）
let API_BASE = '';    // ''=同域；App 里填 http://192.168.x.x:5000
const LS_API = 'xwApiBase';

function emptyState(){
  return {
    settings: { dailyNew: 25 },
    words: {},
    days: {},
    extTasks: {},
    plan: { extra: {}, settledThrough: null },
    study: {},
    updatedAt: 0
  };
}

function lsKey(){ return 'xwState_' + CURRENT; }

function todayStr(){
  const d = new Date();
  return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
}

function localDateFromTs(t){
  const d = new Date(t);
  return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
}

function cmpDate(a, b){ return a < b ? -1 : a > b ? 1 : 0; }

function addDays(dateStr, n){
  const [y, m, d] = dateStr.split('-').map(Number);
  const dt = new Date(y, m - 1, d, 12, 0, 0);
  dt.setDate(dt.getDate() + n);
  return dt.getFullYear()+'-'+String(dt.getMonth()+1).padStart(2,'0')+'-'+String(dt.getDate()).padStart(2,'0');
}

function dayNum(){
  const a = new Date(START_DATE + 'T12:00:00');
  const b = new Date(todayStr() + 'T12:00:00');
  const d = Math.floor((b - a) / 86400000) + 1;
  return Math.max(1, Math.min(56, d));
}

function daysLeftExam(){
  const a = new Date(todayStr() + 'T12:00:00');
  const b = new Date(EXAM_DATE + 'T12:00:00');
  return Math.max(0, Math.ceil((b - a) / 86400000));
}

function now(){ return Date.now(); }

function esc(s){
  return String(s == null ? '' : s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function isFilePage(){ return location.protocol === 'file:'; }

function isCapApp(){
  try{
    return !!(window.Capacitor && typeof window.Capacitor.isNativePlatform === 'function'
      && window.Capacitor.isNativePlatform());
  }catch(e){ return false; }
}

function loadApiBase(){
  try{
    API_BASE = String(localStorage.getItem(LS_API) || '').trim().replace(/\/+$/, '');
  }catch(e){ API_BASE = ''; }
}

function saveApiBase(url){
  API_BASE = String(url || '').trim().replace(/\/+$/, '');
  try{
    if(API_BASE) localStorage.setItem(LS_API, API_BASE);
    else localStorage.removeItem(LS_API);
  }catch(e){}
}

function apiUrl(path){
  const p = path.charAt(0) === '/' ? path : '/' + path;
  return API_BASE ? (API_BASE + p) : p;
}

function cleanUserName(name){
  return String(name || '').trim().replace(/[^a-zA-Z0-9_\u4e00-\u9fff\-]/g, '').slice(0, 20);
}

function normalizeServerUrl(raw){
  let u = String(raw || '').trim();
  if(!u) return '';
  if(!/^https?:\/\//i.test(u)) u = 'http://' + u;
  return u.replace(/\/+$/, '');
}

/* 探测服务器是否可用：不可用则进入纯本地模式（进度只存 localStorage）。
   App 内同源没有 /api，须配置局域网地址；并校验 JSON 内容，避免误判。 */
async function detectMode(){
  if(isFilePage()){ SERVER = false; return; }
  loadApiBase();
  if(isCapApp() && !API_BASE){ SERVER = false; return; }
  try{
    const ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    const timer = setTimeout(() => { try{ ctrl && ctrl.abort(); }catch(e){} }, 3500);
    const res = await fetch(apiUrl('/api/health'), {
      cache: 'no-store',
      signal: ctrl ? ctrl.signal : undefined
    });
    clearTimeout(timer);
    const data = await res.json();
    SERVER = !!(res.ok && data && data.ok === true);
  }catch(e){ SERVER = false; }
}

/* 本机用户名单（含联网学过的用户，断网后仍可进入） */
function localUsers(){
  const names = [];
  const add = (n) => {
    n = cleanUserName(n);
    if(n && names.indexOf(n) < 0) names.push(n);
  };
  try{
    const u = JSON.parse(localStorage.getItem('xwUsers') || '[]');
    if(Array.isArray(u)) u.forEach(add);
  }catch(e){}
  try{
    for(let i = 0; i < localStorage.length; i++){
      const k = localStorage.key(i);
      if(k && k.indexOf('xwState_') === 0) add(k.slice('xwState_'.length));
    }
  }catch(e){}
  return names.sort();
}

function rememberUser(name){
  const clean = cleanUserName(name);
  if(!clean) return;
  const users = localUsers();
  if(users.indexOf(clean) < 0){
    users.push(clean);
    users.sort();
  }
  try{ localStorage.setItem('xwUsers', JSON.stringify(users)); }catch(e){}
}

function stateTs(st){
  return (st && st.updatedAt) | 0;
}

function userButtons(list){
  return list.length
    ? list.map(n =>
        `<button class="userbtn" onclick="selectUser('${encodeURIComponent(n)}')">👤 ${esc(n)}<span class="note">进入 ›</span></button>`
      ).join('')
    : '<p class="note">还没有用户，先在下方新建一个</p>';
}

function setSyncStatus(st){
  const el = document.getElementById('syncChip');
  if(!el) return;
  el.className = 'syncchip' + (st === 'ok' || st === 'warn' || st === 'err' ? ' ' + st : '');
  const map = { ok: '已同步', warn: '同步中…', err: '本地已存', '…': '同步中…', '本地': '本地' };
  el.textContent = map[st] || String(st);
}

function requireReady(){
  if(!ready){
    alert('请稍候同步完成');
    return false;
  }
  return true;
}

async function save(){
  if(!CURRENT) return;
  ensurePlan();
  S.updatedAt = Date.now();
  try{ localStorage.setItem(lsKey(), JSON.stringify(S)); }catch(e){}
  if(!SERVER){ setSyncStatus('本地'); return; }
  setSyncStatus('…');
  try{
    const res = await fetch(apiUrl('/api/state?user=' + encodeURIComponent(CURRENT)), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(S),
      keepalive: true
    });
    if(res.status === 409){
      const data = await res.json();
      if(data && data.conflict && data.state){
        S = data.state;
        ensurePlan();
        try{ localStorage.setItem(lsKey(), JSON.stringify(S)); }catch(e){}
        setSyncStatus('warn');
        alert('其他设备已更新进度，已加载最新数据');
        reRenderActive();
        return;
      }
    }
    if(!res.ok) throw new Error('http ' + res.status);
    setSyncStatus('ok');
  }catch(e){
    setSyncStatus('err');
  }
}

function reRenderActive(){
  const active = document.querySelector('nav button.active');
  const t = active ? active.dataset.tab : 'home';
  if(t === 'home') renderHome();
  else if(t === 'learn') startLearn();
  else if(t === 'review') renderReview();
  else if(t === 'stats') renderStats();
  else if(t === 'quiz') renderQuizHome();
  else if(t === 'drill') renderDrillHome();
  else if(t === 'wrong') renderWrong();
  else if(t === 'materials') renderMaterials();
  else if(t === 'study') renderStudy();
}

/* ---------- 用户 ---------- */
function refreshServerCfgUi(){
  const input = document.getElementById('serverUrl');
  const st = document.getElementById('serverStatus');
  if(input && document.activeElement !== input){
    input.value = API_BASE || '';
    input.placeholder = isCapApp()
      ? 'http://192.168.x.x:5000（电脑启动窗口里的地址）'
      : '留空=本机；或填 http://192.168.x.x:5000';
  }
  if(!st) return;
  if(SERVER && API_BASE) st.textContent = '已连接：' + API_BASE;
  else if(SERVER) st.textContent = '已连接本机服务器';
  else if(API_BASE) st.textContent = '未连上：' + API_BASE + '（请确认电脑已启动、同一 Wi-Fi）';
  else if(isCapApp()) st.textContent = '未配置电脑地址，当前为纯本机模式';
  else st.textContent = '未连上服务器，当前为纯本机模式';
}

function showUserPicker(){
  document.getElementById('userGate').style.display = 'flex';
  document.getElementById('gateErr').textContent = '';
  refreshServerCfgUi();
  const note = document.getElementById('gateNote');
  const locals = localUsers();
  if(!SERVER){
    if(note) note.textContent = isCapApp()
      ? '可先填电脑地址连接同步；断网时选同一名字即可继续本机进度'
      : '进度保存在本机；换设备可在「今日 → 设置」里导出/导入进度迁移';
    document.getElementById('userList').innerHTML = userButtons(locals);
    return;
  }
  if(note) note.textContent = '进度会同时保存在手机和电脑；手机与电脑选同一名字即可同步';
  fetch(apiUrl('/api/users')).then(r => r.json()).then(list => {
    const merged = [];
    const add = (n) => {
      n = cleanUserName(n);
      if(n && merged.indexOf(n) < 0) merged.push(n);
    };
    (Array.isArray(list) ? list : []).forEach(add);
    locals.forEach(add);
    merged.sort();
    document.getElementById('userList').innerHTML = userButtons(merged);
  }).catch(() => {
    document.getElementById('userList').innerHTML = userButtons(locals);
    document.getElementById('gateErr').textContent =
      '连不上服务器，已显示本机用户。本机进度仍在，连上后再同步即可';
  });
}

async function connectServer(){
  const input = document.getElementById('serverUrl');
  const err = document.getElementById('gateErr');
  const raw = input ? input.value : API_BASE;
  const url = normalizeServerUrl(raw);
  if(!url){
    if(err) err.textContent = '请先填写电脑地址，例如 http://192.168.1.8:5000';
    return;
  }
  if(err) err.textContent = '';
  saveApiBase(url);
  if(input) input.value = url;
  const st = document.getElementById('serverStatus');
  if(st) st.textContent = '正在连接…';
  await detectMode();
  refreshServerCfgUi();
  if(SERVER){
    if(err) err.textContent = '';
    showUserPicker();
  }else if(err){
    err.textContent = '连接失败：请确认电脑已启动、手机与电脑同一 Wi-Fi，且地址与启动窗口一致';
  }
}

async function useLocalMode(){
  saveApiBase('');
  SERVER = false;
  const err = document.getElementById('gateErr');
  if(err) err.textContent = '';
  showUserPicker();
}

function createUser(){
  const name = document.getElementById('newUserName').value.trim();
  if(!name) return;
  const clean = cleanUserName(name);
  if(!clean){
    document.getElementById('gateErr').textContent = '名字含非法字符，请换一个';
    return;
  }
  rememberUser(clean);
  if(!SERVER){
    selectUser(encodeURIComponent(clean));
    return;
  }
  fetch(apiUrl('/api/newuser?user=' + encodeURIComponent(clean)), { method: 'POST' })
    .then(r => {
      if(!r.ok) throw new Error('http ' + r.status);
      return r.json();
    })
    .then(r => {
      if(r.ok) selectUser(encodeURIComponent(r.user));
      else document.getElementById('gateErr').textContent = r.err || '创建失败';
    })
    .catch(() => {
      // 服务器不可用：仍可进入本机进度，避免联网学过的数据“消失”
      SERVER = false;
      setSyncStatus('本地');
      document.getElementById('gateErr').textContent = '服务器暂不可用，已用本机进度进入';
      selectUser(encodeURIComponent(clean));
    });
}

async function selectUser(enc){
  CURRENT = decodeURIComponent(enc);
  ready = false;
  setSyncStatus('…');
  document.getElementById('userGate').style.display = 'none';
  document.getElementById('userChip').textContent = '👤 ' + CURRENT;
  rememberUser(CURRENT);

  S = emptyState();
  let hasLocal = false;
  try{
    const raw = localStorage.getItem(lsKey());
    const local = raw ? JSON.parse(raw) : null;
    if(local && typeof local === 'object'){
      S = local;
      hasLocal = true;
      ensurePlan();
      renderHome();
    }
  }catch(e){}

  if(SERVER){
    try{
      const res = await fetch(apiUrl('/api/state?user=' + encodeURIComponent(CURRENT)));
      if(!res.ok) throw new Error('http ' + res.status);
      const s = await res.json();
      if(s && typeof s === 'object' && (s.words || s.updatedAt != null)){
        const srvTs = stateTs(s);
        const locTs = stateTs(S);
        // 取更新的一份，避免断网期间的本机进度被服务器旧数据盖掉
        if(!hasLocal || srvTs > locTs){
          S = s;
        }
        ensurePlan();
        try{ localStorage.setItem(lsKey(), JSON.stringify(S)); }catch(e){}
        if(hasLocal && locTs > srvTs){
          // 本机更新：立刻回传服务器
          ready = true;
          await save();
          settlePlan();
          renderHome();
          bindVisibility();
          return;
        }
      }
      setSyncStatus('ok');
    }catch(e){
      // 拉服务器失败：继续用本机进度
      try{ localStorage.setItem(lsKey(), JSON.stringify(S)); }catch(err){}
      setSyncStatus(hasLocal ? '本地' : 'err');
    }
  }else{
    try{ localStorage.setItem(lsKey(), JSON.stringify(S)); }catch(e){}
    setSyncStatus('本地');
  }

  ready = true;
  settlePlan();
  renderHome();
  bindVisibility();
}

async function pullServerState(){
  if(!SERVER || !CURRENT || !ready) return;
  try{
    const res = await fetch(apiUrl('/api/state?user=' + encodeURIComponent(CURRENT)));
    if(!res.ok) throw new Error('http ' + res.status);
    const s = await res.json();
    const srvTs = (s && s.updatedAt) | 0;
    const locTs = (S && S.updatedAt) | 0;
    if(s && srvTs > locTs){
      S = s;
      ensurePlan();
      try{ localStorage.setItem(lsKey(), JSON.stringify(S)); }catch(e){}
      setSyncStatus('ok');
      reRenderActive();
    }
  }catch(e){
    setSyncStatus('err');
  }
}

function bindVisibility(){
  if(visBound) return;
  visBound = true;
  const onShow = () => {
    if(document.visibilityState === 'visible' && CURRENT) pullServerState();
  };
  document.addEventListener('visibilitychange', onShow);
  window.addEventListener('focus', () => {
    if(CURRENT) pullServerState();
  });
}

/* ---------- 计划 / 欠债 ---------- */
function ensurePlan(){
  if(!S.plan || typeof S.plan !== 'object') S.plan = { extra: {}, settledThrough: null };
  if(!S.plan.extra || typeof S.plan.extra !== 'object') S.plan.extra = {};
  if(!S.settings || typeof S.settings !== 'object') S.settings = { dailyNew: 25 };
  if(S.settings.dailyNew == null) S.settings.dailyNew = 25;
  if(!S.words) S.words = {};
  if(!S.days) S.days = {};
  if(!S.extTasks) S.extTasks = {};
}

function learnedNewOn(date){
  let n = 0;
  for(const r of Object.values(S.words || {})){
    const d = (r.hist && r.hist[0] && r.hist[0].d) || r.learnedOn;
    if(d === date) n++;
  }
  return n;
}

function dayTarget(date){
  ensurePlan();
  const base = S.settings.dailyNew || 25;
  return Math.min(60, base + (S.plan.extra[date] | 0));
}

function distributeDebt(amount, afterDate){
  if(amount <= 0) return;
  const days = [];
  let d = addDays(afterDate, 1);
  while(cmpDate(d, EXAM_DATE) <= 0){
    days.push(d);
    d = addDays(d, 1);
  }
  if(!days.length) return;
  ensurePlan();
  const base = Math.floor(amount / days.length);
  let rem = amount - base * days.length;
  days.forEach((day, i) => {
    const add = base + (i < rem ? 1 : 0);
    if(add) S.plan.extra[day] = (S.plan.extra[day] | 0) + add;
  });
}

function settlePlan(){
  ensurePlan();
  const yesterday = addDays(todayStr(), -1);
  if(cmpDate(yesterday, START_DATE) < 0){
    S.plan.settledThrough = yesterday;
    return;
  }
  let dirty = false;
  let d = START_DATE;
  const through = S.plan.settledThrough;
  while(cmpDate(d, yesterday) <= 0){
    if(through && cmpDate(d, through) <= 0){
      d = addDays(d, 1);
      continue;
    }
    const target = dayTarget(d);
    const done = learnedNewOn(d);
    const short = Math.max(0, target - done);
    if(!S.plan.history) S.plan.history = {};
    S.plan.history[d] = { target, done, short };
    if(short > 0){
      distributeDebt(short, d);
    }
    dirty = true;
    d = addDays(d, 1);
  }
  if(S.plan.settledThrough !== yesterday){
    S.plan.settledThrough = yesterday;
    dirty = true;
  }
  if(dirty){
    // 异步落盘，不阻塞今日任务渲染
    Promise.resolve().then(() => save());
  }
}

function todayNewWords(){
  settlePlan();
  const target = dayTarget(todayStr());
  return VOCAB.filter(v => !S.words[v.w]).slice(0, target);
}

function planSnapshot(){
  ensurePlan();
  settlePlan();
  const today = todayStr();
  const base = S.settings.dailyNew || 25;
  const extra = S.plan.extra[today] | 0;
  const target = dayTarget(today);
  const doneToday = learnedNewOn(today);
  const remain = Math.max(0, target - doneToday);
  const unlearned = VOCAB.filter(v => !S.words[v.w]).length;
  const daysLeft = daysLeftExam();
  let debtTotal = 0;
  let d = addDays(today, 1);
  while(cmpDate(d, EXAM_DATE) <= 0){
    debtTotal += (S.plan.extra[d] | 0);
    d = addDays(d, 1);
  }
  if(!debtTotal && S.plan.history){
    debtTotal = Object.values(S.plan.history).reduce((s, h) => s + (h.short | 0), 0);
  }
  return { base, extra, target, doneToday, remain, unlearned, daysLeft, debtTotal };
}

/* ---------- SM-2 ---------- */
function logActivity(){
  (S.act = S.act || []).push(now());
  if(S.act.length > 5000) S.act = S.act.slice(-5000);
}

function quality(rt, remembered){
  if(!remembered) return 1;
  return rt < 3000 ? 5 : rt < 8000 ? 4 : 3;
}

function sm2(r, q){
  if(q < 3){
    r.reps = 0; r.iv = 1; r.lapses = (r.lapses || 0) + 1;
  }else{
    r.reps = (r.reps || 0) + 1;
    r.iv = r.reps === 1 ? 1 : r.reps === 2 ? 3 : Math.round((r.iv || 1) * r.ef);
    r.ef = Math.max(1.3, (r.ef || 2.5) + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)));
  }
  r.due = addDays(todayStr(), r.iv);
  r.st = (r.reps >= 5 || r.iv > 21) ? 'mastered' : 'learning';
}

function recordHist(r, q, rt){
  (r.hist = r.hist || []).push({ d: todayStr(), q, rt: Math.round(rt / 100) / 10 });
  if(r.hist.length > 50) r.hist = r.hist.slice(-50);
}

function isDue(w){
  const r = S.words[w];
  return r && r.st === 'learning' && r.due <= todayStr();
}
function dueWords(){ return VOCAB.filter(v => isDue(v.w)); }
function learningWords(){ return VOCAB.filter(v => S.words[v.w] && S.words[v.w].st === 'learning'); }

function shuffle(a){
  for(let i = a.length - 1; i > 0; i--){
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
}

/* ---------- 今日任务 ---------- */
function renderHome(){
  ensurePlan();
  const snap = planSnapshot();
  const dn = dayNum();
  document.getElementById('countdown').textContent = '距考试 ' + snap.daysLeft + ' 天';
  const dayTitle = document.getElementById('dayTitle');
  if(dayTitle) dayTitle.textContent = `Day ${dn} · ${todayStr()}`;

  const bannerInner =
    `<b>今日配额 ${snap.target} 词</b>（基础 ${snap.base}` +
    (snap.extra ? ` + 欠债补量 ${snap.extra}` : '') +
    `）· 已学 ${snap.doneToday} · 还剩 ${snap.remain}` +
    `<br><span class="note">过去未完成的新词会均摊到考试前剩余天数（单日上限 60）。未学词库 ${snap.unlearned}，距考 ${snap.daysLeft} 天` +
    (snap.debtTotal ? `，未来补量合计约 ${snap.debtTotal}` : '') +
    `。</span>`;

  const bannerEl = document.getElementById('planBanner');
  if(bannerEl){
    bannerEl.className = 'plan-banner';
    bannerEl.innerHTML = bannerInner;
  }

  const doneNew = snap.doneToday;
  const target = snap.target;
  const due = dueWords().length;
  const t = S.days[todayStr()] || {};
  const wd = wrongDue().length;
  const tasks = [
    { name: `背新词 ${target} 个`, prog: `${doneNew}/${target}`, go: 'learn', btn: '去学' },
    { name: '复习到期生词', prog: `${due} 个待复习`, go: 'review', btn: '去复习' },
    { name: '单词测验 10 题', prog: t.quiz != null ? `已做：${t.quiz}/10` : '未做', go: 'quiz', btn: '去测验' },
    { name: '刷真题', prog: `题库 ${QUESTIONS.length} 题`, go: 'drill', btn: '去刷题' },
    { name: '重做错题', prog: wd ? `${wd} 题待重做` : '无待重做', go: 'wrong', btn: '去错题本' }
  ];
  const ext = [
    { key: 'reading', name: '精读 1 篇阅读理解（资料17-21 或真题）' },
    { key: 'grammar', name: '语法/专项任务（见下方本周安排）' },
    { key: 'colloc', name: '固定搭配 1 页（资料5）' }
  ];
  let html = bannerEl ? '' : `<div class="plan-banner">${bannerInner}</div>`;
  tasks.forEach(x => {
    html += `<div class="task"><div>${esc(x.name)}<div class="note">${esc(x.prog)}</div></div>
      <button class="btn" onclick="goto('${x.go}')">${esc(x.btn)}</button></div>`;
  });
  ext.forEach(x => {
    const done = S.extTasks[todayStr() + '_' + x.key];
    html += `<div class="task ${done ? 'done' : ''}"><div>${esc(x.name)}</div>
      <button class="btn ghost" onclick="toggleExt('${x.key}')">${done ? '✓ 已完成' : '打卡'}</button></div>`;
  });
  document.getElementById('taskList').innerHTML = html;

  const weekPlan = document.getElementById('weekPlan');
  if(weekPlan) weekPlan.textContent = WEEK_PLANS[Math.min(7, Math.floor((dn - 1) / 7))];
  const dailyNew = document.getElementById('dailyNew');
  if(dailyNew) dailyNew.value = S.settings.dailyNew;

  const noteEl = document.getElementById('settingsNote');
  if(noteEl){
    noteEl.innerHTML =
      `词库共 ${VOCAB.length} 词。开始 ${START_DATE}，考试 ${EXAM_DATE}。` +
      `每日基础量会加上过去欠债的均摊；某天少学的词不会永远跳过。` +
      `<br>刷题题库来自 questions.json（已录入选择题），PDF 请在「资料」阅读，不会自动变成刷题。` +
      ` <a href="javascript:goto('materials')" style="color:#8b5e3c">打开资料</a>`;
  }
}

function goto(tab){
  const btn = document.querySelector(`nav button[data-tab="${tab}"]`);
  if(btn) btn.click();
}

function toggleExt(key){
  if(!requireReady()) return;
  const k = todayStr() + '_' + key;
  S.extTasks[k] = !S.extTasks[k];
  save();
  renderHome();
}

function saveSettings(){
  if(!requireReady()) return;
  S.settings.dailyNew = Math.max(10, Math.min(50, +document.getElementById('dailyNew').value || 25));
  save();
  renderHome();
  alert('已保存（欠债补量仍会叠加在基础量上）');
}

/* ---------- 学单词 ---------- */
let learnQueue = [], learnIdx = 0, cardShownAt = 0;

function startLearn(){
  if(!requireReady()){
    document.getElementById('fcWord').textContent = '…';
    document.getElementById('fcIpa').textContent = '';
    document.getElementById('fcPos').textContent = '正在同步，请稍候';
    document.getElementById('fcMeaning').textContent = '';
    document.getElementById('learnProgress').textContent = '';
    return;
  }
  learnQueue = todayNewWords().filter(v => !S.words[v.w]);
  learnIdx = 0;
  if(!learnQueue.length){
    document.getElementById('fcWord').textContent = '🎉';
    document.getElementById('fcIpa').textContent = '';
    document.getElementById('fcPos').textContent = '今天的新词学完了';
    document.getElementById('fcMeaning').textContent = '';
    document.getElementById('learnProgress').textContent = '可以去复习或做测验';
    return;
  }
  showCard();
}

function showCard(){
  const v = learnQueue[learnIdx];
  const fc = document.getElementById('flashcard');
  fc.classList.remove('revealed');
  document.getElementById('fcWord').textContent = v.w;
  document.getElementById('fcIpa').textContent = v.ipa || '';
  document.getElementById('fcPos').textContent = v.pos || '';
  document.getElementById('fcMeaning').textContent = v.m;
  document.getElementById('learnProgress').textContent =
    `今日新词 ${learnIdx + 1} / ${learnQueue.length}`;
  cardShownAt = now();
  speak();
}

function reveal(){
  document.getElementById('flashcard').classList.add('revealed');
}

function speak(){
  const v = learnQueue[learnIdx];
  if(!v || !v.w) return;
  speakText(v.w);
}

function speakText(text){
  const t = String(text || '').trim();
  if(!t) return;
  // Android WebView 的 speechSynthesis 基本不可用，App 内走系统 TTS
  try{
    const cap = window.Capacitor;
    const tts = cap && cap.Plugins && cap.Plugins.TextToSpeech;
    if(tts && typeof tts.speak === 'function'){
      tts.speak({
        text: t,
        lang: 'en-US',
        rate: 0.9,
        pitch: 1.0,
        volume: 1.0,
        queueStrategy: 1
      }).catch(function(){});
      return;
    }
  }catch(e){}
  if(typeof speechSynthesis === 'undefined' || typeof SpeechSynthesisUtterance === 'undefined') return;
  try{ speechSynthesis.cancel(); }catch(e){}
  const u = new SpeechSynthesisUtterance(t);
  u.lang = 'en-US';
  u.rate = 0.85;
  speechSynthesis.speak(u);
}

function markWord(known){
  if(!requireReady()) return;
  const v = learnQueue[learnIdx];
  if(!v) return;
  const rt = now() - cardShownAt;
  const td = todayStr();
  const histEntry = { d: td, q: known ? 5 : 1, rt: Math.round(rt / 100) / 10, learnedOn: td };
  if(known){
    S.words[v.w] = {
      st: 'mastered', ef: 2.5, reps: 5, iv: 999, due: '', n: 1, lapses: 0,
      learnedOn: td, hist: [histEntry]
    };
  }else{
    S.words[v.w] = {
      st: 'learning', ef: 2.5, reps: 0, iv: 1, due: addDays(td, 1), n: 1, lapses: 0,
      learnedOn: td, hist: [histEntry]
    };
  }
  logActivity();
  save();
  learnIdx++;
  if(learnIdx >= learnQueue.length){
    alert('今天的新词完成！');
    goto('home');
  }else showCard();
}

/* ---------- 测验 ---------- */
let quizQ = [], quizI = 0, quizScore = 0, qShownAt = 0;

function renderQuizHome(){
  const t = S.days[todayStr()] || {};
  document.getElementById('quizBox').innerHTML = `
    <h2>单词测验</h2>
    <p class="note" style="margin-bottom:14px">从「今日新词 + 待复习生词」中抽 10 题，英译中/中译英混合。
    ${t.quiz != null ? `<br>今天成绩：${t.quiz}/10，可再测一次。` : ''}</p>
    <div class="center"><button class="btn big" onclick="startQuiz()">开始测验</button></div>`;
}

function startQuiz(){
  if(!requireReady()) return;
  let pool = [...new Set([...todayNewWords().map(v => v.w), ...dueWords().map(v => v.w)])];
  if(pool.length < 10) pool = pool.concat(learningWords().map(v => v.w));
  if(pool.length < 10) pool = pool.concat(VOCAB.slice(0, 200).map(v => v.w));
  pool = [...new Set(pool)];
  shuffle(pool);
  quizQ = pool.slice(0, 10).map(w => {
    const v = VOCAB.find(x => x.w === w);
    const en2cn = Math.random() < 0.6;
    const distract = VOCAB.filter(x => x.w !== w);
    shuffle(distract);
    const opts = [v, ...distract.slice(0, 3)];
    shuffle(opts);
    return { v, en2cn, opts };
  });
  quizI = 0;
  quizScore = 0;
  showQuizQ();
}

function showQuizQ(){
  const q = quizQ[quizI];
  const box = document.getElementById('quizBox');
  let html = `<div class="qhead">第 ${quizI + 1} / ${quizQ.length} 题 · ${q.en2cn ? '选出正确中文' : '选出正确英文'}</div>
    <div class="qword">${q.en2cn ? esc(q.v.w) + ' <span style="font-size:14px;color:#999">' + esc(q.v.pos) + '</span>' : esc(q.v.m)}</div>`;
  q.opts.forEach(o => {
    html += `<button class="opt" onclick="answerQuiz(this, ${o.w === q.v.w})">${q.en2cn ? esc(o.m) : esc(o.w)}</button>`;
  });
  box.innerHTML = html;
  qShownAt = now();
}

function answerQuiz(el, correct){
  if(!requireReady()) return;
  document.querySelectorAll('.opt').forEach(b => { b.disabled = true; });
  const q = quizQ[quizI];
  const rt = now() - qShownAt;
  (S.quizLog = S.quizLog || []).push({
    d: todayStr(), w: q.v.w, dir: q.en2cn ? 'e2c' : 'c2e',
    ok: correct ? 1 : 0, rt: Math.round(rt / 100) / 10
  });
  if(S.quizLog.length > 2000) S.quizLog = S.quizLog.slice(-2000);
  logActivity();
  el.classList.add(correct ? 'correct' : 'wrong');
  if(!correct){
    const label = q.en2cn ? q.v.m : q.v.w;
    document.querySelectorAll('.opt').forEach(b => {
      if(b.textContent === label) b.classList.add('correct');
    });
  }
  if(correct) quizScore++;
  setTimeout(() => {
    quizI++;
    if(quizI < quizQ.length) showQuizQ();
    else{
      if(!S.days[todayStr()]) S.days[todayStr()] = {};
      S.days[todayStr()].quiz = quizScore;
      save();
      document.getElementById('quizBox').innerHTML = `
        <h2>测验完成</h2>
        <p class="center" style="font-size:40px;margin:20px 0">${quizScore} / ${quizQ.length}</p>
        <p class="center note">${quizScore >= 8 ? '很棒！' : quizScore >= 5 ? '继续加油，错题回生词本复习' : '别灰心，错词已记录，明天复习它们'}</p>
        <div class="row"><button class="btn" onclick="startQuiz()">再测一次</button>
        <button class="btn ghost" onclick="goto('home')">返回</button></div>`;
    }
  }, correct ? 400 : 1200);
}

/* ---------- 复习 ---------- */
let revQueue = [], revIdx = 0, revShownAt = 0;

function renderReview(){
  document.getElementById('dueCount').textContent = dueWords().length;
  const lw = learningWords();
  document.getElementById('learnCount').textContent = lw.length;
  document.getElementById('allLearning').innerHTML = lw.map(v => {
    const r = S.words[v.w];
    return `<tr><td><b>${esc(v.w)}</b> <span class="note">${esc(v.pos)}</span></td><td>${esc(v.m)}</td>
      <td class="note">${r.due <= todayStr() ? '今天到期' : esc(r.due) + ' 复习'}</td></tr>`;
  }).join('') || '<tr><td class="note">还没有生词，去学新词时标记「不认识」就会进这里</td></tr>';
}

function startReview(){
  if(!requireReady()) return;
  revQueue = dueWords();
  revIdx = 0;
  if(!revQueue.length){ alert('今天没有到期复习的词 🎉'); return; }
  document.getElementById('reviewCard').classList.remove('hidden');
  showRev();
}

function showRev(){
  const v = revQueue[revIdx];
  document.getElementById('rFlash').classList.remove('revealed');
  document.getElementById('rWord').textContent = v.w;
  document.getElementById('rIpa').textContent = v.ipa || '';
  document.getElementById('rPos').textContent = v.pos || '';
  document.getElementById('rMeaning').textContent = v.m;
  revShownAt = now();
}

function reviewAnswer(remember){
  if(!requireReady()) return;
  const v = revQueue[revIdx];
  const r = S.words[v.w];
  const rt = now() - revShownAt;
  const q = quality(rt, remember);
  recordHist(r, q, rt);
  sm2(r, q);
  r.n++;
  logActivity();
  save();
  revIdx++;
  if(revIdx >= revQueue.length){
    document.getElementById('reviewCard').classList.add('hidden');
    alert('复习完成！');
    renderReview();
  }else showRev();
}

/* ---------- 刷真题 ---------- */
let drillQ = [], drillI = 0, drillScore = 0, drillWrong = [], drillShownAt = 0, drillMode = '';

function renderDrillHome(){
  const parts = [...new Set(QUESTIONS.map(q => q.part))];
  const bySrc = {};
  QUESTIONS.forEach(q => { bySrc[q.src] = (bySrc[q.src] || 0) + 1; });
  const srcNote = Object.entries(bySrc).map(([k, v]) => `${k} ${v}题`).join(' · ');
  const byPart = parts.map(p => {
    const qs = QUESTIONS.filter(q => q.part === p);
    return `<div class="task"><div>${esc(p)}<div class="note">${qs.length} 题</div></div>
      <button class="btn" onclick="startDrill(decodeURIComponent('${encodeURIComponent(p)}'))">开始</button></div>`;
  }).join('');
  const srcButtons = Object.keys(bySrc).map(s =>
    `<button class="btn ghost" style="margin:4px" onclick="startDrillSrc('${encodeURIComponent(s)}')">${esc(s)}（${bySrc[s]}）</button>`
  ).join('');
  document.getElementById('drillBox').innerHTML = `
    <h2>刷真题（${QUESTIONS.length} 题）</h2>
    <p class="note" style="margin-bottom:12px">
      <b>已入库：</b>${esc(srcNote)}。<br>
      题型：完成对话 / 阅读理解 / 词汇语法。翻译与作文请在「资料」打开 PDF。<br>
      湖南 2021 真题与全真模拟卷为扫描件，暂未全部自动入库，可在「资料」看原卷。
    </p>
    ${byPart}
    <div class="task"><div>全部混合练习</div><button class="btn" onclick="startDrill('')">开始</button></div>
    <h2 style="font-size:15px;margin-top:16px">按来源练习</h2>
    <div>${srcButtons}</div>`;
}

function startDrill(part){
  if(!requireReady()) return;
  drillMode = part;
  drillQ = part ? QUESTIONS.filter(q => q.part === part) : QUESTIONS.slice();
  shuffle(drillQ);
  drillI = 0;
  drillScore = 0;
  drillWrong = [];
  if(!drillQ.length){
    alert('题库为空');
    return;
  }
  showDrillQ();
}

function startDrillSrc(enc){
  if(!requireReady()) return;
  const src = decodeURIComponent(enc);
  drillMode = 'src:' + src;
  drillQ = QUESTIONS.filter(q => q.src === src).slice();
  shuffle(drillQ);
  drillI = 0; drillScore = 0; drillWrong = [];
  if(!drillQ.length){ alert('该来源暂无题目'); return; }
  showDrillQ();
}

function showDrillQ(){
  const q = drillQ[drillI];
  const keys = Object.keys(q.options);
  let html = `<div class="qhead">第 ${drillI + 1} / ${drillQ.length} 题 · ${esc(q.part)} · ${esc(q.src)}</div>
    <div style="font-size:17px;line-height:1.7;margin-bottom:16px;white-space:pre-line">${esc(q.stem)}</div>`;
  keys.forEach(k => {
    html += `<button class="opt" data-k="${esc(k)}" onclick="answerDrill(this,'${esc(k)}')"><b>${esc(k)}.</b> ${esc(q.options[k])}</button>`;
  });
  html += `<div id="drillExp"></div>`;
  document.getElementById('drillBox').innerHTML = html;
  drillShownAt = now();
}

function answerDrill(el, chosen){
  if(!requireReady()) return;
  const q = drillQ[drillI];
  const correct = chosen === q.answer;
  document.querySelectorAll('#drillBox .opt').forEach(b => {
    b.disabled = true;
    const k = b.dataset.k;
    if(k === q.answer) b.classList.add('correct');
    else if(k === chosen) b.classList.add('wrong');
  });
  if(correct) drillScore++;
  else drillWrong.push(q.id);
  recordWrong(q, chosen, correct);
  logActivity();
  save();
  document.getElementById('drillExp').innerHTML = `
    <div style="background:#faf6f0;border-radius:10px;padding:14px;margin-top:14px">
      <b>${correct ? '✅ 答对了' : '❌ 答错了，正确答案：' + esc(q.answer)}</b>
      <p style="margin-top:8px;line-height:1.7">${esc(q.exp)}</p>
    </div>
    <div class="row"><button class="btn big" onclick="nextDrill()">${drillI + 1 >= drillQ.length ? '看结果' : '下一题'}</button></div>`;
}

function nextDrill(){
  drillI++;
  if(drillI < drillQ.length) showDrillQ();
  else{
    const backWrong = drillMode === 'wrong';
    document.getElementById('drillBox').innerHTML = `
      <h2>练习完成</h2>
      <p class="center" style="font-size:40px;margin:16px 0">${drillScore} / ${drillQ.length}</p>
      <p class="center note">${drillWrong.length ? '错 ' + drillWrong.length + ' 题，已存入错题本，记得回来重做' : '全对！太棒了 🎉'}</p>
      <div class="row"><button class="btn" onclick="${backWrong ? 'goto(\'wrong\')' : 'renderDrillHome()'}">${backWrong ? '回错题本' : '再练'}</button>
      <button class="btn ghost" onclick="goto('wrong')">看错题本</button></div>`;
  }
}

function recordWrong(q, chosen, correct){
  S.wrong = S.wrong || {};
  let r = S.wrong[q.id];
  if(!correct){
    r = S.wrong[q.id] = {
      stage: 0, due: addDays(todayStr(), 1),
      first: (r ? r.first : todayStr()), last: todayStr(),
      lastPick: chosen, times: (r ? r.times : 0) + 1, cleared: false
    };
  }else if(r && !r.cleared){
    r.stage = (r.stage || 0) + 1;
    r.last = todayStr();
    r.lastPick = chosen;
    if(r.stage >= REVIEW_IV.length){ r.cleared = true; r.due = ''; }
    else r.due = addDays(todayStr(), REVIEW_IV[r.stage]);
  }
}

/* ---------- 错题本 ---------- */
function wrongList(){
  return Object.entries(S.wrong || {})
    .map(([id, r]) => ({ q: QUESTIONS.find(x => x.id === id), r }))
    .filter(x => x.q);
}

function wrongDue(){
  return wrongList().filter(x => !x.r.cleared && x.r.due && x.r.due <= todayStr());
}

function renderWrong(){
  const all = wrongList();
  const due = wrongDue();
  const active = all.filter(x => !x.r.cleared);
  const clearedN = all.filter(x => x.r.cleared).length;
  let html = `<h2>错题本</h2>
    <div class="stat-grid" style="margin-bottom:14px">
      <div class="stat-box"><div class="num">${active.length}</div><div class="label">待攻克</div></div>
      <div class="stat-box"><div class="num">${due.length}</div><div class="label">今日待重做</div></div>
    </div>`;
  if(due.length){
    html += `<div class="row" style="margin-bottom:16px"><button class="btn big" onclick="startWrongReview()">重做今日错题（${due.length}）</button></div>`;
  }else{
    html += `<p class="note center" style="margin-bottom:16px">今天没有待重做的错题${active.length ? '，继续去刷题积累' : ''} 👍</p>`;
  }
  html += `<h2 style="font-size:15px">全部错题（${all.length}，已攻克 ${clearedN}）</h2>`;
  html += all.map(x => `<div class="task ${x.r.cleared ? 'done' : ''}">
    <div style="flex:1"><div>${esc(x.q.part)} · ${esc(x.q.src)}</div>
    <div class="note">错 ${x.r.times} 次${x.r.cleared ? ' · 已攻克' : ' · ' + (x.r.due <= todayStr() ? '今日重做' : esc(x.r.due) + ' 重做')}</div></div>
    <button class="btn ghost" onclick="previewWrong('${esc(x.q.id)}')">看题</button></div>`).join('')
    || '<p class="note">还没有错题，去刷真题吧</p>';
  html += `<div id="wrongPreview"></div>`;
  document.getElementById('wrongBox').innerHTML = html;
}

function previewWrong(id){
  const q = QUESTIONS.find(x => x.id === id);
  if(!q) return;
  const keys = Object.keys(q.options);
  document.getElementById('wrongPreview').innerHTML = `
    <div style="background:#faf6f0;border-radius:10px;padding:14px;margin-top:14px">
      <div style="white-space:pre-line;margin-bottom:10px">${esc(q.stem)}</div>
      ${keys.map(k =>
        `<div style="padding:3px 0;${k === q.answer ? 'color:#4caf50;font-weight:bold' : ''}">${esc(k)}. ${esc(q.options[k])}${k === q.answer ? ' ✓' : ''}</div>`
      ).join('')}
      <p style="margin-top:10px;line-height:1.7"><b>解析：</b>${esc(q.exp)}</p>
    </div>`;
}

let wrQ = [], wrI = 0;

function startWrongReview(){
  if(!requireReady()) return;
  wrQ = wrongDue().map(x => x.q);
  shuffle(wrQ);
  wrI = 0;
  if(!wrQ.length) return;
  drillQ = wrQ;
  drillI = 0;
  drillScore = 0;
  drillWrong = [];
  drillMode = 'wrong';
  goto('drill');
  showWrongQ();
}

function showWrongQ(){ showDrillQ(); }

/* ---------- 资料 ---------- */
async function renderMaterials(){
  const box = document.getElementById('materialsBox');
  if(!box) return;
  box.innerHTML = `
    <h2>学习资料（PDF）</h2>
    <p class="note" style="margin-bottom:14px">
      刷题题库来自 questions.json（已录入的选择题），PDF 资料需自行阅读，不会自动变成刷题。
      完整真题/模拟卷请在此打开 PDF。
    </p>
    <p class="note">加载中…</p>`;
  try{
    const res = await fetch(apiUrl('/api/materials'));
    if(!res.ok) throw new Error('http ' + res.status);
    const items = await res.json();
    if(!items.length){
      box.innerHTML += '<p class="note">未找到 PDF 资料夹</p>';
      return;
    }
    const groups = {};
    items.forEach(it => {
      (groups[it.group] = groups[it.group] || []).push(it);
    });
    let html = `
      <h2>学习资料（PDF）</h2>
      <p class="note" style="margin-bottom:14px">
        语法/搭配/翻译/作文等资料已整理进「复习资料」标签页，可在线阅读并标记进度；
        此处为原始 PDF，需要对照原文时使用。
      </p>`;
    for(const g of Object.keys(groups)){
      html += `<h2 style="font-size:15px;margin-top:12px">${esc(g)}</h2>`;
      groups[g].forEach(it => {
        const href = apiUrl(it.url);
        html += `<div class="mat-item"><span>${esc(it.name)}</span>
          <a href="${esc(href)}" target="_blank" rel="noopener">打开</a></div>`;
      });
    }
    box.innerHTML = html;
  }catch(e){
    box.innerHTML = `
      <h2>学习资料（PDF）</h2>
      <p class="note">${SERVER
        ? '无法加载资料列表，请确认服务器已启动。'
        : '手机版不含 PDF 资料；真题/模拟卷等 PDF 请在电脑端「资料」页查看。'}</p>`;
  }
}

/* ---------- 复习资料（study.json） ---------- */
const PAIR_PAGE = 60;

function studyMods(){ return (STUDY && STUDY.modules) || []; }

function studyDoneSet(modId){
  if(!S.study || typeof S.study !== 'object') S.study = {};
  return new Set(S.study[modId] || []);
}

function pairTable(items, swap, unitKey){
  let rows = '';
  items.forEach((it, i) => {
    const first = swap ? it.cn : it.en;
    const second = swap ? it.en : it.cn;
    rows += `<tr><td class="pen">${esc(first)}</td>
      <td class="pcn" data-u="${unitKey}" data-i="${i}">${esc(second)}</td></tr>`;
  });
  return `<table class="pair-tab">${rows}</table>`;
}

function studyUnits(mod){
  if(mod.kind === 'article')
    return (mod.sections || []).map((s, i) => ({
      key: 's' + i,
      title: s.t || ('第 ' + (i + 1) + ' 节'),
      html: `<div class="study-text">${esc(s.body)}</div>`
    }));
  if(mod.kind === 'essays')
    return (mod.items || []).map((it, i) => ({
      key: 'e' + i,
      title: it.t || ('范文 ' + (i + 1)),
      html: `<div class="study-text">${esc(it.body)}</div>`
    }));
  // pairs：有 groups 按组分；否则每 PAIR_PAGE 条一页
  const units = [];
  if(Array.isArray(mod.groups)){
    mod.groups.forEach((g, gi) => units.push({
      key: 'g' + gi,
      title: `${g.t}（${g.items.length} 条）`,
      html: pairTable(g.items, mod.swap, 'g' + gi)
    }));
  }else{
    const items = mod.items || [];
    for(let p = 0; p * PAIR_PAGE < items.length; p++){
      const slice = items.slice(p * PAIR_PAGE, (p + 1) * PAIR_PAGE);
      units.push({
        key: 'p' + p,
        title: `第 ${p * PAIR_PAGE + 1}–${p * PAIR_PAGE + slice.length} 条`,
        html: pairTable(slice, mod.swap, 'p' + p)
      });
    }
  }
  return units;
}

function renderStudy(){
  const box = document.getElementById('studyBox');
  if(!box) return;
  if(studyView) return renderStudyModule(box);
  const mods = studyMods();
  if(!mods.length){
    box.innerHTML = '<h2>复习资料</h2><p class="note">未找到 study.json，请重新生成。</p>';
    return;
  }
  const cats = {};
  mods.forEach(m => { (cats[m.cat] = cats[m.cat] || []).push(m); });
  let html = `<h2>复习资料</h2>
    <p class="note" style="margin-bottom:8px">
      语法讲解、固定搭配、同位词、完形、翻译、作文模板都已整理进来，点开即读，可标记「已读」跟踪进度。
    </p>`;
  for(const cat of Object.keys(cats)){
    html += `<h3 class="study-cat">${esc(cat)}</h3>`;
    cats[cat].forEach(m => {
      const total = studyUnits(m).length;
      const done = studyDoneSet(m.id).size;
      const pct = total ? Math.round(done / total * 100) : 0;
      html += `<div class="study-mod" onclick="openStudyModule('${m.id}')">
        <div><div class="sm-title">${esc(m.title)}</div>
        <div class="sm-meta">${total} 个单元 · ${esc(m.src || '')}</div></div>
        <div class="sm-prog">
          <div class="note">${done}/${total}</div>
          <div class="progress"><div style="width:${pct}%"></div></div>
        </div>
      </div>`;
    });
  }
  box.innerHTML = html;
}

function openStudyModule(id){
  studyView = id;
  renderStudy();
}

function closeStudyModule(){
  studyView = null;
  renderStudy();
}

function renderStudyModule(box){
  const mod = studyMods().find(m => m.id === studyView);
  if(!mod){ studyView = null; return renderStudy(); }
  const units = studyUnits(mod);
  const done = studyDoneSet(mod.id);
  const isPairs = mod.kind === 'pairs';
  let html = `<h2>${esc(mod.title)}</h2>
    <p class="note" style="margin-bottom:10px">
      <a href="javascript:closeStudyModule()" style="color:#8b5e3c">‹ 返回资料列表</a>
      　已完成 ${done.size}/${units.length}
      ${isPairs ? `　<button class="btn ghost" style="padding:3px 10px;font-size:12px" onclick="toggleStudyMask()">${studyMask ? '显示中文' : '遮挡中文'}</button>` : ''}
    </p>`;
  units.forEach(u => {
    const isDone = done.has(u.key);
    html += `<div class="study-unit${isDone ? ' done' : ''}" id="su-${u.key}">
      <div class="study-unit-head" onclick="toggleUnitOpen('${u.key}')">
        <span>${esc(u.title)}</span>
        <span class="su-done" onclick="event.stopPropagation();toggleStudyUnit('${mod.id}','${u.key}')">
          ${isDone ? '✓ 已读（点我取消）' : '标记已读'}
        </span>
      </div>
      <div class="study-unit-body${isPairs && studyMask ? ' mask-cn' : ''}">${u.html}</div>
    </div>`;
  });
  box.innerHTML = html;
}

function toggleUnitOpen(key){
  const el = document.getElementById('su-' + key);
  if(el) el.classList.toggle('open');
}

function toggleStudyMask(){
  studyMask = !studyMask;
  renderStudy();
}

function revealPair(el){
  el.classList.add('reveal');
}

function toggleStudyUnit(modId, key){
  if(!requireReady()) return;
  if(!S.study || typeof S.study !== 'object') S.study = {};
  const arr = S.study[modId] || [];
  const i = arr.indexOf(key);
  if(i >= 0) arr.splice(i, 1); else arr.push(key);
  S.study[modId] = arr;
  save();
  renderStudy();
}

/* ---------- 统计 ---------- */
function posGroup(pos){
  if(!pos) return '其他';
  if(pos.includes('n.')) return '名词';
  if(pos.includes('vt') || pos.includes('vi') || pos.match(/(^|\s)v\./)) return '动词';
  if(pos.includes('a.')) return '形容词';
  if(pos.includes('ad.')) return '副词';
  return '其他';
}

function renderStats(){
  const ws = Object.values(S.words);
  const mastered = ws.filter(r => r.st === 'mastered').length;
  const learning = ws.filter(r => r.st === 'learning').length;
  const activeDays = new Set([
    ...Object.keys(S.days),
    ...(S.act || []).map(t => localDateFromTs(t))
  ]).size;
  const quizzes = Object.values(S.days).filter(d => d.quiz != null);
  const avg = quizzes.length
    ? (quizzes.reduce((s, d) => s + d.quiz, 0) / quizzes.length).toFixed(1)
    : '-';
  document.getElementById('statGrid').innerHTML = `
    <div class="stat-box"><div class="num">${mastered}</div><div class="label">已掌握单词</div></div>
    <div class="stat-box"><div class="num">${learning}</div><div class="label">生词本（复习中）</div></div>
    <div class="stat-box"><div class="num">${activeDays}</div><div class="label">累计学习天数</div></div>
    <div class="stat-box"><div class="num">${avg}</div><div class="label">测验平均分</div></div>`;
  const bar = document.getElementById('vocabBar');
  if(bar) bar.style.width = (VOCAB.length ? mastered / VOCAB.length * 100 : 0).toFixed(1) + '%';

  const hist = ws.flatMap(r => r.hist || []);
  const rev = hist.filter(h => h.q >= 1);
  const kept = rev.filter(h => h.q >= 3).length;
  const retention = rev.length ? Math.round(kept / rev.length * 100) : null;

  const log = S.quizLog || [];
  const byDir = {};
  log.forEach(l => {
    const k = l.dir === 'e2c' ? '英 → 中' : '中 → 英';
    byDir[k] = byDir[k] || [0, 0];
    byDir[k][1]++;
    byDir[k][0] += l.ok;
  });

  const posMap = {};
  VOCAB.forEach(v => { posMap[v.w] = posGroup(v.pos); });
  const byPos = {};
  log.forEach(l => {
    const k = posMap[l.w] || '其他';
    byPos[k] = byPos[k] || [0, 0];
    byPos[k][1]++;
    byPos[k][0] += l.ok;
  });

  const hard = Object.entries(S.words)
    .filter(([, r]) => (r.lapses || 0) > 0)
    .sort((a, b) => (b[1].lapses || 0) - (a[1].lapses || 0))
    .slice(0, 8);

  const dayMin = {};
  (S.act || []).slice().sort((a, b) => a - b).forEach(t => {
    const d = localDateFromTs(t);
    dayMin[d] = dayMin[d] || { last: null, min: 0 };
    const e = dayMin[d];
    if(e.last && t - e.last < 5 * 60 * 1000) e.min += (t - e.last) / 60000;
    e.last = t;
  });
  const last7 = Object.keys(dayMin).sort().slice(-7);

  let html = '<div class="card"><h2>记忆与薄弱点分析</h2>';
  html += `<p style="margin-bottom:10px">复习记忆保持率：<b>${retention == null ? '暂无数据' : retention + '%'}</b>
    <span class="note">${retention == null ? '（复习几次后出数据）' : retention >= 85 ? '—— 很好，节奏合适' : retention >= 70 ? '—— 正常，继续' : '—— 偏低，建议每天新词减量'}</span></p>`;
  if(Object.keys(byDir).length){
    html += '<p style="margin:8px 0 4px"><b>测验方向正确率</b></p>';
    for(const k in byDir)
      html += `<p class="note">${k}：${Math.round(byDir[k][0] / byDir[k][1] * 100)}%（${byDir[k][0]}/${byDir[k][1]}）</p>`;
  }
  if(Object.keys(byPos).length){
    html += '<p style="margin:8px 0 4px"><b>按词性正确率</b></p>';
    for(const k in byPos)
      html += `<p class="note">${k}：${Math.round(byPos[k][0] / byPos[k][1] * 100)}%（${byPos[k][0]}/${byPos[k][1]}）</p>`;
  }
  if(hard.length){
    html += '<p style="margin:8px 0 4px"><b>最难缠的词（反复遗忘）</b></p><p class="note">' +
      hard.map(([w, r]) => `${esc(w)}（忘${r.lapses}次）`).join('、') + '</p>';
  }
  if(last7.length){
    html += '<p style="margin:8px 0 4px"><b>最近学习时长</b></p>' + last7.map(d =>
      `<div class="note">${esc(d)}<div class="progress" style="margin:3px 0"><div style="width:${Math.min(100, dayMin[d].min / 1.2)}%"></div></div>${Math.round(dayMin[d].min)} 分钟</div>`
    ).join('');
  }
  html += '<p class="note" style="margin-top:10px">💡 想要更深度分析？学习后回到对话对我说「分析一下我的进度」即可</p></div>';
  const old = document.getElementById('analysisCard');
  if(old) old.remove();
  const div = document.createElement('div');
  div.id = 'analysisCard';
  div.innerHTML = html;
  document.getElementById('tab-stats').appendChild(div);
}

/* ---------- 备份 ---------- */
async function exportData(){
  const json = JSON.stringify(S, null, 1);
  const fname = '学位英语进度备份_' + (CURRENT || 'user') + '_' + todayStr() + '.json';
  // App 内（Capacitor）：写缓存文件后调系统分享，可发微信/QQ/网盘
  const cap = window.Capacitor;
  if(cap && cap.isNativePlatform && cap.isNativePlatform() && cap.Plugins && cap.Plugins.Filesystem){
    try{
      const r = await cap.Plugins.Filesystem.writeFile({
        path: fname, data: json, directory: 'CACHE', recursive: true
      });
      if(cap.Plugins.Share){
        await cap.Plugins.Share.share({ title: '学习进度备份', text: '学习进度备份', url: r.uri, dialogTitle: '发送/保存进度备份' });
      }else{
        alert('已保存：' + r.uri);
      }
    }catch(e){
      if(e && e.message !== 'Share canceled') alert('导出失败：' + (e.message || e));
    }
    return;
  }
  const blob = new Blob([json], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = fname;
  a.click();
}

function importData(e){
  if(!requireReady()) return;
  const f = e.target.files[0];
  if(!f) return;
  const rd = new FileReader();
  rd.onload = () => {
    try{
      const data = JSON.parse(rd.result);
      if(!data || typeof data !== 'object') throw new Error('bad');
      S = data;
      ensurePlan();
      save();
      renderHome();
      alert('导入成功');
    }catch(err){
      alert('文件格式错误');
    }
  };
  rd.readAsText(f);
}

/* ---------- Boot ---------- */
function wireNav(){
  document.querySelectorAll('nav button').forEach(b => {
    b.onclick = () => {
      document.querySelectorAll('nav button').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      document.querySelectorAll('main > div').forEach(d => d.classList.add('hidden'));
      document.getElementById('tab-' + b.dataset.tab).classList.remove('hidden');
      const t = b.dataset.tab;
      if(t === 'home') renderHome();
      if(t === 'learn') startLearn();
      if(t === 'review') renderReview();
      if(t === 'stats') renderStats();
      if(t === 'quiz') renderQuizHome();
      if(t === 'drill') renderDrillHome();
      if(t === 'wrong') renderWrong();
      if(t === 'materials') renderMaterials();
      if(t === 'study') renderStudy();
    };
  });
}

(async function boot(){
  const bootEl = document.getElementById('boot');
  try{
    const [vRes, qRes, sRes] = await Promise.all([
      fetch('/vocab.json'),
      fetch('/questions.json'),
      fetch('/study.json')
    ]);
    if(!vRes.ok || !qRes.ok) throw new Error('load fail');
    VOCAB = await vRes.json();
    QUESTIONS = await qRes.json();
    if(sRes.ok) STUDY = await sRes.json();
    if(!Array.isArray(VOCAB)) VOCAB = [];
    if(!Array.isArray(QUESTIONS)) QUESTIONS = [];
    if(!STUDY || !Array.isArray(STUDY.modules)) STUDY = { modules: [] };
  }catch(e){
    if(bootEl) bootEl.textContent = '加载词库/题库失败，请确认已通过「启动学习系统.bat」访问本站';
    if(isFilePage()){
      alert('请先运行「启动学习系统.bat」，再用浏览器打开 http://localhost:5000（不要直接双击打开 HTML）');
    }
    return;
  }
  if(bootEl){
    bootEl.classList.add('hidden');
    bootEl.style.display = 'none';
  }
  wireNav();
  document.addEventListener('click', e => {
    if(e.target && e.target.classList && e.target.classList.contains('pcn'))
      e.target.classList.add('reveal');
  });
  await detectMode();
  showUserPicker();
})();
