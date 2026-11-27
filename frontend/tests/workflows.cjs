const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('frontend/app.js', 'utf8');
function extract(name, text=source) {
  const start = text.search(new RegExp(`(?:async )?function ${name}\\(`));
  assert.ok(start >= 0, name);
  const next = text.slice(start + 1).search(/\n(?:async )?function \w+\(/);
  return next < 0 ? text.slice(start) : text.slice(start, start + 1 + next);
}
function context(extra={}) {
  const elements = {};
  const alerts = [];
  const ctx = {Blob, File, FormData, crypto: require('node:crypto').webcrypto, console,
    document: {getElementById: id => elements[id] ||= {value:'',innerHTML:'',disabled:false}},
    alert: msg => alerts.push(msg), ...extra};
  vm.createContext(ctx);
  return {ctx,elements,alerts};
}
(async()=>{
  const {ctx, elements, alerts}=context({window:{EDU_GUARD_API_URL:'https://configured.example'}, API_BASE_URL:'https://default.example',
    parseJSONUpload:JSON.parse, getAuthHeaders:()=>({Authorization:'Bearer test'}), closeModal:()=>{}, getCurrentUser:()=>null});
  vm.runInContext(source.match(/^const WEEKLY_COLS = .+;$/m)[0] + extract('buildWeeklyCsvForWeek'),ctx);
  const row={Student_ID:'NEW1',Week_Number:7,Attendance_Percentage:60,IA_Marks:30,IA_Max:50,Backlog_Count:0,Fee_Outstanding:'No'};
  const csv=ctx.buildWeeklyCsvForWeek([row],2);
  assert.ok(csv.includes('IA_Max'));
  assert.ok(csv.includes('NEW1,7,60,30,50,'));
  assert.throws(()=>ctx.buildWeeklyCsvForWeek([{...row,Fee_Outstanding:''}],2),/required/);
  let captured;
  ctx.fetch=async(url, options)=>{captured={url,file:await options.body.get('file').text()};return {ok:true,json:async()=>({created:1,updated:0,skipped:0,errors:[]})}};
  ctx.facultyWeeklyUploadFile={name:'weekly.json',text:async()=>JSON.stringify([row])};
  elements.facultyWeekSelect={value:'2'};
  vm.runInContext(extract('submitFacultyWeeklyUpload'),ctx);
  await ctx.submitFacultyWeeklyUpload();
  assert.equal(captured.url,'https://configured.example/api/upload/weekly');
  assert.ok(captured.file.includes('NEW1,7,60,30,50,'));
  ctx.fetch=async()=>({ok:false,status:503,json:async()=>({detail:'Prediction unavailable; upload rolled back'})});
  await ctx.submitFacultyWeeklyUpload();
  assert.ok(alerts.at(-1).includes('rolled back'));

  const support=context({supportSubmissionKey:null,renderStudentHelpRequests:async()=>{}});
  support.elements.studentHelpCategory={value:'Academic'};
  support.elements.studentHelpMessage={value:'Please help'};
  support.ctx.fetchAPI=async()=>{throw new Error('network unavailable')};
  vm.runInContext(extract('submitStudentHelpRequest'),support.ctx);
  await support.ctx.submitStudentHelpRequest();
  assert.equal(support.elements.studentHelpMessage.value,'Please help');
  assert.ok(support.alerts.at(-1).includes('not confirmed'));
  support.ctx.fetchAPI=async()=>({id:1});
  await support.ctx.submitStudentHelpRequest();
  assert.equal(support.elements.studentHelpMessage.value,'');
  assert.ok(support.alerts.at(-1).includes('saved to the support inbox'));

  const auth=fs.readFileSync('frontend/auth.js','utf8');
  assert.ok(!extract('handleLogin',auth).includes('tryMockLogin('),'Backend rejection must not fall through to mock login');
  assert.ok(!source.includes('fetch("http://127.0.0.1:8000/api/upload'));
  console.log('Frontend workflow checks passed: upload scale/week, deployed URL, failed upload, request persistence/error, real login.');
})();
