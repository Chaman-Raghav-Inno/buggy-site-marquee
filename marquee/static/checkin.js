(function () {
  'use strict';

  const F = window.Marquee;
  const { $, esc } = F;

  F.pages.checkin = async function () {
    let d = null;

    function drawList() {
      const done = d.attendees.filter((a) => a.checked_in).sort((a, b) => b.checked_in.localeCompare(a.checked_in));
      $('#ci-count').textContent = `${done.length} of ${d.attendees.filter((a) => a.status === 'valid').length}`;
      $('#ci-list').innerHTML = done.map((a) => `<li><span class="mono">${esc(a.code)}</span> · ${esc(a.name)} · ${F.venueTime(a.checked_in, d.event.offset)}</li>`).join('') || '<li class="muted">Nobody yet.</li>';
    }

    async function pick() {
      const r = await F.api(`/api/organiser/events/${$('#ci-event').value}`);
      if (!r.ok) return F.say($('#ci-msg'), r.data.error || 'Could not load that event.', 'error');
      d = r.data;
      F.say($('#ci-msg'), '');
      drawList();
    }

    $('#ci-event').addEventListener('change', pick);
    $('#ci-form').addEventListener('submit', async () => {
      const msg = $('#ci-msg');
      const code = $('#ci-code').value.trim();
      if (!code) return F.say(msg, 'Enter the ticket reference.', 'error');
      F.say(msg, '');
      const r = await F.api('/api/organiser/checkin', { event: Number($('#ci-event').value), code });
      if (!r.ok) return F.say(msg, r.data.error || 'Could not check that ticket.', 'error');
      d = r.data;
      const t = d.ticket;
      F.say(msg, `Checked in: ${t.name}, ${t.tier}${t.seat ? `, seat ${t.seat}` : ''}.`, 'success');
      $('#ci-code').value = '';
      drawList();
    });

    const r = await F.api('/api/organiser');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your events.', 'error');
    const live = r.data.events.filter((e) => e.status !== 'cancelled');
    $('#ci-event').innerHTML = live.map((e) => `<option value="${e.id}">${esc(e.name)} (${F.day(e.date)})</option>`).join('');
    const want = F.params.get('event');
    if (want && live.some((e) => String(e.id) === want)) $('#ci-event').value = want;
    await pick();
    $('#loading').hidden = true;
    $('#checkin').hidden = false;
  };
})();
