// TWKS panel — фронт без сборки, чистый JS
const $ = (sel) => document.querySelector(sel);
const state = { slots: null, agent: null, accounts: [], events: [], busy: false };

const STATE_LABEL = {
  parsed: 'В архиве',
  checking: 'Проверяю',
  ready: 'Готов',
  proxy_fail: 'Прокси мёртв',
  opening: 'Открывается',
  in_account: 'В аккаунте',
  done: 'Готово',
  failed: 'Ошибка',
};

// ------------------------------------------------------------------ utils

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function notify(message, level = 'error') {
  const box = document.createElement('div');
  box.textContent = message;
  box.style.cssText = `position:fixed;right:18px;bottom:18px;z-index:99;padding:12px 16px;border-radius:10px;
    background:${level === 'error' ? '#3a1d22' : '#12261c'};color:${level === 'error' ? '#ff9a9a' : '#7ef0b0'};
    border:1px solid ${level === 'error' ? '#5c2a32' : '#24503a'};font:14px sans-serif;max-width:380px`;
  document.body.appendChild(box);
  setTimeout(() => box.remove(), 4000);
}

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: 'same-origin', ...options });
  if (response.status === 401) {
    showLogin();
    throw new Error('unauthorized');
  }
  return response;
}

async function apiJson(path, options = {}) {
  const response = await api(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  return data;
}

// ------------------------------------------------------------------ auth

function showLogin() {
  $('#app').classList.add('hidden');
  $('#login').classList.remove('hidden');
  if (state.timer) { clearInterval(state.timer); state.timer = null; }
}

function showApp() {
  $('#login').classList.add('hidden');
  $('#app').classList.remove('hidden');
  if (!state.timer) state.timer = setInterval(refresh, 2000);
  refresh();
}

async function boot() {
  try {
    const response = await fetch('/api/me');
    const data = await response.json();
    if (data.auth) showApp(); else showLogin();
  } catch {
    showLogin();
  }
}

$('#login-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  $('#login-error').textContent = '';
  try {
    await apiJson('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: $('#password').value }),
    });
    $('#password').value = '';
    showApp();
  } catch (error) {
    $('#login-error').textContent = error.message;
  }
});

$('#logout').addEventListener('click', async () => {
  await api('/api/logout', { method: 'POST' });
  showLogin();
});

// ------------------------------------------------------------------ state

async function refresh() {
  if (state.busy) return;
  state.busy = true;
  try {
    const data = await apiJson('/api/state');
    state.slots = data.slots;
    state.agent = data.agent;
    state.accounts = data.accounts;
    state.events = data.events;
    render();
  } catch (error) {
    if (error.message !== 'unauthorized') console.warn(error);
  } finally {
    state.busy = false;
  }
}

function render() {
  renderSlots();
  renderStats();
  renderAccounts();
  renderLog();
}

function renderSlots() {
  const slots = state.slots || { max: 0, busy: 0, items: [] };
  $('#slots-value').textContent = `${slots.busy}/${slots.max}`;
  $('#slots-dots').innerHTML = slots.items
    .map((slot) => `<i class="${slot.state === 'busy' ? 'busy' : slot.state === 'reserved' ? 'reserved' : ''}"></i>`)
    .join('');
}

function renderStats() {
  const accounts = state.accounts;
  const count = (value) => accounts.filter((a) => a.state === value).length;
  $('#stats').innerHTML = [
    ['Аккаунтов', accounts.length],
    ['Готовы', count('ready')],
    ['В работе', count('in_account') + count('opening')],
    ['С сессией', accounts.filter((a) => a.has_session).length],
  ].map(([label, value]) => `<div class="chip">${label}: <b>${value}</b></div>`).join('');
}

function renderAccounts() {
  const box = $('#accounts');
  if (!state.accounts.length) {
    box.innerHTML = '<div class="empty">Пока пусто. Загрузи архив с tdata.</div>';
    return;
  }
  box.innerHTML = state.accounts.map(cardHtml).join('');
}

