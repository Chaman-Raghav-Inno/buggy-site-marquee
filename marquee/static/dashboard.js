(function () {
  'use strict';

  const F = window.Marquee;
  const { $, esc } = F;

  F.pages.dashboard = async function () {
    const r = await F.api('/api/organiser');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your events.', 'error');
    const d = r.data;
    $('#db-title').textContent = `${d.name}'s events`;
    $('#db-events').textContent = d.events.length;
    $('#db-sold').textContent = F.num(d.sold);
    $('#db-revenue').textContent = F.eur(d.revenue);
    $('#db-rows').innerHTML = d.events.map((e) => `<tr><td><a href="/event?id=${e.id}">${esc(e.name)}</a></td><td>${F.venueDay(e.doors_at, e.offset)}</td>
        <td>${F.status(e.status)}</td><td class="num">${F.num(e.sold)}</td><td class="num">${F.num(e.released)}</td><td class="num">${F.num(e.capacity)}</td>
        <td class="num">${F.eur(e.revenue)}</td><td><a class="btn btn-small btn-ghost" href="/manage?id=${e.id}">Manage</a></td></tr>`).join('');
    $('#loading').hidden = true;
    $('#dashboard').hidden = false;
  };
})();
