"""Marquee's demo world: venues, events, ticket types, orders, tickets, waitlists and promo codes, dated from today.

Every visitor gets a fresh copy (see server.Store), so scans never disturb each other.
"""

import datetime as dt
import hashlib

PASSWORD = "Marquee@2026"
SALT = b"marquee-demo-salt"

BOOKING_FEE_RATE = 0.12
ORDER_FEE = 2.50
HOLD_MINUTES = 10
MAX_PER_ORDER = 8
TRANSFER_DAYS = 2
FULL_REFUND_DAYS = 15
HALF_REFUND_DAYS = 8
FEW_LEFT = 10
CONCESSION_UNDER, CONCESSION_FROM = 16, 65


def password_hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 20_000).hex()


DEMO_HASH = password_hash(PASSWORD, SALT)


def fee(price: float) -> float:
    """The booking fee on one ticket: 12% of its price, to the nearest cent."""
    return round(price * BOOKING_FEE_RATE + 1e-9, 2)


def code(kind: str, n: int) -> str:
    return "MQ-" + hashlib.sha1(f"marquee-{kind}-{n}".encode()).hexdigest()[:6].upper()


VENUES = [
    {"id": 1, "name": "The Corn Exchange", "city": "Northport", "offset": 0, "capacity": 96, "rows": "ABCDEFGH",
     "per_row": 12, "wheelchair": ["H1", "H2"]},
    {"id": 2, "name": "Harbour Arena", "city": "Calder Bay", "offset": -5, "capacity": 1200},
    {"id": 3, "name": "The Lantern Rooms", "city": "Veloria", "offset": 2, "capacity": 250},
    {"id": 4, "name": "Riverside Playhouse", "city": "Ashby Fields", "offset": 1, "capacity": 60, "rows": "ABCDEF",
     "per_row": 10, "wheelchair": ["F1", "F2"]},
    {"id": 5, "name": "Fairgrounds Stadium", "city": "Northport", "offset": 0, "capacity": 5000},
]  # fmt: skip


def seats(rows: str, numbers: str) -> list[str]:
    """seats("AB", "1-3") -> A1 A2 A3 B1 B2 B3."""
    lo, _, hi = numbers.partition("-")
    return [f"{r}{n}" for r in rows for n in range(int(lo), int(hi or lo) + 1)]


