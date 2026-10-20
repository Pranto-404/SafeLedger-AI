# Pitch deck build (Capzoryx Copilot, 10-minute talk)

Outputs: `submission/Capzoryx_Copilot_Pitch_Deck_10min.pdf` (16:9, Inter embedded, live links), the editable `.pptx` and the speaker notes next to it.

| File | Purpose |
| --- | --- |
| `capture_screens.py` | Takes the real screenshots from a **local** copy of the app (throwaway database, sample business). Never run it against the live site. |
| `shots/` | The screenshots the deck uses (1280-wide desktop at 2x, one 390-wide phone shot at 3x). Only transient banners and the floating Assistant button are hidden; no recovery key or personal data is on screen. |
| `build_deck.py` | Builds the PPTX (python-pptx) and the speaker-notes text file. The logo is rendered from `web/public/favicon.svg`; the QR code is generated and decoded back to `https://capzoryx-copilot.vercel.app`. |
| `speaker_notes_source.py` | Speaker notes and timings (about 9 minutes 35 seconds in total). |
| `check_fit.py` | Static check with real Inter metrics: text that does not fit its box, text under 14 pt, shapes outside the slide. |
| `render_pdf.py` | PPTX to PDF without Office: lays the same geometry out as HTML and prints it with Chrome (fonts embedded, hyperlinks kept). |
| `verify_claims.py` | Re-derives the numbers on the evidence slide (test count, 14,280 randomized financing scenarios, languages, currencies). |
| `fonts/` | Inter Regular and Bold (SIL Open Font License). Install them before opening the PPTX, otherwise PowerPoint substitutes another font. |

```sh
pip install python-pptx pillow segno opencv-python-headless playwright
python submission/deck_build/build_deck.py          # writes .pptx and notes to the parent of the repo folder
python submission/deck_build/check_fit.py <deck.pptx> submission/deck_build/fonts
python submission/deck_build/render_pdf.py <deck.pptx> <deck.pdf>
```

Numbers on the slides and where they come from: 490 backend tests (`pytest --collect-only`), 60 of 60 probe checks (`scripts/security_probe.py`, local server), 14,280 randomized scenarios (`verify_claims.py`, 119 seeds x 120 rounds of `api/tests/test_financing_fuzz.py`), 73.7% = 70/95 on `heldout_eval_v3` (`docs/LOCAL_ASSISTANT_EVALUATION.md`, `scripts/evaluate_local_assistant.cjs`), 37 languages (`web/public/locales` plus English), 150+ currencies (the picker lists 155).
