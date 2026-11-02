"""Marquee's server-side planted bugs stay planted (BUGS.md) and nothing it serves gives them away."""

import datetime as dt
import http.cookiejar
import json
import re
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from urllib.parse import urlencode

import pytest

from marquee import data, server

T = server.today()
CARD = {"name": "Zoe Park", "card": "4242 4242 4242 4242", "expiry": "12/39", "cvc": "123"}


def day(n: int) -> str:
    return (T + dt.timedelta(days=n)).isoformat()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Client:
    def __init__(self, base: str):
        self.base = base
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect())

    def request(self, path: str, body=None) -> tuple[int, bytes, dict]:
        payload = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=payload, headers={"Content-Type": "application/json"})
        try:
            with self.opener.open(req) as resp:
                return resp.status, resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as err:
            return err.code, err.read(), dict(err.headers)

    def get(self, path: str, **query):
        status, raw, _ = self.request(path + ("?" + urlencode(query) if query else ""))
        return status, json.loads(raw)

    def post(self, path: str, body: dict | None = None):
        status, raw, _ = self.request(path, body or {})
        return status, json.loads(raw)

    def login(self, who: str, password: str = data.PASSWORD) -> int:
        self.post("/api/logout")
        return self.post("/api/login", {"email": f"{who}@marquee.test", "password": password})[0]

    def add(self, event: int, **body):
        return self.post("/api/basket", {"event": event} | body)

    def buy(self, **card):
        return self.post("/api/checkout", CARD | card)

    def order(self, event: int) -> dict:
        return next(o for o in self.get("/api/tickets")[1]["orders"] if o["event"]["id"] == event)


@pytest.fixture
def base_url():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(server.Store()))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture
def zoe(base_url):
    c = Client(base_url)
    assert c.login("zoe") == 200
    return c


def test_pages_and_access(base_url, zoe):
    visitor = Client(base_url)
    for path in ("/", "/help", "/login", "/events", "/event?id=2"):
        assert visitor.request(path)[0] == 200, path
    status, _, headers = visitor.request("/tickets")
    assert status == 302 and headers["Location"] == "/login?next=%2Ftickets"
    assert visitor.request("/nope")[0] == 404 and visitor.request("/healthz")[1] == b"ok"
    assert visitor.add(2, tier=21, qty=1)[0] == 401
    assert zoe.request("/dashboard")[0] == 403 and zoe.get("/api/organiser")[0] == 403
    assert zoe.login("max") == 200 and zoe.request("/basket")[0] == 403 and zoe.add(2, tier=21, qty=1)[0] == 403


def test_answer_key_is_never_served_or_hinted(base_url):
    visitor = Client(base_url)
    for path in ("/BUGS.md", "/static/../BUGS.md", "/server.py", "/data.py"):
        assert visitor.request(path)[0] == 404, path
    for folder in (server.STATIC_DIR, server.PAGES_DIR):
        for f in folder.iterdir():
            assert not re.search(r"bug|planted", f.read_text(), re.I), f.name


def test_seed_orders_follow_the_rules():
    w = data.world(T)
    kite = next(o for o in w["orders"] if o["event"] == 13 and o["user"] == 1)
    assert (kite["subtotal"], kite["discount"], kite["booking_fees"], kite["total"]) == (80.0, 8.0, 9.6, 84.1)
    assert sum(1 for t in w["tickets"] if t["owner"] == 1) == 14


def test_listing(base_url):
    c = Client(base_url)
    first = c.get("/api/events")[1]
    assert first["events"][0]["name"] == "Midnight Brass" and first["events"][0]["date"] == day(-1)  # BUG-04
    seen = [e["id"] for p in range(1, first["pages"] + 1) for e in c.get("/api/events", page=p)[1]["events"]]
    assert first["count"] == 15 and len(seen) == 14 and 2 not in seen  # BUG-03: The Velvet Static never shows
    paper = c.get("/api/events", q="paper")[1]["events"][0]
    assert paper["sold_out"] and not c.get("/api/events/3")[1]["all_sold_out"]  # BUG-01
    assert c.get("/api/events", q="lantern")[1]["count"] == 0  # BUG-05
    assert c.get("/api/events", q="BRASS")[1]["count"] == 1
    by_price = [e["from"] for e in c.get("/api/events", sort="price")[1]["events"]]
    assert by_price[:2] == [40.0, 12.0]  # BUG-02: Paper Moons (Standard €22, from €40) comes first
    assert c.get("/api/events", **{"from": day(6), "to": day(6)})[1]["count"] == 1


