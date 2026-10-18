# CROMO submission video: the final script (v2)

**v2: `CROMO_submission_v2.mp4`, length 3:30 (209.7 s)** · 1920×1080, 30 fps, H.264 · loudness −14 LUFS · English
captions burned in and as a separate `CROMO_submission_v2.srt`. Credits and licences: `VIDEO_CREDITS.md`. Upload text:
`YOUTUBE.md`.

v2 adds one 45-second scene after the problem and before the product: a real, officially investigated case
(Williams Olefins Plant, Geismar, Louisiana, 2013, from the US Chemical Safety Board), how the reason behind a
safeguard gets lost, the US management-of-change rule (OSHA 29 CFR 1910.119(l)), and fossil versus fence. Everything
else is the v1 film unchanged, shifted by 45.3 s (v1, 2:44, stays as `CROMO_submission.mp4`). The film never says or
implies that CROMO would have prevented any real incident.

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
- **Illustrations** (the story, the problem, the real case, the results and the close) are original SVG/HTML, animated
  in code. The real-case scene reuses the film's template (palette, grain, vignette, camera push, card style, CROMO UI
  tokens) and was rendered at the same 2880×1620 as the other illustrations. v2 reuses v1's encoded frames unchanged
  up to 0:43.6 and from 1:37.2, joined at v1 keyframes; only 0:43.6–1:37.2 was re-encoded, with v1's encoder settings.
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
| 0:46–1:04 | **New in v2.** Illustrated: “Geismar, Louisiana · 2013”; a reboiler and its relief valve (the safe path glows green); a valve slides onto the pipe with a tag “Change · valves added · not properly reviewed”; the valve closes (“Cut off”), heat under the vessel, the gauge climbs into the red, a soft flash (no fire, no people shown); a quiet card “Two workers were killed. 167 others reported injuries.” Source note: US Chemical Safety Board (CSB), final case study, Williams Olefins Plant, 2016 | “This is not only a story. In 2013, at a chemical plant in Louisiana, a poorly reviewed change let a vessel be cut off from its relief valve.” “One day, it was cut off and heated. The pressure had nowhere to go. The vessel ruptured, and two workers were killed.” |
| 1:04–1:13 | Illustrated, “How a reason gets lost”: a safeguard card with its reason, an anonymous engineer walks away, papers scatter along a 30-year timeline, the reason fades, the step is still there: “Why is this here?” | “The reason behind a safeguard is easy to lose. People move on. Paperwork scatters across decades. And nobody remembers why it's there.” |
| 1:12–1:22 | CROMO UI style: “Before a change, check its basis.” A checklist paraphrasing four of the five considerations in OSHA 29 CFR 1910.119(l)(2) (technical basis, impact on safety and health, operating procedures, authorisation); then an “AI optimiser” card whose proposed changes pile up faster and faster. Source note: US OSHA, 29 CFR 1910.119(l), Management of change | “In the US, plants that handle highly hazardous chemicals must check the technical basis of a change before making it. And now, AI optimisers propose changes too.” |
| 1:22–1:32 | CROMO UI style, “Fossil, or fence?”: two identical step cards are revealed as FOSSIL (reason gone, costs money every batch) and FENCE (looks pointless, prevents an accident); a “remove step 5” action heads for the fence, a red ring, “The dangerous mistake: a safeguard marked as waste.” | “So before any change, ask: is this step a fossil, or a fence? Mistake a fence for a fossil, and the old accident can come back.” |
| 1:31–1:47 | App, home page: the hero metrics, then the Fossil Map; the Fossil and Fence legend chips highlight the tiles | “CROMO reads a plant's own archive, and works out why every step exists.” “Orange steps are fossils: their reason is gone, and they cost money every batch. Green steps are fences: they look pointless, but they protect you.” |
| 1:46–2:14 | Ctrl K, "why do we add ammonium chloride", ALK-04; Replay AMD run: the Why-Trail fills hop by hop; FOSSIL verdict, €15,713 a year; Key evidence; the scanned lab report with the cited passage | “Ask why about any step.” “CROMO doesn't chat. It digs. What you see is a replay of a run recorded on AMD. Google's open Gemma model reads old recipes, follows the change request from nineteen ninety-five, and the lab report, then checks whether the reason still holds.” “Verdict: fossil, with strong evidence. Over fifteen thousand euros a year. Every claim is a quote, checked against the original page.” |
| 2:13–2:25 | SOL-02 Bond and earth: FENCE, the 1997 static-spark near-miss, the legal requirement | “Now the opposite. Bonding and earthing a drum looks like paperwork. But CROMO finds a static spark incident and a legal requirement. It's a fence.” |
| 2:24–2:35 | What if → Change a step: "Shorten the cooling hold" → BLOCKED (stored AMD answer) | “Before anyone changes a step, ask CROMO first. Shortening this cooling hold is blocked: there was a flash fire, and the solvent is still in use.” |
| 2:34–2:46 | What if → Change the plant: cheaper epoxy resin → a fossil is needed again (stored AMD answer) | “When the plant changes, CROMO warns you too. A cheaper epoxy resin brings back an old crystallisation problem, so a step we called a fossil is needed again.” |
| 2:45–2:53 | Trials: the engineer approves the safe trial for ALK-04; cut to the decision recorded by the Evolus workflow and the trial marked Approved | “And CROMO never deletes anything. It drafts a safe trial, and an engineer approves it through an Evolus workflow.” |
| 2:52–3:05 | System page: Gemma 4 on the AMD Token Factory, the measured numbers, the model comparison | “Every model call runs on AMD, through the AMD Token Factory. Gemma reads scanned, faxed and handwritten pages, and does the reasoning. Rules, not the model, decide what may be removed.” |
| 3:04–3:17 | Illustrated: fences found 89% vs 56%, fences called fossils 0 vs 1, verdicts right 80% vs 65% | “On a synthetic plant with a hidden answer key, CROMO found eighty-nine percent of the fences, and called none of them a fossil. A rule-based baseline found fifty-six percent.” |
| 3:16–3:30 | Who it's for, €305,298 a year of fossils, 16 fences; title card with the repository and demo URLs | “For process engineers and safety managers, CROMO turns forgotten paperwork into money saved, and accidents avoided.” “CROMO. Find the waste. Keep the fences.” |


