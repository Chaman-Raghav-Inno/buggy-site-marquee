(function () {
  'use strict';

  const F = window.Marquee;
  const { $, esc } = F;

  F.pages.ticket = async function () {
    const id = Number(F.params.get('id'));
    let t;
    const at = (iso) => new Date(iso).toLocaleString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });

    function draw() {
      const e = t.event;
      document.title = `${e.name} ticket · Marquee`;
      $('#tk-qr').innerHTML = F.qr(t.code);
      $('#tk-code').textContent = t.code;
      const stopped = t.status !== 'valid' || e.status === 'cancelled';
      $('#tk-status').textContent = stopped ? `Not valid: ${e.status === 'cancelled' ? 'event cancelled' : t.status}` : t.checked_in ? 'Checked in' : 'Valid ticket';
      $('#tk-name').innerHTML = `<a href="/event?id=${e.id}">${esc(e.name)}</a>`;
      const facts = [
        ['Doors', at(e.doors_at)],
        ['Starts', at(e.starts_at)],
        ['Venue', `${esc(e.venue)}, ${esc(e.city)}`],
        ['Ticket', esc(t.tier)],
        ['Seat', t.seat ? esc(t.seat) : 'Standing / unreserved'],
        ['Face value', F.eur(t.face)],
        ['Name on ticket', esc(t.name)],
        ['Email', esc(t.email)],
      ];
      if (t.resale) facts.push(['On resale for', F.eur(t.resale)]);
      $('#tk-facts').innerHTML = facts.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('');
      $('#tk-actions').hidden = !t.can_transfer && !t.can_resell && !t.resale;
      $('#tf-form').hidden = !t.can_transfer;
      $('#rs-form').hidden = !t.can_resell && !t.resale;
      $('#rs-cap').textContent = `Up to 2 days before the event, for no more than the face value of ${F.eur(t.face)}.`;
      $('#rs-unlist').hidden = !t.resale;
    }

    $('#tf-form').addEventListener('submit', async () => {
      const msg = $('#tf-msg');
      const name = $('#tf-name').value.trim();
      const email = $('#tf-email').value.trim();
      if (!name) return F.say(msg, 'Enter your friend\'s name.', 'error');
      if (!F.EMAIL.test(email)) return F.say(msg, 'Enter your friend\'s email address.', 'error');
      const r = await F.api(`/api/tickets/${id}/transfer`, { name, email });
      if (!r.ok) return F.say(msg, r.data.error || 'Could not send the ticket.', 'error');
      t = r.data.ticket;
      draw();
      $('#tf-form').reset();
      F.say(msg, `Sent to ${r.data.sent_to}. They'll get the ticket by email.`, 'success');
    });
    $('#rs-form').addEventListener('submit', async () => {
      const msg = $('#rs-msg');
      const raw = $('#rs-price').value.trim();
      if (!/^\d+(\.\d{1,2})?$/.test(raw) || !(Number(raw) > 0)) return F.say(msg, 'Enter a price in euros and cents, like 25.00.', 'error');
      const r = await F.api(`/api/tickets/${id}/resell`, { price: Number(raw) });
      if (!r.ok) return F.say(msg, r.data.error || 'Could not list the ticket.', 'error');
      t = r.data.ticket;
      draw();
      F.say(msg, `Listed on Marquee Resale for ${F.eur(t.resale)}.`, 'success');
    });
    $('#rs-unlist').addEventListener('click', async () => {
      const r = await F.api(`/api/tickets/${id}/unlist`, {});
      if (!r.ok) return F.say($('#rs-msg'), r.data.error || 'Could not take it off resale.', 'error');
      t = r.data.ticket;
      draw();
      F.say($('#rs-msg'), 'Taken off resale.', 'success');
    });

    const r = await F.api(`/api/tickets/${id}`);
    $('#loading').hidden = true;
    if (!r.ok) {
      $('#tk-missing').hidden = false;
      return;
    }
    t = r.data.ticket;
    draw();
    $('#ticket').hidden = false;
  };
})();
