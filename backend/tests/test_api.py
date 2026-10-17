"""End-to-end API test with a fake TinyFish client (no network)."""
import json
import os
import time

os.environ.setdefault("TINYFISH_API_KEY", "test-key")

from fastapi.testclient import TestClient  # noqa: E402

from backend.app import main  # noqa: E402
from backend.app.tinyfish import Hit, TinyFishError  # noqa: E402


class FakeTinyFish:
    def __init__(self):
        self.breakers = {}
        self.fetched = []

    async def search(self, query, **kw):
        if kw.get("include_domains", "") and "linkedin.com" in kw["include_domains"]:
            return [Hit("https://www.linkedin.com/in/asha-rao", "Asha Rao - Designer - Nimbus Labs | LinkedIn",
                        "Pune, Maharashtra · Designer at Nimbus Labs", "linkedin.com", 1)]
        if "address" in query:
            raise TinyFishError("search HTTP 503", 503)
        return [
            Hit("https://directory.test/asha-rao-pune", "Asha Rao, Pune - Contact", "Asha Rao Pune phone", "directory.test", 1),
            Hit("https://lookup.test/9999900000", "9999900, Asha Rao Pune", "Asha Rao 99999-000..", "lookup.test", 4),
            Hit("https://blocked.test/asha", "Asha Rao profile", "Asha Rao Pune", "blocked.test", 2),
            Hit("https://other.test/ravi", "Ravi Kumar", "unrelated", "other.test", 3),
        ]

    async def fetch(self, urls):
        self.fetched += urls
        results, errors = [], []
        for u in urls:
            if "blocked" in u:
                errors.append({"url": u, "error": "bot_blocked"})
            else:
                results.append({"url": u, "title": "Asha Rao", "text": "Asha Rao, Pune. Mobile: +91 98765 43210."})
        return results, errors

    async def aclose(self):
        pass


def run_scan(client, body):
    res = client.post("/api/scan", json=body)
    assert res.status_code == 202, res.text
    sid = res.json()["scan_id"]
    for _ in range(100):
        r = client.get(f"/api/scan/{sid}/report").json()
        if r["status"] != "running":
            return sid, r
        time.sleep(0.05)
    raise AssertionError("scan did not finish")


def test_full_scan_flow():
    with TestClient(main.app) as client:
        fake = FakeTinyFish()
        main.app.state.tf = fake
        main.limiter.hits.clear()

        req = {"full_name": "Asha Rao", "phone": "+91 99999 00000", "city": "Pune"}
        assert client.post("/api/scan", json={"level": "light", "consent": False, "fields": req}).status_code == 422
        assert client.post("/api/scan", json={"level": "light", "consent": True,
                                              "fields": {"full_name": "Asha Rao", "city": "Pune"}}).status_code == 422

        sid, report = run_scan(client, {"level": "light", "consent": True, "fields": req})
        assert report["status"] == "done"
        assert report["partial"] is True                      # one search failed
        assert not any("linkedin" in u for u in fake.fetched)  # login-walled: snippet only
        assert not any("other.test" in u for u in fake.fetched)  # unrelated hit filtered out

        blob = json.dumps(report)
        assert "98765 43210" not in blob and "9876543210" not in blob, "raw phone must never leave the server"
        shown = json.dumps([{k: v for k, v in f.items() if k != "source_url"} for f in report["findings"]])
        assert "9999900" not in shown and "99999-000" not in shown, "partial phone fragments must be masked too"
        events = [json.loads(line[6:]) for line in client.get(f"/api/scan/{sid}/stream").text.splitlines()
                  if line.startswith("data: ")]
        assert not any("9999900" in e["name"] for e in events if e["type"] == "source"), "live source rows must be masked"
        phones = [f for f in report["findings"] if f["type"] == "phone"]
        assert phones and phones[0]["risk"] == "red"
        assert any(s["status"] == "blocked" for s in report["sources"])

        assert all(f["confidence_label"] for f in report["findings"])
        assert phones[0]["confidence"] < 0.75, "phone on the page isn't the user's own number"

        # "Not me" on a page removes everything from that page from the score
        before = report["score"]
        target = phones[0]
        after = client.post(f"/api/scan/{sid}/verdict", json={"finding_id": target["id"], "verdict": "not_me"}).json()
        assert after["score"] < before
        assert all(f["user_verdict"] == "not_me" for f in after["findings"] if f["source_url"] == target["source_url"])

        stream = client.get(f"/api/scan/{sid}/stream").text
        assert '"type": "done"' in stream

        assert client.delete(f"/api/scan/{sid}").status_code == 204
        assert client.get(f"/api/scan/{sid}/report").status_code == 404


def test_health():
    with TestClient(main.app) as client:
        body = client.get("/health").json()
        assert body["status"] == "ok" and body["tinyfish_key"] is True