## Real-world facts in v2, and their sources
Paraphrased, no quotations; each was checked on the source page on 18 Oct 2026.

| Fact on screen or in the narration | Source |
|---|---|
| 13 June 2013, Williams Olefins Plant, Geismar, Louisiana: a reboiler, offline and isolated from its pressure relief device, was heated during non-routine work; the pressure rose and the shell ruptured (a BLEVE and fire) | US Chemical Safety Board (CSB), news release of its final case study, 19 Oct 2016: csb.gov/csb-releases-final-case-study-into-2013-explosion-and-fire-at-williams-olefins-plant-in-geismar-louisiana/ |
| Two workers were killed; 167 others reported injuries | same CSB release |
| The CSB found the plant failed to appropriately manage or effectively review two significant changes, including block valves that could isolate the reboiler from its relief device, within process safety management gaps over the 12 years before the incident ("a poorly reviewed change") | same CSB release |
| Under OSHA's Process Safety Management standard, the employer's management-of-change procedures must address, before any change to process chemicals, technology, equipment or procedures: the technical basis, the impact on safety and health, modifications to operating procedures, the time period and authorisation (the film shows four of the five) | US OSHA, 29 CFR 1910.119(l): osha.gov/laws-regs/regulations/standardnumber/1910/1910.119 |

The scene illustrates the reboiler, the valves and the timeline schematically; it shows no fire, no people involved in
the incident and no likeness of anyone. The step cards ("add the salt", "earth the drum") and the optimiser's proposals
belong to CROMO's fictional plant. Nothing in the film says that CROMO would have prevented the incident.

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
- **The problem is real (v2):** 0:46–1:32, an officially investigated incident and the US management-of-change rule,
  each with a source note on screen, then fossil versus fence.
- **The idea by 0:20:** the opening card at 0:00–0:04 ("Every factory runs on reasons nobody remembers. CROMO finds
  them."), then the Levi story makes it concrete.
- **Application of technology:** the Why-Trail replay (Gemma 4 on the AMD Token Factory), the scanned page with the
  verified quote, the System page (where every model call runs, measured numbers, the model comparison).
- **Presentation:** one story (a fossil step in a real paint factory) carried from the cold open to the app.
- **Business value:** € per year of fossils, fences protected from "optimisation", every change gated by a person
  through Evolus; who it is for.
- **Originality:** asking *why* a step exists, rather than optimising it, with fences that may never be removed.
