# Marquee: answer key (40 planted bugs)

Marquee is a demo event ticketing site (event listings with search and filters, event pages with ticket types and
seat maps, a basket with timed holds, promo codes, checkout, my tickets with transfers, resale and refunds, waitlists,
and an organiser dashboard with price changes, ticket releases, cancellation, an attendee list and check-in) with
**functional bugs planted on purpose**, for checking what the AI QA Scanner finds. Most bugs break a rule published on
the site, so finding them takes the rules, some arithmetic, a download, a second page or the organiser account.

This file is never served, and nothing the site serves (pages, scripts, CSS, images) names or hints at a bug.
Server-side code marks each one with a `BUG-nn` comment; `tests/test_marquee.py` keeps the server-side ones in place.
The rules every bug breaks are published on the site's **Ticket rules** page (`/help`), and the important ones are
repeated on the event, ticket and organiser pages.

## Run it

- **Locally**: `python -m marquee` (port 8088, or `PORT`), then open http://localhost:8088.
- **Railway**: New service → GitHub repo → this repository, then **Generate domain**. `railway.json` sets the start
  command and health check; no variables or volume needed.

Every visitor (cookie) gets a private copy of the demo world, dated around today, so parallel scans never see each
other's changes. Logging in as Zoe and then Max in the same browser shares one world, so what Max does shows up for
Zoe. A restart resets everything.

## Test data

Days below are counted from the day the session starts ("day 0" is today, UTC). Times are venue times.

| What | Value |
|---|---|
| Accounts (password `Marquee@2026`, listed on the login page) | `zoe@marquee.test` Zoe Park, fan · `max@marquee.test` Max Okafor, organiser of The Velvet Static, Hamlet, Static Bloom, Glasshouse Orchestra, Tidewater, Northern Lights Revue, Kite Hill and Quiet Hours. Other events are run by Rhea Banks (no login) |
| Venues | The Corn Exchange, Northport (UTC, seated A–H × 12, ♿ H1–H2, capacity 96) · Harbour Arena, Calder Bay (UTC−5, standing, 1,200) · The Lantern Rooms, Veloria (UTC+2, standing, 250) · Riverside Playhouse, Ashby Fields (UTC+1, seated A–F × 10, ♿ F1–F2, 60) · Fairgrounds Stadium, Northport (UTC, standing, 5,000) |
| Events (15) | Midnight Brass (day −1) · Quiet Hours (+3, €26) · Comet Club (**postponed** from +1 to +5, €32) · Comets v Gulls (+6, Standard €24, Concession €12) · Tidewater (+7, seated) · Hamlet, Unplugged (+9, seated: Premium rows A–B €58, Standard €36) · The Velvet Static (+12, Standard €45, VIP €95, **limit 4 per account**, doors 19:00 UTC−5) · Laugh Track Live (+16, seated: Premium €32.45, Standard €24.95) · Ferris & Wheel (+18, **early bird €18 until day 0**, Standard €25) · Paper Moons (+20, Standard €22 **sold out**, VIP €40 with 20 left) · Static Bloom (+25, €30, **3 left**) · Glasshouse Orchestra (+30, **sold out**, 6 on the waitlist) · Kite Hill (+35, €40) · Northern Lights Revue (+40, seated: Premium €48, Standard €30) · Rivals Cup Final (+50, **presale until day +3**, code `RIVALS26`) |
| Fees | 12% booking fee per ticket (to the nearest cent) + one €2.50 order fee |
| Promo codes (listed on `/help`) | `MARQUEE10` 10% until day +60 · `ENCORE5` 5% until day +30 · `AUTUMN15` 15%, **ended day −1** |
| Zoe's bookings | Midnight Brass 2 × €28 (€65.22) · The Velvet Static 2 × €45 (€103.30, tickets 103–104) · Comet Club 2 × €32 (€74.18) · Tidewater seats C5–C6 at €36 (€83.14) · Kite Hill 2 × €40 with MARQUEE10 (tickets €72 after the code, €84.10 in all) · Quiet Hours 2 × €26 (€60.74, tickets 111–112) · Northern Lights Revue Premium A7–A8 at €48 (€110.02) |
| Other people's bookings | Ivy Chen: Quiet Hours ticket 113, Northern Lights B3 · "Lee, Jordan": 2 Quiet Hours, 2 Static Bloom · Priya Nair 1 and Tom Okoro 4 (with AUTUMN15) for Kite Hill · Ana Rios: Laugh Track Live D4–D5 · Ben Hale, Sofia Marin |
| Basket | Zoe's basket starts with 2 Comets v Gulls Standard tickets whose 10-minute hold ran out 5 minutes before the session began |
| Waitlist | Glasshouse Orchestra: Zoe is number 4 of 6 |

