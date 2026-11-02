(function () {
  'use strict';

  const F = window.Marquee;
  const { $, esc } = F;

  F.pages.help = async function () {
    const [r, me] = await Promise.all([F.api('/api/offers'), F.api('/api/me')]);
    if (!r.ok) return F.toast('Could not load the offers.', 'error');
    const today = me.data.today;
    $('#offer-rows').innerHTML = r.data.codes.map((c) => `<tr><td class="mono">${esc(c.code)}</td><td>${esc(c.about)}</td>
        <td>${F.date(c.ends)}${c.ends < today ? ' <span class="pill pill-expired">Ended</span>' : ''}</td></tr>`).join('');
  };
})();
