"""Builds the Capzoryx Copilot 10-minute pitch deck (editable PPTX + speaker notes) from real app screenshots.

    pip install python-pptx pillow segno opencv-python-headless playwright
    python submission/deck_build/capture_screens.py ...      # screenshots from a LOCAL app copy (see that file)
    python submission/deck_build/build_deck.py               # writes the .pptx and the speaker-notes .txt next to the repo's parent folder
    soffice --headless --convert-to pdf Capzoryx_Copilot_Pitch_Deck_10min.pptx   # PDF with embedded fonts and live links

Font: Inter (SIL OFL, files in submission/deck_build/fonts/) must be installed to open the PPTX with the intended look.
Every number on a slide is re-derived by submission/deck_build/verify_claims.py or comes from a document named on the slide.
"""
import asyncio, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from lxml import etree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SHOTS = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / 'shots'
OUT_DIR = Path(sys.argv[2]) if len(sys.argv) > 2 else REPO.parent
WORK = HERE / '_assets'; WORK.mkdir(exist_ok=True)
LIVE_URL = 'https://capzoryx-copilot.vercel.app'
REPO_URL = 'https://github.com/Pranto-404/capzoryx-copilot'
N_SLIDES = 13

# ---- palette (dark navy, teal and lime accents) ------------------------------------------------
BG, CARD, CARD2, LINE = '0A1220', '121F31', '172A44', '2A3F5C'
TEAL, LIME, AMBER, ROSE, BLUE = '3BE3C1', 'C7F36B', 'F5B642', 'FF7A8A', '6FB7FF'
WHITE, MUTED, DIM = 'FFFFFF', 'B4C1D2', '8FA0B5'
FONT = 'Inter'
SW, SH = 13.333, 7.5


def rgb(h): return RGBColor.from_string(h)


# ---- assets: logo (rendered from web/public/favicon.svg), QR, framed screenshots ----------------
def make_logo():
    p = WORK / 'logo.png'
    svg = (REPO / 'web/public/favicon.svg').read_text(encoding='utf-8')
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel='chrome'); pg = b.new_page(viewport={'width': 1024, 'height': 1024})
        pg.set_content('<body style="margin:0;background:transparent"><div style="width:1024px;height:1024px">' + svg.replace('<svg ', '<svg width="1024" height="1024" ', 1) + '</div></body>')
        pg.screenshot(path=str(p), omit_background=True); b.close()
    return p


def make_qr():
    import segno
    p = WORK / 'qr.png'
    segno.make(LIVE_URL, error='h').save(str(p), scale=24, border=2, dark='#0A1220', light='#FFFFFF')
    import cv2
    txt, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(str(p)))
    assert txt == LIVE_URL, f'QR decodes to {txt!r}'
    return p


PPI = 240  # pixels per inch for framed screenshots


def framed(src, crop, width_in, name, pad_in=0.28, radius_in=0.12):
    """Crop (x0,y0,x1,y1 in source px or None), round the corners, add a soft shadow. Returns (png path, height_in)."""
    im = Image.open(SHOTS / src).convert('RGBA')
    if crop: im = im.crop(crop)
    w_px = int(width_in * PPI); h_px = int(im.height * w_px / im.width)
    im = im.resize((w_px, h_px), Image.LANCZOS)
    r = int(radius_in * PPI); pad = int(pad_in * PPI)
    mask = Image.new('L', im.size, 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, w_px - 1, h_px - 1), r, fill=255)
    canvas = Image.new('RGBA', (w_px + 2 * pad, h_px + 2 * pad), (0, 0, 0, 0))
    sh = Image.new('L', canvas.size, 0); ImageDraw.Draw(sh).rounded_rectangle((pad, pad + int(0.06 * PPI), pad + w_px, pad + h_px + int(0.06 * PPI)), r, fill=150)
    sh = sh.filter(ImageFilter.GaussianBlur(int(0.12 * PPI)))
    canvas.paste(Image.new('RGBA', canvas.size, (0, 0, 0, 255)), (0, 0), sh)
    canvas.paste(im, (pad, pad), mask)
    ring = Image.new('RGBA', canvas.size, (0, 0, 0, 0)); ImageDraw.Draw(ring).rounded_rectangle((pad, pad, pad + w_px - 1, pad + h_px - 1), r, outline=(255, 255, 255, 40), width=2)
    canvas = Image.alpha_composite(canvas, ring)
    out = WORK / f'{name}.png'; canvas.save(out, optimize=True)
    return out, h_px / PPI