Difficulty: **Medium** needs a flow or a comparison; **Hard** needs the published rules, a second page, a download,
a reload or the other account; **Expert** needs arithmetic across several numbers, an age or a date boundary.

## The bugs

### Events and search

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-01 | "Sold out" when only one ticket type has gone | Events: Paper Moons; open it | No badge (VIP still on sale) | Listing says "Sold out"; the event page sells VIP at €40 | Low | Medium | `server.py` `Store.summary` |
| BUG-02 | Price sort ignores the "from" price | Events, sort by Price: lowest first | Comets v Gulls (from €12) first | Paper Moons (from €40) first: sorted by the Standard price | Low | Hard | `server.py` `Store.events` |
| BUG-03 | Paging skips an event | Events: "15 events"; page through all 3 pages | 15 cards | 14 cards; The Velvet Static never shows (page 2 starts one late) | Medium | Hard | `server.py` `Store.events` |
| BUG-04 | A past event is listed and on sale | Events: Midnight Brass (yesterday) is first; add 2 tickets | Not listed; tickets off sale | Listed, and "Added to your basket" (it can be bought) | High | Medium | `server.py` `Store.events`, `Store.tier_info`, `Store.add_to_basket` |
| BUG-05 | Search ignores venues | Events: search "Lantern Rooms" (or "Corn Exchange") | The events there | "0 events" | Low | Medium | `server.py` `Store.events` |

### Event page and seats

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-06 | Early bird ends a day early | Ferris & Wheel: Early bird "Until" today | On sale at €18 until the end of today | "Not on sale" | Medium | Hard | `server.py` `Store.tier_info` |
| BUG-07 | Ticket times use the browser's time zone | The Velvet Static: event page says doors 19:00 (UTC−5); open Zoe's ticket (`/ticket?id=103`) | Doors 19:00 on the same day | "Sun … 00:00" (UTC, the next day) in a browser that isn't on UTC−5 | Medium | Hard | `static/ticket.js` (no venue offset) |
| BUG-08 | Concession age uses the birth year only | Comets v Gulls, Concession, date of birth 65 years before the event day plus one day | Refused (64 on the day) | Added. The other way, a 15-year-old whose birthday is after the event is refused | Medium | Expert | `server.py` `concession_ok` |
| BUG-09 | Premium seats are charged as Standard | Hamlet: pick A1 and A2 ("2 seats … €116.00"), add, open the basket | Premium €58 each | "Standard × 2 … €36.00 each" (€72) | High | Hard | `server.py` `Store.add_to_basket` |
| BUG-10 | Wheelchair spaces open to anyone | Hamlet: pick ♿ F1 without ticking "I need a wheelchair space" | Not selectable / refused | Added | Medium | Medium | `server.py` `Store.add_to_basket`, `static/event.js` |
| BUG-11 | Single-seat gaps only checked on the left | Hamlet: pick C5 (refused: leaves C4), then pick D6 alone | D6 refused (leaves D7 between it and taken D8) | Added | Low | Hard | `server.py` `single_gap` |

