# CROMO submission video: the final script

**Length 2:44** · 1920×1080, 30 fps, H.264 · loudness −14 LUFS · English captions burned in and as a separate
`.srt` file. Credits and licences: `VIDEO_CREDITS.md`. Upload text: `YOUTUBE.md`.

## How it was made
- **Screen recordings** are the real app, recorded frame by frame in headless Chrome at 1920×1080. The app ran in
  live Token Factory mode on a local PC, with the results recorded on AMD:
  - the ALK-04 dig is the **replay of the run recorded on AMD** ("Replay AMD run"), slowed with `?pace=2.4` so the
    hops can be read; the blue "Replay of a run recorded on AMD …" label is on screen, and the narration says so;
  - SOL-02 shows its stored AMD verdict ("Computed on the AMD Token Factory by Gemma-4-31B-IT …");
  - "Before you change" and the Tripwire answers are the **stored answers computed on AMD** (marked "stored answer
    from …" in the app and in the on-screen label);
  - the trial approval is a real decision sent through the Evolus workflow; the film cuts from the click to the
    decision Evolus recorded about 50 s later.
- **Illustrations** (the story, the problem, the results and the close) are original SVG/HTML, animated in code.
- **Narration:** the AssemblyAI Voice Agent API (voice "charles"), every line checked word for word with AssemblyAI
  speech-to-text; captions are timed from the AssemblyAI word timestamps.
- **Music:** an original ambient score synthesised in numpy (CC0), ducked under the voice.
- Every number comes from `data/recorded/` (AMD run of 16–17 Oct 2026) or the app's own data. Nothing on screen shows a key,
  a private URL, an IP address, an email address or a file path.

## The film

| Time | Screen | Narration |
|---|---|---|
| 0:00–0:04 | Title card: "Every factory runs on reasons nobody remembers. CROMO finds them." | (music) |
| 0:03–0:33 | Illustrated: the paint factory, the jelly batch rescued with ammonium chloride, years later the salt still added, the book card (Primo Levi, The Periodic Table) | “Italy, just after the war. A young chemist starts work at a paint factory.” “A batch of anti-rust paint keeps turning to jelly. He traces it to one bad delivery of pigment, and rescues it by adding a simple salt: ammonium chloride.” “Years later, that pigment is long gone. But the factory still adds the salt to every batch. Nobody remembers why.” “Primo Levi tells this story in The Periodic Table.” |
| 0:32–0:46 | Illustrated: a row of process steps, one waste and one safeguard, then the archive shelves | “Every factory is full of steps like this. Some are pure waste. Some are the only thing standing between a batch and a fire.” “From the outside, they look the same. And the reasons are buried in decades of paperwork.” |
| 0:46–1:01 | App, home page: the hero metrics, then the Fossil Map; the Fossil and Fence legend chips highlight the tiles | “CROMO reads a plant's own archive, and works out why every step exists.” “Orange steps are fossils: their reason is gone, and they cost money every batch. Green steps are fences: they look pointless, but they protect you.” |
| 1:01–1:29 | Ctrl K, "why do we add ammonium chloride", ALK-04; Replay AMD run: the Why-Trail fills hop by hop; FOSSIL verdict, €15,713 a year; Key evidence; the scanned lab report with the cited passage | “Ask why about any step.” “CROMO doesn't chat. It digs. What you see is a replay of a run recorded on AMD. Google's open Gemma model reads old recipes, follows the change request from nineteen ninety-five, and the lab report, then checks whether the reason still holds.” “Verdict: fossil, with strong evidence. Over fifteen thousand euros a year. Every claim is a quote, checked against the original page.” |
| 1:28–1:39 | SOL-02 Bond and earth: FENCE, the 1997 static-spark near-miss, the legal requirement | “Now the opposite. Bonding and earthing a drum looks like paperwork. But CROMO finds a static spark incident and a legal requirement. It's a fence.” |
| 1:39–1:49 | What if → Change a step: "Shorten the cooling hold" → BLOCKED (stored AMD answer) | “Before anyone changes a step, ask CROMO first. Shortening this cooling hold is blocked: there was a flash fire, and the solvent is still in use.” |
| 1:49–2:00 | What if → Change the plant: cheaper epoxy resin → a fossil is needed again (stored AMD answer) | “When the plant changes, CROMO warns you too. A cheaper epoxy resin brings back an old crystallisation problem, so a step we called a fossil is needed again.” |
| 1:59–2:08 | Trials: the engineer approves the safe trial for ALK-04; cut to the decision recorded by the Evolus workflow and the trial marked Approved | “And CROMO never deletes anything. It drafts a safe trial, and an engineer approves it through an Evolus workflow.” |
| 2:07–2:19 | System page: Gemma 4 on the AMD Token Factory, the measured numbers, the model comparison | “Every model call runs on AMD, through the AMD Token Factory. Gemma reads scanned, faxed and handwritten pages, and does the reasoning. Rules, not the model, decide what may be removed.” |
| 2:19–2:31 | Illustrated: fences found 89% vs 56%, fences called fossils 0 vs 1, verdicts right 80% vs 65% | “On a synthetic plant with a hidden answer key, CROMO found eighty-nine percent of the fences, and called none of them a fossil. A rule-based baseline found fifty-six percent.” |
| 2:30–2:44 | Who it's for, €305,298 a year of fossils, 16 fences; title card with the repository and demo URLs | “For process engineers and safety managers, CROMO turns forgotten paperwork into money saved, and accidents avoided.” “CROMO. Find the waste. Keep the fences.” |


## Where each number comes from
| Number in the film | Value | Source, and where it is on screen |
|---|---|---|
| ALK-04 cost and evidence | €15,713 a year ("over fifteen thousand euros"), strong | `data/recorded/runs/ALK-04.json`; the ALK-04 verdict card |
| Fossils found, fences kept | €305,298 a year, 16 steps kept as fences | the app's home page metrics (AMD verdicts); the close card |
| Fences found | 89% (baseline 56%) | `data/recorded/eval_amd.json` / `eval_fixture.json`; System page and the results card |
| Fences called fossils | 0 (baseline 1) | same files; the results card |
| Verdicts right | 80% (baseline 65%) | same files; the results card |
| OCR error rate | Gemma 2.2% CER | `data/recorded/ocr_comparison.json`; System → *Which model reads the archive best?* |

## Judging criteria, where they show
- **The idea by 0:20:** the opening card at 0:00–0:04 ("Every factory runs on reasons nobody remembers. CROMO finds
  them."), then the Levi story makes it concrete.
- **Application of technology:** the Why-Trail replay (Gemma 4 on the AMD Token Factory), the scanned page with the
  verified quote, the System page (where every model call runs, measured numbers, the model comparison).
- **Presentation:** one story (a fossil step in a real paint factory) carried from the cold open to the app.
- **Business value:** € per year of fossils, fences protected from "optimisation", every change gated by a person
  through Evolus; who it is for.
- **Originality:** asking *why* a step exists, rather than optimising it, with fences that may never be removed.