# ---- pptx helpers ------------------------------------------------------------------------------
prs = Presentation(); prs.slide_width = Inches(SW); prs.slide_height = Inches(SH)
BLANK = prs.slide_layouts[6]


def new_slide(notes):
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid(); s.background.fill.fore_color.rgb = rgb(BG)
    s.notes_slide.notes_text_frame.text = notes
    return s


def set_run(r, size, color, bold=False, spc=None, link=None):
    f = r.font; f.name = FONT; f.size = Pt(size); f.bold = bold; f.color.rgb = rgb(color)
    rpr = r._r.get_or_add_rPr()
    for tag in ('a:ea', 'a:cs'):
        el = etree.SubElement(rpr, qn(tag)); el.set('typeface', FONT)
    if spc: rpr.set('spc', str(spc))
    if link: r.hyperlink.address = link


def text(s, x, y, w, h, paras, size=20, color=WHITE, bold=False, align='l', anchor='t', line=1.1, space_after=0, spc=None, link=None):
    """paras: str | list of (str | list of (text, {opts}) runs | dict(runs=..., size=..., ...))."""
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf = tb.text_frame
    tf.word_wrap = True; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = {'t': MSO_ANCHOR.TOP, 'm': MSO_ANCHOR.MIDDLE, 'b': MSO_ANCHOR.BOTTOM}[anchor]
    if isinstance(paras, str): paras = [paras]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        opts = {}
        if isinstance(para, dict): opts = para; runs = para['runs']
        else: runs = para
        if isinstance(runs, str): runs = [(runs, {})]
        p.alignment = {'l': PP_ALIGN.LEFT, 'c': PP_ALIGN.CENTER, 'r': PP_ALIGN.RIGHT}[opts.get('align', align)]
        p.line_spacing = opts.get('line', line); p.space_after = Pt(opts.get('space_after', space_after))
        for t, o in runs:
            r = p.add_run(); r.text = t
            set_run(r, o.get('size', opts.get('size', size)), o.get('color', opts.get('color', color)), o.get('bold', opts.get('bold', bold)), o.get('spc', opts.get('spc', spc)), o.get('link', link))
    return tb


def box(s, x, y, w, h, fill=CARD, line=None, radius=0.14, line_w=1.0, shape=None):
    shp = s.shapes.add_shape(shape or MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    if shape is None: shp.adjustments[0] = min(0.5, radius / min(w, h))
    if fill: shp.fill.solid(); shp.fill.fore_color.rgb = rgb(fill)
    else: shp.fill.background()
    if line: shp.line.color.rgb = rgb(line); shp.line.width = Pt(line_w)
    else: shp.line.fill.background()
    shp.shadow.inherit = False
    return shp


def picture(s, path, x, y, w=None, h=None, link=None):
    p = s.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w) if w else None, Inches(h) if h else None)
    if link: p.click_action.hyperlink.address = link
    return p


def framed_pic(s, src, crop, x, y, w, name, alt=None):
    path, h = framed(src, crop, w, name)
    pad = 0.28
    p = picture(s, path, x - pad, y - pad, w + 2 * pad, h + 2 * pad)
    p._element.nvPicPr.cNvPr.set('descr', alt or f'Screenshot of the running app: {name}')
    return h


def chevron(s, x, y, w=0.3, h=0.4, color=TEAL):
    c = s.shapes.add_shape(MSO_SHAPE.CHEVRON, Inches(x), Inches(y), Inches(w), Inches(h))
    c.fill.solid(); c.fill.fore_color.rgb = rgb(color); c.line.fill.background(); c.shadow.inherit = False
    return c


def header(s, n, kicker, title, subtitle=None):
    text(s, 0.7, 0.42, 9, 0.3, kicker.upper(), size=14, color=TEAL, bold=True, spc=200)
    text(s, 0.7, 0.78, 11.9, 0.8, title, size=36, bold=True, line=1.0)
    if subtitle: text(s, 0.7, 1.52, 11.9, 0.45, subtitle, size=20, color=MUTED)


