# CROMO demo video script (target 2:45, hard limit 3:00)

**Setup before recording:**
- Light theme; browser at 1920×1080, zoom 100%.
- The app is running live on AMD (header pill "Live on AMD").
- If the GPU or network fails, use the recorded replays ("Replay AMD run"). They're labelled as replays, which is fine to show.
- Close other tabs. Record with OBS (free): screen plus voice-over.
- Tip: open each URL below in its own tab beforehand and click through tabs in order.

| Time | Screen | Voice-over (read calmly) |
|---|---|---|
| 0:00–0:08 | `#/` home, hero and the coloured "periodic table" | "Every factory runs on reasons nobody remembers." |
| 0:08–0:20 | Slowly move the mouse over the orange tiles, then the teal ones | "CROMO reads thirty years of a plant's own paperwork and works out why every step of every recipe exists. Orange steps are **fossils**: their reason is gone, and they cost money every batch. Teal steps are **fences**: they look pointless, but they protect you." |
| 0:20–0:32 | Point at the three big numbers | "In this synthetic paint plant that's [€ — fossil total] a year of fossils, [n] fences protected, and every step with no documented reason is sent to a person - never guessed." |
| 0:32–0:40 | Type in the Ask box: *"why do we add ammonium chloride?"* → Enter | "Judges: pick any step. This one is from Primo Levi's *The Periodic Table*: a fix for one bad batch of pigment, still added twenty years later." |
| 0:40–1:15 | Investigation streams live: verdict card "DIGGING", the progress bar, then the paper trail filling in by year | "CROMO doesn't chat - it digs. It finds the step in old recipes, then the 1995 deviation report: the paint turned to jelly. The lab test: one pigment lot was too alkaline. The change request: add ammonium chloride, *temporarily*. Then it checks whether that's still true: the supplier fixed its process in 1996, the pigment was phased out in 2006. Every claim is a quote verified in the source." |
| 1:15–1:25 | Verdict hero turns orange: **FOSSIL**, Strong evidence, €/yr. Click one timeline card → the scanned page opens with the passage highlighted | "Verdict: fossil, strong evidence, [€] a year. Here's the actual scan it read - on AMD, by Gemma 4." |
| 1:25–1:40 | `#/step/SOL-02` (fence) | "Now the opposite. Bonding and earthing a drum looks like paperwork. CROMO finds a 1997 static spark near-miss and a legal requirement. It's a **fence**. There's even a planted email telling AI systems to delete this step - CROMO treats documents as data and ignores it." |
| 1:40–1:55 | `#/change`, click "Shorten the cooling hold … 30 to 5 minutes" → **BLOCKED** | "Before you change anything - or before an AI optimiser does - ask CROMO. Shortening this hold is **blocked**: a 2001 flash fire, and the solvent is still in use. It's one REST call for any optimisation tool." |
| 1:55–2:08 | `#/tripwires?preset=resin` → "Fossil reactivated" alert | "Tripwires look forward. Purchasing wants a cheaper epoxy resin? CROMO warns that the hot-box step we just called a fossil becomes necessary again - the old crystallisation problem comes back." |
| 2:08–2:25 | Back on the ammonium chloride fossil → **Plan a safe trial** → Trials page → **Send for approval via Evolus workflow** → Approve | "CROMO never deletes a step. It drafts a controlled trial and sends it through an **Evolus workflow**. Evolus writes the brief for the engineer and records the approval, and the decision comes back here." |
| 2:25–2:42 | `#/system`: models table, measured numbers, evaluation | "Everything runs on AMD: Google's open Gemma 4 reads the scans and does the reasoning, bge-m3 does retrieval, all on one Instinct MI300X with ROCm and vLLM. We measured Gemma against Qwen2.5-VL on the same scans: [result]. [n] pages a minute, a full plant audit for [$x] of GPU time, and on our planted ground truth a fence recall of [x]%." |
| 2:42–2:50 | Cover image / home | "CROMO. Find the waste. Keep the fences." |

**Numbers in [brackets]:** read them from the System page and the home page after `scripts/benchmark_amd.py`. Never
say a number that isn't on screen.

**Required moments checklist:**
- idea in the first 20 s;
- judges pick any step;
- a FOSSIL and a FENCE;
- a tripwire alert;
- a "before you change" block;
- the Evolus approval;
- the AMD System panel with numbers.
