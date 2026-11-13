(()=>{
const $=id=>document.getElementById(id);
const V=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const colors=()=>({line:V("--accent"),cyan:V("--cyan"),warn:V("--warn"),bad:V("--bad"),obs:V("--obs"),pred:V("--pred"),grid:V("--grid"),geo:V("--geo"),mute:V("--mute"),vline:V("--line2"),mono:V("--mono")});
let K=colors();
const px=n=>parseFloat(V(n))||10;
const chartFont=(n="--fs-chart",family=K.mono)=>px(n)+"px "+family;
const PARAM={delta1:["δ1 J1 零点","°"],delta2:["δ2 J2 零点","°"],delta3:["δ3 J3 零点","°"],h:["h 肩高","mm"],L1:["L1 大臂","mm"],L2:["L2 小臂","mm"],e:["e 延长","mm"],beta:["β 激光俯仰","°"],gamma:["γ 激光偏摆","°"],x_b:["x_b 底座 X","mm"],y_b:["y_b 底座 Y","mm"],psi_b:["ψ_b 底座朝向","°"]};
const CODE={H1:"J1 零点偏移",H2:"J2 零点偏移",H3:"末端延长变化",H4:"底座位姿变化",H6:"全参数重标定"};
const BUSY=["发现异常","认旧状态","诊断","校准","护栏"];
const FEED=new Set(["estop","estop_reset","alarm","switch","version_committed","rejected","rollback","retrained","damage_injected","manual_switch"]);
const DMG={j1:"J1 错位",j2:"J2 错位",extension:"延长杆",base_x:"底座平移 X",base_y:"底座平移 Y",base_rotation:"底座旋转",weight:"加配重",loose:"松动",restore:"复原所有伤",combination:"组合伤"};
function evText(e){const d=e.data||{};switch(e.kind){
  case"estop":return["bad","已急停，禁止动作与出光"];
  case"estop_reset":return["info","已解除急停"];
  case"alarm":return["bad",`发现异常，开始自愈（第 ${d.count} 次报警）`];
  case"switch":return["info",`认出旧伤，${d.probe_shots||3} 发切回 ${d.version_id}`];
  case"version_committed":{const k=(d.meta||{}).kind;return["ok",`启用 ${d.version_id}`+({baseline:"（首次标定）",geometry:"（自愈修复）",residual:"（细节补偿）",initial:"（初始）"}[k]||"")]}
  case"rejected":return["bad",`候选 ${d.version_id} 未通过护栏`];
  case"rollback":return["info",`版本 ${d.from} → ${d.to}`];
  case"retrained":return[d.accepted?"ok":"busy",d.accepted?"补偿重训完成并启用":"补偿重训未带来改善，保留旧模型"];
  case"damage_injected":{const g=d.damage||{};return["busy",`仿真注入：${DMG[g.kind]||g.kind}${g.amount?" "+g.amount+(g.kind==="j1"||g.kind==="j2"?" 格":g.kind==="base_rotation"?"°":" mm"):""}`]}
  case"manual_switch":return["info",`手动${d.undo?"撤销":"切换"} ${d.from} → ${d.to}${d.forced?"（强制）":""}`];}
  return["",e.kind]}
function renderFeed(){const ev=(S.events||[]).filter(e=>e.kind!=="rollback").slice(-40).reverse();
  const key=ev.length+":"+(ev.length?ev[0].timestamp:0);if(key===feedKey)return;feedKey=key;
  $("feed").innerHTML=ev.length?ev.map(e=>{const[c,t]=evText(e);return `<div class="ev"><time>${clock(e.timestamp)}</time><i class="${c}"></i><span>${esc(t)}</span></div>`}).join(""):'<div class="empty">还没有事件</div>'}
let diagOpen=false,minorOpen=false,diagKey="",feedKey="",histKey="",hoverI=null,EC=null,S=null,busy=false,imgQueued=false,undoTimer=null,modalVersion=null,modalErr="",docLoaded=false,raf=0;

let connected=false,wsSnapshot=false,retryDelay=500,activeCommand=null,versionsKey="",modalKey="",modalAction=null,modalTrigger=null;
const f=(v,d=1)=>v==null||!isFinite(v)?"—":Number(v).toFixed(d);
const mag=r=>r?Math.hypot(r[0],r[1]):null;
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const codeName=n=>!n?"":n.startsWith("H5:")?"两组同时："+n.slice(3).split("+").map(c=>CODE[c]||c).join(" + "):(CODE[n]||n);
const signed=(v,d=1)=>{if(v==null||!isFinite(v))return"—";const t=Math.abs(v).toFixed(d);return(+t===0?"":v>0?"+":"−")+t};
const tableNumber=(v,d=2)=>signed(v,d).replace(/^\+/,"");
const clock=t=>new Date(t*1000).toLocaleTimeString("zh-CN",{hour12:false});
const roleName=r=>({task:"常规",baseline_fit:"标定拟合",baseline_holdout:"标定验证",recognition:"认旧探测",diagnostic:"诊断",active_diagnostic:"主动诊断",guard:"护栏验证",preview:"预检"}[r]||r);
function dur(s){if(s==null)return"—";s=Math.floor(s);const h=Math.floor(s/3600),m=Math.floor(s%3600/60);return h?`${h} 时 ${m} 分`:m?`${m} 分 ${s%60} 秒`:`${s} 秒`}

/* Split a correction into the few changes that matter and the small tweaks around them. */
function deltaParts(d){
  const all=Object.entries(d.deltas||{}).filter(([k,x])=>Math.abs(x)>1e-6).map(([k,x])=>{const g=(d.gear_steps||{})[k],p=PARAM[k]||[k,""],deg=p[1]==="°";
    const val=`${signed(x,2)}${deg?"°":" "+p[1]}${g?`（${signed(g,0)} 格）`:""}`;
    return{score:Math.abs(x)/(deg?2:5)+(g?100:0),short:p[0].split(" ")[0]+" "+val,full:p[0]+" "+val}}).sort((a,b)=>b.score-a.score);
  let major=all.filter(p=>p.score>=1);if(!major.length)major=all.slice(0,1);
  return{major,minor:all.filter(p=>!major.includes(p))};
}
function deltaText(d){const{major,minor}=deltaParts(d);return major.map(p=>p.short).join("，")+(minor.length?` 等 ${major.length+minor.length} 项`:"")}
function versionWhat(v){
  const m=v.meta||{};
  if(m.kind==="initial")return"初始名义参数";
  if(m.kind==="baseline")return"首次标定";
  if(m.kind==="residual")return"细节补偿 "+v.residual_id;
  if(m.kind==="geometry"&&m.diagnosis)return m.diagnosis.best.name.split(":")[0]+" "+(deltaText(m.diagnosis)||codeName(m.diagnosis.best.name));
  if(m.kind==="insufficient_observations")return"观测不足";
  return m.kind||"";
}
function versionTime(v){const t=(v.meta||{}).created;return t?new Date(t*1000).toLocaleTimeString("zh-CN",{hour12:false}):""}

/* networking: only a fresh WebSocket snapshot makes commands available. */
const ERR={
  "machine busy; preview needs an idle arm":"机械臂正忙，预检需要空闲状态",
  "machine busy; wait for the current operation":"机械臂正忙，请等待当前操作完成",
  "run a fresh preview of this version before switching":"请先对该版本做预检",
  "preview did not pass; switching needs force":"预检未通过，需勾选“强制切换”",
  "confirmation does not match the selected version":"确认的版本号不一致",
  "resolve the geometry anomaly before residual training":"请先解决几何异常再重训补偿",
  "not enough clean samples to train":"可用的正常打靶数据不足，请继续自检积累数据",
  "temporal holdout must be strictly after all training data":"验证数据的时间必须晚于全部训练数据",
  "unknown command":"无法识别的操作",
  "damage injection is simulation-only":"伤注入仅可在仿真模式使用",
  "invalid version id":"版本号格式不正确",
  "cannot activate a rejected version":"不能启用未通过验证的版本",
  "component must be both, geometry or residual":"请选择完整版本、几何或细节补偿",
  "invalid residual artifact id":"补偿模型编号不正确",
  "invalid movement":"动作超出限位或参数无效",
  "fitting needs observations and free parameters":"校准缺少观测数据或可拟合参数",
  "invalid free parameter list":"拟合参数列表无效",
  "no measured points for diagnosis":"没有可用于诊断的实测落点",
  "no unused valid discriminating pose":"没有剩余的有效诊断姿势",
  "invalid GP training shapes":"补偿训练数据的维度不正确",
  "nonfinite GP training data":"补偿训练数据包含无效数值",
  "cannot save an unfitted GP":"补偿模型尚未训练，无法保存",
  "unsupported GP artifact":"补偿模型文件格式不受支持",
  "not a ZeroResidual artifact":"零补偿模型文件格式不正确",
  "holdout median exceeds 3 mm":"验证姿势上的误差中位数仍大于 3 mm",
  "holdout improvement below 70 percent":"新版本比旧版本改善不足 70%",
  "parameter bounds exceeded":"拟合出的参数超出物理范围",
  "missing observations or invalid holdout poses":"验证姿势打不到靶板或看不到光点",
  "optimizer failed":"优化器没有收敛",
  "unknown damage {damage.kind}":"无法识别的仿真伤类型",
  "damage exceeds {name} bounds":"注入伤幅度超出物理范围",
  "required data file not found":"找不到所需的版本或模型文件",
  "required field missing: {field}":"请求或数据文件缺少必要字段",
  "emergency stop active; reset before operating":"已急停，请先解除急停再操作",
  "operation still stopping; wait before resetting emergency stop":"流程正在中止，请稍后解除急停",
  "laser shutdown failed; cannot reset emergency stop":"激光关闭失败，不能解除急停，请检查硬件",
  "laser shutdown failed; check hardware emergency stop":"激光关闭未确认，请使用硬件急停并检查设备",
  "no camera attached":"尚未连接摄像头",
  "frame encoding failed":"摄像头画面编码失败",
  "fault code document missing":"找不到故障码文档",
  "static file not found":"找不到界面资源"
};
function tr(message){
  const m=String(message||"未知错误").replace(/^['"]|['"]$/g,"");
  if(ERR[m])return ERR[m];
  for(const [key,value] of Object.entries(ERR)){
    if(!key.includes("{"))continue;
    const pattern=key.split(/\{[^}]+\}/).map(x=>x.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")).join(".+");
    if(new RegExp("^"+pattern+"$").test(m))return value;
  }
  return /[\u3400-\u9fff]/.test(m)?m:"操作失败，错误信息："+m;
}
const ACTION_LABELS={selfcheck:"自检中…",baseline:"标定中…",retrain:"重训中…",preview:"试打中…",switch:"切换中…",inject:"注入中…",reset_estop:"解除中…"};
async function command(name,payload={}){
  if(!connected)throw new Error("连接断开，数据已过期，请等待重连");
  const urgent=name==="estop";
  if(!urgent&&(busy||S?.busy))throw new Error("上一个操作还在执行");
  if(!urgent){busy=true;activeCommand=name}syncControls();
  try{const r=await fetch("/api/command/"+name,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    const body=await r.json().catch(()=>({}));
    if(!r.ok)throw new Error(tr(body.detail||("HTTP "+r.status)));
    return body}
  finally{if(!urgent){busy=false;activeCommand=null}syncControls()}
}
function syncControls(){
  const running=busy||S?.busy,action=activeCommand||S?.active_command;
  document.querySelectorAll("[data-cmd],[data-command]").forEach(b=>{
    const name=b.dataset.cmd||b.dataset.command;
    b.disabled=!connected||(name!=="estop"&&(running||(S?.estop&&name!=="reset_estop")));
    b.setAttribute("aria-busy",String(!!running&&action===name));
    if(!b.dataset.label)b.dataset.label=b.textContent;
    b.textContent=running&&action===name?(ACTION_LABELS[name]||"执行中…"):b.dataset.label;
  });
}
function connectionState(ok,message="连接断开，数据已过期，正在重连…"){
  connected=ok;document.body.classList.toggle("stale",!ok);
  $("dot").classList.toggle("on",ok);$("conn").textContent=ok?"实时连接":message;
  $("connectionbar").hidden=ok;$("connectionbar").textContent=message;
  if(!ok){$("chipstate").textContent="连接断开";$("chipstate").className="chip state s-bad";stopCamera()}
  syncControls();schedule();announce();
}
function connect(){
  const ws=new WebSocket((location.protocol==="https:"?"wss://":"ws://")+location.host+"/ws");
  ws.onmessage=ev=>{const e=JSON.parse(ev.data);if(e.kind==="snapshot"){wsSnapshot=true;retryDelay=500;connectionState(true)}handle(e)};
  ws.onerror=()=>ws.close();
  ws.onclose=()=>{connectionState(false);setTimeout(connect,retryDelay);retryDelay=Math.min(10000,retryDelay*2)};
}
function handle(e){
  if(e.kind==="snapshot"){S=Object.assign(S||{},e.data.snapshot);refreshCamera()}
  else if(!S)return;
  else if(["state","operation","estop","estop_reset","safety","laser"].includes(e.kind))Object.assign(S,e.data);
  else if(e.kind==="shot"){S.recent=[...(S.recent||[]),e.data.shot].slice(-(S.history_limit||200));S.shots=(S.shots||0)+1;refreshCamera()}
  else if(e.kind==="diagnosis")S.diagnosis=e.data.diagnosis;
  else if(e.kind==="preview")S.preview=e.data.preview;
  else if(!FEED.has(e.kind))return;
  if(FEED.has(e.kind))S.events=[...(S.events||[]),e].slice(-(S.history_limit||200));
  syncControls();schedule();
}
function schedule(){if(!raf)raf=requestAnimationFrame(()=>{raf=0;render()})}
/* Optional modules (digital twin, presentation mode) only ever see this event, never app internals. */
function announce(){document.dispatchEvent(new CustomEvent("rearm:state",{detail:{state:S,connected}}))}
document.addEventListener("rearm:theme",()=>{schedule()});
document.addEventListener("rearm:modules-ready",announce);
let cameraRequest=null,cameraTimer=null;
const cameraFrame=document.createElement("canvas");
function stopCamera(){
  const source=cameraRequest;cameraRequest=null;
  clearInterval(cameraTimer);cameraTimer=null;imgQueued=false;
  if(source){source.onload=source.onerror=null;source.removeAttribute("src")}
}
function showCameraFrame(source){
  if(source!==cameraRequest||!connected||!source.naturalWidth||!source.naturalHeight)return;
  if(cameraFrame.width!==source.naturalWidth)cameraFrame.width=source.naturalWidth;
  if(cameraFrame.height!==source.naturalHeight)cameraFrame.height=source.naturalHeight;
  cameraFrame.getContext("2d").drawImage(source,0,0);
  // The visible image only receives decoded, local frames, never a network URL.
  const img=$("camimg");img.src=cameraFrame.toDataURL();img.hidden=false;
}
function refreshCamera(){
  if(!S||!connected)return;
  if(cameraRequest){if(S.simulation)imgQueued=true;return}
  const stream=!S.simulation,source=cameraRequest=new Image();
  const finish=()=>{if(source!==cameraRequest)return;const queued=imgQueued;stopCamera();if(queued)refreshCamera()};
  source.onload=()=>{showCameraFrame(source);if(!stream)finish()};
  source.onerror=finish;
  // MJPEG may not emit load until the stream ends; sample its decoded frames at 5 fps.
  if(stream)cameraTimer=setInterval(()=>showCameraFrame(source),200);
  source.src=stream?"/api/camera.mjpg":"/api/camera.jpg?t="+Date.now();
}

/* home */
function render(){
  K=colors();
  if(!S)return;
  $("mode").hidden=!S.simulation;$("debugtoggle").hidden=!S.simulation;$("cam").classList.toggle("sim",!!S.simulation);
  const head=S.head||{},recent=S.recent||[],last=recent[recent.length-1],alarm=S.alarm_mm||6;
  $("vcur").textContent=head.id?head.id:"—";
  const st=!connected?"连接断开":S.estop?"已急停":S.state||"—",cs=$("chipstate");
  cs.className="chip state "+(st==="正常"?"s-ok":["已拒绝","已急停","连接断开"].includes(st)?"s-bad":st==="重训残差"?"s-info":"s-busy");
  cs.textContent=st+(BUSY.includes(st)&&S.heal_start!=null?` · 已打 ${Math.max(0,S.shots-S.heal_start)} 发`:"");
  $("estopbar").hidden=!S.estop;
  $("stopdetail").textContent=S.estop_error?tr(S.estop_error):"已禁止动作与出光";
  $("chiplaser").textContent=!connected?"激光 未知":S.laser_on?"激光 开":"激光 关";
  $("chiplaser").classList.toggle("laser-on",connected&&!!S.laser_on);
  syncControls();
  $("chipver").textContent="当前版本 "+(head.id||"—");
  const err=last?mag(last.residual):null,ce=$("chiperr");
  ce.className="chip err "+(err==null?"s-info":err>alarm?"s-bad":"s-ok");
  ce.textContent=last?(err==null?"未看到光点":"误差 "+f(err,2)+" mm"):"等待第一发";
  drawOverlay(recent);
  $("k-err").innerHTML=err==null?"—":`<span class="${err>alarm?"badc":""}">${f(err,2)}</span><small>mm</small>`;
  $("k-err-d").textContent=`报警阈值 ${f(alarm,0)} mm`+(last?` · ${roleName(last.role)}`:"");
  const comp=compensation();
  if(comp){const gain=(comp.geometry_median-comp.new_median)/comp.geometry_median*100;
    $("k-comp").innerHTML=`<span class="goodc">−${f(gain,0)}</span><small>%</small>`;$("k-comp-d").textContent=`${f(comp.geometry_median,2)} → ${f(comp.new_median,2)} mm（${head.residual_id}）`}
  else{const learned=(S.versions||[]).some(v=>v.residual_id!=="zero");
    $("k-comp").innerHTML=`<span style="color:var(--mute)">${learned?"需重训":"未学习"}</span>`;
    $("k-comp-d").textContent=learned?"几何参数已更新，旧补偿停用，需重训":"在右上角 ⋯ 里重训补偿后生效"}
  const st2=S.stats||{};
  $("k-shots").textContent=S.shots||0;$("k-shots-d").textContent="运行 "+dur(st2.uptime_s)+" · 报警 "+(S.alarms||0)+" 次";
  $("k-heal").innerHTML=`${(st2.recoveries||0)+(st2.recognitions||0)}<small>次</small>`;
  $("k-heal-d").textContent=`诊断修复 ${st2.recoveries||0} · 认出旧伤 ${st2.recognitions||0}`;
  const lim=S.joint_limits||[[-90,90],[0,110],[-150,0]],q=last?last.q:null;
  $("joints").innerHTML=["J1 底座","J2 大臂","J3 小臂"].map((n,i)=>{const[lo,hi]=lim[i],v=q?q[i]:null,p=v==null?null:(v-lo)/(hi-lo)*100;
    return `<div class="joint"><span class="n">${n}</span><div class="bar" title="限位 ${lo}° ~ ${hi}°">${p==null?"":`<i style="left:calc(${p}% - 1px)"></i>`}</div><span class="num" style="text-align:right">${v==null?"—":signed(v)+"°"}</span></div>`}).join("");
  $("e-load").textContent=last?f(last.load*100,0)+"%":"—";$("e-temp").textContent=last?f(last.temperature,1)+" °C":"—";$("e-volt").textContent=last?f(last.voltage,1)+" V":"—";
  drawErr();renderDiag();drawLearn(comp);renderVersions();renderOverview();renderFeed();
  if(modalVersion)renderModal();updateChartLabels();announce();
}
function toPx(xy){const c=S.camera||{width:1000,height:760,pixels_per_mm:2};return[c.width/2+xy[0]*c.pixels_per_mm,c.height/2-xy[1]*c.pixels_per_mm]}
function drawOverlay(recent){
  const c=S.camera||{width:1000,height:760,pixels_per_mm:2},svg=$("overlay");
  svg.setAttribute("viewBox",`0 0 ${c.width} ${c.height}`);$("cam").style.setProperty("--cam-ar",`${c.width}/${c.height}`);
  const b=S.board_mm||[420,297],[x0,y0]=toPx([-b[0]/2,b[1]/2]);
  let h=`<rect x="${x0}" y="${y0}" width="${b[0]*c.pixels_per_mm}" height="${b[1]*c.pixels_per_mm}" fill="none" stroke="${K.vline}" stroke-width="2" stroke-dasharray="8 6" opacity=".7"/>`;
  for(const s of recent.slice(-15,-1))if(s.observed){const[x,y]=toPx(s.observed);h+=`<circle cx="${x}" cy="${y}" r="4" fill="${K.obs}" opacity=".35"/>`}
  const last=recent[recent.length-1];
  if(last){const[px,py]=toPx(last.predicted);
    if(last.observed){const[ox,oy]=toPx(last.observed);h+=`<line x1="${px}" y1="${py}" x2="${ox}" y2="${oy}" stroke="${K.obs}" stroke-width="2" stroke-dasharray="6 4"/><circle cx="${ox}" cy="${oy}" r="13" fill="none" stroke="${K.obs}" stroke-width="2"/><circle cx="${ox}" cy="${oy}" r="5" fill="${K.obs}"/>`}
    h+=`<path d="M${px-11} ${py-11}L${px+11} ${py+11}M${px+11} ${py-11}L${px-11} ${py+11}" stroke="${K.pred}" stroke-width="3.5"/>`}
  svg.innerHTML=h;
}
function setupCanvas(cv){const r=cv.getBoundingClientRect(),d=devicePixelRatio||1;cv.width=Math.max(1,r.width*d);cv.height=Math.max(1,r.height*d);const g=cv.getContext("2d");g.setTransform(d,0,0,d,0,0);g.clearRect(0,0,r.width,r.height);return[g,r.width,r.height]}
function nice(v){const p=10**Math.floor(Math.log10(v/4)),step=[1,2,5,10].map(m=>m*p).find(x=>v/x<=4);return[Math.ceil(v/step-1e-9)*step,step]}
function axes(g,w,h,ymax,step,pad){const scale=px("--fs-chart")/10;g.font=chartFont();g.fillStyle=K.mute;g.strokeStyle=K.grid;g.lineWidth=1;g.textAlign="left";const d=step>=1?0:step>=.1?1:2;
  for(let v=0;v<=ymax+1e-9;v+=step){const y=pad.t+(h-pad.t-pad.b)*(1-v/ymax);g.beginPath();g.moveTo(pad.l,y);g.lineTo(w-pad.r,y);g.stroke();g.fillText(f(v,d),2*scale,y+3*scale)}}
function emptyChart(g,h,pad,msg){g.fillStyle=K.mute;g.font=chartFont("--fs-chart-empty",V("--sans"));g.textAlign="left";g.fillText(msg,pad.l,h/2)}
/* Log scale: a healthy arm sits near 1 mm and a damaged one near 100 mm, and both must stay readable. */
function drawErr(){
  const[g,w,h]=setupCanvas($("errchart")),rec=(S.recent||[]).slice(-120),alarm=S.alarm_mm||6,scale=px("--fs-chart")/10,pad={l:30*scale,r:8*scale,t:10*scale,b:18*scale};
  EC=null;
  if(!rec.length)return emptyChart(g,h,pad,"点“自检”开始打靶");
  const vals=rec.map(s=>mag(s.residual)),FLOOR=.1,top=Math.max(alarm*3,...vals.filter(v=>v!=null))*1.5,lo=Math.log10(FLOOR),span=Math.log10(top)-lo;
  const X=i=>pad.l+(w-pad.l-pad.r)*(rec.length<2?.5:i/(rec.length-1)),Y=v=>pad.t+(h-pad.t-pad.b)*(1-(Math.log10(Math.max(v,FLOOR))-lo)/span),base=h-pad.b;
  g.font=chartFont();g.lineWidth=1;g.textAlign="left";
  for(let t=FLOOR;t<=top;t*=10){const y=Y(t);g.strokeStyle=K.grid;g.beginPath();g.moveTo(pad.l,y);g.lineTo(w-pad.r,y);g.stroke();g.fillStyle=K.mute;g.fillText(t<1?"0.1":String(Math.round(t)),2*scale,y+3*scale)}
  g.strokeStyle=K.vline;g.setLineDash([2,3]);let lastLabel=-99*scale;
  for(let i=1;i<rec.length;i++)if(rec[i].version_id!==rec[i-1].version_id&&rec[i].role!=="preview"&&rec[i-1].role!=="preview"){g.beginPath();g.moveTo(X(i),pad.t);g.lineTo(X(i),base);g.stroke();
    if(X(i)-lastLabel>44*scale&&X(i)<w-pad.r-40*scale){g.fillStyle=K.mute;g.fillText(rec[i].version_id,X(i)+3*scale,pad.t+7*scale);lastLabel=X(i)}}
  g.setLineDash([5,4]);g.strokeStyle=K.warn;g.beginPath();g.moveTo(pad.l,Y(alarm));g.lineTo(w-pad.r,Y(alarm));g.stroke();g.setLineDash([]);
  g.fillStyle=K.warn;g.textAlign="right";g.fillText("报警 "+f(alarm,0),w-pad.r,Y(alarm)-4*scale);g.textAlign="left";
  const grad=g.createLinearGradient(0,pad.t,0,base);grad.addColorStop(0,"rgba(61,139,255,.28)");grad.addColorStop(1,"rgba(61,139,255,0)");
  g.fillStyle=grad;g.beginPath();vals.forEach((v,i)=>{const y=v==null?base:Y(v);i?g.lineTo(X(i),y):g.moveTo(X(i),y)});g.lineTo(X(vals.length-1),base);g.lineTo(X(0),base);g.closePath();g.fill();
  g.strokeStyle=K.line;g.lineWidth=1.5;g.lineJoin="round";g.beginPath();let on=false;vals.forEach((v,i)=>{if(v==null){on=false;return}on?g.lineTo(X(i),Y(v)):g.moveTo(X(i),Y(v));on=true});g.stroke();
  vals.forEach((v,i)=>{if(v==null||v<=alarm)return;g.fillStyle=K.bad;g.beginPath();g.arc(X(i),Y(v),2,0,7);g.fill()});
  const seq0=(S.shots||rec.length)-rec.length+1;
  g.fillStyle=K.mute;g.fillText("第 "+seq0+" 发",pad.l,h-3*scale);g.textAlign="right";g.fillText("第 "+(seq0+rec.length-1)+" 发",w-pad.r,h-3*scale);g.textAlign="left";
  EC={rec,vals,seq0,pad,w};
  if(hoverI!=null){const i=Math.min(hoverI,rec.length-1),v=vals[i];g.strokeStyle=K.mute;g.lineWidth=1;g.beginPath();g.moveTo(X(i),pad.t);g.lineTo(X(i),base);g.stroke();
    if(v!=null){g.fillStyle=v>alarm?K.bad:K.line;g.strokeStyle="#fff";g.beginPath();g.arc(X(i),Y(v),3.5,0,7);g.fill();g.stroke()}}
}
function hoverErr(e){
  if(!EC)return;const cv=$("errchart"),r=cv.getBoundingClientRect(),n=EC.rec.length,tip=$("tip");
  const i=n<2?0:Math.max(0,Math.min(n-1,Math.round((e.clientX-r.left-EC.pad.l)/(EC.w-EC.pad.l-EC.pad.r)*(n-1))));
  hoverI=i;drawErr();const s=EC.rec[i],v=EC.vals[i];
  tip.innerHTML=`<b>第 ${EC.seq0+i} 发</b>${v==null?"未看到光点":f(v,2)+" mm"}<br>${esc(roleName(s.role))} · ${esc(s.version_id)} · ${clock(s.timestamp)}`;
  tip.style.display="block";tip.style.left=Math.max(8,Math.min(innerWidth-tip.offsetWidth-8,e.clientX+14))+"px";tip.style.top=Math.max(8,e.clientY-tip.offsetHeight-10)+"px";
}
function renderDiag(){
  const d=S.diagnosis;if(!d){$("diagaside").textContent="";return}
  const key=[d.best.name,d.ranked.length,d.ranked[0].bic,diagOpen,minorOpen].join("|");if(key===diagKey)return;diagKey=key;
  $("diagaside").textContent="按 BIC 排序，越小越可信";
  const best=d.ranked[0].bic,{major,minor}=deltaParts(d),concl=d.changes&&d.changes.length===1?d.changes[0]:d.best.name;
  const shown=diagOpen?d.ranked:d.ranked.slice(0,6);
  const free=r=>r.fit.free.length>4?`${r.fit.free.length} 个参数`:r.fit.free.map(k=>(PARAM[k]||[k])[0].split(" ")[0]).join(", ");
  const rows=shown.map((r,i)=>`<tr class="${i===0?"best":""}"><td title="${esc(codeName(r.name))}">${esc(r.name)}</td><td title="${esc(r.fit.free.map(k=>(PARAM[k]||[k])[0]).join("、"))}">${esc(free(r))}</td><td class="r num">${f(r.fit.rms,2)}</td><td class="r num">${f(r.bic,1)}</td><td class="r num">${i===0?"—":"+"+f(r.bic-best,1)}</td></tr>`).join("");
  const minorText=minor.map(p=>p.short).join("，");
  $("diag").innerHTML=`<div class="concl">${esc(concl)} · ${esc(codeName(concl))}</div>
    ${major.length?`<div class="fixes">${major.map(p=>`<span class="fix num">${esc(p.full)}</span>`).join("")}${minor.length?`<button class="morefix" id="minorbtn" title="${esc(minorText)}">${minorOpen?"收起微调":`另有 ${minor.length} 项微调`}</button>`:""}</div>`:'<div class="note">无参数变化</div>'}
    ${minorOpen&&minor.length?`<div class="note num">${esc(minorText)}</div>`:""}${(d.ambiguous||[]).length?'<div class="note">注意：J1 零点与底座朝向无法仅凭落点区分</div>':""}
    <div style="overflow-x:auto"><table class="diagt"><colgroup><col class="c1"><col class="c2"><col><col><col></colgroup><thead><tr><th>码</th><th>放开参数</th><th class="r">RMS mm</th><th class="r">BIC</th><th class="r">ΔBIC</th></tr></thead><tbody>${rows}</tbody></table></div>${d.ranked.length>6?`<button class="foldbtn" id="diagfold">${diagOpen?"收起":`展开全部 ${d.ranked.length} 个候选`}</button>`:""}`;
  if($("diagfold"))$("diagfold").onclick=()=>{diagOpen=!diagOpen;renderDiag()};
  if($("minorbtn"))$("minorbtn").onclick=()=>{minorOpen=!minorOpen;renderDiag()};
}
function compensation(){
  const head=S.head;if(!head||head.residual_id==="zero")return null;
  const v=(S.versions||[]).filter(x=>x.residual_id===head.residual_id&&x.meta&&x.meta.kind==="residual"&&x.meta.training).pop();
  return v?v.meta.training:null;
}
function learnPoints(){
  return (S.versions||[]).filter(v=>v.accepted).map(v=>{const m=v.meta||{};
    if(m.kind==="residual"&&m.training)return{id:v.id,model:m.training.new_median,geo:m.training.geometry_median};
    if(m.guard&&m.guard.candidate_median!=null)return{id:v.id,model:m.guard.candidate_median,geo:m.guard.candidate_median};
    return null}).filter(Boolean);
}
function drawLearn(comp){
  $("compbox").hidden=!comp;$("comphint").hidden=!!comp;
  if(comp){$("c-id").textContent=S.head.residual_id;$("c-geo").textContent=f(comp.geometry_median,2)+" mm";$("c-new").textContent=f(comp.new_median,2)+" mm"}
  const[g,w,h]=setupCanvas($("learnchart")),pts=learnPoints(),scale=px("--fs-chart")/10,pad={l:30*scale,r:10*scale,t:8*scale,b:18*scale},split=pts.some(p=>Math.abs(p.geo-p.model)>1e-9);
  $("lg-geo").hidden=!split;
  if(!pts.length)return emptyChart(g,h,pad,"还没有带验证数据的版本");
  const[ymax,step]=nice(Math.max(.5,...pts.map(p=>Math.max(p.model,p.geo)))*1.05);axes(g,w,h,ymax,step,pad);
  const X=i=>pad.l+(w-pad.l-pad.r)*(pts.length<2?.5:i/(pts.length-1)),Y=v=>pad.t+(h-pad.t-pad.b)*(1-v/ymax);
  const line=(key,col,dash)=>{g.strokeStyle=col;g.setLineDash(dash);g.lineWidth=1.8;g.beginPath();pts.forEach((p,i)=>i?g.lineTo(X(i),Y(p[key])):g.moveTo(X(i),Y(p[key])));g.stroke();g.setLineDash([]);
    pts.forEach((p,i)=>{g.fillStyle=col;g.beginPath();g.arc(X(i),Y(p[key]),2.6,0,7);g.fill()})};
  if(split)line("geo",K.geo,[4,3]);line("model",K.line,[]);
  const lastP=pts[pts.length-1];g.font=chartFont();g.fillStyle=K.line;g.textAlign="right";g.fillText(f(lastP.model,2),w-pad.r,Y(lastP.model)-7*scale);
  g.fillStyle=K.mute;g.font=chartFont("--fs-chart-label",V("--sans"));const stepX=Math.ceil(pts.length/6);
  pts.forEach((p,i)=>{if(i%stepX===0||i===pts.length-1){g.textAlign=i===0?"left":i===pts.length-1?"right":"center";g.fillText(p.id,X(i),h-3*scale)}});g.textAlign="left";
}

/* versions */
function renderVersions(){
  const head=S.head||{},list=[...(S.versions||[])].reverse();
  const key=JSON.stringify([head,S.versions]);if(key===versionsKey)return;versionsKey=key;
  const focused=document.activeElement?.dataset.v;
  $("vlist").innerHTML=list.map(v=>{const tag=v.id===head.id?'<span class="tag cur">使用中</span>':v.accepted?'<span class="tag ok">已启用</span>':'<span class="tag bad">未通过验证</span>';
    return `<button class="vrow" role="menuitem" data-v="${esc(v.id)}"><span class="id">${esc(v.id)}</span><span class="what">${esc(versionWhat(v))}<br><span style="color:var(--mute)">${versionTime(v)}</span></span>${tag}</button>`}).join("")||'<div class="empty">暂无版本</div>';
  if(focused)Array.from($("vlist").children).find(b=>b.dataset.v===focused)?.focus();
}
function showModal(trigger){
  modalTrigger=trigger||document.activeElement;$("mask").classList.add("open");document.body.classList.add("modal-open");
}
function focusModal(){($("modal").querySelector("input,button:not(:disabled)")||$("modal")).focus()}
function openVersion(id){modalVersion=id;modalAction=null;modalErr="";modalKey="";$("modal").replaceChildren();closeDropdowns();showModal($("vbtn"));renderModal();focusModal()}
function closeModal(){const open=$("mask").classList.contains("open");modalVersion=null;modalAction=null;modalKey="";$("mask").classList.remove("open");document.body.classList.remove("modal-open");if(open)modalTrigger?.focus()}
function confirmAction(name,trigger){
  closeDropdowns();modalVersion=null;modalAction=name;
  const text=name==="baseline"?`将试打 ${S.command_shots?.baseline??"待确认"} 发，重新拟合几何参数。通过护栏后会产生并启用新版本；未通过时保留当前版本。`:
    name==="retrain"?"新增试打 0 发，使用已有正常打靶记录重训细节补偿。验证有改善后会产生并启用新版本，否则保留当前版本。":"确认设备周围安全后解除急停。解除不会续跑被中止的流程，需要重新发起操作。";
  const title={baseline:"确认首次标定",retrain:"确认重训补偿",reset_estop:"确认解除急停"}[name];
  $("modal").innerHTML=`<h2 id="modal-title">${title}</h2><p>${text}</p><div id="action-error" class="err-msg" role="alert"></div><div class="foot"><button id="cancel-action">取消</button><button id="confirm-action" class="primary" data-command="${name}">确认执行</button></div>`;
  showModal(trigger);$("cancel-action").onclick=closeModal;
  $("confirm-action").onclick=async()=>{try{await command(name);if(modalAction===name)closeModal()}catch(e){if(modalAction===name)$("action-error").textContent=tr(e.message);else toast(tr(e.message))}};
  syncControls();focusModal();
}
function renderModal(){
  const v=(S.versions||[]).find(x=>x.id===modalVersion),head=S.head;if(!v||!head)return closeModal();
  const cur=v.id===head.id,pv=S.preview&&S.preview.version_id===v.id&&S.preview.from===head.id?S.preview:null,stage=cur?0:!pv?1:2;
  const key=JSON.stringify([v,head,pv,modalErr]);if(key===modalKey)return;modalKey=key;
  const diff=Object.keys(PARAM).filter(k=>Math.abs((v.params[k]??0)-(head.params[k]??0))>1e-9)
    .map(k=>`<tr><td>${PARAM[k][0]}</td><td class="r num">${tableNumber(head.params[k])}</td><td class="r num">${tableNumber(v.params[k])}</td><td class="r num">${signed(v.params[k]-head.params[k],2)} ${PARAM[k][1]}</td></tr>`).join("");
  const resid=v.residual_id!==head.residual_id?`<tr><td>细节补偿</td><td class="r">${esc(head.residual_id)}</td><td class="r">${esc(v.residual_id)}</td><td></td></tr>`:"";
  let html=`<h2 id="modal-title">${esc(v.id)} <span class="tag ${cur?"cur":v.accepted?"ok":"bad"}" style="vertical-align:middle">${cur?"使用中":v.accepted?"已启用":"未通过验证"}</span></h2>
    <div class="note">${esc(versionWhat(v))}${versionTime(v)?" · 创建于 "+versionTime(v):""}</div>
    <div class="steps"><div class="${stage>=1?"done":""}">① 查看差异</div><div class="${stage===1?"on":stage===2?"done":""}">② 预检试打 3 发</div><div class="${stage===2?"on":""}">③ 确认切换</div></div>
    <div class="box"><b>与当前版本 ${esc(head.id)} 的差异</b>${diff||resid?`<table style="margin-top:6px"><thead><tr><th>参数</th><th class="r">当前</th><th class="r">${esc(v.id)}</th><th class="r">变化</th></tr></thead><tbody>${diff}${resid}</tbody></table>`:'<div class="note" style="margin-top:6px">参数完全相同</div>'}
    ${(v.reasons||[]).length?`<div class="err-msg">未通过原因：${esc(v.reasons.map(tr).join("；"))}</div>`:""}</div>`;
  if(cur)html+=`<div class="foot"><button id="modal-close" data-close>关闭</button></div>`;
  else if(!v.accepted)html+=`<div class="note" style="margin-top:12px">未通过护栏验证的版本只用于留档和排查，不能启用。</div><div class="foot"><button id="modal-close" data-close>关闭</button></div>`;
  else{
    if(pv){const rows=pv.shots.map((s,i)=>`<tr><td>第 ${i+1} 发</td><td class="r num">${tableNumber(s.current_mm)}</td><td class="r num">${tableNumber(s.candidate_mm)}</td></tr>`).join("");
      html+=`<div class="box"><b>预检结果</b><table style="margin-top:6px"><thead><tr><th>探测</th><th class="r">当前 ${esc(head.id)} 误差 mm</th><th class="r">${esc(v.id)} 误差 mm</th></tr></thead><tbody>${rows}
        <tr><td><b>中位数</b></td><td class="r num"><b>${tableNumber(pv.current_median)}</b></td><td class="r num"><b>${tableNumber(pv.candidate_median)}</b></td></tr></tbody></table>
        <div class="verdict" style="background:var(--${pv.passed?"accent":"bad"}-bg);color:var(--${pv.passed?"accent":"bad"})">${pv.passed?`通过：${esc(v.id)} 在机器当前状态下误差中位数 ≤ ${f(pv.limit_mm,0)} mm`:`未通过：${esc(v.id)} 与机器当前状态不符，切换后瞄准会变差`}</div></div>
        <div class="box"><b>确认切换</b><div class="note" style="margin-top:4px">切换会改变机器使用的自我模型，并记入日志。输入版本号 <b>${esc(v.id)}</b> 确认；切换后 ${S.undo_s||30} 秒内可撤销。</div>
        <input id="confirm" aria-label="输入版本号确认切换" placeholder="${esc(v.id)}" autocomplete="off" style="width:140px">
        ${pv.passed?"":`<label style="margin-left:10px;color:var(--bad)"><input type="checkbox" id="force"> 我了解风险，强制切换</label>`}</div>`}
    html+=`${modalErr?`<div class="err-msg">${esc(modalErr)}</div>`:""}<div class="foot"><button id="modal-close" data-close>取消</button>
      <button id="btnpreview" data-command="preview">${pv?"重新预检":"预检：试打 3 发"}</button>
      ${pv?`<button id="btnswitch" data-command="switch" class="${pv.passed?"primary":"danger"}">切换到 ${esc(v.id)}</button>`:""}</div>`;
  }
  const keep=$("confirm")?$("confirm").value:"",force=$("force")?$("force").checked:false;
  const active=document.activeElement,focused=$("modal").contains(active),focusId=active?.id,selection=focusId==="confirm"?[active.selectionStart,active.selectionEnd,active.selectionDirection]:null,scroll=$("modal").scrollTop;
  $("modal").innerHTML=html;
  if($("confirm")){$("confirm").value=keep;if($("force"))$("force").checked=force}
  syncControls();
  if(focused){const target=focusId&&$(focusId);if(target){target.focus({preventScroll:true});if(selection)target.setSelectionRange(...selection)}else focusModal()}
  $("modal").scrollTop=scroll;
  $("modal").querySelectorAll("[data-close]").forEach(b=>b.onclick=closeModal);
  if($("btnpreview"))$("btnpreview").onclick=async()=>{modalErr="";
    try{const p=await command("preview",{version_id:v.id});S.preview=p.preview||S.preview}catch(e){if(modalVersion===v.id)modalErr=tr(e.message);else toast(tr(e.message))}if(modalVersion===v.id)renderModal()};
  if($("btnswitch"))$("btnswitch").onclick=async()=>{modalErr="";const c=$("confirm").value.trim();
    if(c!==v.id){modalErr=`请输入 ${v.id} 以确认`;return renderModal()}
    const from=head.id;
    try{await command("switch",{version_id:v.id,confirm:c,force:$("force")?$("force").checked:false});if(modalVersion===v.id)closeModal();offerUndo(from,v.id)}
    catch(e){if(modalVersion===v.id){modalErr=tr(e.message);renderModal()}else toast(tr(e.message))}};
}
function offerUndo(from,to){
  let left=S.undo_s||30;clearInterval(undoTimer);clearTimeout(undoTimer);
  const tick=()=>{$("toastmsg").textContent=`已切换到 ${to}（${left} 秒内可撤销）`;if(left--<=0){clearInterval(undoTimer);$("toast").classList.remove("open")}};
  $("toastbtn").hidden=false;$("toast").classList.add("open");tick();undoTimer=setInterval(tick,1000);
  $("toastbtn").onclick=async()=>{clearInterval(undoTimer);try{await command("switch",{version_id:from,confirm:from});toast(`已撤销，回到 ${from}`)}catch(e){toast("撤销失败："+tr(e.message))}};
}
function toast(msg){clearInterval(undoTimer);clearTimeout(undoTimer);$("toastbtn").hidden=true;$("toastmsg").textContent=msg;$("toast").classList.add("open");undoTimer=setTimeout(()=>$("toast").classList.remove("open"),4500)}

/* overview */
const KIND={recognition:["认出旧伤","cy"],repair:["诊断修复","cur"],rejected:["被护栏拦下","bad"]};
function renderOverview(){
  const st=S.stats||{},hist=st.history||[],shots=hist.filter(r=>r.kind!=="rejected").map(r=>r.shots),pts=learnPoints(),best=pts.length?Math.min(...pts.map(p=>p.model)):null;
  const acc=(S.versions||[]).filter(v=>v.accepted).length,rej=(S.versions||[]).length-acc,avg=shots.length?shots.reduce((a,b)=>a+b,0)/shots.length:null;
  const tiles=[["自愈成功",(st.recoveries||0)+(st.recognitions||0),"次",`诊断修复 ${st.recoveries||0} · 认出旧伤 ${st.recognitions||0}`],
    ["平均恢复",avg==null?"—":f(avg,1),avg==null?"":"发",shots.length?`最快 ${Math.min(...shots)} 发 · 最慢 ${Math.max(...shots)} 发`:"还没有恢复记录"],["最佳精度",best==null?"—":f(best,2),best==null?"":"mm","历次版本验证误差的最小值"],
    ["异常报警",S.alarms||0,"次",`累计打靶 ${S.shots||0} 发 · 运行 ${dur(st.uptime_s)}`],["拦下的修复",st.rejections||0,"次","护栏拒绝的不可靠候选"],["已启用版本",acc,"个",`未通过 ${rej} 个 · 手动切换 ${st.manual_switches||0} 次`]];
  $("tiles").innerHTML=tiles.map(([k,v,u,d])=>`<div class="card tile"><div class="k">${k}</div><div class="v num">${v}<small>${u}</small></div><div class="d" title="${esc(d)}">${esc(d)}</div></div>`).join("");
  const key=hist.length+":"+(hist.length?hist[hist.length-1].timestamp:0);
  if(key!==histKey){histKey=key;$("history").innerHTML=hist.length?`<table><thead><tr><th>时间</th><th>结果</th><th>诊断结论</th><th class="r">用了几发</th><th class="r">自愈前 mm</th><th class="r">自愈后 mm</th><th class="r">启用版本</th></tr></thead><tbody>${[...hist].reverse().map(r=>{const[k,c]=KIND[r.kind]||[r.kind,"ok"];
      const what=r.code?`${r.code} · ${codeName(r.code)}`:r.kind==="recognition"?"以前见过的状态，直接切回":"观测不足，无法诊断";
      return `<tr><td class="num">${clock(r.timestamp)}</td><td><span class="tag ${c}">${k}</span></td><td>${esc(what)}</td><td class="r num">${r.shots}</td><td class="r num">${f(r.before_mm,2)}</td><td class="r num">${f(r.after_mm,2)}</td><td class="r num">${esc(r.version_id||"—")}</td></tr>`}).join("")}</tbody></table>`
    :'<div class="empty">还没有自愈记录。到右上角“⋯ → 仿真调试”注入一处伤，再点“自检”试试。</div>'}
  const faults=Object.entries(st.faults||{}).sort((a,b)=>b[1]-a[1]),mx=Math.max(1,...faults.map(x=>x[1]));
  $("faultbars").innerHTML=faults.length?faults.map(([c,n])=>`<div class="hbar"><span>${esc(c)} ${esc(CODE[c]||"组合")}</span><div class="t"><i style="width:${n/mx*100}%"></i></div><span class="num">${n}</span></div>`).join(""):'<div class="empty">还没有诊断修复记录</div>';
  if($("page-overview").classList.contains("on"))drawHeal(hist);
}
function drawHeal(hist){
  const[g,w,h]=setupCanvas($("healchart")),scale=px("--fs-chart")/10,pad={l:30*scale,r:8*scale,t:18*scale,b:6*scale};
  if(!hist.length)return emptyChart(g,h,pad,"还没有恢复记录");
  const[ymax,step]=nice(Math.max(4,...hist.map(r=>r.shots)));axes(g,w,h,ymax,step,pad);const n=hist.length,slot=(w-pad.l-pad.r)/n,bw=Math.min(28,slot*.7);
  hist.forEach((r,i)=>{const x=pad.l+slot*(i+.5),y=pad.t+(h-pad.t-pad.b)*(1-r.shots/ymax);g.fillStyle=r.kind==="recognition"?K.cyan:r.kind==="rejected"?K.bad:K.line;g.fillRect(x-bw/2,y,bw,h-pad.b-y);
    if(slot>22*scale){g.fillStyle=K.mute;g.font=chartFont();g.textAlign="center";g.fillText(r.shots,x,y-4*scale)}});g.textAlign="left";
}

/* fault codes */
function md(src){
  const inline=s=>esc(s).replace(/\*\*(.+?)\*\*/g,"<b>$1</b>").replace(/`(.+?)`/g,"<code>$1</code>");
  const lines=src.split("\n");let out="",i=0;
  while(i<lines.length){const l=lines[i];
    if(/^#{1,3} /.test(l)){const n=l.match(/^#+/)[0].length;out+=`<h${n}>${inline(l.slice(n+1))}</h${n}>`;i++}
    else if(l.startsWith("|")){const rows=[];while(i<lines.length&&lines[i].startsWith("|"))rows.push(lines[i++]);
      const cells=r=>r.split("|").slice(1,-1).map(c=>c.trim()),head=cells(rows[0]),body=rows.slice(2).map(cells);
      out+=`<div style="overflow-x:auto"><table><thead><tr>${head.map(c=>`<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${body.map(r=>`<tr>${r.map(c=>`<td>${inline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`}
    else if(l.startsWith("- ")){out+="<ul>";while(i<lines.length&&lines[i].startsWith("- "))out+=`<li>${inline(lines[i++].slice(2))}</li>`;out+="</ul>"}
    else{if(l.trim())out+=`<p>${inline(l)}</p>`;i++}}
  return out;
}
async function loadDoc(){if(docLoaded)return;try{const r=await fetch("/api/fault-codes");if(!r.ok)throw 0;const src=await r.text(),parts=src.split(/\n(?=## )/),left=parts.slice(0,2).join("\n"),right=parts.slice(2).join("\n");
    $("doc").innerHTML=`<div class="card doc">${md(left)}</div><div class="card doc">${md(right)}</div>`;docLoaded=true}catch{$("doc").innerHTML='<div class="card doc"><div class="empty">故障码文档加载失败</div></div>'}}

function updateChartLabels(){
  const rec=(S.recent||[]).slice(-120),vals=rec.map(s=>mag(s.residual)).filter(v=>v!=null),pts=learnPoints(),hist=S.stats?.history||[];
  $("errchart").setAttribute("aria-label",`瞄准误差：最近 ${rec.length} 发，最新 ${f(rec.length?mag(rec.at(-1).residual):null,2)} 毫米，最大 ${f(vals.length?Math.max(...vals):null,2)} 毫米，报警阈值 ${S.alarm_mm||6} 毫米`);
  $("learnchart").setAttribute("aria-label",`学习效果：${pts.length} 个验证版本，最新模型误差中位数 ${f(pts.at(-1)?.model,2)} 毫米`);
  $("healchart").setAttribute("aria-label",`自愈发数：${hist.length} 次记录，最近一次 ${hist.at(-1)?.shots??"暂无"} 发`);
}
/* Hash is the single source of navigation state. */
function route(){
  const page=["home","overview","codes"].includes(location.hash.slice(1))?location.hash.slice(1):"home";
  document.querySelectorAll("nav button").forEach(b=>{const on=b.dataset.page===page;b.classList.toggle("on",on);if(on)b.setAttribute("aria-current","page");else b.removeAttribute("aria-current")});
  document.querySelectorAll(".page").forEach(p=>p.classList.toggle("on",p.id==="page-"+page));
  if(page==="codes")loadDoc();schedule();
}
function dropdown(id,open,focus=false){const button=$(id==="vlist"?"vbtn":"more");$(id).classList.toggle("open",open);button.setAttribute("aria-expanded",String(open));if(open&&focus)$(id).querySelector("button:not(:disabled):not([hidden])")?.focus()}
function closeDropdowns(){dropdown("vlist",false);dropdown("morelist",false)}
function wireDropdown(button,id){
  button.onclick=e=>{e.stopPropagation();const open=!$(id).classList.contains("open");closeDropdowns();dropdown(id,open,true)};
  button.onkeydown=e=>{if(["ArrowDown","ArrowUp"].includes(e.key)){e.preventDefault();closeDropdowns();dropdown(id,true,true)}};
  $(id).onkeydown=e=>{
    const rows=[...$(id).querySelectorAll("button:not(:disabled):not([hidden])")],i=rows.indexOf(document.activeElement);
    if(["ArrowDown","ArrowUp","Home","End"].includes(e.key)){e.preventDefault();const n=e.key==="Home"?0:e.key==="End"?rows.length-1:(i+(e.key==="ArrowDown"?1:-1)+rows.length)%rows.length;rows[n]?.focus()}
  };
}
document.querySelectorAll("nav button").forEach(b=>b.onclick=()=>{location.hash=b.dataset.page});
addEventListener("hashchange",route);if(!location.hash)history.replaceState(null,"","#home");route();
wireDropdown($("vbtn"),"vlist");wireDropdown($("more"),"morelist");
document.addEventListener("click",e=>{if(!e.target.closest(".vpick"))dropdown("vlist",false);if(!e.target.closest(".menu"))dropdown("morelist",false)});
$("vlist").onclick=e=>{const r=e.target.closest(".vrow");if(r)openVersion(r.dataset.v)};
$("mask").onclick=e=>{if(e.target===$("mask"))closeModal()};
document.addEventListener("keydown",e=>{
  if(e.key==="Escape"){
    e.preventDefault();if($("mask").classList.contains("open"))closeModal();
    else{const id=$("vlist").classList.contains("open")?"vbtn":$("morelist").classList.contains("open")?"more":null;closeDropdowns();if(id)$(id).focus()}
  }
  if(e.key==="Tab"&&$("mask").classList.contains("open")){
    const all=[...$("modal").querySelectorAll("button:not(:disabled),input:not(:disabled),select:not(:disabled),[tabindex='0']")],first=all[0],last=all.at(-1);
    if(!first){e.preventDefault();$("modal").focus()}
    else if(e.shiftKey&&(document.activeElement===first||!all.includes(document.activeElement))){e.preventDefault();last.focus()}
    else if(!e.shiftKey&&(document.activeElement===last||!all.includes(document.activeElement))){e.preventDefault();first.focus()}
  }
});
document.querySelectorAll("[data-cmd]").forEach(b=>b.onclick=async()=>{const name=b.dataset.cmd;if(["baseline","retrain"].includes(name)){confirmAction(name,$("more"));return}closeDropdowns();try{await command(name)}catch(e){toast(tr(e.message))}});
$("estop").onclick=async()=>{try{await command("estop")}catch(e){toast(tr(e.message))}};
$("resetstop").onclick=()=>confirmAction("reset_estop",$("resetstop"));
function placeDebug(reset=false){
  const d=$("debug"),r=d.getBoundingClientRect(),cam=$("cam").getBoundingClientRect();
  const x=reset?cam.left:r.left,y=reset?cam.bottom-r.height-44:r.top;
  d.style.left=Math.max(8,Math.min(innerWidth-r.width-8,x))+"px";
  d.style.top=Math.max(8,Math.min(innerHeight-r.height-8,y))+"px";d.style.bottom="auto";
}
$("debugtoggle").onclick=()=>{closeDropdowns();$("debug").classList.toggle("on");if($("debug").classList.contains("on"))placeDebug(!$("debug").style.left)};
$("debugclose").onclick=()=>{$("debug").classList.remove("on");$("more").focus()};
let drag=null;
$("debugtitle").onpointerdown=e=>{if(e.target.closest("button"))return;const r=$("debug").getBoundingClientRect();drag={x:e.clientX-r.left,y:e.clientY-r.top};e.currentTarget.setPointerCapture(e.pointerId)};
$("debugtitle").onpointermove=e=>{if(!drag)return;$("debug").style.left=e.clientX-drag.x+"px";$("debug").style.top=e.clientY-drag.y+"px";placeDebug()};
$("debugtitle").onpointerup=$("debugtitle").onpointercancel=()=>{drag=null};
addEventListener("resize",()=>{if($("debug").classList.contains("on"))placeDebug()});
$("inject").onclick=async()=>{const[kind,amount]=$("damage").value.split(":");try{await command("inject",{kind,amount:Number(amount)});toast(`已注入：${$("damage").selectedOptions[0].text}。点“自检”看它自愈`)}catch(e){toast(tr(e.message))}};
$("errchart").onmousemove=hoverErr;
$("errchart").onmouseleave=()=>{hoverI=null;$("tip").style.display="none";if(S)drawErr()};
/* Short desktop screens: fold the event feed into the diagnosis card as a second tab. */
const shortMQ=matchMedia("(min-width:1081px) and (max-height:800px)");
function layout(){document.documentElement.style.setProperty("--header-height",document.querySelector("header").offsetHeight+"px");const short=shortMQ.matches;document.body.classList.toggle("short",short);const feed=$("feed"),to=short?$("feedslot"):$("feedcard");if(feed.parentNode!==to)to.appendChild(feed)}
shortMQ.addEventListener("change",()=>{layout();schedule()});layout();
$("dtabs").onclick=e=>{const b=e.target.closest("button");if(!b)return;const feed=b.dataset.t==="feed";document.body.classList.toggle("tab-feed",feed);
  $("dtabs").querySelectorAll("button").forEach(x=>x.classList.toggle("on",x===b));$("diagaside").hidden=feed};
addEventListener("resize",()=>{layout();schedule()});
connectionState(false,"正在连接，数据尚未就绪");
fetch("/api/state").then(r=>{if(!r.ok)throw new Error();return r.json()}).then(s=>{if(!wsSnapshot){S=s;render()}}).catch(()=>{if(!connected)connectionState(false,"首次状态加载失败，正在重连；数据尚未就绪")});
connect();
})();
