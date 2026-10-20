"""Captures the real app screenshots used in the pitch deck from a LOCAL copy of the app (never the live site).

Start a local backend with a throwaway database and the dev server first (see README, "Run and verify locally"):
    SAFELEDGER_DB=<temp file> SAFELEDGER_SIGNING_KEY=<64 hex, throwaway> python -m uvicorn api.app.main:app --port 8000
    cd web && npm run dev -- --port 5173 --strictPort
then:  python submission/deck_build/capture_screens.py http://127.0.0.1:5173 submission/deck_build/shots
Needs: pip install playwright (uses the installed Chrome). It signs up a throwaway account, loads the built-in
"Try a sample business", types the three sample lender quotes and prepares one payment. Only transient banners and the
floating Assistant button are hidden so each frame shows one idea; no recovery key or personal data is ever on screen.
"""
import asyncio, secrets, sys
from pathlib import Path
from playwright.async_api import async_playwright

URL = (sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5173').rstrip('/') + '/'
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else 'shots'); OUT.mkdir(parents=True, exist_ok=True)
USER = 'sample_owner_' + secrets.token_hex(2)
PASSWORD = 'Tq9-' + secrets.token_urlsafe(12)  # throwaway, local database only

HIDE_JS = """
() => {
  const hide = el => { if (el) el.style.display = 'none'; };
  document.querySelectorAll('.success.banner').forEach(hide);
  document.querySelectorAll('.success,.error').forEach(e => { if (/^(Payment prepared|Records imported|This supplier can)/.test(e.textContent.trim())) hide(e); });
  const first = document.querySelector('main select');
  if (first && first.options.length > 100) hide(first.closest('section,.panel,.card') || first.parentElement.parentElement.parentElement);
  document.querySelectorAll('main .notice').forEach(n => { if (n.querySelector('a,button') && n.textContent.length < 220) hide(n); });
  [...document.querySelectorAll('button')].forEach(b => { if (getComputedStyle(b).position === 'fixed' && /Assistant|助手|المساعد|সহকারী/.test(b.textContent)) b.style.display = 'none'; });
}
"""


async def clean(pg):
    await pg.evaluate(HIDE_JS); await pg.wait_for_timeout(300)


async def dismiss(pg):
    for name in ['I saved it', 'Skip tour']:
        try: await pg.get_by_role('button', name=name).click(timeout=1500)
        except Exception: pass
    await pg.wait_for_timeout(400)


async def nav(pg, label):
    await pg.locator('nav').get_by_text(label, exact=True).first.click(); await pg.wait_for_timeout(1300)


