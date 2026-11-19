const $ = (s) => document.querySelector(s);
const state = { slots:null, agent:null, accounts:[], events:[], busy:false, timer:null, first:true };
const LBL = { parsed:'В архиве', checking:'Проверяю', ready:'Готов', proxy_fail:'Прокси мёртв',
  opening:'Открывается', in_account:'В аккаунте', done:'Готово', failed:'Ошибка' };
const I = {
  wifi:'<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 12a11 11 0 0 1 16 0"/><path d="M7.5 15.5a7 7 0 0 1 9 0"/><circle cx="12" cy="19" r="1.2" fill="currentColor" stroke="none"/></svg>',
  play:'<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>',
  stop:'<svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>',
  trash:'<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M8 6V4h8v2M6 6l1 14h10l1-14"/></svg>',
  save:'<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/></svg>'
};
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function notify(msg,kind='error'){
  const ok=kind==='ok'; const b=document.createElement('div');
  b.innerHTML='<span style="font-size:15px">'+(ok?'✓':'!')+'</span><span>'+esc(msg)+'</span>';
  b.style.cssText='position:fixed;right:22px;bottom:22px;z-index:999;display:flex;align-items:center;gap:10px;padding:13px 18px;'+
    'border-radius:14px;font:13px Inter,sans-serif;max-width:420px;backdrop-filter:blur(18px);animation:fadeUp .25s ease both;'+
    'box-shadow:0 20px 50px rgba(0,0,0,.45);'+(ok?'background:rgba(20,45,33,.92);color:#7ef0b0;border:1px solid rgba(46,224,138,.3)'
      :'background:rgba(52,24,28,.92);color:#ff9a9a;border:1px solid rgba(255,107,107,.3)');
  document.body.appendChild(b);
  setTimeout(()=>{b.style.transition='opacity .3s,transform .3s';b.style.opacity='0';b.style.transform='translateY(8px)';setTimeout(()=>b.remove(),320);},4000);
}
async function api(path,opt={}){
  const r=await fetch(path,{credentials:'same-origin',cache:'no-store',...opt});
  if(r.status===401){showLogin();throw new Error('unauthorized');} return r;
}
async function apiJson(path,opt={}){
  const r=await api(path,opt); const d=await r.json().catch(()=>({}));
  if(!r.ok) throw new Error(d.detail||('HTTP '+r.status)); return d;
}
function showLogin(){$('#app').classList.add('hidden');$('#login').classList.remove('hidden');if(state.timer){clearInterval(state.timer);state.timer=null;}}
function showApp(){$('#login').classList.add('hidden');$('#app').classList.remove('hidden');if(!state.timer)state.timer=setInterval(refresh,2500);refresh();}
let sigRows='', sigStats='', sigSlots='', lastLog=0;
async function refresh(){
  if(state.busy) return; state.busy=true;
  try{
    const d=await apiJson('/api/state');
    state.slots=d.slots; state.agent=d.agent; state.accounts=d.accounts; state.events=d.events;
    renderAgent();
    const s1=JSON.stringify(d.slots);
    if(s1!==sigSlots){sigSlots=s1;renderSlots();}
    const s2=JSON.stringify(d.accounts.map(a=>[a.state,a.premium,a.has_session]));
    if(s2!==sigStats){sigStats=s2;renderStats();}
    renderRows(); renderLog();
  }catch(e){ if(e.message!=='unauthorized') console.warn(e); }
  finally{ state.busy=false; }
}
function renderAgent(){
  const on=Boolean(state.agent&&state.agent.online); const box=$('#agent'); if(!box) return;
  box.classList.toggle('online',on);
  const t=on?'агент онлайн':'агент офлайн';
  if($('#agent-text').textContent!==t) $('#agent-text').textContent=t;
}
function renderSlots(){
  const s=state.slots||{max:0,busy:0,items:[]};
  $('#slots-value').textContent=s.busy+'/'+s.max;
  $('#slots-dots').innerHTML=s.items.map(i=>'<i class="'+(i.state==='busy'?'busy':i.state==='reserved'?'reserved':'')+'"></i>').join('');
}
function renderStats(){
  const a=state.accounts,n=v=>a.filter(x=>x.state===v).length;
  const data=[['Аккаунтов',a.length],['Готовы',n('ready')],['В работе',n('in_account')+n('opening')],
    ['Премиум',a.filter(x=>x.premium).length],['С сессией',a.filter(x=>x.has_session).length]];
  $('#stats').innerHTML=data.map(p=>'<div class="chip">'+p[0]+': <b>'+p[1]+'</b></div>').join('');
}
function renderRows(){
  const box=$('#accounts');
  const sig=JSON.stringify(state.accounts.map(a=>[a.id,a.state,a.premium,a.has_session,a.phone,a.name,a.country,a.proxy_web,a.device]));
  if(sig===sigRows) return; sigRows=sig;
  if(!state.accounts.length){
    box.innerHTML='<div class="muted" style="padding:44px;text-align:center">Пока пусто. Загрузи архив с tdata выше.</div>';
    return;
  }
  box.innerHTML=state.accounts.map((a,i)=>rowHtml(a,i)).join('');
}
function short(s){s=String(s||'');const m=s.match(/@([^:\/]+)/);return m?m[1]:s.slice(0,22);}
function rowHtml(a,i){
  const tags=[];
  if(a.country) tags.push('<span class="tag">'+esc(a.country)+'</span>');
  if(a.proxy_web) tags.push('<span class="tag">'+esc(short(a.proxy_web))+'</span>');
  if(a.device) tags.push('<span class="tag">'+esc(a.device)+'</span>');
  if(a.premium) tags.push('<span class="tag prem">PREMIUM</span>');
  if(a.has_session) tags.push('<span class="tag ok">сессия</span>');
  const free=(state.slots&&state.slots.free?state.slots.free:0)>0;
  const on=Boolean(state.agent&&state.agent.online);
  const acts=[];
  if(['parsed','proxy_fail','ready','failed'].includes(a.state))
    acts.push('<button class="ghost tiny wifi" data-act="check" data-id="'+a.id+'" title="Проверить прокси">'+I.wifi+'</button>');
  if(['ready','failed','done'].includes(a.state))
    acts.push('<button class="tiny" data-act="open" data-id="'+a.id+'"'+(free&&on?'':' disabled')+' title="Открыть Web">'+I.play+'</button>');
  if(['opening','in_account'].includes(a.state))
    acts.push('<button class="danger tiny" data-act="finish" data-id="'+a.id+'" title="Завершить">'+I.stop+'</button>');
  if(a.has_session)
    acts.push('<a class="tag" style="display:flex;align-items:center;gap:4px;text-decoration:none" href="/api/accounts/'+a.id+'/session" title="Скачать сессию">'+I.save+'</a>');
  if(!['opening','in_account'].includes(a.state))
    acts.push('<button class="ghost tiny" data-act="del" data-id="'+a.id+'" title="Удалить">'+I.trash+'</button>');
  const title=a.name&&a.name!=='—'?a.name:(a.phone||('Аккаунт #'+a.id));
  const sub=[a.phone?'+'+a.phone:'',a.country].filter(Boolean).join(' · ')||('#'+a.id);
  return '<div class="row '+(a.state==='in_account'?'busy':'')+'">'+
    '<div class="st '+esc(a.state)+'"></div>'+
    '<div class="who"><b>'+esc(title)+'</b><span>'+esc(sub)+'</span></div>'+
    '<div class="tags">'+tags.join('')+'</div>'+
    '<span class="pill '+esc(a.state)+'">'+esc(LBL[a.state]||a.state)+'</span>'+
    '<div class="acts">'+acts.join('')+'</div></div>';
}
function renderLog(){
  const box=$('#log');
  const fresh=state.events.filter(e=>e.id>lastLog);
  if(!fresh.length) return;
  const pin=box.scrollTop+box.clientHeight>=box.scrollHeight-40;
  fresh.forEach(e=>{
    const t=e.ts?new Date(e.ts).toLocaleTimeString('ru-RU'):'';
    const l=e.level==='error'?'error':(e.level==='warn'?'warn':'');
    const div=document.createElement('div');
    div.className='log-row '+l;
    div.innerHTML='<span class="log-time">'+esc(t)+'</span><b>'+esc(e.message)+'</b>';
    box.appendChild(div);
    lastLog=Math.max(lastLog,e.id);
  });
  while(box.children.length>200) box.removeChild(box.firstChild);
  if(pin) box.scrollTop=box.scrollHeight;
}
$('#login-form').addEventListener('submit',async ev=>{
  ev.preventDefault(); $('#login-error').textContent='';
  try{ await apiJson('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:$('#password').value})});
    $('#password').value=''; showApp(); }catch(e){ $('#login-error').textContent=e.message; }
});
$('#logout').addEventListener('click',async()=>{ await api('/api/logout',{method:'POST'}); showLogin(); });
$('#zip').addEventListener('change',()=>{const f=$('#zip').files[0];$('#zip-name').textContent=f?f.name:'Выбрать ZIP с tdata';});
$('#upload').addEventListener('submit',async ev=>{
  ev.preventDefault(); const f=$('#zip').files[0]; if(!f) return notify('Выбери ZIP-архив');
  const body=new FormData(); body.append('file',f); body.append('proxies',$('#proxies').value);
  const btn=$('#upload-btn'); btn.disabled=true; const old=btn.textContent; btn.textContent='Разбираю...';
  try{ const d=await apiJson('/api/batches',{method:'POST',body}); notify('Найдено tdata: '+d.found,'ok');
    $('#proxies').value=''; $('#zip').value=''; $('#zip-name').textContent='Выбрать ZIP с tdata'; refresh();
  }catch(e){ notify(e.message); } finally{ btn.disabled=false; btn.textContent=old; }
});
$('#accounts').addEventListener('click',async ev=>{
  const b=ev.target.closest('button[data-act]'); if(!b) return;
  const id=Number(b.dataset.id), act=b.dataset.act;
  if(act==='open'){ openProxy(id); return; }
  if(act==='del'){ confirmDelete(id); return; }
  b.disabled=true;
  try{
    if(act==='check'){ const d=await apiJson('/api/accounts/'+id+'/check',{method:'POST'});
      notify(d.ok?'Прокси живой: '+d.ip:'Прокси мёртв: '+d.error,d.ok?'ok':'error'); }
    if(act==='finish'){ const d=await apiJson('/api/accounts/'+id+'/finish',{method:'POST'});
      notify(d.has_session?'Сессия сохранена, слот свободен':'Закрыто без сессии','ok'); }
    refresh();
  }catch(e){ notify(e.message); } finally{ b.disabled=false; }
});
let pendingId=null;
function openProxy(id){
  if(!state.agent||!state.agent.online) return notify('Агент на ПК офлайн');
  const free=state.slots&&state.slots.free?state.slots.free:0;
  if(free<=0) return notify('Нет свободных слотов: '+state.slots.busy+'/'+state.slots.max);
  const a=state.accounts.find(x=>x.id===id); pendingId=id;
  $('#proxy-input').value=(a&&a.proxy_web)||''; $('#proxy-modal').showModal();
}
$('#proxy-modal').addEventListener('close',async()=>{
  if($('#proxy-modal').returnValue!=='ok'||!pendingId) return;
  const id=pendingId; pendingId=null;
  try{ const d=await apiJson('/api/accounts/'+id+'/open',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({proxy:$('#proxy-input').value})});
    notify('Профиль создаётся, слот '+d.slot,'ok'); refresh();
  }catch(e){ notify(e.message); }
});
let delId=null;
function confirmDelete(id){ delId=id; $('#confirm-modal').showModal(); }
$('#confirm-modal').addEventListener('close',async()=>{
  if($('#confirm-modal').returnValue!=='ok'||!delId) return;
  const id=delId; delId=null;
  try{ await apiJson('/api/accounts/'+id+'/remove',{method:'POST'}); notify('Аккаунт удалён','ok'); refresh(); }
  catch(e){ notify(e.message); }
});
fetch('/api/me',{cache:'no-store'}).then(r=>r.json())
  .then(d=>{ if(d.auth) showApp(); else showLogin(); }).catch(()=>showLogin());
