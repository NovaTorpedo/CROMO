# Hosting CROMO for free

## Constraints we checked (October 2026)
- **Hugging Face Spaces:** Docker/Gradio Spaces now need a paid plan; only static Spaces are free
  ([HF docs](https://huggingface.co/docs/hub/en/spaces-overview)).
- **Fly.io / Railway / Google Cloud Run:** need a card on file.
- **AMD droplet:** running the full app there costs GPU credits every hour, even when it's idle.

So the setup is:

| What | Where | Cost | Live models? |
|---|---|---|---|
| **Public demo URL** (submission "Application URL") | **GitHub Pages**: a static, read-only build of the same UI with the recorded results | free, no card, never sleeps | No. It replays the recorded AMD runs and shows the stored AMD verdicts, all labelled as recorded |
| **Full app, live** | `docker compose up` on any machine (your laptop during judging, or the AMD droplet) | free locally | Yes. Token Factory or own vLLM, configured in `.env` |

Keys never reach the browser in either setup: the static demo has no keys at all, and the full app keeps them server-side.

## 1. Public demo on GitHub Pages (one-time, ~3 minutes)
1. Make the repository public (GitHub → repo → Settings → General → Danger zone → Change visibility). The secret scan
   has already run on the full history.
2. GitHub → repo → **Settings → Pages** → Source: **GitHub Actions**.
3. Push to `main`. The workflow `.github/workflows/pages.yml`:
   - exports the demo data (`scripts/export_static.py`, which starts from `data/recorded/snapshot.db` when present);
   - builds the UI with `VITE_STATIC=1`;
   - publishes it.
4. The URL is `https://<user>.github.io/CROMO/` (e.g. `https://novatorpedo.github.io/CROMO/`).

What works there:
- the plant map;
- every investigation, replayed with its original timing;
- every archive page with highlighted citations;
- Evolus compare results;
- the recorded Evolus trial approval;
- the System page with the measured AMD numbers;
- the example buttons of *Check a change*, *Tripwires* and *Ask why* (pre-computed).

Anything else shows a clear "read-only demo - run locally for live use" message.

After AMD is linked (`LINK_AMD.md` step 8), commit `data/recorded/` and push. The demo then shows AMD-computed results.

## 2. Full app with live AMD models (judging / pitch)
```
git clone https://github.com/NovaTorpedo/CROMO.git && cd CROMO
copy .env.example .env      # then fill the AMD + Evolus values (LINK_AMD.md)
docker compose up --build   # http://localhost:8000
```
If you expose it publicly (e.g. a tunnel during the live pitch):
- set `CROMO_ACCESS_TOKEN` to a passcode;
- keep `CROMO_ALLOWED_ORIGINS` empty (same origin).

Write and GPU/credit-spending endpoints then require the passcode and are rate limited. Read-only views stay open.

## Why not run the backend on the AMD droplet for the whole judging period?
One MI300X is $1.99/hour list price, billed even when the droplet is powered off. The judging window would burn most of
the free credits. The recorded runs plus a short live session cover the demo at a fraction of the cost.
