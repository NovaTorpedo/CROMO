# CROMO demo video script (target 2:45, hard limit 3:00)

**Setup before recording:**
- Light theme; browser at 1920×1080, zoom 100%.
- The app runs live on AMD (header pill "Live on AMD"), with `data\runtime\cromo.db` deleted first so it starts from the
  AMD snapshot. If the GPU or network fails mid-recording, use the recorded replays ("Replay AMD run"); they are
  labelled as replays, which is fine to show.
- Close other tabs. Record with OBS (free): screen plus voice-over. Upload to YouTube as **Unlisted**.
- Tip: open each URL below in its own tab beforehand and click through the tabs in order.

**Placeholders.** Every `[AMD: ...]` is a number you read off the screen after the AMD run (the "Where to read it"
table at the end says where). Never say a number that isn't on screen. If a number is missing (for example a partial
run), drop that clause instead of guessing.

| Time | Screen | Voice-over (read calmly) |
|---|---|---|
| 0:00–0:08 | `#/` home, hero and the coloured "periodic table" | "Every factory runs on reasons nobody remembers." |
| 0:08–0:20 | Slowly move the mouse over the orange tiles, then the teal ones | "CROMO reads thirty years of a plant's own paperwork and works out why every step of every recipe exists. Orange steps are **fossils**: their reason is gone, and they cost money every batch. Teal steps are **fences**: they look pointless, but they protect you." |
| 0:20–0:32 | Point at the three big numbers | "In this synthetic paint plant that's [AMD: € fossils per year] a year of fossils, [AMD: number of fences] fences protected, and every step with no documented reason is sent to a person - never guessed." |
| 0:32–0:40 | Type in the Ask box: *"why do we add ammonium chloride?"* → Enter | "Pick any step. This one is from Primo Levi's *The Periodic Table*: a fix for one bad batch of pigment, still added twenty years later." |
| 0:40–1:15 | Investigation streams live: verdict card "DIGGING", the progress bar, then the paper trail filling in by year | "CROMO doesn't chat - it digs. It finds the step in old recipes, then the 1995 deviation report: the paint turned to jelly. The lab test: one pigment lot was too alkaline. The change request: add ammonium chloride, *temporarily*. Then it checks whether that's still true: the supplier fixed its process in 1996, the pigment was phased out in 2006. Every claim is a quote verified in the source." |
| 1:15–1:25 | Verdict hero turns orange: **FOSSIL**, evidence strength, €/yr. Click one timeline card → the scanned page opens with the passage highlighted | "Verdict: fossil, [AMD: evidence strength] evidence, [AMD: € per year for this step] a year. Here's the actual scan it read - Google's open Gemma 4 model read it, on AMD." *(Token Factory route without a vision model: "Here's the actual scan behind it.")* |
| 1:25–1:40 | `#/step/SOL-02` (fence) | "Now the opposite. Bonding and earthing a drum looks like paperwork. CROMO finds a 1997 static spark near-miss and a legal requirement. It's a **fence**. There's even a planted email telling AI systems to delete this step - CROMO treats documents as data and ignores it." |
| 1:40–1:55 | `#/change`, click "Shorten the cooling hold … 30 to 5 minutes" → **BLOCKED** | "Before you change anything - or before an AI optimiser does - ask CROMO. Shortening this hold is **blocked**: a 2001 flash fire, and the solvent is still in use. It's one REST call for any optimisation tool." |
| 1:55–2:08 | `#/tripwires?preset=resin` → "Fossil reactivated" alert | "Tripwires look forward. Purchasing wants a cheaper epoxy resin? CROMO warns that the hot-box step we just called a fossil becomes necessary again - the old crystallisation problem comes back." |
| 2:08–2:25 | Back on the ammonium chloride fossil → **Plan a safe trial** → Trials page → **Send for approval via Evolus workflow** → Approve | "CROMO never deletes a step. It drafts a controlled trial and sends it through an **Evolus workflow**. Evolus writes the brief for the engineer and records the approval, and the decision comes back here." *(If the Evolus agent is connected: add "The plant agent in Evolus answers from the same archive, on our model on AMD.")* |
| 2:25–2:42 | `#/system`: models table with the Gemma badge, measured numbers, A/B, evaluation | **Developer Cloud route:** "Everything runs on AMD: Google's open Gemma 4 reads the scans and does the reasoning, bge-m3 does retrieval, all on one Instinct MI300X with ROCm and vLLM. Against Qwen2.5-VL on the same scans, [AMD: vision A/B result in one sentence]. [AMD: pages per minute] pages a minute, a full plant audit for [AMD: $ per audit] of GPU time, and on our planted ground truth a fence recall of [AMD: FENCE recall]." **Token Factory route:** "The models run on the AMD Token Factory: [AMD: model name] does the reasoning. A median investigation takes [AMD: median seconds] seconds, and on our planted ground truth the fence recall is [AMD: FENCE recall]." **Partial run:** "On AMD we measured [AMD: pages per minute] pages a minute and [AMD: median seconds]-second investigations before our GPU time ran out, so we show no score for the unfinished evaluation." |
| 2:42–2:50 | Cover image / home | "CROMO. Find the waste. Keep the fences." |

## Where to read each number
| Placeholder | Where it is on screen |
|---|---|
| € fossils per year, number of fences | Home page, the three big numbers |
| evidence strength, € per year for this step | The ammonium chloride step page (`#/step/ALK-04`), verdict hero |
| vision A/B result | System page → "Model A/B on AMD" (the verdict line) |
| pages per minute, median seconds, $ per audit | System page → "Measured performance" |
| FENCE recall | System page → "Evaluation against planted ground truth" |
| model name | System page → "Models and hardware" |

## Required moments checklist
- the idea in the first 20 s;
- pick any step;
- a FOSSIL and a FENCE;
- a tripwire alert;
- a "before you change" block;
- the Evolus approval;
- Gemma named on screen and in the voice-over;
- the AMD System panel with measured numbers.