def world(today: dt.date, now: dt.datetime | None = None) -> dict:
    """A fresh copy of everything one visitor can see and change."""
    now = now or dt.datetime.combine(today, dt.time(12, 0), dt.UTC)

    def day(n: int) -> str:
        return (today + dt.timedelta(days=n)).isoformat()

    def stamp(minutes: float) -> str:
        return (now + dt.timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def tier(tid, name, kind, price, qty=0, sold=0, ends=None, rows=""):
        return {"id": tid, "name": name, "kind": kind, "price": price, "qty": qty, "sold": sold, "ends": ends,
                "rows": rows}  # fmt: skip

    def event(eid, name, performer, category, venue, organiser, offset, doors, start, tiers, about, **extra):
        return {"id": eid, "name": name, "performer": performer, "category": category, "venue": venue,
                "organiser": organiser, "date": day(offset), "doors": doors, "start": start, "status": "on sale",
                "original_date": None, "limit": None, "presale_until": None, "presale_code": "", "about": about,
                "tiers": tiers, "taken": []} | extra  # fmt: skip

    events = [
        event(1, "Midnight Brass", "The Midnight Brass Collective", "Concerts", 3, 4, -1, "19:30", "20:30",
              [tier(11, "Standard", "standard", 28.0, 250, 238)],
              "A ten-piece brass band playing late-night jazz standards and their own tunes."),
        event(2, "The Velvet Static", "The Velvet Static", "Concerts", 2, 2, 12, "19:00", "20:00",
              [tier(21, "Standard", "standard", 45.0, 1000, 645), tier(22, "VIP", "vip", 95.0, 100, 80)],
              "Fuzz-pop four-piece on their first tour of the coast. VIP includes early entry and a signed poster.",
              limit=4),
        event(3, "Paper Moons", "Paper Moons", "Concerts", 3, 4, 20, "19:00", "20:00",
              [tier(31, "Standard", "standard", 22.0, 220, 220), tier(32, "VIP", "vip", 40.0, 30, 10)],
              "Dream-folk duo with a string quartet. VIP seats are on the balcony."),
        event(4, "Hamlet, Unplugged", "Ashby Fields Players", "Theatre", 4, 2, 9, "18:45", "19:30",
              [tier(41, "Premium", "premium", 58.0, rows="AB"), tier(42, "Standard", "standard", 36.0, rows="CDEF")],
              "Shakespeare's tragedy in ninety minutes, with live acoustic music.",
              taken=seats("A", "3-6") + seats("B", "1-2") + seats("C", "1-3") + seats("D", "8-10") + seats("F", "5-7")),
        event(5, "Laugh Track Live", "Dana Quill, Marcus Bell and guests", "Comedy", 1, 4, 16, "19:00", "19:45",
              [tier(51, "Premium", "premium", 32.45, rows="AB"),
               tier(52, "Standard", "standard", 24.95, rows="CDEFGH")],
              "Three comics, one host, no safety net. Contains strong language.",
              taken=seats("A", "1-8") + seats("C", "4-9") + seats("E", "1-12") + seats("G", "5-6")),
        event(6, "Northport Comets v Calder Bay Gulls", "Northport Comets, Calder Bay Gulls", "Sports", 5, 4, 6,
              "17:30", "19:00",
              [tier(61, "Standard", "standard", 24.0, 4000, 2210),
               tier(62, "Concession", "concession", 12.0, 800, 310)],
              "League basketball: the Comets host their rivals from across the bay."),
        event(7, "Static Bloom", "Static Bloom", "Concerts", 3, 2, 25, "20:00", "21:00",
              [tier(71, "Standard", "standard", 30.0, 250, 247)],
              "Shoegaze trio, loud and lovely. Earplugs at the bar."),
        event(8, "Glasshouse Orchestra", "Glasshouse Orchestra", "Concerts", 2, 2, 30, "18:30", "19:30",
              [tier(81, "Standard", "standard", 38.0, 1000, 1000), tier(82, "VIP", "vip", 85.0, 150, 150)],
              "Film scores and video-game suites played by a sixty-piece orchestra."),
        event(9, "Ferris & Wheel: Double Act", "Ferris & Wheel", "Comedy", 3, 4, 18, "19:30", "20:15",
              [tier(91, "Early bird", "early", 18.0, 60, 41, ends=day(0)),
               tier(92, "Standard", "standard", 25.0, 190, 40)],
              "The sketch duo's new hour: two chairs, one ladder, far too many hats."),
        event(10, "Comet Club", "Comet Club", "Concerts", 3, 4, 5, "19:00", "20:00",
              [tier(101, "Standard", "standard", 32.0, 250, 180)],
              "Synth-pop five-piece. Moved to a new date because the band's van broke down.",
              status="postponed", original_date=day(1)),
        event(11, "Tidewater", "Harbour Light Theatre Company", "Theatre", 4, 2, 7, "19:00", "19:30",
              [tier(111, "Premium", "premium", 48.0, rows="AB"), tier(112, "Standard", "standard", 36.0, rows="CDEF")],
              "A new play about three generations of a fishing family.",
              taken=seats("A", "1-10") + seats("B", "1-6") + seats("C", "1-4") + seats("C", "7-10")
              + seats("DE", "1-10")),
        event(12, "Northern Lights Revue", "The Aurora Company", "Theatre", 1, 2, 40, "19:00", "19:30",
              [tier(121, "Premium", "premium", 48.0, rows="AB"),
               tier(122, "Standard", "standard", 30.0, rows="CDEFGH")],
              "Song, dance and a great deal of glitter: the winter revue.",
              taken=seats("A", "1-4") + seats("D", "1-12") + seats("F", "3-8")),
        event(13, "Sunday Sessions: Kite Hill", "Kite Hill", "Concerts", 3, 2, 35, "15:00", "16:00",
              [tier(131, "Standard", "standard", 40.0, 250, 120)],
              "Afternoon set from the folk-rock band, with a long interval for cake."),
        event(14, "Rivals Cup Final", "Northport Comets v Ashby Fields Rovers", "Sports", 5, 4, 50, "13:00", "15:00",
              [tier(141, "Standard", "standard", 35.0, 4500, 900), tier(142, "VIP", "vip", 80.0, 500, 60)],
              "The cup final. VIP includes lounge access and a three-course lunch.",
              presale_until=day(3), presale_code="RIVALS26"),
        event(15, "Quiet Hours", "Mira Lane", "Theatre", 3, 2, 3, "19:00", "19:30",
              [tier(151, "Standard", "standard", 26.0, 250, 96)],
              "A one-woman show about night shifts, insomnia and the people who keep a city running."),
    ]  # fmt: skip
    by_id = {e["id"]: e for e in events}
    venues = {v["id"]: v for v in VENUES}
    for e in events:
        v = venues[e["venue"]]
        for t in e["tiers"]:
            if t["rows"]:
                t["qty"] = len(t["rows"]) * v["per_row"]

    users = [
        {"id": 1, "name": "Zoe Park", "email": "zoe@marquee.test", "role": "fan"},
        {"id": 2, "name": "Max Okafor", "email": "max@marquee.test", "role": "organiser"},
        {"id": 3, "name": "Ivy Chen", "email": "ivy.chen@example.com", "role": "fan"},
        {"id": 4, "name": "Rhea Banks", "email": "rhea@brighttent.example", "role": "organiser"},
    ]
    for u in users:
        demo = u["id"] in (1, 2)
        u |= {"salt": SALT.hex(), "hash": DEMO_HASH if demo else password_hash(u["email"], SALT)}

    codes = [
        {"code": "MARQUEE10", "percent": 10, "starts": day(-60), "ends": day(60), "about": "10% off tickets"},
        {"code": "ENCORE5", "percent": 5, "starts": day(-10), "ends": day(30), "about": "5% off tickets"},
        {"code": "AUTUMN15", "percent": 15, "starts": day(-45), "ends": day(-1), "about": "15% off tickets"},
    ]
    percent = {c["code"]: c["percent"] for c in codes}

    orders: list[dict] = []
    tickets: list[dict] = []

    def order(event_id, user, name, email, lines, created, promo=""):
        """lines: (tier id, quantity or a list of seats)."""
        oid = 501 + len(orders)
        ev = by_id[event_id]
        rows = []
        for tid, what in lines:
            t = next(t for t in ev["tiers"] if t["id"] == tid)
            seat_list = what if isinstance(what, list) else []
            qty = len(seat_list) or what
            rows.append({"tier": tid, "qty": qty, "price": t["price"], "seats": seat_list})
            for i in range(qty):
                n = 101 + len(tickets)
                tickets.append({"id": n, "order": oid, "event": event_id, "tier": tid,
                                "seat": seat_list[i] if seat_list else "", "owner": user, "name": name,
                                "email": email, "code": code("ticket", n), "status": "valid", "checked_in": None,
                                "resale": None})  # fmt: skip
        subtotal = sum(r["price"] * r["qty"] for r in rows)
        booking = sum(fee(r["price"]) * r["qty"] for r in rows)
        discount = round(subtotal * percent.get(promo, 0) / 100 + 1e-9, 2)
        total = round(subtotal + booking + ORDER_FEE - discount, 2)
        orders.append({"id": oid, "ref": code("order", oid), "user": user, "name": name, "email": email,
                       "event": event_id, "created": day(created), "lines": rows, "code": promo,
                       "subtotal": round(subtotal, 2), "discount": discount, "booking_fees": round(booking, 2),
                       "order_fee": ORDER_FEE, "total": total, "status": "paid", "refunded": 0.0})  # fmt: skip

    zoe = ("Zoe Park", "zoe@marquee.test")
    order(1, 1, *zoe, [(11, 2)], -30)
    order(2, 1, *zoe, [(21, 2)], -21)
    order(10, 1, *zoe, [(101, 2)], -40)
    order(11, 1, *zoe, [(112, ["C5", "C6"])], -12)
    order(13, 1, *zoe, [(131, 2)], -9, "MARQUEE10")
    order(15, 1, *zoe, [(151, 2)], -6)
    order(15, 3, "Ivy Chen", "ivy.chen@example.com", [(151, 1)], -5)
    order(12, 1, *zoe, [(121, ["A7", "A8"])], -3)
    order(15, None, "Lee, Jordan", "jordan.lee@example.com", [(151, 2)], -4)
    order(13, None, "Priya Nair", "priya.nair@example.com", [(131, 1)], -8)
    order(13, None, "Tom Okoro", "tom.okoro@example.com", [(131, 4)], -20, "AUTUMN15")
    order(12, None, "Sofia Marin", "sofia.marin@example.com", [(122, ["C4", "C5"])], -14)
    order(2, None, "Ben Hale", "ben.hale@example.com", [(21, 3)], -16)
    order(12, 3, "Ivy Chen", "ivy.chen@example.com", [(121, ["B3"])], -2)
    order(5, None, "Ana Rios", "ana.rios@example.com", [(52, ["D4", "D5"])], -7)
    order(7, None, "Lee, Jordan", "jordan.lee@example.com", [(71, 2)], -11)

    waitlist = [
        {"event": 8, "user": None, "name": "Priya Nair", "joined": day(-9)},
        {"event": 8, "user": None, "name": "Tom Okoro", "joined": day(-8)},
        {"event": 8, "user": None, "name": "Sofia Marin", "joined": day(-6)},
        {"event": 8, "user": 1, "name": "Zoe Park", "joined": day(-5)},
        {"event": 8, "user": 3, "name": "Ivy Chen", "joined": day(-2)},
        {"event": 8, "user": None, "name": "Ben Hale", "joined": day(-1)},
    ]

    return {
        "today": today.isoformat(),
        "users": users,
        "venues": [dict(v) for v in VENUES],
        "events": events,
        "codes": codes,
        "orders": orders,
        "tickets": tickets,
        "waitlist": waitlist,
        "baskets": {
            "1": {"event": 6, "codes": [], "lines": [
                {"id": 1, "tier": 61, "qty": 2, "seats": [], "dob": "", "added": stamp(-15), "expires": stamp(-5)},
            ]},
        },
        "next_id": 2000,
    }  # fmt: skip