def footer(s, n, left=None, logo_path=None):
    s.shapes.add_connector(1, Inches(0.7), Inches(6.98), Inches(SW - 0.7), Inches(6.98)).line.color.rgb = rgb(LINE)
    picture(s, logo_path, 0.7, 7.05, 0.32, 0.32)
    text(s, 1.12, 7.07, 8.5, 0.3, [[('Capzoryx Copilot', {'bold': True, 'color': MUTED}), ('  ·  ' + (left or '2026 Shenzhen International FinTechathon  ·  Topic E'), {'color': DIM})]], size=14, anchor='m')
    text(s, SW - 2.7, 7.07, 2.0, 0.3, f'{n:02d} / {N_SLIDES}', size=14, color=MUTED, bold=True, align='r', anchor='m')


def pill(s, x, y, w, h, label, color=TEAL, fill=CARD2, size=16):
    box(s, x, y, w, h, fill=fill, line=color, radius=h / 2, line_w=1.25)
    text(s, x, y, w, h, label, size=size, color=color, bold=True, align='c', anchor='m')


def caption(s, x, y, w, label, color=DIM, size=14, align='l'):
    text(s, x, y, w, 0.3, label, size=size, color=color, align=align)


# =================================================================================================
LOGO = make_logo(); QR = make_qr()
NOTES = {}


