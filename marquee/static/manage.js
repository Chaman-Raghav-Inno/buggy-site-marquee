(function () {
  'use strict';

  const F = window.Marquee;
  const { $, $$, esc } = F;

  F.attendeeRows = (d) => d.attendees.map((a) => `<tr><td class="mono">${esc(a.code)}</td><td>${esc(a.name)}</td><td>${esc(a.email)}</td><td>${esc(a.tier)}</td>
      <td>${esc(a.seat) || '—'}</td><td>${F.status(a.status)}</td><td>${a.checked_in ? F.venueTime(a.checked_in, d.event.offset) : '—'}</td></tr>`).join('')
    || '<tr><td colspan="7" class="muted">Nobody has booked on Marquee yet.</td></tr>';

  F.pages.manage = async function () {
    const id = Number(F.params.get('id'));
    let d;

    function draw() {
      const e = d.event;
      document.title = `${e.name} · Manage · Marquee`;
      $('#mg-name').textContent = e.name;
      $('#mg-when').textContent = `${F.when(e)} · ${e.venue}, ${e.city}`;
      $('#mg-status').innerHTML = F.status(e.status);
      $('#mg-sold').textContent = F.num(e.sold);
      $('#mg-released').textContent = `of ${F.num(e.released)} released`;
      $('#mg-capacity').textContent = F.num(e.capacity);
      $('#mg-revenue').textContent = F.eur(e.revenue);
      $('#mg-waitlist').textContent = F.plural(d.waitlist, 'person', 'people');
      const open = e.status !== 'cancelled';
      $('#mg-tiers').innerHTML = d.tiers.map((t) => `<tr><td>${esc(t.name)}${t.rows ? ` <span class="muted small">(rows ${t.rows.split('').join(', ')})</span>` : ''}</td>
          <td class="num">${F.num(t.qty)}</td><td class="num">${F.num(t.sold)}</td><td class="num">${F.num(t.remaining)}</td>
          <td>${open ? `<form class="inline-form" data-tier="${t.id}" novalidate><input class="price-input" inputmode="decimal" aria-label="Price for ${esc(t.name)}" value="${t.price.toFixed(2)}"><button type="submit" class="btn btn-small">Save</button></form>` : F.eur(t.price)}</td></tr>`).join('');
      const standing = d.tiers.filter((t) => !t.rows);
      $('#rl-form').hidden = !open || e.seated;
      $('#rl-tier').innerHTML = standing.map((t) => `<option value="${t.id}">${esc(t.name)}</option>`).join('');
      $('#cx-card').hidden = !open || e.days < 0;
      $('#mg-csv').href = `/api/organiser/events/${id}/attendees.csv`;
      $('#mg-csv').setAttribute('download', `${e.name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}-attendees.csv`);
      $('#mg-attendees').innerHTML = F.attendeeRows(d);
    }

    $('#mg-tiers').addEventListener('submit', async (e) => {
      const form = e.target.closest('[data-tier]');
      const raw = form.querySelector('input').value.trim();
      const msg = $('#mg-price-msg');
      if (!/^\d+(\.\d{1,2})?$/.test(raw) || !(Number(raw) > 0)) return F.say(msg, 'Enter a price in euros and cents.', 'error');
      const r = await F.api(`/api/organiser/events/${id}/price`, { tier: Number(form.dataset.tier), price: Number(raw) });
      if (!r.ok) return F.say(msg, r.data.error || 'Could not change the price.', 'error');
      d = r.data;
      draw();
      F.say(msg, `Price saved: ${F.eur(Number(raw))}.`, 'success');
    });
    $('#rl-form').addEventListener('submit', async () => {
      const msg = $('#rl-msg');
      const qty = Number($('#rl-qty').value.trim());
      if (!Number.isInteger(qty) || qty < 1) return F.say(msg, 'Enter how many tickets to release.', 'error');
      const r = await F.api(`/api/organiser/events/${id}/release`, { tier: Number($('#rl-tier').value), qty });
      if (!r.ok) return F.say(msg, r.data.error || 'Could not release the tickets.', 'error');
      d = r.data;
      draw();
      $('#rl-qty').value = '';
      F.say(msg, `${F.plural(qty, 'ticket')} released. ${F.num(d.event.released)} released in total.`, 'success');
    });
    $('#cx-open').addEventListener('click', () => {
      $('#cx-text').textContent = `${d.event.name} will be cancelled and every booking refunded. This can't be undone.`;
      $('#cx-dialog').returnValue = '';
      $('#cx-dialog').showModal();
    });
    $$('#cx-dialog button').forEach((b) => b.addEventListener('click', () => $('#cx-dialog').close(b.dataset.value)));
    $('#cx-dialog').addEventListener('close', async () => {
      if ($('#cx-dialog').returnValue !== 'cancel') return;
      const r = await F.api(`/api/organiser/events/${id}/cancel`, {});
      if (!r.ok) return F.toast(r.data.error || 'Could not cancel the event.', 'error');
      d = r.data;
      draw();
      F.toast('Event cancelled. Everyone has been refunded.');
    });

    const r = await F.api(`/api/organiser/events/${id}`);
    $('#loading').hidden = true;
    if (!r.ok) {
      $('#mg-missing').hidden = false;
      $('#mg-missing-text').textContent = r.data.error || 'We couldn\'t find that event.';
      return;
    }
    d = r.data;
    draw();
    $('#manage').hidden = false;
  };
})();
