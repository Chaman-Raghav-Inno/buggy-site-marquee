"""Marquee: a demo event ticketing site with planted functional bugs, for checking what the AI QA Scanner finds.

The bugs are listed in BUGS.md (the answer key), which is never served. Comments marking a planted bug (BUG-nn)
only appear in server-side code; the pages and scripts the scanner reads carry none.

Each visitor (cookie) gets a private copy of the demo world, kept in memory, so parallel scans never see each
other's changes. Logging in as the fan or the organiser in the same browser shares that world.
"""

import datetime as dt
import hmac
import html
import json
import math
import os
import re
import secrets
import threading
from collections import OrderedDict
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

from . import data

HERE = Path(__file__).resolve().parent
PAGES_DIR = HERE / "pages"
STATIC_DIR = HERE / "static"
STATIC_TYPES = {".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml"}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'"
    ),
}
MAX_BODY = 1024 * 1024
MAX_SESSIONS = 1500
PAGE_SIZE = 6
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
PRICE = re.compile(r"\d{1,5}(\.\d{1,2})?")
CATEGORIES = ("Concerts", "Theatre", "Comedy", "Sports")

# path -> (page, title, who may open it)
PAGES = {
    "/": ("landing", "Welcome", None),
    "/login": ("login", "Log in", None),
    "/help": ("help", "Ticket rules", None),
    "/events": ("events", "Events", None),
    "/event": ("event", "Event", None),
    "/basket": ("basket", "Basket", "fan"),
    "/checkout": ("checkout", "Checkout", "fan"),
    "/tickets": ("tickets", "My tickets", "fan"),
    "/ticket": ("ticket", "Ticket", "fan"),
    "/dashboard": ("dashboard", "Organiser dashboard", "organiser"),
    "/manage": ("manage", "Manage event", "organiser"),
    "/checkin": ("checkin", "Check-in", "organiser"),
}


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def today() -> dt.date:
    return dt.datetime.now(dt.UTC).date()


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def stamp(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_stamp(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.UTC)


def _text(body: dict, key: str, limit: int = 200) -> str:
    value = body.get(key, "")
    return value.strip()[:limit] if isinstance(value, str) else ""


def _int(value, message: str) -> int:
    if isinstance(value, bool):
        raise ApiError(400, message)
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ApiError(400, message) from None


def _price(value, message: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not 0 < value <= 2000:
        raise ApiError(400, message)
    if not PRICE.fullmatch(f"{value}".removesuffix(".0")):
        raise ApiError(400, message)
    return float(value)


def money(x: float) -> float:
    return round(x + 1e-9, 2)


def booking_fee(price: float) -> float:
    return math.ceil(round(price * data.BOOKING_FEE_RATE * 100, 6)) / 100  # BUG-18: rounds up, not to the nearest


def concession_ok(dob: dt.date, on: dt.date) -> bool:
    age = on.year - dob.year  # BUG-08: a birthday later in the year isn't allowed for
    return age < data.CONCESSION_UNDER or age >= data.CONCESSION_FROM


def single_gap(picked: set[int], filled: set[int], per_row: int) -> int | None:
    """The seat number of a single empty seat the picked seats would leave, if any."""
    taken = filled | picked
    for s in sorted(picked):
        left = s - 1
        if left >= 1 and left not in taken and (left - 1 < 1 or left - 1 in taken):
            return left
        # BUG-11: the seat to the right of each pick is never checked
    return None


def refund_share(days: int) -> float:
    if days >= data.FULL_REFUND_DAYS:
        return 1.0
    if days >= data.HALF_REFUND_DAYS - 1:  # BUG-29: 7 days before still gets half
        return 0.5
    return 0.0


def card_expired(expiry: str, on: dt.date) -> bool:
    month, year = int(expiry[:2]), 2000 + int(expiry[3:])
    return (year, month) <= (on.year, on.month)  # BUG-24: cards expiring this month are refused


def luhn(number: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(number)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


class Store:
    def __init__(self):
        self.lock = threading.Lock()
        self.sessions: OrderedDict[str, dict] = OrderedDict()

    def session(self, sid: str | None) -> tuple[str, dict]:
        if sid and sid in self.sessions:
            self.sessions.move_to_end(sid)
            return sid, self.sessions[sid]
        sid = secrets.token_urlsafe(24)
        self.sessions[sid] = {"world": None, "user": None}
        while len(self.sessions) > MAX_SESSIONS:
            self.sessions.popitem(last=False)
        return sid, self.sessions[sid]

    @staticmethod
    def world(sess: dict) -> dict:
        if sess["world"] is None:
            sess["world"] = data.world(today(), now_utc())
        return sess["world"]

    def user(self, sess: dict) -> dict | None:
        if sess["user"] is None:
            return None
        return next((u for u in self.world(sess)["users"] if u["id"] == sess["user"]), None)

    def signed_in(self, sess: dict, role: str = "fan") -> tuple[dict, dict]:
        user = self.user(sess)
        if not user:
            raise ApiError(401, "Please log in.")
        if user["role"] != role:
            raise ApiError(403, "Log in as a fan to buy tickets." if role == "fan" else "That is for organisers.")
        return self.world(sess), user

    def me(self, sess: dict) -> dict:
        user = self.user(sess)
        out = {"today": self.world(sess)["today"]}
        return out | {"user": {k: user[k] for k in ("id", "name", "email", "role")} if user else None}

    def login(self, sess: dict, body: dict) -> dict:
        w = self.world(sess)
        email = _text(body, "email").lower()
        u = next((u for u in w["users"] if u["email"] == email), None)
        password = body.get("password")
        if not (u and isinstance(password, str)) or not hmac.compare_digest(
            u["hash"], data.password_hash(password, bytes.fromhex(u["salt"]))
        ):
            raise ApiError(401, "Incorrect email or password.")
        sess["user"] = u["id"]
        return self.me(sess)

    # events

    @staticmethod
    def today(w: dict) -> dt.date:
        return dt.date.fromisoformat(w["today"])

    @staticmethod
    def venue(w: dict, vid: int) -> dict:
        return next(v for v in w["venues"] if v["id"] == vid)

    @staticmethod
    def event(w: dict, eid: int) -> dict:
        found = next((e for e in w["events"] if e["id"] == eid), None)
        if not found:
            raise ApiError(404, "We couldn't find that event.")
        return found

    @staticmethod
    def tier(ev: dict, tid) -> dict:
        found = next((t for t in ev["tiers"] if t["id"] == tid), None)
        if not found:
            raise ApiError(400, "Choose a ticket type.")
        return found

    def days(self, w: dict, ev: dict) -> int:
        return (dt.date.fromisoformat(ev["date"]) - self.today(w)).days

    def times(self, w: dict, ev: dict) -> dict:
        v = self.venue(w, ev["venue"])
        out = {}
        for key, name in (("doors", "doors_at"), ("start", "starts_at")):
            local = dt.datetime.fromisoformat(f"{ev['date']}T{ev[key]}:00")
            out[name] = stamp((local - dt.timedelta(hours=v["offset"])).replace(tzinfo=dt.UTC))
        return out

    @staticmethod
    def live_lines(w: dict, ev_id: int, now: dt.datetime):
        for uid, b in w["baskets"].items():
            if b["event"] != ev_id:
                continue
            for line in b["lines"]:
                if parse_stamp(line["expires"]) > now:
                    yield uid, line

    def seat_states(self, w: dict, ev: dict, uid: int | None = None) -> dict[str, str]:
        v = self.venue(w, ev["venue"])
        states = {s: "free" for s in data.seats(v["rows"], f"1-{v['per_row']}")}
        for s in v["wheelchair"]:
            states[s] = "wheelchair"
        for s in ev["taken"]:
            states[s] = "taken"
        for t in w["tickets"]:
            if t["event"] == ev["id"] and t["seat"] and t["status"] not in ("refunded", "cancelled"):
                states[t["seat"]] = "taken"
        for owner, line in self.live_lines(w, ev["id"], now_utc()):
            for s in line["seats"]:
                states[s] = "mine" if owner == str(uid) else "taken"
        return states

    def tier_info(self, w: dict, ev: dict, t: dict, states: dict | None = None) -> dict:
        if t["rows"]:
            states = states or self.seat_states(w, ev)
            free = sum(1 for s, st in states.items() if s[0] in t["rows"] and st in ("free", "wheelchair"))
            sold = t["qty"] - free
            remaining = free
        else:
            sold = t["sold"]
            held = sum(line["qty"] for _, line in self.live_lines(w, ev["id"], now_utc()) if line["tier"] == t["id"])
            remaining = t["qty"] - sold - held
        on_sale = ev["status"] != "cancelled"  # BUG-04: events that have already taken place stay on sale
        if t["ends"]:
            on_sale = on_sale and self.today(w).isoformat() < t["ends"]  # BUG-06: ends a day early
        return {k: t[k] for k in ("id", "name", "kind", "price", "ends", "rows")} | {
            "qty": t["qty"],
            "sold": sold,
            "remaining": max(remaining, 0),
            "on_sale": on_sale,
        }

    def summary(self, w: dict, ev: dict) -> dict:
        v = self.venue(w, ev["venue"])
        states = self.seat_states(w, ev) if v.get("rows") else None
        tiers = [self.tier_info(w, ev, t, states) for t in ev["tiers"]]
        live = [t for t in tiers if t["on_sale"] and t["remaining"] > 0]
        left = sum(t["remaining"] for t in live)
        return {
            "id": ev["id"],
            "name": ev["name"],
            "performer": ev["performer"],
            "category": ev["category"],
            "date": ev["date"],
            "status": ev["status"],
            "original_date": ev["original_date"],
            "venue": v["name"],
            "city": v["city"],
            "offset": v["offset"],
            "from": min(t["price"] for t in (live or tiers)),
            "sold_out": tiers[0]["remaining"] <= 0,  # BUG-01: only the first ticket type is looked at
            "few_left": 0 < left <= data.FEW_LEFT,
        } | self.times(w, ev)

    def events(self, sess: dict, query: dict) -> dict:
        w = self.world(sess)
        arg = {k: (query.get(k) or [""])[0].strip() for k in query}
        rows = [e for e in w["events"] if e["status"] != "cancelled"]  # BUG-04: past events are listed
        q = arg.get("q", "").lower()
        if q:
            # BUG-05: venues aren't searched
            rows = [e for e in rows if q in e["name"].lower() or q in e["performer"].lower()]
        if arg.get("category"):
            rows = [e for e in rows if e["category"] == arg["category"]]
        if arg.get("city"):
            rows = [e for e in rows if self.venue(w, e["venue"])["city"] == arg["city"]]
        if arg.get("from"):
            rows = [e for e in rows if e["date"] >= arg["from"]]
        if arg.get("to"):
            rows = [e for e in rows if e["date"] <= arg["to"]]
        cards = [self.summary(w, e) for e in rows]
        if arg.get("sort") == "price":
            standard = {e["id"]: next(t["price"] for t in e["tiers"] if t["kind"] == "standard") for e in rows}
            cards.sort(key=lambda c: (standard[c["id"]], c["date"]))  # BUG-02: sorts by Standard, not "from"
        else:
            cards.sort(key=lambda c: (c["date"], c["doors_at"], c["id"]))
        try:
            page = max(1, int(arg.get("page") or 1))
        except ValueError:
            raise ApiError(400, "Bad page.") from None
        pages = max(1, -(-len(cards) // PAGE_SIZE))
        start = (page - 1) * PAGE_SIZE + (1 if page > 1 else 0)  # BUG-03: page 2 onwards starts one too late
        cities = sorted({v["city"] for v in w["venues"]})
        return {
            "events": cards[start : start + PAGE_SIZE],
            "count": len(cards),
            "page": page,
            "pages": pages,
            "categories": list(CATEGORIES),
            "cities": cities,
        }

    def event_page(self, sess: dict, eid: int) -> dict:
        w = self.world(sess)
        ev = self.event(w, eid)
        user = self.user(sess)
        uid = user["id"] if user else None
        v = self.venue(w, ev["venue"])
        states = self.seat_states(w, ev, uid) if v.get("rows") else None
        tiers = [self.tier_info(w, ev, t, states) for t in ev["tiers"]]
        seat_map = None
        if states:
            zone = {r: t["id"] for t in ev["tiers"] for r in t["rows"]}
            seat_map = [
                {"row": r, "seats": [{"id": f"{r}{n}", "n": n, "state": states[f"{r}{n}"], "tier": zone[r]}
                                     for n in range(1, v["per_row"] + 1)]}
                for r in v["rows"]
            ]  # fmt: skip
        queue = [x for x in w["waitlist"] if x["event"] == eid]
        mine = next((i + 1 for i, x in enumerate(queue) if uid and x["user"] == uid), None)
        presale = ev["presale_until"] and self.today(w).isoformat() < ev["presale_until"]
        return {
            "event": self.summary(w, ev)
            | {"about": ev["about"], "limit": ev["limit"], "presale_until": ev["presale_until"] if presale else None},
            "venue": {k: v[k] for k in ("name", "city", "offset", "capacity")} | {"seated": bool(v.get("rows"))},
            "tiers": tiers,
            "seats": seat_map,
            "all_sold_out": all(t["remaining"] <= 0 for t in tiers),
            "waitlist": {"count": len(queue), "position": mine},
        }

    def offers(self, sess: dict) -> dict:
        w = self.world(sess)
        return {"codes": [{k: c[k] for k in ("code", "percent", "ends", "about")} for c in w["codes"]]}

    # basket

    def basket_of(self, w: dict, uid: int) -> dict:
        return w["baskets"].setdefault(str(uid), {"event": None, "codes": [], "lines": []})

    def add_to_basket(self, sess: dict, body: dict) -> dict:
        w, user = self.signed_in(sess)
        ev = self.event(w, _int(body.get("event"), "Choose an event."))
        if ev["status"] == "cancelled":
            raise ApiError(400, "This event has been cancelled.")
        # BUG-04: there is no check that the event is still to come
        if ev["presale_until"] and self.today(w).isoformat() < ev["presale_until"]:
            given = _text(body, "presale", 40).upper()
            if given and given != ev["presale_code"]:  # BUG-23: a blank presale code is let through
                raise ApiError(400, "That presale code isn't right.")
        v = self.venue(w, ev["venue"])
        basket = self.basket_of(w, user["id"])
        replaced = basket["event"] not in (None, ev["id"]) and bool(basket["lines"])
        dob = ""
        if v.get("rows"):
            picked = body.get("seats")
            if not isinstance(picked, list) or not picked or not all(isinstance(s, str) for s in picked):
                raise ApiError(400, "Choose your seats on the seat map.")
            picked = list(dict.fromkeys(s.strip().upper() for s in picked))
            states = self.seat_states(w, ev, user["id"])
            for s in picked:
                if s not in states:
                    raise ApiError(400, f"There's no seat {s}.")
                if states[s] in ("taken", "mine"):
                    raise ApiError(409, f"Seat {s} has just been taken. Choose another.")
                # BUG-10: wheelchair spaces aren't kept for people who ticked that they need one
            for r in {s[0] for s in picked}:
                nums = {int(s[1:]) for s in picked if s[0] == r}
                filled = {int(s[1:]) for s, st in states.items() if s[0] == r and st in ("taken", "mine")}
                gap = single_gap(nums, filled, v["per_row"])
                if gap:
                    raise ApiError(400, f"That would leave a single empty seat ({r}{gap}). Choose seats next to it.")
            standard = next(t for t in ev["tiers"] if t["kind"] == "standard")
            tier = standard  # BUG-09: every seat is priced as Standard, even in the Premium rows
            qty = len(picked)
        else:
            tier = self.tier(ev, body.get("tier"))
            info = self.tier_info(w, ev, tier)
            if not info["on_sale"]:
                raise ApiError(400, f"{tier['name']} tickets are no longer on sale.")
            qty = _int(body.get("qty"), "Choose how many tickets.")
            if qty < 1:
                raise ApiError(400, "Choose how many tickets.")
            if qty > tier["qty"]:  # BUG-16: compared with all tickets released, not the ones left
                raise ApiError(409, f"Only {info['remaining']} {tier['name']} tickets left.")
            if tier["kind"] == "concession":
                if qty != 1:
                    raise ApiError(400, "Add concession tickets one at a time, with the holder's date of birth.")
                try:
                    born = dt.date.fromisoformat(_text(body, "dob", 10))
                except ValueError:
                    raise ApiError(400, "Enter the ticket holder's date of birth.") from None
                if not concession_ok(born, dt.date.fromisoformat(ev["date"])):
                    raise ApiError(400, "Concessions are for under-16s and over-65s on the day of the event.")
                dob = born.isoformat()
            picked = []
        if qty > data.MAX_PER_ORDER:  # BUG-13: tickets already in the basket aren't counted
            raise ApiError(400, f"You can buy up to {data.MAX_PER_ORDER} tickets per order.")
        in_basket = 0 if replaced else sum(line["qty"] for line in basket["lines"])
        # BUG-12: tickets from earlier orders don't count towards the per-account limit
        if ev["limit"] and in_basket + qty > ev["limit"]:
            raise ApiError(400, f"This event has a limit of {ev['limit']} tickets per account.")
        if replaced:
            basket.update(codes=[], lines=[])
        basket["event"] = ev["id"]
        now = now_utc()
        basket["lines"].append(
            {
                "id": w["next_id"],
                "tier": tier["id"],
                "qty": qty,
                "seats": picked,
                "dob": dob,
                "added": stamp(now),
                "expires": stamp(now + dt.timedelta(minutes=data.HOLD_MINUTES)),
            }
        )
        w["next_id"] += 1
        return self.basket(sess) | {"replaced": replaced}

    def priced(self, w: dict, basket: dict) -> dict:
        now = now_utc()
        ev = self.event(w, basket["event"]) if basket["event"] else None
        lines = []
        for line in basket["lines"]:
            t = self.tier(ev, line["tier"])
            lines.append(
                line
                | {
                    "name": t["name"],
                    "price": t["price"],
                    "fee": booking_fee(t["price"]),
                    "amount": money(t["price"] * line["qty"]),
                    "expired": parse_stamp(line["expires"]) <= now,
                }
            )
        subtotal = money(sum(x["amount"] for x in lines))
        booking = money(sum(x["fee"] * x["qty"] for x in lines))
        count = sum(x["qty"] for x in lines)
        order_fee = data.ORDER_FEE * count  # BUG-17: charged per ticket, not once per order
        percent = {c["code"]: c["percent"] for c in w["codes"]}
        discounts = [
            {"code": c, "percent": percent[c], "amount": money((subtotal + booking) * percent[c] / 100)}  # BUG-21
            for c in basket["codes"]
        ]
        discount = money(sum(d["amount"] for d in discounts))
        return {
            "event": self.summary(w, ev) if ev else None,
            "lines": lines,
            "count": count,
            "subtotal": subtotal,
            "booking_fees": booking,
            "order_fee": money(order_fee),
            "discounts": discounts,
            "discount": discount,
            "total": money(subtotal + booking + order_fee - discount),
            "hold_minutes": data.HOLD_MINUTES,
        }

    def basket(self, sess: dict) -> dict:
        w, user = self.signed_in(sess)
        # BUG-14: lines whose hold has run out are never taken out of the basket
        return self.priced(w, self.basket_of(w, user["id"]))

    def remove_line(self, sess: dict, lid: int) -> dict:
        w, user = self.signed_in(sess)
        basket = self.basket_of(w, user["id"])
        line = next((x for x in basket["lines"] if x["id"] == lid), None)
        if not line:
            raise ApiError(404, "That's no longer in your basket.")
        basket["lines"].remove(line)
        if not basket["lines"]:
            basket.update(event=None, codes=[])
        return self.basket(sess)

    def apply_code(self, sess: dict, body: dict) -> dict:
        w, user = self.signed_in(sess)
        basket = self.basket_of(w, user["id"])
        if not basket["lines"]:
            raise ApiError(400, "Add some tickets first.")
        given = _text(body, "code", 40).upper()
        promo = next((c for c in w["codes"] if c["code"] == given), None)
        if not promo:
            raise ApiError(400, "That code isn't valid.")
        if self.today(w).isoformat() < promo["starts"]:
            raise ApiError(400, "That code isn't valid yet.")
        # BUG-20: codes past their end date are still accepted
        if given in basket["codes"]:
            raise ApiError(400, "That code is already applied.")
        basket["codes"].append(given)  # BUG-22: a second code is added to the first instead of replacing it
        return self.basket(sess)

    def remove_codes(self, sess: dict) -> dict:
        w, user = self.signed_in(sess)
        self.basket_of(w, user["id"])["codes"] = []
        return self.basket(sess)

    def checkout(self, sess: dict, body: dict) -> dict:
        w, user = self.signed_in(sess)
        basket = self.basket_of(w, user["id"])
        if not basket["lines"]:
            raise ApiError(400, "Your basket is empty.")
        name = _text(body, "name", 80)
        if not name:
            raise ApiError(400, "Enter the name on the card.")
        number = re.sub(r"[\s-]", "", _text(body, "card", 40))
        if not number.isdigit() or not 13 <= len(number) <= 19 or not luhn(number):
            raise ApiError(400, "Check the card number.")
        expiry = _text(body, "expiry", 5)
        if not re.fullmatch(r"(0[1-9]|1[0-2])/\d\d", expiry):
            raise ApiError(400, "Enter the expiry date as MM/YY.")
        if card_expired(expiry, self.today(w)):
            raise ApiError(400, "That card has expired.")
        if not re.fullmatch(r"\d{3,4}", _text(body, "cvc", 4)):
            raise ApiError(400, "Enter the 3-digit security code.")
        # BUG-14: lines whose hold has expired are charged and booked too
        p = self.priced(w, basket)
        ev = self.event(w, basket["event"])
        oid = w["next_id"]
        w["next_id"] += 1
        order = {
            "id": oid,
            "ref": data.code("order", oid),
            "user": user["id"],
            "name": user["name"],
            "email": user["email"],
            "event": ev["id"],
            "created": w["today"],
            "lines": [{k: x[k] for k in ("tier", "qty", "price", "seats")} for x in p["lines"]],
            "code": ",".join(basket["codes"]),
            "subtotal": p["subtotal"],
            "discount": p["discount"],
            "booking_fees": p["booking_fees"],
            "order_fee": p["order_fee"],
            "total": p["total"],
            "status": "paid",
            "refunded": 0.0,
        }
        w["orders"].append(order)
        for x in p["lines"]:
            t = self.tier(ev, x["tier"])
            if not t["rows"]:
                t["sold"] += x["qty"]
            for i in range(x["qty"]):
                tid = w["next_id"]
                w["next_id"] += 1
                w["tickets"].append(
                    {
                        "id": tid,
                        "order": oid,
                        "event": ev["id"],
                        "tier": t["id"],
                        "seat": x["seats"][i] if x["seats"] else "",
                        "owner": user["id"],
                        "name": user["name"],
                        "email": user["email"],
                        "code": data.code("ticket", tid),
                        "status": "valid",
                        "checked_in": None,
                        "resale": None,
                    }
                )
        basket.update(event=None, codes=[], lines=[])
        return {"order": self.order_view(w, order)}

    # my tickets

    def face(self, w: dict, t: dict) -> float:
        ev = self.event(w, t["event"])
        return self.tier(ev, t["tier"])["price"]  # BUG-35: the current price, not the price paid

    def ticket_view(self, w: dict, t: dict) -> dict:
        ev = self.event(w, t["event"])
        v = self.venue(w, ev["venue"])
        days = self.days(w, ev)
        valid = t["status"] == "valid" and ev["status"] != "cancelled" and days >= 0
        open_ = valid and not t["checked_in"] and days >= data.TRANSFER_DAYS
        return {k: t[k] for k in ("id", "order", "seat", "name", "email", "code", "status", "checked_in", "resale")} | {
            "tier": self.tier(ev, t["tier"])["name"],
            "face": self.face(w, t),
            "event": {"id": ev["id"], "name": ev["name"], "date": ev["date"], "status": ev["status"],
                      "venue": v["name"], "city": v["city"], "offset": v["offset"]} | self.times(w, ev),
            "can_transfer": open_ and t["resale"] is None,
            "can_resell": open_,
        }  # fmt: skip

    def order_view(self, w: dict, o: dict, owner: int | None = None) -> dict:
        ev = self.event(w, o["event"])
        mine = [t for t in w["tickets"] if t["order"] == o["id"] and (owner is None or t["owner"] == owner)]
        return {k: o[k] for k in o if k != "user"} | {
            "event": self.summary(w, ev),
            "days": self.days(w, ev),
            "tickets": [self.ticket_view(w, t) for t in mine],
        }

    def my_tickets(self, sess: dict) -> dict:
        w, user = self.signed_in(sess)
        ids = {o["id"] for o in w["orders"] if o["user"] == user["id"]}
        ids |= {t["order"] for t in w["tickets"] if t["owner"] == user["id"]}
        orders = [self.order_view(w, o, user["id"]) for o in w["orders"] if o["id"] in ids]
        orders.sort(key=lambda o: (o["event"]["date"], o["id"]))
        waits = []
        for x in w["waitlist"]:
            if x["user"] == user["id"]:
                queue = [y for y in w["waitlist"] if y["event"] == x["event"]]
                ev = self.event(w, x["event"])
                waits.append({"event": self.summary(w, ev), "position": queue.index(x) + 1, "joined": x["joined"]})
        return {"orders": orders, "waitlist": waits}

    def ticket(self, sess: dict, tid: int) -> dict:
        w, user = self.signed_in(sess)
        t = next((t for t in w["tickets"] if t["id"] == tid), None)
        if not t:  # BUG-25: anyone's ticket opens, not just your own
            raise ApiError(404, "We couldn't find that ticket.")
        return {"ticket": self.ticket_view(w, t)}

    def own_ticket(self, w: dict, user: dict, tid: int) -> dict:
        t = next((t for t in w["tickets"] if t["id"] == tid and t["owner"] == user["id"]), None)
        if not t:
            raise ApiError(404, "We couldn't find that ticket.")
        return t

    def transfer(self, sess: dict, tid: int, body: dict) -> dict:
        w, user = self.signed_in(sess)
        t = self.own_ticket(w, user, tid)
        if not self.ticket_view(w, t)["can_transfer"]:
            raise ApiError(400, "This ticket can't be transferred any more.")
        email = _text(body, "email", 120).lower()
        name = _text(body, "name", 80)
        if not name:
            raise ApiError(400, "Enter your friend's name.")
        if not EMAIL.fullmatch(email):
            raise ApiError(400, "Enter your friend's email address.")
        # BUG-26: your own email address isn't refused
        friend = next((u for u in w["users"] if u["email"] == email), None)
        nid = w["next_id"]
        w["next_id"] += 1
        w["tickets"].append(
            t
            | {
                "id": nid,
                "owner": friend["id"] if friend else None,
                "name": name,
                "email": email,
                "code": data.code("ticket", nid),
                "resale": None,
            }
        )
        # BUG-27: the original ticket isn't marked as transferred, so it stays valid
        return {"ticket": self.ticket_view(w, t), "sent_to": email}

    def resell(self, sess: dict, tid: int, body: dict) -> dict:
        w, user = self.signed_in(sess)
        t = self.own_ticket(w, user, tid)
        if not self.ticket_view(w, t)["can_resell"]:
            raise ApiError(400, "This ticket can't be resold any more.")
        price = _price(body.get("price"), "Enter a price in euros and cents.")
        face = self.face(w, t)
        if price > face + booking_fee(face):  # BUG-28: the cap includes the booking fee
            raise ApiError(400, f"Resale prices are capped at face value ({face:.2f}).")
        t["resale"] = price
        return {"ticket": self.ticket_view(w, t)}

    def unlist(self, sess: dict, tid: int) -> dict:
        w, user = self.signed_in(sess)
        t = self.own_ticket(w, user, tid)
        t["resale"] = None
        return {"ticket": self.ticket_view(w, t)}

    def own_order(self, w: dict, user: dict, oid: int) -> dict:
        o = next((o for o in w["orders"] if o["id"] == oid and o["user"] == user["id"]), None)
        if not o:
            raise ApiError(404, "We couldn't find that booking.")
        return o

    def quote(self, w: dict, o: dict) -> dict:
        ev = self.event(w, o["event"])
        days = self.days(w, ev)
        if o["status"] != "paid":
            return {"amount": 0.0, "reason": "This booking has already been refunded."}
        if days < 0:
            return {"amount": 0.0, "reason": "This event has taken place."}
        tickets = [t for t in w["tickets"] if t["order"] == o["id"] and t["owner"] == o["user"]]
        paid = sum(self.face(w, t) for t in tickets if t["status"] == "valid")  # BUG-31: promo discount ignored
        # BUG-30: postponed events follow the usual refund window instead of a full refund
        share = refund_share(days)
        amount = money(paid * share)
        if not amount:
            return {"amount": 0.0, "reason": "Refunds close 7 days before the event."}
        label = "Full refund of the ticket price" if share == 1 else "Half the ticket price"
        return {"amount": amount, "reason": f"{label}; booking fees aren't refunded."}

    def refund_quote(self, sess: dict, oid: int) -> dict:
        w, user = self.signed_in(sess)
        return self.quote(w, self.own_order(w, user, oid))

    def refund(self, sess: dict, oid: int) -> dict:
        w, user = self.signed_in(sess)
        o = self.own_order(w, user, oid)
        q = self.quote(w, o)
        if not q["amount"]:
            raise ApiError(400, q["reason"])
        self.settle(w, o, q["amount"], "refunded")
        return self.my_tickets(sess)

    def settle(self, w: dict, o: dict, amount: float, status: str) -> None:
        ev = self.event(w, o["event"])
        o.update(status="refunded", refunded=amount)
        for t in w["tickets"]:
            if t["order"] == o["id"] and t["status"] == "valid":
                t["status"] = status
                t["resale"] = None
                tier = self.tier(ev, t["tier"])
                if not tier["rows"]:
                    tier["sold"] -= 1

    def join_waitlist(self, sess: dict, body: dict) -> dict:
        w, user = self.signed_in(sess)
        ev = self.event(w, _int(body.get("event"), "Choose an event."))
        page = self.event_page(sess, ev["id"])
        if not page["all_sold_out"] or ev["status"] == "cancelled":
            raise ApiError(400, "Tickets are still on sale for this event.")
        if page["waitlist"]["position"]:
            raise ApiError(409, "You're already on the waitlist.")
        w["waitlist"].append({"event": ev["id"], "user": user["id"], "name": user["name"], "joined": w["today"]})
        return self.event_page(sess, ev["id"])

    # organisers

    def own_event(self, w: dict, user: dict, eid: int) -> dict:
        ev = self.event(w, eid)
        # BUG-33: events run by other organisers aren't refused
        return ev

    def revenue(self, w: dict, ev: dict) -> float:
        paid = [o for o in w["orders"] if o["event"] == ev["id"] and o["status"] == "paid"]
        return money(sum(x["price"] * x["qty"] for o in paid for x in o["lines"]))  # BUG-37: discounts ignored

    def org_summary(self, w: dict, ev: dict) -> dict:
        s = self.summary(w, ev)
        v = self.venue(w, ev["venue"])
        tiers = [self.tier_info(w, ev, t) for t in ev["tiers"]]
        return s | {
            "sold": sum(t["sold"] for t in tiers),
            "released": sum(t["qty"] for t in tiers),
            "capacity": v["capacity"],
            "revenue": self.revenue(w, ev),
        }

    def dashboard(self, sess: dict) -> dict:
        w, user = self.signed_in(sess, "organiser")
        mine = [self.org_summary(w, e) for e in w["events"] if e["organiser"] == user["id"]]
        mine.sort(key=lambda e: e["date"])
        return {
            "events": mine,
            "sold": sum(e["sold"] for e in mine if e["status"] != "cancelled"),
            "revenue": money(sum(e["revenue"] for e in mine)),
            "name": user["name"].split()[0],
        }

    def manage(self, sess: dict, eid: int) -> dict:
        w, user = self.signed_in(sess, "organiser")
        ev = self.own_event(w, user, eid)
        v = self.venue(w, ev["venue"])
        attendees = []
        for t in w["tickets"]:
            if t["event"] == ev["id"]:
                o = next(o for o in w["orders"] if o["id"] == t["order"])
                attendees.append(
                    {
                        "code": t["code"],
                        "name": t["name"],
                        "email": t["email"],
                        "booking": o["ref"],
                        "tier": self.tier(ev, t["tier"])["name"],
                        "seat": t["seat"],
                        "status": t["status"],
                        "checked_in": t["checked_in"],
                    }  # fmt: skip
                )
        return {
            "event": self.org_summary(w, ev) | {"seated": bool(v.get("rows")), "days": self.days(w, ev)},
            "tiers": [self.tier_info(w, ev, t) for t in ev["tiers"]],
            "attendees": attendees,
            "waitlist": sum(1 for x in w["waitlist"] if x["event"] == ev["id"]),
        }

    def set_price(self, sess: dict, eid: int, body: dict) -> dict:
        w, user = self.signed_in(sess, "organiser")
        ev = self.own_event(w, user, eid)
        if ev["status"] == "cancelled":
            raise ApiError(400, "This event has been cancelled.")
        t = self.tier(ev, body.get("tier"))
        t["price"] = _price(body.get("price"), "Enter a price in euros and cents, up to 2,000.")
        return self.manage(sess, eid)

    def release(self, sess: dict, eid: int, body: dict) -> dict:
        w, user = self.signed_in(sess, "organiser")
        ev = self.own_event(w, user, eid)
        if ev["status"] == "cancelled":
            raise ApiError(400, "This event has been cancelled.")
        t = self.tier(ev, body.get("tier"))
        if t["rows"]:
            raise ApiError(400, "Seated tickets are sold by seat; you can't release more.")
        qty = _int(body.get("qty"), "Enter how many tickets to release.")
        if not 1 <= qty <= 10_000:
            raise ApiError(400, "Enter how many tickets to release.")
        # BUG-34: the venue's capacity isn't checked
        t["qty"] += qty
        # BUG-32: the new tickets go straight on general sale; nobody on the waitlist is offered them
        return self.manage(sess, eid)

    def cancel_event(self, sess: dict, eid: int) -> dict:
        w, user = self.signed_in(sess, "organiser")
        ev = self.own_event(w, user, eid)
        if ev["status"] == "cancelled":
            raise ApiError(409, "This event is already cancelled.")
        if self.days(w, ev) < 0:
            raise ApiError(400, "This event has already taken place.")
        ev["status"] = "cancelled"
        for o in w["orders"]:
            if o["event"] == ev["id"] and o["status"] == "paid":
                self.settle(w, o, money(o["total"] - o["booking_fees"] - o["order_fee"]), "cancelled")  # BUG-36
        w["waitlist"] = [x for x in w["waitlist"] if x["event"] != ev["id"]]
        for b in w["baskets"].values():
            if b["event"] == ev["id"]:
                b.update(event=None, codes=[], lines=[])
        return self.manage(sess, eid)

    def attendees_csv(self, sess: dict, eid: int) -> bytes:
        rows = self.manage(sess, eid)["attendees"]
        lines = ["Ticket reference,Name,Email,Ticket,Seat,Status,Checked in"]
        for a in rows:
            # BUG-38: values aren't quoted, so a comma in a name splits it across columns
            lines.append(
                f"{a['code']},{a['name']},{a['email']},{a['tier']},{a['seat']},{a['status']},{a['checked_in'] or ''}"
            )
        return ("\n".join(lines) + "\n").encode()

    def check_in(self, sess: dict, body: dict) -> dict:
        w, user = self.signed_in(sess, "organiser")
        ev = self.own_event(w, user, _int(body.get("event"), "Choose an event."))
        given = _text(body, "code", 20).upper()
        t = next((t for t in w["tickets"] if t["code"] == given and t["event"] == ev["id"]), None)
        if not t:
            raise ApiError(404, "No ticket with that reference for this event.")
        if t["status"] != "valid":
            raise ApiError(409, f"Not valid: this ticket was {t['status']}.")
        # BUG-39: a ticket that has already been checked in is let in again
        t["checked_in"] = stamp(now_utc())
        tier = self.tier(ev, t["tier"])["name"]
        return {"ticket": {"code": t["code"], "name": t["name"], "tier": tier, "seat": t["seat"]}} | self.manage(
            sess, ev["id"]
        )


def render(path: str, store: Store, sess: dict, status_page: str | None = None) -> bytes:
    name, title, _ = PAGES[path] if not status_page else (status_page, "Page not found", None)
    if status_page == "403":
        title = "Not for this account"
    user = store.user(sess)
    if not user:
        links = [("/events", "events", "Events"), ("/help", "help", "Ticket rules")]
        account = '<a href="/login" id="login-link">Log in</a>'
    else:
        if user["role"] == "fan":
            w = store.world(sess)
            count = sum(x["qty"] for x in store.basket_of(w, user["id"])["lines"])
            basket = f'Basket <span class="badge" id="basket-count">{count}</span>'
            links = [
                ("/events", "events", "Events"),
                ("/basket", "basket", basket),
                ("/tickets", "tickets", "My tickets"),
            ]
        else:
            links = [("/dashboard", "dashboard", "Dashboard"), ("/checkin", "checkin", "Check-in"),
                     ("/events", "events", "Events")]  # fmt: skip
        links.append(("/help", "help", "Ticket rules"))
        account = f'<span class="who">{html.escape(user["name"].split()[0])}</span>'
        account += '<button type="button" id="logout" class="link">Log out</button>'
    nav = "".join(f'<a href="{h}" data-nav="{k}">{t}</a>' for h, k, t in links)
    script = f'<script src="/static/{name}.js" defer></script>' if (STATIC_DIR / f"{name}.js").exists() else ""
    out = (PAGES_DIR / "_layout.html").read_text()
    values = {
        "title": html.escape(title),
        "page": name,
        "role": user["role"] if user else "",
        "nav": nav,
        "account": account,
        "content": (PAGES_DIR / f"{name}.html").read_text(),
        "scripts": script,
    }
    for k, v in values.items():
        out = out.replace("{{" + k + "}}", v)
    return out.encode()


def make_handler(store: Store | None = None):
    store = store or Store()
    static = {f.name: f for f in STATIC_DIR.iterdir() if f.is_file() and f.suffix in STATIC_TYPES}

    class Handler(BaseHTTPRequestHandler):
        server_version = "marquee"

        def log_message(self, fmt, *args):
            pass

        def _session(self) -> tuple[str, dict, bool]:
            sid = None
            try:
                cookie = SimpleCookie(self.headers.get("Cookie", ""))
                sid = cookie["mq_sid"].value if "mq_sid" in cookie else None
            except CookieError:
                pass
            new_sid, sess = store.session(sid)
            return new_sid, sess, new_sid != sid

        def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in {**SECURITY_HEADERS, **(extra or {})}.items():
                self.send_header(k, v)
            if self._new_sid:
                secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
                self.send_header("Set-Cookie", f"mq_sid={self._sid}; Path=/; HttpOnly; SameSite=Lax{secure}")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status: int, payload: dict):
            self._send(status, json.dumps(payload).encode(), "application/json")

        def _body(self) -> dict:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                raise ApiError(400, "Bad request.") from None
            if length > MAX_BODY:
                raise ApiError(413, "Request too large.")
            raw = self.rfile.read(length) if length > 0 else b""
            try:
                payload = json.loads(raw or b"{}")
            except ValueError:
                raise ApiError(400, "Send JSON.") from None
            if not isinstance(payload, dict):
                raise ApiError(400, "Send a JSON object.")
            return payload

        def do_HEAD(self):
            self._handle("GET")

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

        def _handle(self, method: str):
            self._sid, self._new_sid = None, False
            url = urlsplit(self.path)
            path = url.path.rstrip("/") or "/"
            query = parse_qs(url.query)
            try:
                if path == "/healthz":
                    return self._send(200, b"ok", "text/plain")
                if path == "/robots.txt":
                    return self._send(200, b"User-agent: *\nAllow: /\n", "text/plain")
                if path.startswith("/static/") and path[8:] in static:
                    f = static[path[8:]]
                    return self._send(200, f.read_bytes(), STATIC_TYPES[f.suffix])
                with store.lock:
                    self._sid, sess, self._new_sid = self._session()
                    if path.startswith("/api/"):
                        body = self._body() if method == "POST" else {}
                        result = self._api(sess, method, path, body, query)
                        if isinstance(result, bytes):
                            extra = {"Content-Disposition": 'attachment; filename="attendees.csv"'}
                            return self._send(200, result, "text/csv; charset=utf-8", extra)
                        return self._json(200, result)
                    if method != "GET":
                        return self._send(405, b"Method not allowed", "text/plain", {"Allow": "GET, HEAD"})
                    if path not in PAGES:
                        return self._send(404, render("/", store, sess, "404"), "text/html; charset=utf-8")
                    role = PAGES[path][2]
                    user = store.user(sess)
                    if role and not user:
                        location = "/login?next=" + quote(self.path, safe="")
                        return self._send(302, b"", "text/plain", {"Location": location})
                    if role and user["role"] != role:
                        return self._send(403, render("/", store, sess, "403"), "text/html; charset=utf-8")
                    return self._send(200, render(path, store, sess), "text/html; charset=utf-8")
            except ApiError as err:
                return self._json(err.status, {"ok": False, "error": str(err)})
            except Exception:
                return self._json(500, {"ok": False, "error": "Internal Server Error"})

        def _api(self, sess: dict, method: str, path: str, body: dict, query: dict):
            if method == "GET":
                gets = {
                    "/api/me": lambda: store.me(sess),
                    "/api/events": lambda: store.events(sess, query),
                    "/api/offers": lambda: store.offers(sess),
                    "/api/basket": lambda: store.basket(sess),
                    "/api/tickets": lambda: store.my_tickets(sess),
                    "/api/organiser": lambda: store.dashboard(sess),
                }
                if path in gets:
                    return gets[path]()
                routes = (
                    (r"/api/events/(\d+)", lambda i: store.event_page(sess, int(i))),
                    (r"/api/tickets/(\d+)", lambda i: store.ticket(sess, int(i))),
                    (r"/api/orders/(\d+)/refund", lambda i: store.refund_quote(sess, int(i))),
                    (r"/api/organiser/events/(\d+)", lambda i: store.manage(sess, int(i))),
                    (r"/api/organiser/events/(\d+)/attendees\.csv", lambda i: store.attendees_csv(sess, int(i))),
                )
            else:
                posts = {
                    "/api/login": lambda: store.login(sess, body),
                    "/api/logout": lambda: sess.update(user=None) or {"ok": True},
                    "/api/basket": lambda: store.add_to_basket(sess, body),
                    "/api/basket/code": lambda: store.apply_code(sess, body),
                    "/api/basket/code/remove": lambda: store.remove_codes(sess),
                    "/api/checkout": lambda: store.checkout(sess, body),
                    "/api/waitlist": lambda: store.join_waitlist(sess, body),
                    "/api/organiser/checkin": lambda: store.check_in(sess, body),
                }
                if path in posts:
                    return posts[path]()
                routes = (
                    (r"/api/basket/(\d+)/remove", lambda i: store.remove_line(sess, int(i))),
                    (r"/api/tickets/(\d+)/transfer", lambda i: store.transfer(sess, int(i), body)),
                    (r"/api/tickets/(\d+)/resell", lambda i: store.resell(sess, int(i), body)),
                    (r"/api/tickets/(\d+)/unlist", lambda i: store.unlist(sess, int(i))),
                    (r"/api/orders/(\d+)/refund", lambda i: store.refund(sess, int(i))),
                    (r"/api/organiser/events/(\d+)/price", lambda i: store.set_price(sess, int(i), body)),
                    (r"/api/organiser/events/(\d+)/release", lambda i: store.release(sess, int(i), body)),
                    (r"/api/organiser/events/(\d+)/cancel", lambda i: store.cancel_event(sess, int(i))),
                )
            for pattern, run in routes:
                m = re.fullmatch(pattern, path)
                if m:
                    return run(m.group(1))
            raise ApiError(404, "Not found.")

    return Handler


def serve(env: dict[str, str] | None = None) -> None:
    env = dict(os.environ if env is None else env)
    port = int(env.get("PORT", "8088"))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), make_handler())
    print(f"Marquee listening on :{port}", flush=True)
    httpd.serve_forever()