def build():
    # ---------------- 1 TITLE ----------------
    s = new_slide(NOTES[1])
    text(s, 0.8, 0.62, 8, 0.3, '2026 SHENZHEN INTERNATIONAL FINTECHATHON', size=16, color=TEAL, bold=True, spc=160)
    text(s, 0.8, 1.0, 8, 0.3, 'INTERNATIONAL TRACK  ·  TOPIC E: SME FINANCE COPILOT', size=16, color=MUTED, bold=True, spc=100)
    picture(s, LOGO, 0.8, 1.9, 1.35, 1.35)
    text(s, 2.45, 1.78, 5.5, 0.9, 'Capzoryx', size=58, bold=True, line=0.95)
    text(s, 2.45, 2.55, 5.5, 0.9, 'Copilot', size=58, bold=True, color=TEAL, line=0.95)
    text(s, 0.8, 3.7, 6.4, 1.8, [[('AI that helps small businesses decide.', {'bold': True}), ('  Without ever taking control of their money.', {'color': MUTED})]], size=26, line=1.12)
    pill(s, 0.8, 5.5, 4.3, 0.5, 'TEAM CAPZORYX  ·  BANGLADESH', size=16)
    text(s, 0.8, 6.2, 7, 0.3, [[('Live product', {'link': LIVE_URL, 'color': TEAL}), ('   ·   ', {}), ('Source code', {'link': REPO_URL, 'color': TEAL}), ('   ·   Tested decision controls', {})]], size=16, color=MUTED)
    framed_pic(s, 'landing_en.png', None, 7.2, 1.65, 5.5, 's1_landing', 'The Capzoryx Copilot landing page and sign-up card')
    caption(s, 7.2, 5.5, 5.5, 'The real landing page · 37 languages · free to start', align='l')
    footer(s, 1, 'AI as a financial participant  ·  10-minute pitch', LOGO)

    # ---------------- 2 PROBLEM ----------------
    s = new_slide(NOTES[2])
    header(s, 2, '01 / The SME problem', 'Profitable on paper. Short of cash in reality.', 'Three questions small-business owners answer too late.')
    qs = [('01', 'When will cash run short?', 'Receipts and supplier deadlines rarely arrive together.'),
          ('02', 'Which financing truly fits?', 'The lowest advertised rate can hide a higher effective cost.'),
          ('03', 'Which payment is safe?', 'Duplicate invoices and rushed approvals put working capital at risk.')]
    for i, (n, q, d) in enumerate(qs):
        x = 0.7 + i * 4.05
        box(s, x, 2.2, 3.85, 3.0, fill=CARD, line=LINE)
        text(s, x + 0.3, 2.4, 1.5, 0.6, n, size=32, bold=True, color=TEAL)
        text(s, x + 0.3, 3.05, 3.3, 0.9, q, size=24, bold=True, line=1.05)
        text(s, x + 0.3, 3.95, 3.3, 1.15, d, size=18, color=MUTED, line=1.15)
    box(s, 0.7, 5.4, 11.93, 0.72, fill=CARD2)
    text(s, 1.0, 5.4, 11.4, 0.72, [[('The gap is not a lack of data.  ', {}), ('It is the lack of a trusted next decision.', {'color': TEAL})]], size=22, bold=True, anchor='m')
    text(s, 0.7, 6.25, 11.93, 0.65, 'We start with SMEs in Bangladesh. The engine is not local: 37 languages, 150+ currencies.', size=17, color=MUTED, line=1.1)
    footer(s, 2, logo_path=LOGO)

    # ---------------- 3 APPROACH ----------------
    s = new_slide(NOTES[3])
    header(s, 3, '02 / The Capzoryx approach', 'A verified decision, not a blind guess.', 'One workspace turns business records into informed, controlled action.')
    cards = [('SEE', TEAL, 'Bills, balances, due dates and a cash outlook for 7 and 30 days.'),
             ('DECIDE', BLUE, 'Compare loans by effective rate, total cost and fit.'),
             ('CONTROL', LIME, 'A second person approves; every step is audited.')]
    for i, (t, c, d) in enumerate(cards):
        x = 0.7 + i * 4.05
        box(s, x, 2.25, 3.85, 2.6, fill=CARD, line=LINE)
        box(s, x + 0.3, 2.62, 0.1, 0.5, fill=c, radius=0.05)
        text(s, x + 0.55, 2.58, 3, 0.6, t, size=28, bold=True)
        text(s, x + 0.3, 3.3, 3.3, 1.45, d, size=20, color=MUTED, line=1.12)
    box(s, 0.7, 5.15, 11.93, 1.0, fill=CARD2, line=LINE)
    steps = ['VERIFIED EVIDENCE', 'EXACT MATH', 'POLICY + APPROVAL', 'AUDIT']
    xs = [0.95, 4.2, 6.7, 10.15]
    widths = [2.6, 1.75, 2.7]
    for i, t in enumerate(steps):
        text(s, xs[i], 5.15, 2.8, 1.0, t, size=19, bold=True, color=TEAL if i == 3 else WHITE, anchor='m')
        if i < 3: chevron(s, xs[i] + widths[i] + 0.22, 5.48, 0.25, 0.35)
    text(s, 0.7, 6.4, 11.93, 0.45, 'AI may propose. Deterministic code calculates. People approve.', size=20, bold=True, color=LIME)
    footer(s, 3, logo_path=LOGO)

    # ---------------- 4 PRODUCT OVERVIEW ----------------
    s = new_slide(NOTES[4])
    header(s, 4, '03 / The product: overview', 'From records to a clear financial picture.')
    h = framed_pic(s, 'overview.png', (0, 0, 2560, 1720), 0.95, 1.7, 7.0, 's4_overview', 'The Overview screen with the sample business')
    caption(s, 0.95, 1.7 + h + 0.2, 7.0, 'Real screen, local copy, fictional sample business.')
    items = [('BDT 150,000', 'cleared balance, with an approximate USD value beside it', TEAL),
             ('7 and 30 days', 'a deterministic cash outlook that flags the first reserve breach', AMBER),
             ('1 click', '“Try a sample business” loads fictional data so every feature can be tested', LIME)]
    for i, (big, small, c) in enumerate(items):
        y = 1.75 + i * 1.65
        box(s, 8.5, y, 0.1, 1.35, fill=c, radius=0.05)
        text(s, 8.8, y - 0.03, 3.85, 0.55, big, size=28, bold=True, color=c)
        text(s, 8.8, y + 0.55, 3.85, 1.0, small, size=17, color=MUTED, line=1.1)
    footer(s, 4, logo_path=LOGO)

    # ---------------- 5 ADD RECORDS ----------------
    s = new_slide(NOTES[5])
    header(s, 5, '03 / The product: add records', 'Snap it or type it. You confirm.')
    box(s, 0.95, 1.75, 5.2, 0.62, fill=TEAL, radius=0.3)
    text(s, 1.2, 1.75, 4.8, 0.62, '“I paid Rahman 5000 for freight yesterday”', size=17, bold=True, color=BG, anchor='m')
    chevron(s, 3.45, 2.5, 0.28, 0.3).rotation = 90
    h = framed_pic(s, 'draft_panel.png', (0, 852, 1932, 1815), 0.95, 2.95, 6.2, 's5_draft', 'The draft card: amount, direction, date and note, to confirm before saving')
    modes = [('Photo of a bill or receipt', 'Read by the optional cloud model.', TEAL),
             ('A typed sentence', 'Becomes a draft, even without cloud AI.', BLUE),
             ('A plain form', 'Cash activity or an unpaid supplier invoice.', LIME)]
    for i, (t, d, c) in enumerate(modes):
        y = 1.75 + i * 1.3
        box(s, 7.5, y, 0.1, 1.1, fill=c, radius=0.05)
        text(s, 7.8, y - 0.04, 4.8, 0.45, t, size=22, bold=True)
        text(s, 7.8, y + 0.45, 4.8, 0.7, d, size=18, color=MUTED, line=1.1)
    box(s, 7.5, 5.7, 5.13, 1.0, fill=CARD2, line=TEAL, line_w=1.25)
    text(s, 7.75, 5.7, 4.7, 1.0, 'You always check the draft. Recording something never sends money.', size=18, bold=True, anchor='m', line=1.1)
    footer(s, 5, logo_path=LOGO)

    # ---------------- 6 SCENARIO ----------------
    s = new_slide(NOTES[6])
    header(s, 6, '04 / Demo scenario', 'The cash gap shows up six days early.')
    h = framed_pic(s, 'cashflow.png', (520, 340, 2500, 1605), 0.95, 1.7, 6.9, 's6_cashflow', 'The Cash flow screen: lowest balance, first reserve breach, projection chart')
    caption(s, 0.95, 1.7 + h + 0.2, 6.9, 'Fictional sample business, BDT, safety reserve 0.')
    stats = [('BDT 150,000', 'cleared cash today', TEAL), ('BDT 420,000', 'material bill, due in 6 days', AMBER), ('−BDT 360,000', 'lowest balance in 30 days', ROSE)]
    for i, (big, small, c) in enumerate(stats):
        y = 1.75 + i * 1.45
        box(s, 8.9, y, 3.73, 1.25, fill=CARD, line=LINE)
        text(s, 9.15, y + 0.12, 3.3, 0.55, big, size=28, bold=True, color=c)
        text(s, 9.15, y + 0.72, 3.4, 0.5, small, size=15, color=MUTED, line=1.0)
    text(s, 8.9, 6.1, 3.73, 0.6, 'Customers pay BDT 600,000 on day 25.', size=16, color=MUTED, line=1.1)
    footer(s, 6, logo_path=LOGO)

    # ---------------- 7 FINANCING ----------------
    s = new_slide(NOTES[7])
    header(s, 7, '05 / Financing intelligence', 'The cheapest-looking rate can cost more.')
    h = framed_pic(s, 'loans_result.png', (0, 455, 1932, 1650), 0.95, 1.7, 6.9, 's7_loans', 'Loan comparison result: ranked quotes with effective annual rates and cash-flow fit')
    caption(s, 0.95, 1.7 + h + 0.2, 6.9, 'Three fictional quotes, entered by hand. Not lender offers.')
    rows = [('16.59%', 'Bank term loan, 13.5% reducing. Best match.', TEAL),
            ('17.74%', '“9% flat” NBFI offer. The real annual cost.', AMBER),
            ('15.79%', 'Supplier finance. Cheapest, but too small for the gap.', ROSE)]
    for i, (big, small, c) in enumerate(rows):
        y = 1.75 + i * 1.5
        box(s, 8.4, y, 4.23, 1.35, fill=CARD, line=LINE)
        text(s, 8.65, y + 0.1, 1.9, 0.7, big, size=30, bold=True, color=c)
        text(s, 8.65, y + 0.68, 3.8, 0.65, small, size=16, color=MUTED, line=1.1)
    text(s, 8.4, 6.3, 4.23, 0.5, 'Exact schedules · effective annual rate · cash-flow fit', size=14, color=DIM)
    footer(s, 7, logo_path=LOGO)

    # ---------------- 8 SAFETY ----------------
    s = new_slide(NOTES[8])
    header(s, 8, '06 / Safety as a feature', 'The model can suggest. It cannot approve.')
    steps = [('01', 'SOURCE', 'Invoice + payee'), ('02', 'EXACT MATH', 'Amount + reserve'), ('03', 'AI PROPOSES', 'Typed tools only'), ('04', 'HUMAN APPROVES', 'Other account'), ('05', 'LEDGER + AUDIT', 'Once, signed')]
    for i, (n, t, d) in enumerate(steps):
        x = 0.7 + i * 2.43
        hot = (i == 3)
        box(s, x, 1.7, 2.25, 1.3, fill=('123A3A' if hot else CARD), line=(TEAL if hot else LINE), line_w=1.5 if hot else 1)
        text(s, x + 0.15, 1.78, 1.9, 0.35, n, size=16, bold=True, color=TEAL)
        text(s, x + 0.15, 2.1, 2.05, 0.4, t, size=14, bold=True)
        text(s, x + 0.15, 2.5, 2.05, 0.4, d, size=14, color=MUTED)
        if i < 4: chevron(s, x + 2.27, 2.22, 0.14, 0.26)
    hb = framed_pic(s, 'duplicate_banner.png', None, 0.95, 3.5, 7.0, 's8_dup', 'Warning banner: this invoice may be a duplicate')
    caption(s, 0.95, 3.5 + hb + 0.1, 7.0, 'A resent invoice with an “ignore duplicate checks” memo is paused.')
    ha = framed_pic(s, 'approvals_panel.png', None, 0.95, 4.4, 6.0, 's8_appr', 'Approvals panel: payment waiting for a second person')
    chips = ['NO BANK CREDENTIALS', 'NO AI PAYMENT EXECUTION', 'NO SELF-APPROVAL']
    for i, t in enumerate(chips):
        pill(s, 8.5, 3.55 + i * 0.8, 4.13, 0.6, t, color=LIME, size=16)
    text(s, 8.5, 6.0, 4.13, 0.9, 'Approving records a posting in the books. Capzoryx never sends a bank transfer.', size=15, color=MUTED, line=1.1)
    footer(s, 8, logo_path=LOGO)

    # ---------------- 9 BUILT FOR REAL USE ----------------
    s = new_slide(NOTES[9])
    header(s, 9, '07 / Built for real use', 'Built for real use, not just a demo.')
    tiles = [('Accounts', 'Two-step sign-in with an authenticator app'), ('Sharing with roles', 'Approver or viewer, by invitation link'),
             ('37 languages', 'Right-to-left layouts included'), ('Photo, chat, form', 'Every draft is checked by you'),
             ('PDF report', 'Plus a full backup file'), ('150+ currencies', 'Live conversion on the overview')]
    for i, (t, d) in enumerate(tiles):
        x = 0.7 + (i % 2) * 3.3; y = 1.75 + (i // 2) * 1.7
        box(s, x, y, 3.15, 1.5, fill=CARD, line=LINE)
        box(s, x + 0.22, y + 0.28, 0.08, 0.38, fill=[TEAL, BLUE, LIME, AMBER, TEAL, BLUE][i], radius=0.04)
        text(s, x + 0.45, y + 0.2, 2.6, 0.5, t, size=20, bold=True)
        text(s, x + 0.25, y + 0.78, 2.75, 0.7, d, size=16, color=MUTED, line=1.08)
    hz = framed_pic(s, 'zh_overview.png', (0, 0, 2560, 1500), 7.6, 1.75, 3.3, 's9_zh', 'The Overview screen in Simplified Chinese')
    caption(s, 7.6, 1.75 + hz + 0.1, 3.3, '简体中文')
    ha = framed_pic(s, 'ar_overview.png', (0, 0, 2560, 1500), 7.6, 4.35, 3.3, 's9_ar', 'The Overview screen in Arabic, laid out right to left')
    caption(s, 7.6, 4.35 + ha + 0.1, 3.3, 'العربية · right to left')
    hp = framed_pic(s, 'phone_overview.png', None, 11.0, 1.75, 1.65, 's9_phone', 'The Overview on a phone-size screen')
    caption(s, 11.0, 1.75 + hp + 0.1, 1.7, 'Phone')
    footer(s, 9, logo_path=LOGO)

    # ---------------- 10 ASSISTANT ----------------
    s = new_slide(NOTES[10])
    header(s, 10, '08 / Local-first intelligence', 'Intelligent assistance, with permission built in.')
    h = framed_pic(s, 'assistant.png', (500, 340, 2480, 1650), 0.95, 1.7, 6.9, 's10_assistant', 'The Assistant answering a balance question and a loan question on the device')
    caption(s, 0.95, 1.7 + h + 0.2, 6.9, '“Answers on your device” · figures come from your own records.')
    pts = [('LOCAL FIRST', 'Balance, bills and how-to questions are answered on the device.', TEAL),
           ('CONSENT GATE', 'Optional online help asks before anything is shared.', BLUE),
           ('OFF-TOPIC STAYS OFF', '25 of 25 off-topic test prompts were declined, none sent online.', LIME)]
    for i, (t, d, c) in enumerate(pts):
        y = 1.75 + i * 1.55
        box(s, 8.4, y, 4.23, 1.35, fill=CARD, line=LINE)
        box(s, 8.4, y + 0.2, 0.09, 0.95, fill=c, radius=0.04)
        text(s, 8.7, y + 0.14, 3.8, 0.4, t, size=17, bold=True, color=c)
        text(s, 8.7, y + 0.58, 3.8, 0.75, d, size=16, color=MUTED, line=1.1)
    footer(s, 10, logo_path=LOGO)

    # ---------------- 11 ARCHITECTURE ----------------
    s = new_slide(NOTES[11])
    header(s, 11, '09 / How it works', 'Trust boundaries are part of the architecture.', 'Financial authority stays in the policy engine, not in the AI model.')
    cols = [('FRONTEND', TEAL, 'React 19 · TypeScript', 'Vercel', 'Entry, dashboards, chat, consent'),
            ('POLICY + FINANCE API', BLUE, 'FastAPI · Pydantic', 'Render', 'Exact money, roles, reserve, approvals'),
            ('PERSISTENT STATE', LIME, 'Turso / libSQL', 'SQLite locally', 'Ledger, journal, signed audit chain')]
    for i, (t, c, a, b, d) in enumerate(cols):
        x = 0.7 + i * 4.1
        box(s, x, 2.35, 3.65, 2.6, fill=CARD, line=LINE)
        box(s, x + 0.28, 2.65, 0.09, 0.45, fill=c, radius=0.04)
        text(s, x + 0.55, 2.62, 3.0, 0.5, t, size=17, bold=True)
        text(s, x + 0.3, 3.3, 3.2, 0.4, a, size=17, bold=True, color=c)
        text(s, x + 0.3, 3.7, 3.2, 0.4, b, size=16, color=MUTED)
        text(s, x + 0.3, 4.1, 3.2, 0.75, d, size=16, color=MUTED, line=1.05)
        if i < 2: chevron(s, x + 3.75, 3.35, 0.25, 0.4)
    box(s, 3.2, 5.2, 6.9, 0.95, fill=CARD2, line=TEAL, line_w=1.25)
    text(s, 3.2, 5.2, 6.9, 0.95, [[('OPTIONAL CLOUD AI  ·  EXPLANATIONS ONLY', {'bold': True, 'size': 16})], [('Typed tools · consent first · no approve or execute tool', {'size': 16, 'color': MUTED})]], align='c', anchor='m', line=1.15)
    text(s, 0.7, 6.3, 11.93, 0.6, 'Server-derived identity · exact integer money · append-only ledger · strict CSP · scrypt-hashed passwords', size=16, color=MUTED, line=1.1)
    footer(s, 11, logo_path=LOGO)

    # ---------------- 12 EVIDENCE ----------------
    s = new_slide(NOTES[12])
    header(s, 12, '10 / Technical evidence', 'We test the controls, and disclose the limits.', 'Internal verification, re-run on 20 October 2026. Not independent certification.')
    stats = [('490', 'backend tests', 'Roles, money, approvals; run in CI', TEAL),
             ('60 / 60', 'black-box probes', 'Auth, inputs, sessions, isolation', TEAL),
             ('14,280', 'randomized scenarios', 'Financing engine: 119 seeds × 120 rounds', TEAL),
             ('73.7%', 'fresh-prompt accuracy', '70 of 95 unseen prompts, run once', AMBER)]
    for i, (big, lab, d, c) in enumerate(stats):
        x = 0.7 + i * 3.0325
        box(s, x, 2.15, 2.8325, 2.95, fill=CARD, line=LINE)
        text(s, x + 0.25, 2.35, 2.5, 0.8, big, size=36, bold=True, color=c)
        text(s, x + 0.25, 3.2, 2.4, 0.75, lab, size=18, bold=True, line=1.05)
        text(s, x + 0.25, 3.98, 2.4, 1.0, d, size=15, color=MUTED, line=1.1)
    box(s, 0.7, 5.3, 11.93, 1.2, fill=CARD2, line=LIME, line_w=1.25)
    text(s, 1.0, 5.4, 3.5, 0.3, 'WHAT WE DO NOT CLAIM', size=14, bold=True, color=LIME, spc=120)
    text(s, 1.0, 5.75, 11.4, 0.7, 'No bank connection · Lender quotes are user-entered · Forecasts are scenarios, not predictions · Decision support, not autonomy', size=17, bold=True, line=1.15)
    text(s, 0.7, 6.6, 11.93, 0.3, 'Sources: docs/SECURITY_SELF_ASSESSMENT.md · docs/LOCAL_ASSISTANT_EVALUATION.md · deck_build/verify_claims.py', size=14, color=DIM)
    footer(s, 12, logo_path=LOGO)

    # ---------------- 13 CLOSE ----------------
    s = new_slide(NOTES[13])
    picture(s, LOGO, 0.8, 0.7, 0.9, 0.9)
    text(s, 1.85, 0.78, 6, 0.8, [[('Capzoryx ', {}), ('Copilot', {'color': TEAL})]], size=34, bold=True, anchor='m')
    text(s, 0.8, 2.0, 7.2, 1.0, 'AI should improve', size=48, bold=True, line=1.0)
    text(s, 0.8, 2.85, 7.2, 1.0, 'financial judgment.', size=48, bold=True, color=TEAL, line=1.0)
    text(s, 0.8, 3.85, 7.2, 0.6, 'Not replace human control.', size=28, bold=True)
    box(s, 0.8, 4.75, 6.9, 1.35, fill=CARD, line=LINE)
    text(s, 1.05, 4.85, 6.4, 0.3, 'NEXT, WHEN GOVERNANCE IS READY', size=14, bold=True, color=LIME, spc=120)
    text(s, 1.05, 5.2, 6.4, 0.9, 'Bank and wallet statement import · bill reminders · validated integrations and a security review', size=18, line=1.15)
    text(s, 0.8, 6.25, 7.2, 0.6, 'A decision-support prototype, not an autonomous bank.', size=15, color=MUTED, line=1.1)
    box(s, 8.75, 1.15, 3.9, 4.55, fill=WHITE, radius=0.22)
    picture(s, QR, 9.1, 1.45, 3.2, 3.2, link=LIVE_URL)
    text(s, 8.75, 4.78, 3.9, 0.4, 'SCAN FOR THE LIVE DEMO', size=16, bold=True, color=BG, align='c')
    text(s, 8.75, 5.15, 3.9, 0.4, 'capzoryx-copilot.vercel.app', size=15, bold=True, color='0B6F5C', align='c', link=LIVE_URL)
    text(s, 8.4, 5.9, 4.6, 0.35, 'github.com/Pranto-404/capzoryx-copilot', size=15, color=TEAL, align='c', link=REPO_URL)
    text(s, 8.4, 6.3, 4.6, 0.35, 'TEAM CAPZORYX  ·  BANGLADESH', size=15, bold=True, color=MUTED, align='c')
    footer(s, 13, 'The future of financial AI is verifiable', LOGO)


def main():
    notes_path = HERE / 'speaker_notes_source.py'
    ns = {}; exec(notes_path.read_text(encoding='utf-8'), ns)
    NOTES.update(ns['NOTES'])
    build()
    prs.core_properties.title = 'Capzoryx Copilot: 10-minute competition pitch'
    prs.core_properties.author = 'Team Capzoryx'
    prs.core_properties.subject = '2026 Shenzhen International FinTechathon, International Track, Topic E: SME Finance Copilot'
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pptx = OUT_DIR / 'Capzoryx_Copilot_Pitch_Deck_10min.pptx'; prs.save(pptx)
    lines = ['Capzoryx Copilot: speaker notes for the 10-minute pitch', f'Timings are a guide; the total is {sum(ns["TIMING"].values()) // 60}:{sum(ns["TIMING"].values()) % 60:02d} at a calm pace.', '']
    total = 0
    for i in range(1, N_SLIDES + 1):
        sec, body = ns['TIMING'][i], ns['NOTES'][i]
        total += sec
        lines += [f'SLIDE {i}  ({sec // 60}:{sec % 60:02d})  ' + ns['TITLES'][i], body, '']
    lines.append(f'Total: {total // 60}:{total % 60:02d}')
    (OUT_DIR / 'Capzoryx_Copilot_Pitch_Deck_speaker_notes.txt').write_text('\n'.join(lines), encoding='utf-8')
    print('saved', pptx, 'total seconds', total)


main()