def test_event_page_and_tiers(base_url, zoe):
    ferris = zoe.get("/api/events/9")[1]["tiers"][0]
    assert ferris["ends"] == day(0) and not ferris["on_sale"]  # BUG-06
    assert zoe.add(9, tier=91, qty=1)[0] == 400
    assert zoe.add(1, tier=11, qty=2)[0] == 200  # BUG-04: Midnight Brass was yesterday
    assert zoe.get("/api/events/99")[0] == 404


def test_concessions():
    on = dt.date(2027, 3, 10)
    assert server.concession_ok(dt.date(1962, 3, 11), on)  # BUG-08: 64 years old, accepted
    assert not server.concession_ok(dt.date(2011, 3, 11), on)  # BUG-08: 15 years old, refused
    assert not server.concession_ok(dt.date(1980, 1, 1), on)


def test_seats(zoe):
    assert zoe.add(4, seats=["C5"])[0] == 400  # leaves C4 alone on the left: refused
    assert zoe.add(4, seats=["D6"])[0] == 200  # BUG-11: leaves D7 alone on the right
    status, basket = zoe.add(4, seats=["A1", "A2"])
    assert status == 200 and basket["lines"][-1]["name"] == "Standard" and basket["lines"][-1]["price"] == 36  # BUG-09
    assert zoe.add(4, seats=["F1"], access=False)[0] == 200  # BUG-10
    assert zoe.add(4, seats=["A1"])[0] == 409


def test_limits_and_holds(zoe):
    basket = zoe.get("/api/basket")[1]
    assert basket["lines"][0]["expired"] and basket["count"] == 2  # BUG-14: still in the basket
    status, order = zoe.buy()
    assert status == 200 and len(order["order"]["tickets"]) == 2  # BUG-14: and booked
    assert zoe.add(2, tier=21, qty=4)[0] == 200  # BUG-12: Zoe already has 2 of the 4 allowed
    assert zoe.add(2, tier=21, qty=1)[0] == 400
    zoe.buy()
    assert zoe.add(13, tier=131, qty=5)[0] == zoe.add(13, tier=131, qty=5)[0] == 200  # BUG-13
    assert zoe.get("/api/basket")[1]["count"] == 10 and zoe.add(13, tier=131, qty=9)[0] == 400
    assert zoe.add(7, tier=71, qty=5)[0] == 200 and zoe.buy()[0] == 200  # BUG-16: 3 were left
    bloom = zoe.get("/api/events/7")[1]["tiers"][0]
    assert bloom["sold"] == 252 and bloom["qty"] == 250


def test_fees_and_codes(zoe):
    assert server.booking_fee(24.95) == 3.0 and data.fee(24.95) == 2.99  # BUG-18
    _, b = zoe.add(13, tier=131, qty=2)
    assert b["order_fee"] == 5.0  # BUG-17: €2.50 per ticket
    assert zoe.post("/api/basket/code", {"code": "NOPE"})[0] == 400
    status, b = zoe.post("/api/basket/code", {"code": "AUTUMN15"})
    assert status == 200 and b["discounts"][0]["code"] == "AUTUMN15"  # BUG-20: ended yesterday
    status, b = zoe.post("/api/basket/code", {"code": "MARQUEE10"})
    assert [d["code"] for d in b["discounts"]] == ["AUTUMN15", "MARQUEE10"]  # BUG-22
    assert b["discounts"][1]["amount"] == 8.96  # BUG-21: 10% of €80 + €9.60 fees, not €8.00
    assert zoe.add(14, tier=141, qty=1, presale="WRONG")[0] == 400
    assert zoe.add(14, tier=141, qty=1)[0] == 200  # BUG-23: no presale code at all
    assert zoe.buy(expiry=T.strftime("%m/%y"))[0] == 400  # BUG-24: valid until the end of this month
    assert zoe.buy(expiry="01/20")[0] == 400 and zoe.buy()[0] == 200


