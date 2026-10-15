# CROMO: submission texts (copy into the lablab.ai form)

## Project title
CROMO — every factory runs on reasons nobody remembers

## Short description (one sentence)
CROMO reads a plant's own archive on AMD GPUs and recovers why every process step exists: it flags costly "fossil" steps whose reason is gone, protects "fence" steps that look pointless but prevent accidents, and warns when a change breaks either.

## Long description
Every factory recipe contains steps nobody can explain anymore. In Primo Levi's "Chromium" (The Periodic Table, 1975),
a paint plant still added ammonium chloride to every batch twenty years after the bad pigment it was meant to fix had
disappeared. That step had become a fossil. Chesterton's fence is the opposite warning: some steps that look pointless
are load-bearing. Plants carry both, and now AI optimisers are starting to propose "remove this, shorten that".

CROMO is an investigator for process engineers, quality/EHS managers and plant managers. Pick any step and it digs
through decades of the plant's own paperwork, hop by hop, streaming each hop to the screen:
- scanned change requests, faxes, deviation and incident reports;
- handwritten Italian shift logbooks;
- supplier qualifications, regulations, emails and old recipe revisions.

It finds the record that introduced the step, follows the references it cites, and checks whether each condition
behind it still holds. It also looks for counter-evidence.

Every verdict is FOSSIL, FENCE, ACTIVE or UNKNOWN, with the reasoning chain, its dependencies and an evidence-strength
grade. Every claim cites a quote verified verbatim in the source. Language models read the evidence; deterministic,
auditable rules decide what may be removed. A fence is never removed, a fossil only through a controlled trial with
rollback, and an unknown goes to a person.

Around the verdicts, CROMO offers:
- **Tripwires:** alerts when a supplier, material, equipment or regulation change makes a step useless, affects a
  fence, or brings an old fossil back to life.
- **"Before you change":** checks proposed changes (blocked / caution / allowed with trial); also a REST endpoint for
  optimisation tools.
- **Cost:** the annual cost of each fossil from explicit MES/ERP inputs.
- **Safe trials:** controlled trial plans approved by an engineer through an Evolus workflow.

The whole AI pipeline runs on one AMD Instinct MI300X with ROCm and vLLM:
- Qwen3-30B-A3B as the reasoner, with tool calling;
- Qwen2.5-VL-7B reading scans and handwriting;
- bge-m3 for multilingual retrieval.

The AMD Token Factory is supported by configuration. Evolus building blocks are driven through the REST API:
- a workflow for trial approval (created and run via the API);
- the compare AI Tool for recipe revisions;
- a document extractor for scans;
- a knowledge library with an agent running on our AMD vLLM model.

Because no real 30-year archive is available, we built a fully synthetic one for a fictional coatings plant:
- 178 documents with realistic scan noise;
- planted ground truth: 12 fossils, 9 fences, 22 active and 6 unknown steps;
- deliberate traps: red herrings, contradictions, a reverted change, a reason found only in a handwritten logbook,
  and a prompt-injection document.

We measure FENCE recall (missing a fence is the dangerous error), the false-FOSSIL rate and citation precision against
it. The numbers come from measured runs, next to a no-LLM heuristic baseline. The repository is MIT licensed, keys
stay server-side, and the demo runs end to end offline in a clearly labelled fixture mode.

## Track
Intelligent Industry (main) · Evolus Business Agents on AMD (partner)

## Technology tags
AMD Instinct MI300X · AMD ROCm · AMD Developer Cloud · AMD Token Factory · vLLM · Qwen3 · Qwen2.5-VL · bge-m3 · Evolus · FastAPI · React · Python · TypeScript · Docker

## Links
- Public demo (read-only, recorded results): https://novatorpedo.github.io/CROMO/
- Repository: https://github.com/NovaTorpedo/CROMO
- Video: *(upload, then paste the link)*
- Slides: `submission/CROMO-slides.pdf`
- Cover image: `submission/cover.png`
