(function () {
  'use strict';

  const F = (window.Marquee = window.Marquee || {});
  F.pages = F.pages || {};
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const ENTITIES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  F.$ = $;
  F.$$ = $$;
  F.esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ENTITIES[c]);
  F.params = new URLSearchParams(location.search);
  F.role = document.body.dataset.role || '';
  F.EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

  document.addEventListener('submit', (e) => {
    if (!e.target.matches('[data-native]')) e.preventDefault();
  }, true);

  F.api = async function (path, body) {
    const opts = body === undefined
      ? { credentials: 'same-origin' }
      : { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
    let res;
    try {
      res = await fetch(path, opts);
    } catch (e) {
      return { ok: false, status: 0, data: { error: 'You appear to be offline. Try again.' } };
    }
    if (res.status === 401 && !path.startsWith('/api/login')) {
      location.href = '/login?next=' + encodeURIComponent(location.pathname + location.search);
    }
    let data = {};
    try {
      data = await res.json();
    } catch (e) {
      data = {};
    }
    return { ok: res.ok, status: res.status, data };
  };

  let toastTimer;
  F.toast = function (text, kind) {
    const el = $('#toast');
    el.textContent = text;
    el.className = 'toast' + (kind ? ' toast-' + kind : '');
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.hidden = true; }, 3500);
  };
  F.say = function (el, text, kind) {
    el.textContent = text || '';
    el.classList.toggle('error', kind === 'error');
    el.classList.toggle('success', kind === 'success');
  };
  F.plural = (n, word, many) => `${n} ${n === 1 ? word : many || word + 's'}`;
  F.day = (iso) => new Date(iso + 'T00:00:00Z').toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' });
  F.date = (iso) => new Date(iso + 'T00:00:00Z').toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
  F.eur = (n) => (n < 0 ? '−€' : '€') + Math.abs(Number(n)).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  F.num = (n) => Number(n).toLocaleString('en-GB');
  F.addDays = (iso, n) => {
    const d = new Date(iso + 'T00:00:00Z');
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  };
  // Times are stored as UTC instants; venues keep a fixed offset from UTC.
  F.tz = (offset) => (offset === 0 ? 'UTC' : `UTC${offset > 0 ? '+' : '−'}${Math.abs(offset)}`);
  const shifted = (iso, offset) => new Date(Date.parse(iso) + offset * 3600000);
  F.venueTime = (iso, offset) => shifted(iso, offset).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' });
  F.venueDay = (iso, offset) => shifted(iso, offset).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
  F.when = (ev) => `${F.venueDay(ev.doors_at, ev.offset)} · doors ${F.venueTime(ev.doors_at, ev.offset)}, starts ${F.venueTime(ev.starts_at, ev.offset)} (${F.tz(ev.offset)})`;
  const LABELS = { 'on sale': 'On sale', postponed: 'Postponed', cancelled: 'Cancelled', valid: 'Valid', refunded: 'Refunded', paid: 'Paid' };
  F.status = (s) => `<span class="pill pill-${F.esc(s.replace(/\s+/g, '-'))}">${F.esc(LABELS[s] || s[0].toUpperCase() + s.slice(1))}</span>`;
  F.badges = function (e) {
    const out = [];
    if (e.status === 'postponed') out.push('<span class="pill pill-postponed">Postponed</span>');
    if (e.sold_out) out.push('<span class="pill pill-soldout">Sold out</span>');
    else if (e.few_left) out.push('<span class="pill pill-few">Few left</span>');
    return out.join('');
  };

  F.lineText = (x) => `${F.esc(x.name)} × ${x.qty}${x.seats.length ? ` · seats ${x.seats.map(F.esc).join(', ')}` : ''}`;

  F.setBasketCount = (n) => { const b = $('#basket-count'); if (b) b.textContent = n; };

  // A decorative QR-style code drawn from the ticket reference.
  F.qr = function (code) {
    const size = 25;
    let seed = 0;
    for (const ch of code) seed = (seed * 31 + ch.charCodeAt(0)) >>> 0;
    const rand = () => { seed = (seed * 1103515245 + 12345) >>> 0; return (seed >>> 16) & 1; };
    const finder = (x, y) => {
      const inBox = (cx, cy) => x >= cx && x < cx + 7 && y >= cy && y < cy + 7;
      for (const [cx, cy] of [[0, 0], [size - 7, 0], [0, size - 7]]) {
        if (inBox(cx, cy)) {
          const dx = x - cx;
          const dy = y - cy;
          return dx === 0 || dx === 6 || dy === 0 || dy === 6 || (dx >= 2 && dx <= 4 && dy >= 2 && dy <= 4) ? 1 : 0;
        }
      }
      return -1;
    };
    let cells = '';
    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        const f = finder(x, y);
        if (f === 1 || (f === -1 && rand())) cells += `<rect x="${x}" y="${y}" width="1" height="1"/>`;
      }
    }
    return `<svg class="qr" viewBox="-2 -2 ${size + 4} ${size + 4}" role="img" aria-label="QR code for ${F.esc(code)}"><rect x="-2" y="-2" width="${size + 4}" height="${size + 4}" fill="#fff"/><g fill="#1c1626">${cells}</g></svg>`;
  };

  function setupChrome() {
    const page = document.body.dataset.page;
    $$('.nav a').forEach((a) => { if (a.dataset.nav === page) a.setAttribute('aria-current', 'page'); });
    const logout = $('#logout');
    if (logout) {
      logout.addEventListener('click', async () => {
        await F.api('/api/logout', {});
        location.href = '/';
      });
    }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    setupChrome();
    const run = F.pages[document.body.dataset.page];
    if (!run) return;
    document.body.classList.add('is-loading');
    try {
      await run();
    } finally {
      document.body.classList.remove('is-loading');
    }
  });
})();
