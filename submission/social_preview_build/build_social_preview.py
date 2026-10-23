"""Builds the 1280x640 social preview image (GitHub repository card, link previews) from the logo and a real screenshot.
    python build_social_preview.py
Writes web/public/og-image.png and ../Capzoryx_Social_Preview_1280x640.png (next to the repo folder)."""
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SHOT = ROOT / 'submission' / 'deck_build' / 'shots' / 'overview.png'
FONTS = ROOT / 'submission' / 'deck_build' / 'fonts'
CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
OUTS = [ROOT / 'web' / 'public' / 'og-image.png', ROOT.parent / 'Capzoryx_Social_Preview_1280x640.png']

LOGO = ('<svg viewBox="0 0 40 40" width="92" height="92"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0f9b7c"/>'
        '<stop offset="1" stop-color="#132a4a"/></linearGradient></defs><rect width="40" height="40" rx="11" fill="url(#g)"/>'
        '<path d="M27.5 13.2A9.6 9.6 0 1 0 27.5 26.8" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round"/>'
        '<path d="M16.5 24.5l4-4.2 3 2.4 6-7.4" fill="none" stroke="#8cebd0" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/></svg>')

HTML = f'''<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:Inter;src:url("{(FONTS / 'Inter-Regular.ttf').as_uri()}");font-weight:400}}
@font-face{{font-family:Inter;src:url("{(FONTS / 'Inter-Bold.ttf').as_uri()}");font-weight:700}}
*{{box-sizing:border-box;margin:0}}
body{{width:1280px;height:640px;overflow:hidden;font-family:Inter,Segoe UI,Arial,sans-serif;color:#fff;
 background:radial-gradient(900px 520px at 8% -10%,#0f7a6355,transparent 60%),radial-gradient(800px 520px at 100% 100%,#3b5bdb44,transparent 60%),#0a1120;position:relative}}
.grid{{position:absolute;inset:0;background-image:linear-gradient(#ffffff0b 1px,transparent 1px),linear-gradient(90deg,#ffffff0b 1px,transparent 1px);background-size:48px 48px;
 -webkit-mask-image:radial-gradient(ellipse at 30% 40%,#000 10%,transparent 70%)}}
.left{{position:absolute;left:68px;top:52px;width:620px}}
.name{{font-size:66px;font-weight:700;letter-spacing:-2px;line-height:1.02;margin-top:20px}}
.name b{{color:#3fe0bf}}
.tag{{font-size:26px;line-height:1.3;margin-top:18px;color:#d6e4f2}}
.chips{{display:flex;gap:10px;flex-wrap:nowrap;margin-top:24px}}
.chips span{{font-size:16px;font-weight:700;color:#8cebd0;background:#0f9b7c26;border:1px solid #3fe0bf55;border-radius:99px;padding:7px 13px;white-space:nowrap}}
.url{{position:absolute;left:68px;bottom:34px;font-size:20px;color:#9fb6cc;letter-spacing:.3px}}
.url b{{color:#fff}}
.shot{{position:absolute;right:-60px;top:118px;width:600px;border-radius:20px;border:1px solid #ffffff2e;box-shadow:0 40px 90px #000a,0 0 0 8px #ffffff10;transform:rotate(-3deg) perspective(1400px) rotateY(-8deg)}}
.badge{{position:absolute;right:54px;bottom:40px;font-size:18px;font-weight:700;color:#0a1120;background:#8cebd0;border-radius:99px;padding:9px 18px}}
</style></head><body><div class="grid"></div>
<div class="left">{LOGO}<div class="name">Capzoryx<br><b>Copilot</b></div>
<div class="tag">Free AI finance copilot for small businesses. It helps them decide and never moves their money.</div>
<div class="chips"><span>37 languages</span><span>Photo and chat records</span><span>Two-person approval</span></div></div>
<img class="shot" src="{SHOT.as_uri()}">
<div class="url"><b>capzoryx-copilot.vercel.app</b> &nbsp;·&nbsp; Team Capzoryx &nbsp;·&nbsp; Topic E</div>
</body></html>'''

tmp = HERE / '_social.html'
tmp.write_text(HTML, encoding='utf-8')
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME)
    pg = b.new_page(viewport={'width': 1280, 'height': 640})
    pg.goto(tmp.as_uri())
    pg.wait_for_timeout(800)
    github = OUTS[1]
    pg.screenshot(path=str(github), clip={'x': 0, 'y': 0, 'width': 1280, 'height': 640})
    print('wrote', github, round(github.stat().st_size / 1024), 'KB')
    # The link-preview version for the website: 1200x630 (1.91:1), which WhatsApp, Facebook, LinkedIn and X show as a large card.
    pg.set_viewport_size({'width': 1200, 'height': 630})
    pg.add_style_tag(content='body{width:1200px;height:630px}.left{left:60px;top:48px;width:600px}.name{font-size:62px}.tag{font-size:24px}.shot{right:-90px;top:112px;width:560px}.url{left:60px;bottom:30px}')
    pg.wait_for_timeout(300)
    site = OUTS[0]
    pg.screenshot(path=str(site), clip={'x': 0, 'y': 0, 'width': 1200, 'height': 630})
    print('wrote', site, round(site.stat().st_size / 1024), 'KB')
    b.close()
tmp.unlink()