function cardHtml(account) {
  const badge = `<span class="badge ${esc(account.state)}">${esc(STATE_LABEL[account.state] || account.state)}</span>`;
  const title = account.name || account.phone || `Аккаунт #${account.id}`;
  const sub = [account.phone, account.country, account.premium ? 'premium' : '']
    .filter(Boolean).join(' · ') || `#${account.id}`;

  const tags = [];
  if (account.device) tags.push(`<span class="tag">${esc(account.device)}</span>`);
  if (account.slot_no) tags.push(`<span class="tag">слот ${account.slot_no}</span>`);
  if (account.has_session) tags.push('<span class="tag ok">сессия есть</span>');

  const actions = [];
  const freeSlots = (state.slots?.free ?? 0) > 0;
  const agentOnline = Boolean(state.agent?.online);

  if (account.state === 'parsed' || account.state === 'proxy_fail' || account.state === 'ready' || account.state === 'failed') {
    actions.push(`<button class="ghost small" data-action="check" data-id="${account.id}">Проверить прокси</button>`);
  }
  if (['ready', 'failed', 'done'].includes(account.state)) {
    const disabled = !freeSlots || !agentOnline;
    const reason = !agentOnline ? 'агент офлайн' : !freeSlots ? 'нет свободных слотов' : '';
    actions.push(`<button class="small" data-action="open" data-id="${account.id}" ${disabled ? 'disabled' : ''}
      title="${esc(reason)}">Открыть Web</button>`);
  }
  if (['opening', 'in_account'].includes(account.state)) {
    actions.push(`<button class="danger small" data-action="finish" data-id="${account.id}">Завершить</button>`);
  }
  if (account.has_session) {
    actions.push(`<a class="tag" href="/api/accounts/${account.id}/session">Скачать сессию</a>`);
  }

  return `
    <div class="card ${account.state === 'in_account' ? 'busy' : ''}">
      <div class="card-head">
        <div>
          <div class="card-title">${esc(title)}</div>
          <div class="card-sub">${esc(sub)}</div>
        </div>
        ${badge}
      </div>
      ${tags.length ? `<div class="card-meta">${tags.join('')}</div>` : ''}
      ${account.error ? `<div class="card-error">${esc(account.error)}</div>` : ''}
      <div class="actions">${actions.join('')}</div>
    </div>`;
}

function renderLog() {
  const box = $('#log');
  const pinned = box.scrollTop + box.clientHeight >= box.scrollHeight - 40;
  box.innerHTML = state.events.map((event) => {
    const time = event.ts ? new Date(event.ts).toLocaleTimeString('ru-RU') : '';
    const level = event.level === 'error' ? 'error' : event.level === 'warn' ? 'warn' : '';
    return `<div class="log-row ${level}"><span class="log-time">${esc(time)}</span><b>${esc(event.message)}</b></div>`;
  }).join('');
  if (pinned) box.scrollTop = box.scrollHeight;
}

// ------------------------------------------------------------------ upload

$('#zip').addEventListener('change', () => {
  const file = $('#zip').files[0];
  $('#zip-name').textContent = file ? file.name : 'Выбрать ZIP с tdata';
});

$('#upload').addEventListener('submit', async (event) => {
  event.preventDefault();
  const file = $('#zip').files[0];
  if (!file) return notify('Выбери ZIP-архив');

  const body = new FormData();
  body.append('file', file);
  body.append('proxies', $('#proxies').value);

  const button = $('#upload-btn');
  button.disabled = true;
  button.textContent = 'Разбираю...';
  try {
    const data = await apiJson('/api/batches', { method: 'POST', body });
    notify(`Найдено tdata: ${data.found}`, 'ok');
    $('#proxies').value = '';
    $('#zip').value = '';
    $('#zip-name').textContent = 'Выбрать ZIP с tdata';
    refresh();
  } catch (error) {
    notify(error.message);
  } finally {
    button.disabled = false;
    button.textContent = 'Разобрать архив';
  }
});

// ------------------------------------------------------------------ actions

$('#accounts').addEventListener('click', async (event) => {
  const button = event.target.closest('button[data-action]');
  if (!button) return;
  const id = Number(button.dataset.id);
  const action = button.dataset.action;

  if (action === 'open') {
    openProxyModal(id);
    return;
  }

  button.disabled = true;
  try {
    if (action === 'check') {
      const data = await apiJson(`/api/accounts/${id}/check`, { method: 'POST' });
      notify(data.ok ? `Прокси живой: ${data.ip}` : `Прокси мёртв: ${data.error}`, data.ok ? 'ok' : 'error');
    } else if (action === 'finish') {
      const data = await apiJson(`/api/accounts/${id}/finish`, { method: 'POST' });
      notify(data.has_session ? 'Сессия сохранена, слот свободен' : 'Закрыто без сессии', 'ok');
    }
    refresh();
  } catch (error) {
    notify(error.message);
  } finally {
    button.disabled = false;
  }
});

// ------------------------------------------------------------------ proxy modal

let pendingAccountId = null;

function openProxyModal(accountId) {
  if (!state.agent?.online) return notify('Агент на ПК офлайн');
  if ((state.slots?.free ?? 0) <= 0) return notify(`Нет свободных слотов: ${state.slots.busy}/${state.slots.max} занято`);

  const account = state.accounts.find((item) => item.id === accountId);
  pendingAccountId = accountId;
  $('#proxy-input').value = account?.proxy_web || '';
  $('#proxy-modal').showModal();
}

$('#proxy-modal').addEventListener('close', async () => {
  if ($('#proxy-modal').returnValue !== 'ok' || !pendingAccountId) return;
  const accountId = pendingAccountId;
  pendingAccountId = null;

  try {
    const data = await apiJson(`/api/accounts/${accountId}/open`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ proxy: $('#proxy-input').value }),
    });
    notify(`Профиль создаётся, слот ${data.slot}`, 'ok');
    refresh();
  } catch (error) {
    notify(error.message);
  }
});

boot();
