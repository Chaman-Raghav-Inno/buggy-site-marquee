(function () {
  'use strict';

  const F = window.Marquee;
  const { $, esc } = F;

  F.pages.events = async function () {
    let page = 1;
    let filled = false;
    if (F.params.get('q')) $('#ev-q').value = F.params.get('q');
    for (const k of ['category', 'city']) {
      const v = F.params.get(k);
      if (!v) continue;
      const opt = document.createElement('option');
      opt.textContent = v;
      $(`#ev-${k}`).append(opt);
      $(`#ev-${k}`).value = v;
    }

    function query() {
      return new URLSearchParams({
        q: $('#ev-q').value.trim(), category: $('#ev-category').value, city: $('#ev-city').value,
        from: $('#ev-from').value, to: $('#ev-to').value, sort: $('#ev-sort').value, page,
      });
    }

    async function load() {
      const r = await F.api(`/api/events?${query().toString()}`);
      if (!r.ok) return F.say($('#ev-count'), r.data.error || 'Could not load events.', 'error');
      const d = r.data;
      if (!filled) {
        const cat = $('#ev-category').value;
        const city = $('#ev-city').value;
        $('#ev-category').innerHTML = '<option value="">All categories</option>' + d.categories.map((c) => `<option>${esc(c)}</option>`).join('');
        $('#ev-city').innerHTML = '<option value="">All cities</option>' + d.cities.map((c) => `<option>${esc(c)}</option>`).join('');
        $('#ev-category').value = cat;
        $('#ev-city').value = city;
        filled = true;
      }
      $('#ev-count').textContent = F.plural(d.count, 'event');
      $('#ev-list').innerHTML = d.events.map((e) => `<a class="event-card" href="/event?id=${e.id}">
          <span class="cat">${esc(e.category)}</span>
          <h2>${esc(e.name)}</h2>
          <p class="event-meta">${F.venueDay(e.doors_at, e.offset)} · ${esc(e.venue)}, ${esc(e.city)}</p>
          <div class="badges">${F.badges(e)}</div>
          <p class="price">from ${F.eur(e.from)}</p></a>`).join('')
        || '<p class="muted">No events match. Try fewer filters.</p>';
      $('#ev-page').textContent = `Page ${d.page} of ${d.pages}`;
      $('#ev-prev').disabled = d.page <= 1;
      $('#ev-next').disabled = d.page >= d.pages;
    }

    let timer;
    $('#ev-q').addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => { page = 1; load(); }, 250); });
    ['#ev-category', '#ev-city', '#ev-from', '#ev-to', '#ev-sort'].forEach((s) => $(s).addEventListener('change', () => { page = 1; load(); }));
    $('#ev-prev').addEventListener('click', () => { page -= 1; load(); });
    $('#ev-next').addEventListener('click', () => { page += 1; load(); });
    await load();
  };
})();
