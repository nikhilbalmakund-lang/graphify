# Matric Rewrite HQ

A 25-day study system for the NSC **Mathematics** and **Physical Sciences** rewrite.
Everything is in one page: no account, no login.

## Open it

- **In Claude:** open the published page (link in the chat where it was built). Progress syncs
  between your phone and computer through your Claude account.
- **Anywhere else:** download `index.html` and open it in Chrome, Safari, Firefox or Edge.
  It works from a phone's file manager, a USB stick or any computer. Progress is saved in that
  browser; use **Settings → Copy backup code** to move it to another device.

You need internet for the YouTube videos and the past-paper PDFs; everything else works offline.

## What's inside

| Screen | What it does |
|---|---|
| Today | Day *n* of 25, today's tasks with ticks, catch-up list, progress meters, score charts |
| 25-day plan | Four phases: easy marks first, then core topics, then one full timed paper a day |
| Learn | 26 topics (10 Maths, 9 Physics, 7 Chemistry): 2–5 short videos each, plain-language ideas, definitions, formulas marked *on the sheet* / *memorise*, step-by-step method, memo-style worked examples, common mistakes, practice with answers, and where the topic sits in past papers |
| Past papers | Every November paper 2017–2025 plus the May/June and Feb/March sessions, question paper + memo (+ Maths P2 answer book), a 3-hour exam timer and a score log |
| Drill | Flashcards: Physics and Chemistry definitions, organic families & reactions, chemistry rules, Maths must-knows, geometry reasons |
| Formula sheets | What the Maths information sheet and Physical Sciences data sheets give you, and what you must memorise |
| Exam game plan | Mark targets per question area, exam-room technique, calculator setup, exam-day checklist |
| Focus timer | 25/5 or 50/10 blocks, logged per subject |

## Sources

- Past papers and memos link to the Department of Basic Education's own PDFs. The link list
  comes from the index in [Willemjvr/sa-matric-papers](https://github.com/Willemjvr/sa-matric-papers),
  which scrapes the official DBE listings. Nov 2017 is not in that index: the app links the DBE's
  2017 page and the one Nov 2017 file that could be confirmed.
- Videos are by their YouTube creators; the app only links to them.
- Not affiliated with the DBE.

## Editing

The page is built from `src/`:

```
src/topics_maths.js    Maths topics (content + video ids)
src/topics_physics.js  Physics and Chemistry topics
src/plan.js            the 25-day plan
src/cards.js           flashcard decks
src/sheets.js          formula sheets, mark targets, resources
src/papers.js          generated paper links (tools/make_papers.py)
src/app.js, styles.css the app
```

```bash
python tools/make_papers.py /path/to/sa-matric-papers/index.json   # refresh paper links
python build.py                                                    # rebuild index.html
```