### Ticket limits and holds

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-12 | Per-account limit ignores earlier orders | The Velvet Static (limit 4; Zoe has 2): add 4 Standard | At most 2 more | 4 added and can be bought (6 in all) | High | Hard | `server.py` `Store.add_to_basket` |
| BUG-13 | 8-per-order limit beaten by adding twice | Kite Hill: add 5, then 5 more | Second add refused | Basket holds 10 and checks out | Medium | Medium | `server.py` `Store.add_to_basket` |
| BUG-14 | Expired holds stay in the basket and are charged | Basket: Comets v Gulls × 2 says "Hold expired"; Checkout, pay | Gone from the basket; nothing to pay | Still totalled; booked and charged (€58.76) | High | Hard | `server.py` `Store.basket`, `Store.checkout` |
| BUG-15 | Hold timer starts at 15 minutes | Add any tickets, open the basket | "Held for 9:59" (10-minute holds) | "Held for 14:59" | Low | Medium | `static/basket.js` |
| BUG-16 | Last tickets can be oversold | Static Bloom ("Only 3 left"): add 5, check out | Refused: only 3 left | Bought; 252 sold of 250 | Critical | Medium | `server.py` `Store.add_to_basket` |

### Basket, fees and checkout

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-17 | Order fee charged per ticket | Add 2 tickets, open the basket | Order fee €2.50 | €5.00 (€2.50 × tickets) | High | Medium | `server.py` `Store.priced` |
| BUG-18 | Booking fee rounded up | Laugh Track Live, two Standard seats (€24.95) | €2.99 each (12% = €2.994) | €3.00 each | Low | Expert | `server.py` `booking_fee` |
| BUG-19 | Checkout total leaves out the order fee | Basket total, then Checkout "You pay", then pay | Same total everywhere | "You pay" is lower by the order fee; the card is charged the basket total | High | Hard | `static/checkout.js` |
| BUG-20 | Expired code accepted | Basket: apply AUTUMN15 (ended yesterday, per `/help`) | "That code has expired" | "AUTUMN15 applied." | Medium | Medium | `server.py` `Store.apply_code` |
| BUG-21 | Promo codes discount the fees too | 2 Laugh Track Standard seats (€49.90 + €6.00 fees), apply MARQUEE10 | −€4.99 | −€5.59 (10% of tickets and fees) | Medium | Hard | `server.py` `Store.priced` |
| BUG-22 | Two codes stack | Apply AUTUMN15, then MARQUEE10 | The second replaces the first | Both discount lines (25% off) | Medium | Medium | `server.py` `Store.apply_code` |
| BUG-23 | Presale sold without a code | Rivals Cup Final (presale until day +3): leave the code blank, add | "Enter the presale code" | Added (a wrong code is refused) | High | Medium | `server.py` `Store.add_to_basket` |
| BUG-24 | Card expiring this month refused | Checkout with expiry = this month (e.g. 11/26 in November 2026) | Accepted (valid to month end) | "That card has expired." | Medium | Hard | `server.py` `card_expired` |

### My tickets

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-25 | Anyone's ticket opens by changing the id | Open Zoe's Quiet Hours ticket (`/ticket?id=112`), change to `id=113` | "We couldn't find that ticket" | Ivy Chen's ticket: name, email, reference and QR code | Critical | Hard | `server.py` `Store.ticket` |
| BUG-26 | A ticket can be sent to yourself | Quiet Hours ticket: send to `zoe@marquee.test` | Refused | "Sent to zoe@marquee.test"; Zoe now holds an extra ticket | Low | Medium | `server.py` `Store.transfer` |
| BUG-27 | A sent ticket stays valid | Quiet Hours ticket: send to ana@example.com | Zoe's copy marked transferred, no QR | Still "Valid ticket" with its QR; it checks in at the door too | High | Hard | `server.py` `Store.transfer` |
| BUG-28 | Resale cap includes the booking fee | Quiet Hours ticket (face €26): resell for €29 | Refused (max €26) | "Listed on Marquee Resale for €29.00" (cap €29.12) | Medium | Hard | `server.py` `Store.resell` |
| BUG-29 | Half refund 7 days before | My tickets: Refund Tidewater (7 days away) | No refund (7 days or fewer) | "You'll get €36.00 back" | Low | Expert | `server.py` `refund_share` |
| BUG-30 | Postponed event has no refund | My tickets: Refund Comet Club (postponed, 5 days away) | €74.18, fees included | "No refund is available. Refunds close 7 days before the event." | High | Hard | `server.py` `Store.quote` |
| BUG-31 | Refunds ignore the promo code | My tickets: Refund Kite Hill (MARQUEE10 saved €8.00) | €72.00 (what the tickets cost) | €80.00 | High | Expert | `server.py` `Store.quote` |