async def shot(pg, name, **kw):
    await clean(pg); await pg.evaluate('window.scrollTo(0,0)')
    await pg.screenshot(path=str(OUT / f'{name}.png'), **kw)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel='chrome')
        # Landing page (fresh visitor): English frame with the animated assistant demo, and Chinese (browser-language start)
        for loc, name, wait in [('en-US', 'landing_en', 3000), ('zh-CN', 'landing_zh', 9000)]:
            c = await b.new_context(viewport={'width': 1280, 'height': 800}, device_scale_factor=2, locale=loc)
            pg = await c.new_page(); await pg.goto(URL); await pg.wait_for_timeout(wait)
            await pg.screenshot(path=str(OUT / f'{name}.png')); await c.close()
        # Sign up (local throwaway account) and load the sample business
        ctx = await b.new_context(viewport={'width': 1280, 'height': 1000}, device_scale_factor=2, locale='en-US')
        pg = await ctx.new_page(); await pg.goto(URL); await pg.wait_for_timeout(2500)
        await pg.get_by_placeholder('letters, numbers, underscore').fill(USER)
        await pg.locator('input[type=password]').first.fill(PASSWORD)
        await pg.get_by_role('button', name='Create my workspace').click(); await pg.wait_for_timeout(3500)
        # The one-time recovery-key dialog (throwaway key) lives only in page memory: a reload drops it, so it is never on a slide.
        await pg.reload(); await pg.wait_for_timeout(2500); await dismiss(pg)
        await pg.get_by_role('button', name='Try a sample business').click(); await pg.wait_for_timeout(3500)
        await nav(pg, 'Overview'); await pg.wait_for_timeout(1500); await shot(pg, 'overview')
        await nav(pg, 'Cash flow'); await pg.wait_for_timeout(1500); await shot(pg, 'cashflow')
        # Add records: typed sentence -> draft the user must confirm
        await nav(pg, 'Add records'); await clean(pg)
        await pg.locator('textarea').first.fill('I paid Rahman 5000 for freight yesterday')
        await pg.get_by_role('button', name='Read it').click(); await pg.wait_for_timeout(2500)
        await shot(pg, 'add_draft')
        await pg.locator('.panel', has_text='Check and add this').last.screenshot(path=str(OUT / 'draft_panel.png'))
        # Loans: the three sample quotes
        await nav(pg, 'Loans')
        quotes = [('Prime Bank SME desk', '400000', '4000', '13.5', 'Per year, on reducing balance', '12', 'months', 'Equal monthly installments'),
                  ('QuickCash NBFI', '400000', '0', '9', 'Flat, for the whole term', '12', 'months', 'Equal monthly installments'),
                  ('Supplier invoice finance', '350000', '1500', '2', 'Flat, for the whole term', '60', 'days', 'One payment at the end')]
        for lender, amt, fee, rate, basis, term, unit, rep in quotes:
            await pg.get_by_label('Lender').fill(lender); await pg.get_by_label('Amount (BDT)').fill(amt)
            await pg.get_by_label('Upfront fees (BDT)').fill(fee); await pg.get_by_label('Quoted rate (%)').fill(rate)
            await pg.get_by_label('Rate basis').select_option(label=basis); await pg.get_by_label('Term length').fill(term)
            await pg.get_by_label('Term unit').select_option(label=unit); await pg.get_by_label('Repayment').select_option(label=rep)
            await pg.get_by_label('Quote source').fill('Sample offer'); await pg.get_by_role('button', name='Add quote').click(); await pg.wait_for_timeout(600)
        await pg.get_by_role('button', name='Match quotes to my cash flow').click(); await pg.wait_for_timeout(2500); await clean(pg)
        res = pg.locator('section,.panel', has=pg.get_by_text('Quotes ranked by cash-flow fit, then total cost')).last
        await res.screenshot(path=str(OUT / 'loans_result.png'))
        # Invoices: allow suppliers, duplicate blocked, one payment prepared
        await nav(pg, 'Invoices'); await clean(pg)
        rows = pg.locator('tbody tr')
        for i in range(await rows.count()):
            r = rows.nth(i)
            await r.locator('summary', has_text='Supplier permission').click()
            await r.get_by_text('Allow payments to this supplier').click(); await pg.wait_for_timeout(700)
        await pg.locator('tbody tr', has_text='DP-1182').first.get_by_role('button', name='Prepare payment').click(); await pg.wait_for_timeout(1500)
        await pg.evaluate('window.scrollTo(0,0)')
        await pg.screenshot(path=str(OUT / 'duplicate_blocked.png'))  # keeps the red "may be a duplicate" banner
        await pg.locator('.error', has_text='may be a duplicate').first.screenshot(path=str(OUT / 'duplicate_banner.png'))
        await pg.locator('tbody tr', has_text='RL-552').first.get_by_role('button', name='Prepare payment').click(); await pg.wait_for_timeout(1500)
        await nav(pg, 'Approvals'); await shot(pg, 'approvals')
        await pg.locator('.panel', has_text='Approve payments').last.screenshot(path=str(OUT / 'approvals_panel.png'))
        await nav(pg, 'Activity'); await shot(pg, 'activity')
        # Assistant: answered on the device from the user's own figures
        await nav(pg, 'Assistant')
        for q in ['What is my balance?', 'Which loan fits my cash flow?']:
            ta = pg.locator('textarea').first; await ta.fill(q); await ta.press('Enter'); await pg.wait_for_timeout(2500)
        await shot(pg, 'assistant')
        # Settings: two-step sign-in and sharing
        await nav(pg, 'Settings')
        for tab, name in [('Password & 2-step', 'settings_2step'), ('Sharing', 'settings_sharing')]:
            await pg.locator('main').get_by_text(tab, exact=True).first.click(); await pg.wait_for_timeout(900); await shot(pg, name)
        # Other languages (Chinese, Arabic right-to-left)
        await nav(pg, 'Overview')
        sel = pg.locator('select', has=pg.locator('option', has_text='简体中文')).last
        await sel.select_option(label='简体中文'); await pg.wait_for_timeout(3000); await shot(pg, 'zh_overview')
        await sel.select_option(label='العربية'); await pg.wait_for_timeout(3000); await shot(pg, 'ar_overview')
        await sel.select_option(label='English'); await pg.wait_for_timeout(1500)
        state = await ctx.storage_state(); await ctx.close()
        # Phone-size shot
        c = await b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True, storage_state=state)
        pg = await c.new_page(); await pg.goto(URL); await pg.wait_for_timeout(3000); await dismiss(pg); await clean(pg)
        await pg.evaluate('window.scrollTo(0, 520)'); await pg.wait_for_timeout(500)
        await pg.screenshot(path=str(OUT / 'phone_overview.png'))
        await b.close()

asyncio.run(main())
