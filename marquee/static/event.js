(function () {
  'use strict';

  const F = window.Marquee;
  const { $, esc } = F;

  F.pages.event = async function () {
    const id = Number(F.params.get('id'));
    let d;
    const picked = new Set();

    function tierNote(t) {
      if (t.kind === 'early') return `Until ${F.day(t.ends)}`;
      if (t.kind === 'concession') return 'Under 16 or 65 and over on the day';
      if (t.kind === 'vip') return 'Includes extras listed above';
      if (t.rows) return `Rows ${t.rows.split('').join(', ')}`;
      return '';
    }

    function tierState(t) {
      if (!t.on_sale) return 'Not on sale';
      if (t.remaining <= 0) return 'Sold out';
      if (t.remaining <= 10) return `Only ${t.remaining} left`;
      return '';
    }

    function drawSeats() {
      const zone = Object.fromEntries(d.tiers.map((t) => [t.id, t]));
      $('#legend').innerHTML = d.tiers.map((t) => `<li><span class="seat${t.kind === 'premium' ? ' premium' : ''}"></span>${esc(t.name)} (rows ${t.rows.split('').join(', ')}) ${F.eur(t.price)}</li>`).join('')
        + '<li><span class="seat wheelchair"></span>♿ Wheelchair space</li><li><span class="seat taken"></span>Taken</li><li><span class="seat mine"></span>In your basket</li><li><span class="seat" aria-pressed="true"></span>Your choice</li>';
      $('#seatmap').innerHTML = '<div class="seat-grid"><div class="stage">STAGE</div>' + d.seats.map((row) => `<div class="seat-row"><span class="row-label">${row.row}</span>${row.seats.map((s) => {
        const t = zone[s.tier];
        const off = s.state === 'taken' || s.state === 'mine';
        const label = `Seat ${s.id}, ${t.name} ${F.eur(t.price)}${s.state === 'wheelchair' ? ', wheelchair space' : ''}${off ? ', not available' : ''}`;
        return `<button type="button" class="seat ${t.kind === 'premium' ? 'premium ' : ''}${s.state}" data-seat="${s.id}" data-tier="${t.id}" aria-pressed="${picked.has(s.id)}" aria-label="${esc(label)}" title="${esc(label)}"${off ? ' disabled' : ''}>${s.state === 'wheelchair' ? '♿' : s.n}</button>`;
      }).join('')}<span class="row-label">${row.row}</span></div>`).join('') + '</div>';
      drawPicked();
    }

    function drawPicked() {
      if (!picked.size) return F.say($('#picked'), 'Choose your seats on the map.');
      const price = Object.fromEntries(d.tiers.map((t) => [t.id, t.price]));
      const seats = [...picked];
      const total = seats.reduce((s, id) => s + price[$(`[data-seat="${id}"]`).dataset.tier], 0);
      F.say($('#picked'), `${F.plural(seats.length, 'seat')}: ${seats.join(', ')} · ${F.eur(total)}`);
    }

    function drawTiers() {
      $('#tiers').innerHTML = d.tiers.map((t) => {
        const state = tierState(t);
        const off = !t.on_sale || t.remaining <= 0;
        const note = [tierNote(t), state].filter(Boolean).join(' · ');
        return `<li><label class="${off ? 'off' : ''}"><span><input type="radio" name="tier" value="${t.id}" data-kind="${t.kind}"${off ? ' disabled' : ''}><span>${esc(t.name)}<span class="tier-note">${esc(note)}</span></span></span><span class="tier-price">${F.eur(t.price)}</span></label></li>`;
      }).join('');
      const first = $('#tiers input:not([disabled])');
      if (first) first.checked = true;
      syncTier();
    }

    function syncTier() {
      const chosen = $('#tiers input:checked');
      const concession = chosen && chosen.dataset.kind === 'concession';
      $('#dob-field').hidden = !concession;
      $('#buy-qty').disabled = concession;
      if (concession) $('#buy-qty').value = '1';
    }

    function draw() {
      const e = d.event;
      const v = d.venue;
      document.title = `${e.name} · Marquee`;
      $('#ev-cat').textContent = e.category;
      $('#ev-name').textContent = e.name;
      $('#ev-performer').textContent = e.performer;
      const badges = [];
      if (e.status !== 'on sale') badges.push(F.status(e.status));
      if (d.all_sold_out) badges.push('<span class="pill pill-soldout">Sold out</span>');
      else if (e.few_left) badges.push('<span class="pill pill-few">Few left</span>');
      $('#ev-badges').innerHTML = badges.join('');
      const facts = [['When', esc(F.when(e))], ['Venue', `${esc(v.name)}, ${esc(v.city)}`], ['Capacity', F.num(v.capacity)]];
      if (e.status === 'postponed' && e.original_date) facts.push(['Was', `${F.date(e.original_date)} (postponed)`]);
      if (e.limit) facts.push(['Limit', `${e.limit} tickets per account`]);
      $('#ev-facts').innerHTML = facts.map(([k, val]) => `<div><dt>${k}</dt><dd>${val}</dd></div>`).join('');
      $('#ev-about').textContent = e.about;
      $('#ev-rules').innerHTML = [
        'Up to 8 tickets per order.',
        e.limit ? `No more than ${e.limit} tickets per account, across all your orders.` : '',
        `Tickets in your basket are held for 10 minutes.`,
        v.seated ? 'Premium rows cost more; wheelchair spaces are kept for people who need them.' : '',
      ].filter(Boolean).map((x) => `<li>${esc(x)}</li>`).join('');

      const closed = e.status === 'cancelled'
        ? 'This event has been cancelled. Everyone who booked has been refunded.'
        : F.role === 'organiser' ? 'Organiser accounts can\'t buy tickets. Log in as a fan to buy.' : '';
      $('#buy-closed').textContent = closed;
      $('#buy-closed').hidden = !closed;
      $('#buy-form').hidden = Boolean(closed) || d.all_sold_out;
      $('#waitlist').hidden = Boolean(closed) || !d.all_sold_out;
      if (d.all_sold_out) {
        const w = d.waitlist;
        $('#wl-text').textContent = `Every ticket has sold out. ${F.plural(w.count, 'person', 'people')} ${w.count === 1 ? 'is' : 'are'} on the waitlist.`;
        $('#wl-join').hidden = Boolean(w.position);
        if (w.position) F.say($('#wl-msg'), `You're number ${w.position} on the waitlist.`, 'success');
      }
      $('#presale').hidden = !e.presale_until;
      if (e.presale_until) $('#presale-text').textContent = `Presale: you need a presale code until general sale opens on ${F.date(e.presale_until)}.`;
      $('#ga').hidden = v.seated;
      $('#seated').hidden = !v.seated;
      if (v.seated) drawSeats();
      else drawTiers();
    }

    async function load() {
      const r = await F.api(`/api/events/${id}`);
      d = r.data;
      draw();
    }

    $('#buy-qty').innerHTML = Array.from({ length: 8 }, (_, i) => `<option>${i + 1}</option>`).join('');
    $('#tiers').addEventListener('change', syncTier);
    $('#seatmap').addEventListener('click', (e) => {
      const b = e.target.closest('[data-seat]');
      if (!b || b.disabled) return;
      const seat = b.dataset.seat;
      if (picked.has(seat)) picked.delete(seat);
      else if (picked.size >= 8) return F.say($('#buy-msg'), 'You can choose up to 8 seats.', 'error');
      else picked.add(seat);
      b.setAttribute('aria-pressed', String(picked.has(seat)));
      F.say($('#buy-msg'), '');
      drawPicked();
    });
    $('#buy-form').addEventListener('submit', async () => {
      const msg = $('#buy-msg');
      const body = { event: id, presale: $('#buy-presale').value.trim() };
      if (d.venue.seated) {
        if (!picked.size) return F.say(msg, 'Choose your seats on the map.', 'error');
        body.seats = [...picked];
        body.access = $('#buy-access').checked;
      } else {
        const chosen = $('#tiers input:checked');
        if (!chosen) return F.say(msg, 'Choose a ticket type.', 'error');
        body.tier = Number(chosen.value);
        body.qty = Number($('#buy-qty').value);
        if (chosen.dataset.kind === 'concession') {
          body.dob = $('#buy-dob').value;
          if (!body.dob) return F.say(msg, 'Enter the ticket holder\'s date of birth.', 'error');
        }
      }
      $('#buy-btn').disabled = true;
      const r = await F.api('/api/basket', body);
      $('#buy-btn').disabled = false;
      if (!r.ok) return F.say(msg, r.data.error || 'Could not add those tickets.', 'error');
      F.setBasketCount(r.data.count);
      picked.clear();
      const fresh = await F.api(`/api/events/${id}`);
      if (fresh.ok) { d = fresh.data; draw(); }
      F.say(msg, `Added to your basket${r.data.replaced ? ' (the tickets for another event were taken out)' : ''}. We'll hold them for ${r.data.hold_minutes} minutes.`, 'success');
      $('#buy-next').hidden = false;
    });
    $('#wl-join').addEventListener('click', async () => {
      const r = await F.api('/api/waitlist', { event: id });
      if (!r.ok) return F.say($('#wl-msg'), r.data.error || 'Could not join the waitlist.', 'error');
      d = r.data;
      draw();
    });

    await load();
    $('#loading').hidden = true;
    $('#event').hidden = false;
  };
})();