### Waitlist

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-32 | Released tickets skip the waitlist | As Max, release 10 Glasshouse Orchestra Standard tickets; as Zoe, check My tickets and the event | Offered to the 6 people waiting, in order | Zoe is still "number 4" with no offer; the event page sells them to anyone | Medium | Hard | `server.py` `Store.release` |

### Organiser (Max)

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-33 | Other organisers' events open by id | As Max, `/manage?id=5` (Laugh Track Live, Rhea's) | Refused / not found | Full control: attendees (Ana Rios), prices, cancel, check-in | Critical | Hard | `server.py` `Store.own_event` |
| BUG-34 | Releases past the venue's capacity | Static Bloom (venue 250, 250 released): release 50 | Refused | "300 released in total" | High | Medium | `server.py` `Store.release` |
| BUG-35 | Price changes rewrite tickets already sold | As Max, The Velvet Static Standard → €55; as Zoe, open ticket 103 and the refund | Face value €45 (the price paid); refund €45 | Face value €55.00, refund €55.00, resale cap €55 | High | Hard | `server.py` `Store.face` |
| BUG-36 | Cancelling keeps the fees | As Max, cancel Northern Lights Revue; as Zoe, My tickets | Refunded €110.02 (fees included) | "Paid €110.02 · refunded €96.00" | High | Hard | `server.py` `Store.cancel_event` |
| BUG-37 | Revenue ignores promo codes | Kite Hill: Ticket revenue | €248.00 (€72 + €40 + €136 after codes) | €280.00 | Medium | Expert | `server.py` `Store.revenue` |
| BUG-38 | Attendee CSV splits names with commas | Quiet Hours: Download CSV | "Lee, Jordan" in one quoted column | Unquoted: the row has 8 columns under 7 headings | Low | Hard | `server.py` `Store.attendees_csv` |
| BUG-39 | A ticket checks in twice | Check-in: Quiet Hours, Zoe's ticket reference twice | Second: "Already checked in" | "Checked in" both times | Critical | Medium | `server.py` `Store.check_in` |

### Errors

| ID | Bug | Steps to reproduce | Expected | Actual | Severity | Difficulty | Where |
|---|---|---|---|---|---|---|---|
| BUG-40 | An unknown event hangs on "Loading…" | Open `/event?id=99` | "We couldn't find that event" | "Loading…" forever and a JavaScript error | Low | Medium | `static/event.js` (no check on the response) |

## What is not a planted bug

- Console errors that come with a bug or a page: 401 when a visitor tries to buy (it sends them to log in), 400 when a
  rule refuses something (a seat gap, an expired card), 404 and the JavaScript error on an unknown event (BUG-40),
  403 on organiser pages as Zoe and on fan pages as Max, 404 on unknown pages.
- Bugs that combine: BUG-17 also inflates the basket total that BUG-19 compares with; BUG-35 also raises refunds and
  the resale cap; BUG-26 with BUG-27 leaves Zoe with an extra ticket; BUG-14 books the expired Comets tickets even when
  the event would be sold out.
- "Sold (all channels)" on the organiser pages includes box office and partner sales, so it is larger than the
  attendee list, which shows Marquee bookings only.
- Date pickers show dates in the browser's format. Event pages, listings, the basket and My tickets show venue times.
- Each visitor has a private world: changes in one browser session do not show in another.
- "Demo ticketing site for QA testing" in the footer, the test card note at checkout, and the demo accounts on the
  login page.

By area: events and search 5, event page and seats 6, ticket limits and holds 5, basket, fees and checkout 8, my
tickets 7, waitlist 1, organiser 7, errors 1.
By difficulty: Medium 15, Hard 20, Expert 5. By severity: Critical 4, High 13, Medium 13, Low 10.
