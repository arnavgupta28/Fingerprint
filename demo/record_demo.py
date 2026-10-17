"""Record the Fingerprint demo video: the live app inside a phone frame, with captions.

Usage:
  1. Start the app:   .venv/bin/uvicorn backend.app.main:app --port 8765
  2. Fill demo/persona.json (copy persona.example.json). Only someone who consented to be scanned and shown.
  3. Run:             .venv/bin/python demo/record_demo.py
Output: demo/out/fingerprint-demo.mp4 (1920x1080). The scan wait is sped up and labelled on screen.
Typed phone / email are blurred in the video; found values are always masked by the app itself.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import Frame, Page, sync_playwright

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
BASE = "http://localhost:8765"
STAGE_URL = f"{BASE}/__demo_stage"
SPEEDUP = 6

TAP_JS = """([x, y]) => {
  const d = document.createElement('div');
  d.style.cssText = `position:fixed;left:${x-22}px;top:${y-22}px;width:44px;height:44px;border-radius:50%;
    background:rgba(31,31,43,.25);border:3px solid rgba(31,31,43,.55);z-index:99999;pointer-events:none;
    transform:scale(.4);opacity:1;transition:transform .35s ease-out, opacity .5s ease-out .15s`;
  document.body.appendChild(d);
  requestAnimationFrame(() => { d.style.transform = 'scale(1.3)'; d.style.opacity = '0'; });
  setTimeout(() => d.remove(), 800);
}"""
BLUR_CSS = "input[name=phone], input[name=email] { filter: blur(6px); } .screen { padding-top: 50px !important; }"


class Demo:
    def __init__(self, page: Page, persona: dict):
        self.page = page
        self.p = persona
        self.marks: dict[str, float] = {}
        self.t0 = time.monotonic()

    @property
    def app(self) -> Frame:
        return self.page.frame(name="app") or self.page.frames[1]

    def mark(self, name: str) -> None:
        self.marks[name] = time.monotonic() - self.t0

    def caption(self, step: str, title: str, sub: str = "", hold: float = 0) -> None:
        self.page.evaluate("([a, b, c]) => window.caption(a, b, c)", [step, title, sub])
        self.wait(0.6 + hold)

    def wait(self, s: float) -> None:
        self.page.wait_for_timeout(int(s * 1000))

    def tap(self, selector: str, pause: float = 0.5) -> None:
        loc = self.app.locator(selector).first
        loc.scroll_into_view_if_needed()
        box = loc.bounding_box()           # page coordinates
        frame_box = self.page.locator("#app").bounding_box()
        if box and frame_box:
            self.app.evaluate(TAP_JS, [box["x"] - frame_box["x"] + box["width"] / 2,
                                       box["y"] - frame_box["y"] + box["height"] / 2])
        self.wait(0.25)
        loc.click()
        self.wait(pause)

    def type(self, selector: str, text: str, delay: int = 55) -> None:
        if not text:
            return
        loc = self.app.locator(selector).first
        loc.scroll_into_view_if_needed()
        loc.click()
        loc.press_sequentially(str(text), delay=delay)
        self.wait(0.25)

    def scroll_to(self, selector: str, offset: int = -70) -> None:
        self.app.evaluate(
            """([sel, off]) => { const el = document.querySelector(sel);
                 if (el) window.scrollTo({top: el.getBoundingClientRect().top + window.scrollY + off, behavior: 'smooth'}); }""",
            [selector, offset])
        self.wait(1.0)

    def scroll_by(self, dy: int) -> None:
        self.app.evaluate("dy => window.scrollBy({top: dy, behavior: 'smooth'})", dy)
        self.wait(1.0)

    # ── the story ───────────────────────────────────────────────────────────
    def run(self) -> None:
        p = self.p
        level = p.get("level", "standard")
        first = p["full_name"].split()[0]
        self.app.wait_for_selector("[data-screen=splash]")
        self.app.add_style_tag(content=BLUR_CSS)

        self.caption("1", "See what the internet knows about you", "Before a scammer, recruiter or stranger does.", hold=2.2)
        self.tap("text=Let's go", pause=0.6)
        self.page.evaluate("() => window.statusSolid(true)")

        self.caption("2", "Meet Smudge", "Your friendly guide. First, your name.")
        self.type("#full_name", p["full_name"])
        self.tap("#name-form button", pause=0.8)

        self.caption("3", "You choose how much to share",
                     "Light, Standard or Deep. More detail means a sharper match, and it's always your call.", hold=1.6)
        self.tap(f"[data-level={level}]", pause=1.2)
        self.app.add_style_tag(content=BLUR_CSS)

        self.caption("4", "Name, phone and city are required",
                     "That's the minimum to tell you apart from people with the same name. (Phone is blurred in this video.)")
        country = p.get("country", "IN")
        self.app.select_option("select[name=country]", country)
        self.type("input[name=phone]", p["phone"])
        self.type("input[name=city]", p["city"])
        self.wait(0.6)

        optional = [(k, p.get(k)) for k in ("birth_year", "email", "usernames", "state", "middle_name", "aliases",
                                            "employer", "school", "past_cities") if p.get(k)]
        if optional and level != "light":
            self.caption("5", "Every optional detail sharpens the match",
                         "Birth year, email, usernames… watch the accuracy meter climb.")
            for k, v in optional:
                if self.app.locator(f"input[name={k}]").is_visible():
                    self.type(f"input[name={k}]", v, delay=40)
            self.scroll_to(".meter", -260)
            self.wait(1.4)

        self.caption("6", "Self-search only", "You confirm it's you. Nothing is stored; the scan is deleted within 30 minutes.")
        self.scroll_to("#consent", -300)
        self.tap("#consent", pause=0.6)
        self.tap("#start-btn", pause=0.4)

        self.caption("7", "A live scan of the public web",
                     "TinyFish Search finds pages; TinyFish Fetch reads them. Smudge shows every source as it goes.")
        self.mark("scan_start")
        self.page.evaluate("t => window.badge(t)", f"⏩ sped up {SPEEDUP}×")
        self.app.wait_for_selector("[data-screen=report]:not([hidden])", timeout=300_000)
        self.page.evaluate("() => window.badge('')")
        self.mark("scan_end")
        self.wait(0.8)

        self.caption("8", "Your exposure score", "One number, plus every finding sorted by risk and type.", hold=2.4)
        self.scroll_to("#summary", -40)
        self.wait(1.6)

        self.caption("9", "Every source shows how likely it's really you",
                     "Very likely · Likely · Maybe · Probably not, so namesakes don't scare you.")
        self.scroll_to("#findings", -20)
        self.wait(2.2)

        self.caption("10", "Why it matched, the proof, and how to fix it",
                     "Matched signals, a masked quote from the page, the source link and removal steps.")
        self.tap("#findings .finding .finding-head", pause=1.2)
        self.scroll_by(260)
        self.wait(1.6)
        self.scroll_to("#findings", -20)

        uncertain = self.app.locator("#findings .finding:has(.cf-low), #findings .finding:has(.cf-none)")
        if uncertain.count():
            self.caption("11", "Not you? One tap",
                         "“Not me” removes that source from your score and re-scores the report instantly.")
            card = uncertain.first
            card.scroll_into_view_if_needed()
            self.wait(0.8)
            card.locator(".finding-head").click()
            self.wait(0.9)
            btn = card.locator("[data-verdict=not_me]")
            box, fb = btn.bounding_box(), self.page.locator("#app").bounding_box()
            if box and fb:
                self.app.evaluate(TAP_JS, [box["x"] - fb["x"] + box["width"] / 2, box["y"] - fb["y"] + box["height"] / 2])
            self.wait(0.25)
            btn.click()
            self.wait(1.2)
            self.app.evaluate("() => window.scrollTo({top: 0, behavior: 'smooth'})")
            self.wait(1.8)

        self.caption("12", "Delete everything with one tap", "Your scan lives in memory only. Nothing to leak later.")
        self.scroll_to(".actions", -420)
        self.wait(0.8)
        self.tap("#delete-btn", pause=1.4)

        self.page.evaluate("() => window.statusSolid(false)")
        self.page.evaluate("() => window.ending()")
        self.wait(3.2)
        self.mark("end")


def main() -> None:
    persona_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "persona.json"
    if not persona_path.exists():
        sys.exit("Create demo/persona.json from demo/persona.example.json first.")
    persona = json.loads(persona_path.read_text())
    if persona.get("consented") is not True:
        sys.exit('Set "consented": true in demo/persona.json once the person has agreed to be scanned and shown.')

    OUT.mkdir(exist_ok=True)
    stage_html = (ROOT / "stage.html").read_text()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1,
                                  record_video_dir=str(OUT / "raw"), record_video_size={"width": 1920, "height": 1080})
        page = ctx.new_page()
        page.route(STAGE_URL, lambda route: route.fulfill(status=200, content_type="text/html", body=stage_html))
        page.goto(STAGE_URL)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1200)
        demo = Demo(page, persona)
        demo.t0 = time.monotonic() - 1.2   # video starts at page creation, roughly
        demo.run()
        video = page.video.path()
        ctx.close()
        browser.close()

    out = OUT / "fingerprint-demo.mp4"
    encode(Path(video), out, demo.marks)
    print(f"saved {out}  ({demo.marks})")


def encode(src: Path, dst: Path, marks: dict[str, float]) -> None:
    """webm → mp4, speeding up the scan wait so the video stays short."""
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    a, b = marks["scan_start"] + 1.0, marks["scan_end"] - 0.3
    graph = (
        f"[0:v]trim=0:{a},setpts=PTS-STARTPTS[v0];"
        f"[0:v]trim={a}:{b},setpts=(PTS-STARTPTS)/{SPEEDUP}[v1];"
        f"[0:v]trim={b},setpts=PTS-STARTPTS[v2];"
        f"[v0][v1][v2]concat=n=3:v=1:a=0,fps=30,format=yuv420p[v]"
    )
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(src), "-filter_complex", graph, "-map", "[v]",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-movflags", "+faststart", str(dst)],
                   check=True)


if __name__ == "__main__":
    main()
