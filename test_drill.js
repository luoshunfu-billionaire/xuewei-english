// test_drill.js
const assert = require('assert');
const fs = require('fs');
const SRC = fs.readFileSync('static/app.js', 'utf8');

// 按花括号配平提取某标识符定义段的源码（function 或整块注释区间）
function grabFn(name) {
  const re = new RegExp('function ' + name + '\\s*\\(([^)]*)\\)\\s*\\{');
  const m = re.exec(SRC);
  if (!m) throw new Error('未找到函数 ' + name);
  const start = src_braceStart(m.index);
  return SRC.slice(m.index, start.end + 1);
}
function src_braceStart(idx) {
  const start = SRC.indexOf('{', idx);
  let depth = 0;
  for (let j = start; j < SRC.length; j++) {
    if (SRC[j] === '{') depth++;
    if (SRC[j] === '}') { depth--; if (depth === 0) return { end: j }; }
  }
  throw new Error('花括号未配平');
}

// 依赖纯函数（真代码）
const depsCode = ['todayStr', 'addDays', 'cmpDate', 'now'].map(grabFn).join('\n');
// 刷题纯函数块（真代码，Step 3 里这五个函数连续排列）
const drillCode = ['ensureDrillProg', 'recordDrill', 'drillStat', 'dueDrills', 'srcList'].map(grabFn).join('\n');

// 用 new Function 注入可变依赖，构建被测模块。S/QUESTIONS/REVIEW_IV 注入；TODAY 用闭包内变量以便改写。
function build(S, QUESTIONS, TODAY) {
  const factory = new Function(
    'S', 'QUESTIONS', 'REVIEW_IV', 'TODAY',
    depsCode + '\n' +
    // 让 todayStr 用注入的 TODAY（覆盖真 todayStr）
    'function todayStr(){ return TODAY; }\n' +
    drillCode + '\n' +
    'return { ensureDrillProg, recordDrill, drillStat, dueDrills, srcList, addDays };'
  );
  return factory(S, QUESTIONS, [1, 3, 7, 15], TODAY);
}

const QUESTIONS = [
  { id: 'q1', src: '卷A', part: '词汇语法' },
  { id: 'q2', src: '卷A', part: '词汇语法' },
  { id: 'q3', src: '卷B', part: '阅读理解' },
];
const REVIEW_IV = [1, 3, 7, 15];
let TODAY = '2026-07-29';

// 每次用例重建，保证 S 隔离
function fresh() { const S = {}; const m = build(S, QUESTIONS, TODAY); m.S = S; return m; }

// 测试 1：首次作答答对
let m = fresh();
let r = m.recordDrill('q1', true);
assert.strictEqual(r.n, 1);
assert.strictEqual(r.ok, 1);
assert.strictEqual(r.lastOk, 1);
assert.strictEqual(r.stage, 1);
assert.strictEqual(r.due, m.addDays(TODAY, REVIEW_IV[1])); // stage=1 -> +3

// 测试 2：答错重置 stage、due=明天
r = m.recordDrill('q1', false);
assert.strictEqual(r.n, 2);
assert.strictEqual(r.ok, 1);
assert.strictEqual(r.lastOk, 0);
assert.strictEqual(r.stage, 0);
assert.strictEqual(r.due, m.addDays(TODAY, 1));

// 测试 3：drillStat 聚合
const st = m.drillStat('q1');
assert.strictEqual(st.n, 2);
assert.strictEqual(st.ok, 1);
assert.strictEqual(st.acc, 50);
assert.strictEqual(m.drillStat('q_nope'), null);

// 测试 4：dueDrills 只含 due<=今天且未巩固且题存在（明天该出现 q1）
m = build(m.S, QUESTIONS, m.addDays(TODAY, 1)); // 到明天
assert.ok(m.dueDrills().some(q => q.id === 'q1'));

// 测试 5：连对 REVIEW_IV.length 次后巩固，不再进 due
m = fresh();
for (let i = 0; i < REVIEW_IV.length; i++) m.recordDrill('q2', true);
assert.strictEqual(m.drillStat('q2').cleared, true);
assert.ok(!m.dueDrills().some(q => q.id === 'q2'));

// 测试 6：srcList 聚合套卷进度
m = fresh();
m.recordDrill('q1', true);
m.recordDrill('q2', false);
const a = m.srcList().find(s => s.src === '卷A');
assert.strictEqual(a.total, 2);
assert.strictEqual(a.done, 2);
assert.strictEqual(a.ok, 1);
assert.strictEqual(a.acc, 50);

console.log('全部通过');
