# CROMO demo video script (target 2:45, hard limit 3:00)

**Setup before recording**
- Run the app on your PC against the AMD Token Factory (`LINK_AMD.md` Route A, step 7). Do **not** delete
  `data\runtime\cromo.db`: it holds the AMD run. The header pill must read **Live on AMD Token Factory · Gemma-4-31B-IT**.
- Run `.venv\Scripts\python scripts\warm_demo.py http://localhost:8000` once after starting the app (it can take
  10–20 minutes on a busy endpoint). Every What-if example then answers at once with the stored AMD answer, marked
  "stored answer from …".
- Turn on **Replay** in the header. Investigations then replay the runs recorded on AMD at speed, with a blue
  "Replay of a run recorded on AMD …" label. A live investigation takes minutes on the shared endpoint, so replay is
  the honest way to show the dig in a 3-minute video. Say "replayed" once (line at 0:32).
- Light theme, Chrome at 1920×1080, zoom 100%, nothing else open. OBS: screen + voice. Upload to YouTube as **Unlisted**.
- Open these tabs beforehand and click through them in order: `#/`, `#/step/ALK-04`, `#/step/SOL-02`,
  `#/change`, `#/tripwires?preset=resin`, `#/trials`, `#/system`.
- First frame: `#/cover` (the cover image) for one second, or the home page.

**Numbers.** The numbers in the voice-over are the measured AMD results (16–17 Oct run); each is visible on the screen
named in the table at the end. If you re-run the benchmark, check them again; never say a number that isn't on screen.

| Time | Screen | Voice-over (calm, slow) |
|---|---|---|
| 0:00–0:08 | Home: the plant map fills the screen | "Every factory runs on reasons nobody remembers." |
| 0:08–0:22 | Slowly hover an orange tile, then a teal one; click the **Fossil** chip in the legend, then the **Fence** chip | "CROMO reads thirty years of a plant's own paperwork and works out why every step of every recipe exists. Orange steps are **fossils**: their reason is gone, and they cost money every batch. Teal steps are **fences**: they look pointless, but they protect you." |
| 0:22–0:30 | Point at the three metric cards | "In this synthetic paint plant: three hundred and five thousand euros a year of fossils, sixteen fences protected, and every step with no documented reason goes to a person. Never guessed." |
| 0:30–0:36 | Press **Ctrl K**, type *why do we add ammonium chloride*, Enter | "Ask why about any step. This one is from Primo Levi's *The Periodic Table*: a fix for one bad pigment delivery, still added twenty years later." |
| 0:36–1:05 | ALK-04 opens. Click **Replay AMD run**: the Why-Trail fills hop by hop (recipe history, change request, lab report, supplier, status) | "CROMO doesn't chat. It digs. This is the run recorded on AMD, replayed: Google's open Gemma 4 finds the step in old recipes, follows the 1995 change request to the lab report, the pigment lot that was too alkaline, then checks whether that's still true." |
| 1:05–1:20 | Verdict card turns orange: **FOSSIL**, evidence meter, €/yr. Switch to **Key evidence**, click one card: the scanned page opens with the passage highlighted | "Verdict: fossil, strong evidence, fifteen thousand seven hundred euros a year. Every claim is a quote verified in the source. Here is the scan it read. Gemma reads typed, faxed and handwritten Italian pages too." |
| 1:20–1:35 | Ctrl K → *bond* → Enter: SOL-02, **FENCE** | "Now the opposite. Bonding and earthing a drum looks like paperwork. CROMO finds a static-spark near-miss and a legal requirement. It's a **fence**. There's even a planted email telling AI systems to delete this step: CROMO treats documents as data and ignores it." |
| 1:35–1:48 | **What if → Change a step**: click *Shorten the cooling hold … 30 to 5 minutes* → **BLOCKED** | "Before anyone changes a step, or an AI optimiser does, ask CROMO. Shortening this hold is **blocked**: a flash fire, and the solvent is still in use. It's one REST call for any optimisation tool." |
| 1:48–2:00 | **What if → Change the plant**: the cheaper-resin preset → **Fossil reactivated** | "And when the plant changes: purchasing wants a cheaper epoxy resin? CROMO warns that the hot-box step we called a fossil becomes necessary again." |
| 2:00–2:15 | Back to ALK-04 → **Plan a safe trial** → Trials → **Send for approval via Evolus workflow** → Approve | "CROMO never deletes a step. It drafts a controlled trial and sends it through an **Evolus workflow**: Evolus writes the brief for the engineer and records the approval, and the decision comes back here." |
| 2:15–2:40 | **System**: the three "where it runs" cards, then the four measured numbers, then open *Which model reads the archive best?* | "Every model call runs on AMD, through the AMD Token Factory. Google's Gemma 4 is both the eyes and the brain. We didn't assume it: on our sixty-eight scanned pages it tied the best of three other AMD-hosted models, at a two percent character error rate, and read the handwritten logbooks best. On our planted ground truth CROMO finds eighty-nine percent of the fences and calls none of them a fossil; a rule-based baseline found fifty-six percent and made that mistake once." |
| 2:40–2:48 | Home / cover | "CROMO. Find the waste. Keep the fences." |

**If the Evolus agent is connected to our own vLLM model by then (droplet route)**, add at 2:12: "The plant agent in
Evolus answers from the same archive, on our own model on AMD."

## Where to read each number
| Number | Value | Where it is on screen |
|---|---|---|
| fossils per year, fences | €305,298 /yr, 16 fences | Home page, the metric cards |
| ALK-04 evidence and cost | Strong, €15,713 /yr | ALK-04 verdict card (`#/step/ALK-04`) |
| Gemma CER | 2.2% (MiniCPM 2.1%) | System → *Which model reads the archive best?* |
| FENCE recall, fences called fossils | 89%, 0 (baseline 56%, 1) | System → "FENCE recall" card and *Evaluation* |

## Required moments checklist
- the idea in the first 20 s;
- ask why about any step (Ctrl K);
- a FOSSIL and a FENCE, with a scanned page opened;
- a tripwire alert and a "before you change" block;
- the Evolus approval;
- Gemma named on screen and in the voice-over;
- the System page with where it runs and measured numbers.
