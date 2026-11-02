(function () {
  'use strict';

  const F = window.Marquee;
  const { $, $$, esc } = F;

  F.totals = function (b, total) {
    const rows = [
      ['Tickets', F.eur(b.subtotal)],
      ['Booking fees', F.eur(b.booking_fees)],
      ['Order fee', F.eur(b.order_fee)],
      ...b.discounts.map((x) => [`Code ${esc(x.code)} (${x.percent}% off)`, F.eur(-x.amount), 'discount']),
    ];
    return rows.map(([k, v, c]) => `<div${c ? ` class="${c}"` : ''}><dt>${k}</dt><dd>${v}</dd></div>`).join('')
      + `<div class="grand"><dt>Total</dt><dd id="${total}">${F.eur(b.total)}</dd></div>`;
  };

  F.pages.basket = async function () {
    let b;
    let tick;

    function remaining(x) {
      return Date.parse(x.added) + 15 * 60000 - Date.now();
    }

    function countdown() {
      $$('[data-timer]').forEach((el) => {
        const x = b.lines.find((l) => String(l.id) === el.dataset.timer);
        const ms = remaining(x);
        if (ms <= 0) {
          el.innerHTML = '<span class="pill pill-expired">Hold expired</span>';
          return;
        }
        const s = Math.floor(ms / 1000);
        el.textContent = `Held for ${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
      });
    }

    function draw() {
      F.setBasketCount(b.count);
      clearInterval(tick);
      $('#bk-empty').hidden = b.lines.length > 0;
      $('#basket').hidden = !b.lines.length;
      if (!b.lines.length) return;
      $('#bk-event').innerHTML = `<a href="/event?id=${b.event.id}">${esc(b.event.name)}</a>`;
      $('#bk-when').textContent = `${F.when(b.event)} · ${b.event.venue}, ${b.event.city}`;
      $('#bk-lines').innerHTML = b.lines.map((x) => `<li${x.expired ? ' class="expired"' : ''}><div><strong>${F.lineText(x)}</strong><br>
          <span class="muted small">${F.eur(x.price)} each + ${F.eur(x.fee)} booking fee</span><br>
          ${x.expired ? '<span class="pill pill-expired">Hold expired</span>' : `<span class="timer" data-timer="${x.id}"></span>`}</div>
          <div class="actions"><span class="amt">${F.eur(x.amount)}</span><button type="button" class="link" data-remove="${x.id}">Remove</button></div></li>`).join('');
      $('#bk-totals').innerHTML = F.totals(b, 'bk-total');
      countdown();
      tick = setInterval(countdown, 1000);
    }

    $('#bk-lines').addEventListener('click', async (e) => {
      const btn = e.target.closest('[data-remove]');
      if (!btn) return;
      const r = await F.api(`/api/basket/${btn.dataset.remove}/remove`, {});
      if (!r.ok) return F.toast(r.data.error || 'Could not remove that.', 'error');
      b = r.data;
      draw();
      F.toast('Removed from your basket.');
    });
    $('#code-form').addEventListener('submit', async () => {
      const code = $('#bk-code').value.trim();
      if (!code) return F.say($('#code-msg'), 'Enter a promo code.', 'error');
      const r = await F.api('/api/basket/code', { code });
      if (!r.ok) return F.say($('#code-msg'), r.data.error || 'Could not apply that code.', 'error');
      b = r.data;
      draw();
      $('#bk-code').value = '';
      F.say($('#code-msg'), `${code.toUpperCase()} applied.`, 'success');
    });

    const r = await F.api('/api/basket');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your basket.', 'error');
    b = r.data;
    $('#loading').hidden = true;
    draw();
  };
})();
