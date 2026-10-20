# Capzoryx Copilot: how to record the demo video (under 5 minutes)

Target length: **4 minutes 30 seconds** (the limit is 5:00, so you have a safety margin). Record in segments, then join them.

## 1. Before you record (15 minutes)

1. **Warm up the server.** Open https://capzoryx-copilot.vercel.app/api/health once. It should answer in about a second (the monitor keeps it awake).
2. **Make a clean account.** Use a new username such as `demo_judge`, a strong password you do not mind showing as dots, and no real email. Do the sign-up on camera, but keep the password hidden (do not press Show).
3. **Screen setup.** 1920×1080, browser at 100% to 110% zoom, a private/incognito window, bookmarks bar hidden, other tabs closed, notifications switched off (Windows: Focus assist on). Use the light or dark theme, whichever looks clearer on your screen, and keep it the same throughout.
4. **Tools (all free).** OBS Studio (record 1920×1080, 30 fps, MP4 or MKV, microphone on) or Windows Game Bar (Win+Alt+R). For joining and subtitles: Clipchamp (built into Windows), CapCut or DaVinci Resolve.
5. **Sound.** A quiet room, microphone close to your mouth, speak slowly. Record the narration while you click, or record the screen first and the voice afterwards. Clear audio matters more than anything else.
6. **Do a dry run once.** Time it. If you are above 4:45, shorten the parts marked optional.
7. **Never show:** passwords, API keys, the Render or Vercel dashboards, your email inbox, the UptimeRobot page.

## 2. Shot list with narration (about 4:30)

| Time | What is on screen | What you say (short and plain) |
| --- | --- | --- |
| 0:00 to 0:20 | Deck slide 1, then the live landing page | "Small businesses run out of cash even when they are profitable. Capzoryx Copilot is an AI finance copilot for them. It helps them decide, but it never holds or moves their money." |
| 0:20 to 0:45 | Landing page: let the logo animation finish, scroll a little, switch the language to Chinese and back to English | "It works in 37 languages, including right-to-left ones, and in over 150 currencies. It is free to use." |
| 0:45 to 1:05 | Create the account (type username and password, keep it hidden), land on the empty Overview | "Every new workspace starts empty, with no preloaded balances. For this demo I will load a fictional exporter with one click." |
| 1:05 to 1:30 | Press **Try a sample business** | "This loads a fictional exporter: 150,000 taka in the bank, a big supplier bill due in six days, and a customer payment that only arrives on day 25." |
| 1:30 to 2:05 | Overview: balance with the approximate USD value, the 7 and 30 day outlook, the reserve warning. Open **Cash flow** and move the delay setting | "The outlook shows cash falling short on day six, before the customer pays. The numbers are exact and deterministic. There is no guessing by the AI. I can test a late customer payment and see the effect." |
| 2:05 to 2:40 | **Add records:** type "I paid Rahman 5000 for freight yesterday" and press **Read it**; show the draft; press **Add**. (Optional: show a photo of a bill if the model is available) | "I can just type what happened, or photograph a bill. The app turns it into a draft that I check. Nothing is saved until I confirm." |
| 2:40 to 3:20 | **Loans:** enter the three offers from deck slide 6 and press **Match quotes to my cash flow** | "I enter the offers I received. The app computes the true yearly cost, not just the advertised rate, and tests each offer against my own cash flow. The cheapest-looking rate is not always the best fit." |
| 3:20 to 3:55 | **Invoices:** point at the flagged duplicate invoice and its odd note. Press **Prepare payment** on a real bill, then open **Approvals** | "The app flags a possible duplicate, and it ignores the note that tells it to pay immediately. A payment can only be recorded after a different person approves it. The AI can suggest, it cannot approve." |
| 3:55 to 4:15 | **Assistant:** ask "How does this website work?" then "Which bills are overdue?" | "Simple questions are answered on the device, without sending data anywhere. The online model is only used with permission." |
| 4:15 to 4:30 | **Settings:** show two-step sign-in and sharing, then press **Download PDF**; end on the live address | "There is two-step sign-in, sharing with roles, and a PDF report. Next we plan bank and wallet statement import. The product is a decision-support tool, not an autonomous bank. Thank you." |

## 3. Tips that save time

- Record each row as its own clip. If you stumble, redo only that clip.
- Move the mouse slowly and pause for one second before each click so viewers can follow.
- Add short on-screen captions for each section (Clipchamp and CapCut both do this) and turn on subtitles; judges may watch without sound.
- Keep the sample numbers on screen long enough to read them (about three seconds).
- Do **not** run the demo in a workspace that already has real records; the sample button only appears on an empty workspace.
- If the photo scan is slow or the cloud model is busy, skip it and say "photo reading uses the optional online model" instead of waiting on camera.

## 4. Export and share

1. Export as **MP4 (H.264), 1080p**. Aim for under 100 MB.
2. Upload to **YouTube as "Unlisted"** or to **Google Drive with "Anyone with the link can view"**. Open the link in a private window to check that it plays without signing in.
3. Put the link in `00_README_LINKS.txt` (the "Demo video" line) and in your email. Include the team name **Capzoryx** in the video title, for example "Capzoryx Copilot demo (4:30)".
