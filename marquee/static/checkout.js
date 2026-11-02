(function () {
  'use strict';

  const F = window.Marquee;
  const { $, esc } = F;

  F.pages.checkout = async function () {
    const r = await F.api('/api/basket');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your basket.', 'error');
    const b = r.data;
    $('#loading').hidden = true;
    if (!b.lines.length) {
      $('#co-empty').hidden = false;
      return;
    }
    $('#co-event').textContent = b.event.name;
    $('#co-when').textContent = `${F.when(b.event)} · ${b.event.venue}, ${b.event.city}`;
    $('#co-lines').innerHTML = b.lines.map((x) => `<li>${F.lineText(x)}: ${F.eur(x.amount)}</li>`).join('');
    const total = b.subtotal + b.booking_fees - b.discount;
    $('#co-totals').innerHTML = [
      ['Tickets', F.eur(b.subtotal)],
      ['Booking fees', F.eur(b.booking_fees)],
      ...b.discounts.map((x) => [`Code ${esc(x.code)}`, F.eur(-x.amount), 'discount']),
    ].map(([k, v, c]) => `<div${c ? ` class="${c}"` : ''}><dt>${k}</dt><dd>${v}</dd></div>`).join('')
      + `<div class="grand"><dt>You pay</dt><dd id="co-total">${F.eur(total)}</dd></div>`;
    $('#co-pay').textContent = `Pay ${F.eur(total)}`;
    $('#checkout').hidden = false;

    $('#co-expiry').addEventListener('input', (e) => {
      const digits = e.target.value.replace(/\D/g, '').slice(0, 4);
      e.target.value = digits.length > 2 ? `${digits.slice(0, 2)}/${digits.slice(2)}` : digits;
    });
    $('#pay-form').addEventListener('submit', async () => {
      const msg = $('#co-msg');
      const body = { name: $('#co-name').value.trim(), card: $('#co-card').value.trim(), expiry: $('#co-expiry').value.trim(), cvc: $('#co-cvc').value.trim() };
      if (!body.name) return F.say(msg, 'Enter the name on the card.', 'error');
      if (!body.card) return F.say(msg, 'Enter the card number.', 'error');
      if (!/^\d\d\/\d\d$/.test(body.expiry)) return F.say(msg, 'Enter the expiry date as MM/YY.', 'error');
      F.say(msg, '');
      $('#co-pay').disabled = true;
      const res = await F.api('/api/checkout', body);
      $('#co-pay').disabled = false;
      if (!res.ok) return F.say(msg, res.data.error || 'Payment failed.', 'error');
      const o = res.data.order;
      F.setBasketCount(0);
      $('#checkout').hidden = true;
      $('#co-done').hidden = false;
      $('#co-done').innerHTML = `<h2>You're going!</h2><p>${F.plural(o.tickets.length, 'ticket')} for <strong>${esc(o.event.name)}</strong>.</p>
        <dl class="facts"><div><dt>Booking reference</dt><dd class="mono" id="co-ref">${esc(o.ref)}</dd></div><div><dt>Charged to your card</dt><dd id="co-charged">${F.eur(o.total)}</dd></div></dl>
        <p class="section"><a class="btn" href="/tickets">See my tickets</a></p>`;
    });
  };
})();
