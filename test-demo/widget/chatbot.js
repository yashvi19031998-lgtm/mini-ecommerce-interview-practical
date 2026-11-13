/*
 * Website chatbot widget (served by the LeadsGen backend at /widget/chatbot.js).
 * Embed on the company website:   <script src="https://YOUR-BACKEND/widget/chatbot.js" defer></script>
 * Self-contained: no libraries, all styles prefixed "sgicb-", all text inserted as text (never as HTML).
 */
(function () {
  if (window.__sgiChatbotLoaded) return;
  window.__sgiChatbotLoaded = true;

  var script = document.currentScript || (function () {
    var all = document.getElementsByTagName('script');
    for (var i = all.length - 1; i >= 0; i--) if ((all[i].src || '').indexOf('/widget/chatbot.js') !== -1) return all[i];
    return null;
  })();
  var API = (script && script.src ? new URL(script.src, location.href).origin : location.origin) + '/public/chat';
  var STORE = 'sgicb-state-v1';

  var state = { open: false, history: [], lead: {}, asked: '' };
  try { var saved = JSON.parse(sessionStorage.getItem(STORE) || 'null'); if (saved && saved.history) state = saved; } catch (e) { /* private mode */ }
  function persist() { try { sessionStorage.setItem(STORE, JSON.stringify(state)); } catch (e) { /* ignore */ } }

  var css = [
    '.sgicb-btn{position:fixed;right:20px;bottom:20px;z-index:2147483000;width:56px;height:56px;border-radius:50%;border:0;',
    'background:#1a6dff;color:#fff;cursor:pointer;box-shadow:0 10px 28px rgba(26,109,255,.35);display:flex;align-items:center;justify-content:center}',
    '.sgicb-btn:focus-visible,.sgicb-send:focus-visible,.sgicb-x:focus-visible{outline:2px solid #1a6dff;outline-offset:2px}',
    '.sgicb-panel{position:fixed;right:20px;bottom:20px;z-index:2147483000;width:min(380px,calc(100vw - 24px));height:min(560px,calc(100vh - 40px));',
    'background:#fff;color:#16181d;border-radius:18px;box-shadow:0 24px 60px rgba(17,18,20,.25);display:flex;flex-direction:column;overflow:hidden;',
    'font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}',
    '.sgicb-head{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;background:#1a6dff;color:#fff}',
    '.sgicb-head b{font-size:14px}.sgicb-head small{display:block;opacity:.85;font-size:11.5px}',
    '.sgicb-x{width:30px;height:30px;border:0;border-radius:50%;background:rgba(255,255,255,.18);color:#fff;cursor:pointer;font-size:18px;line-height:1}',
    '.sgicb-list{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;background:#f7f7f8}',
    '.sgicb-m{max-width:85%;padding:9px 12px;border-radius:14px;white-space:pre-wrap;overflow-wrap:anywhere}',
    '.sgicb-bot{background:#fff;border:1px solid #ececee;align-self:flex-start;border-bottom-left-radius:4px}',
    '.sgicb-me{background:#1a6dff;color:#fff;align-self:flex-end;border-bottom-right-radius:4px}',
    '.sgicb-err{background:#fdecea;color:#c0392b;align-self:flex-start}',
    '.sgicb-form{display:flex;gap:8px;padding:10px;border-top:1px solid #ececee;background:#fff}',
    '.sgicb-in{flex:1;min-width:0;height:40px;border:1px solid #e2e2e5;border-radius:999px;padding:0 14px;font:inherit;outline:none}',
    '.sgicb-in:focus{border-color:#1a6dff;box-shadow:0 0 0 3px rgba(26,109,255,.14)}',
    '.sgicb-send{width:40px;height:40px;border:0;border-radius:50%;background:#1a6dff;color:#fff;cursor:pointer;font-size:16px}',
    '.sgicb-send:disabled{opacity:.5;cursor:not-allowed}',
    '.sgicb-hp{position:absolute!important;left:-9999px!important;width:1px;height:1px;opacity:0}',
    '.sgicb-note{font-size:11px;color:#8a8f98;padding:0 12px 8px;background:#fff}',
    '@media (max-width:480px){.sgicb-panel{right:6px;left:6px;bottom:6px;width:auto;height:calc(100vh - 12px)}}'
  ].join('');
  var style = document.createElement('style'); style.textContent = css; document.head.appendChild(style);

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

  var btn = el('button', 'sgicb-btn'); btn.type = 'button'; btn.setAttribute('aria-label', 'Chat with us'); btn.textContent = '💬';
  var panel = el('section', 'sgicb-panel'); panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-label', 'Chat');
  var head = el('div', 'sgicb-head');
  var titles = el('div'); titles.appendChild(el('b', null, 'Chat with us')); titles.appendChild(el('small', null, 'We usually reply within a day'));
  var close = el('button', 'sgicb-x', '×'); close.type = 'button'; close.setAttribute('aria-label', 'Close chat');
  head.appendChild(titles); head.appendChild(close);
  var list = el('div', 'sgicb-list'); list.setAttribute('aria-live', 'polite');
  var form = el('form', 'sgicb-form');
  var input = el('input', 'sgicb-in'); input.maxLength = 600; input.placeholder = 'Type your message…'; input.setAttribute('aria-label', 'Your message');
  var hp = el('input', 'sgicb-hp'); hp.tabIndex = -1; hp.setAttribute('aria-hidden', 'true'); hp.autocomplete = 'off'; hp.name = 'website';
  var send = el('button', 'sgicb-send', '➤'); send.type = 'submit'; send.setAttribute('aria-label', 'Send');
  form.appendChild(input); form.appendChild(hp); form.appendChild(send);
  var note = el('div', 'sgicb-note', 'Your details are used only to reply to your enquiry.');
  panel.appendChild(head); panel.appendChild(list); panel.appendChild(form); panel.appendChild(note);

  function add(role, text) {
    var m = el('div', 'sgicb-m ' + (role === 'user' ? 'sgicb-me' : role === 'error' ? 'sgicb-err' : 'sgicb-bot'), text);
    list.appendChild(m); list.scrollTop = list.scrollHeight;
  }
  function render() {
    list.textContent = '';
    if (!state.history.length) add('bot', 'Hello! 👋 How can we help you? Ask about websites, apps, software or AI - or tell us what you need.');
    state.history.forEach(function (h) { add(h.role, h.text); });
  }
  function setOpen(v) {
    state.open = v; persist();
    if (v) { btn.remove(); document.body.appendChild(panel); render(); input.focus(); }
    else { panel.remove(); document.body.appendChild(btn); }
  }

  var busy = false;
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var text = (input.value || '').trim();
    if (!text || busy) return;
    input.value = ''; busy = true; send.disabled = true;
    state.history.push({ role: 'user', text: text }); add('user', text); persist();
    var typing = el('div', 'sgicb-m sgicb-bot', '…'); list.appendChild(typing); list.scrollTop = list.scrollHeight;
    fetch(API, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, history: state.history.slice(-12), lead: state.lead, asked: state.asked,
                             page: location.href.slice(0, 300), hp: hp.value })
    }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        typing.remove();
        if (!res.ok || !res.j.success) { add('error', (res.j && res.j.error) || 'Sorry, something went wrong. Please try again.'); return; }
        state.lead = res.j.lead || state.lead; state.asked = res.j.ask || '';
        state.history.push({ role: 'bot', text: res.j.reply }); add('bot', res.j.reply); persist();
      })
      .catch(function () { typing.remove(); add('error', 'Could not reach us right now. Please try again later.'); })
      .then(function () { busy = false; send.disabled = false; input.focus(); });
  });
  btn.addEventListener('click', function () { setOpen(true); });
  close.addEventListener('click', function () { setOpen(false); });
  panel.addEventListener('keydown', function (e) { if (e.key === 'Escape') setOpen(false); });

  function start() { if (state.open) setOpen(true); else document.body.appendChild(btn); }
  if (document.body) start(); else document.addEventListener('DOMContentLoaded', start);
})();
