(function () {
  'use strict';

  const F = window.Marquee;
  const { $, $$, esc } = F;

  F.pages.tickets = async function () {
    let data;
    let refunding = null;

    function orderCard(o) {
      const e = o.event;
      const state = e.status === 'cancelled' ? 'Event cancelled'
        : o.status === 'refunded' ? 'Refunded' : o.days < 0 ? 'Event has taken place' : e.status === 'postponed' ? 'Postponed' : 'Booked';
      const pill = e.status === 'cancelled' || o.status === 'refunded' ? 'refunded' : e.status === 'postponed' ? 'postponed' : 'valid';
      const money = [`Paid ${F.eur(o.total)}`];
      if (o.discount) money.push(`code ${esc(o.code)} saved ${F.eur(o.discount)}`);
      if (o.status === 'refunded') money.push(`<strong>refunded ${F.eur(o.refunded)}</strong>`);
      const tickets = o.tickets.map((t) => `<li><span><span class="mono">${esc(t.code)}</span> · ${esc(t.tier)}${t.seat ? ` · seat ${esc(t.seat)}` : ''} · ${esc(t.name)} ${t.status !== 'valid' ? F.status(t.status) : ''}${t.resale ? ' <span class="pill pill-listed">On resale</span>' : ''}</span><a href="/ticket?id=${t.id}">Open ticket</a></li>`).join('');
      const canRefund = o.status === 'paid' && o.days >= 0 && e.status !== 'cancelled';
      return `<article class="card" data-order="${o.id}">
        <div class="order-head"><div><h3><a href="/event?id=${e.id}">${esc(e.name)}</a></h3>
        <p class="muted small">${esc(F.when(e))}<br>${esc(e.venue)}, ${esc(e.city)}</p></div>
        <span class="pill pill-${pill}">${state}</span></div>
        <p class="small">Booking <span class="mono">${esc(o.ref)}</span> · ${money.join(' · ')}</p>
        <ul class="ticket-rows">${tickets}</ul>
        ${canRefund ? `<div class="actions"><button type="button" class="btn btn-ghost btn-small" data-refund="${o.id}">Refund booking</button></div>` : ''}
      </article>`;
    }

    function draw() {
      const live = (o) => o.status === 'paid' && o.days >= 0 && o.event.status !== 'cancelled';
      $('#tk-upcoming').innerHTML = data.orders.filter(live).map(orderCard).join('') || '<p class="muted">Nothing coming up. <a href="/events">Find an event</a>.</p>';
      $('#tk-past').innerHTML = data.orders.filter((o) => !live(o)).map(orderCard).join('') || '<p class="muted">Nothing here yet.</p>';
      $('#tk-waitlist').innerHTML = data.waitlist.map((w) => `<li><a href="/event?id=${w.event.id}">${esc(w.event.name)}</a> (${F.date(w.event.date)}): you're number ${w.position} on the waitlist</li>`).join('')
        || '<li class="muted">You aren\'t on any waitlists.</li>';
    }

    document.addEventListener('click', async (e) => {
      const b = e.target.closest('[data-refund]');
      if (!b) return;
      refunding = Number(b.dataset.refund);
      const q = await F.api(`/api/orders/${refunding}/refund`);
      if (!q.ok) return F.toast(q.data.error || 'Could not work out your refund.', 'error');
      const o = data.orders.find((x) => x.id === refunding);
      $('#rf-text').textContent = q.data.amount
        ? `You'll get ${F.eur(q.data.amount)} back for ${o.event.name}, and your tickets will stop working.`
        : `${o.event.name}: no refund is available.`;
      $('#rf-reason').textContent = q.data.reason;
      $('#rf-confirm').hidden = !q.data.amount;
      $('#rf-dialog').returnValue = '';
      $('#rf-dialog').showModal();
    });
    $$('#rf-dialog button').forEach((b) => b.addEventListener('click', () => $('#rf-dialog').close(b.dataset.value)));
    $('#rf-dialog').addEventListener('close', async () => {
      if ($('#rf-dialog').returnValue !== 'refund' || !refunding) return;
      const r = await F.api(`/api/orders/${refunding}/refund`, {});
      if (!r.ok) return F.toast(r.data.error || 'Could not refund that booking.', 'error');
      data = r.data;
      draw();
      F.toast('Booking refunded.');
    });

    const r = await F.api('/api/tickets');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your tickets.', 'error');
    data = r.data;
    draw();
    $('#loading').hidden = true;
    $('#tickets').hidden = false;
  };
})();