def test_my_tickets(base_url, zoe):
    quiet = zoe.order(15)
    mine = [t["id"] for t in quiet["tickets"]]
    status, other = zoe.get(f"/api/tickets/{max(mine) + 1}")
    assert status == 200 and other["ticket"]["name"] == "Ivy Chen"  # BUG-25
    assert zoe.post(f"/api/tickets/{max(mine) + 1}/transfer", {"name": "x", "email": "x@example.com"})[0] == 404
    status, sent = zoe.post(f"/api/tickets/{mine[0]}/transfer", {"name": "Ana", "email": "ana@example.com"})
    assert status == 200 and sent["ticket"]["status"] == "valid"  # BUG-27
    assert zoe.post(f"/api/tickets/{mine[1]}/transfer", {"name": "Me", "email": "zoe@marquee.test"})[0] == 200  # BUG-26
    assert zoe.post(f"/api/tickets/{mine[1]}/resell", {"price": 29})[0] == 200  # BUG-28: face value €26
    assert zoe.post(f"/api/tickets/{mine[1]}/resell", {"price": 30})[0] == 400
    assert len(zoe.order(15)["tickets"]) == 3


def test_refunds(zoe):
    tide = zoe.order(11)
    assert tide["days"] == 7 and zoe.get(f"/api/orders/{tide['id']}/refund")[1]["amount"] == 36.0  # BUG-29
    comet = zoe.order(10)
    assert comet["event"]["status"] == "postponed"
    assert zoe.get(f"/api/orders/{comet['id']}/refund")[1]["amount"] == 0  # BUG-30: should be €74.18
    kite = zoe.order(13)
    assert zoe.get(f"/api/orders/{kite['id']}/refund")[1]["amount"] == 80.0  # BUG-31: paid €72 for the tickets
    velvet = zoe.order(2)
    assert zoe.get(f"/api/orders/{velvet['id']}/refund")[1]["amount"] == 45.0
    assert zoe.post(f"/api/orders/{velvet['id']}/refund")[0] == 200
    assert zoe.post(f"/api/orders/{comet['id']}/refund")[0] == 400


def test_organiser(base_url, zoe):
    codes = [t["code"] for t in zoe.order(15)["tickets"]]
    zoe.login("max")
    assert zoe.get("/api/organiser/events/5")[0] == 200  # BUG-33: Laugh Track Live is Rhea's
    assert all(e["id"] != 5 for e in zoe.get("/api/organiser")[1]["events"])
    kite = zoe.get("/api/organiser/events/13")[1]["event"]
    assert kite["revenue"] == 280.0  # BUG-37: fans paid €72 + €40 + €136 = €248 for the tickets
    _, bloom = zoe.post("/api/organiser/events/7/release", {"tier": 71, "qty": 50})
    assert bloom["event"]["released"] == 300 and bloom["event"]["capacity"] == 250  # BUG-34
    _, glass = zoe.post("/api/organiser/events/8/release", {"tier": 81, "qty": 10})
    assert glass["waitlist"] == 6 and glass["tiers"][0]["remaining"] == 10  # BUG-32
    first = zoe.post("/api/organiser/checkin", {"event": 15, "code": codes[0]})
    again = zoe.post("/api/organiser/checkin", {"event": 15, "code": codes[0]})
    assert first[0] == again[0] == 200  # BUG-39
    assert zoe.post("/api/organiser/checkin", {"event": 13, "code": codes[1]})[0] == 404
    status, raw, _ = zoe.request("/api/organiser/events/15/attendees.csv")
    assert ",Lee, Jordan,jordan.lee@example.com," in raw.decode()  # BUG-38
    zoe.post("/api/organiser/events/2/price", {"tier": 21, "price": 55})
    zoe.post("/api/organiser/events/12/cancel")
    zoe.login("zoe")
    velvet = zoe.order(2)
    assert velvet["tickets"][0]["face"] == 55 and velvet["lines"][0]["price"] == 45  # BUG-35
    assert zoe.get(f"/api/orders/{velvet['id']}/refund")[1]["amount"] == 55.0  # BUG-35: half of €110
    revue = zoe.order(12)
    assert revue["status"] == "refunded" and revue["refunded"] == 96.0 and revue["total"] == 110.02  # BUG-36
    assert zoe.get("/api/tickets")[1]["waitlist"][0]["position"] == 4
