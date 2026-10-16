# Evolus setup (partner track: Evolus Business Agents on AMD)

CROMO drives Evolus only through its APIs. Everything below is created by `scripts/evolus_setup.py`
through the REST API, except connecting the model (UI only) and creating a personal key (UI only).

## Building blocks and where CROMO uses them

| Building block | What it does in CROMO | Status |
|---|---|---|
| **Workflow** "CROMO · Trial approval" | A FOSSIL never gets deleted. CROMO sends a safe-trial plan to the workflow. An AI Tool step writes a brief for the approving engineer, a Script step builds the approval record, and the Output step returns it. The engineer's decision goes through the same workflow (`stage=decision`), so request and decision are both recorded in Evolus. | Created via REST; real round-trip tested |
| **AI Tool `compare`** | "What changed when this step was added?" in each investigation: compares the recipe revision that introduced a step with the one before it. 17 comparisons pre-computed and cached. | Live; ~155 credits used |
| **Document extractor** (agent + JSON output structure) | Turns archive documents, including scans, into structured records: type, date, reference numbers, cited documents, suppliers, materials, equipment, regulations. Ingestion uses the cached records (`CROMO_METADATA_SOURCE=auto`). | Script ready; needs a User API key + connected model |
| **Knowledge library** | The 178 archive transcriptions, for the Evolus plant agent. | Script ready; needs a User API key |
| **Agent** "CROMO · Plant archivist" on the AMD vLLM model | Engineers can chat with the plant archive (OpenAI-compatible endpoint). Shown on the **Ask why** page. | Script ready; needs the model connected |

Credits: 50,000 per workspace until 15 Nov 2026. Every call is logged with the credits it used (System page), and every
result is cached in `data/evolus_cache/`, so nothing is paid for twice. Calls are spaced to stay under 60 requests/minute.

## Steps (click by click)

### 1. Application API key (done)
`EVOLUS_API_KEY` and `EVOLUS_APPLICATION_ID` are in `.env`. They work for workflows, agents, AI Tools and agent chat.

### 2. Personal User API key (needed for the extractor and the library)
The API marks creating output structures (extractors) and knowledge memories as "User authentication required".
1. Evolus → left menu → **API documentation** → **API keys** tab.
2. Create a **User API key**, select **all scopes**, and copy it.
3. Add a line to `.env`: `EVOLUS_USER_API_KEY=<the key>`.

### 3. Trial-approval workflow (done)
```
.venv\Scripts\python scripts\evolus_setup.py workflow
```
Creates the workflow with three steps:
1. AI Tool `summarize` (bullet brief)
2. Script (approval record)
3. Output

Parameters: `trial_id`, `step_id`, `process`, `stage`, `decision`, `approver`. It is created **turned on**.
Its id is in `.env` as `EVOLUS_TRIAL_WORKFLOW_ID`.

### 4. Connect the AMD model (after `LINK_AMD.md` route B, step 2)
> **Which endpoint counts?** The Evolus track requires the main agent to use an open model served through *our own
> vLLM endpoint on AMD Developer Cloud* (event page, checked 16 Oct 2026). The Evolus developer page lists Fireworks AI
> or vLLM on AMD Developer Cloud for the hackathon. The AMD Token Factory (CROMO's measured route) is **not** listed, so
> CROMO does not connect it to Evolus or present it as compliant unless the organisers confirm it. The workflow, the
> compare AI Tool and the knowledge library do not need a model endpoint and work today.

1. Evolus → **Your models** → **Add model**.
2. Fill in:
   - OpenAI-compatible base URL: `http://<droplet-ip>:8000/v1`
   - Model: `google/gemma-4-26B-A4B-it` (Gemma 4)
   - API key: the `VLLM_API_KEY` you set on the droplet
3. **Test connection** → **Save**. Note the model key Evolus shows (`own/...`).
4. The vLLM server already runs with `--enable-auto-tool-choice --tool-call-parser gemma4` (Evolus agents use tools).

### 5. Library, extractor, agent
```
set EVOLUS_MODEL_KEY=own/<alias>
.venv\Scripts\python scripts\evolus_setup.py library
.venv\Scripts\python scripts\evolus_setup.py extractor
.venv\Scripts\python scripts\evolus_setup.py agent
```
Paste the printed ids into `.env`:
- `EVOLUS_LIBRARY_ID`
- `EVOLUS_EXTRACTOR_AGENT_ID`
- `EVOLUS_EXTRACTOR_ID`
- `EVOLUS_AGENT_MODEL`

### 6. Fill the library and run the extractor
```
.venv\Scripts\python scripts\evolus_precompute.py library --limit 178    # indexing uses credits; test with --limit 3 first
.venv\Scripts\python scripts\evolus_precompute.py extract --limit 20     # reads PDFs incl. scans; results cached
```
The script prints the credits each run used.

### 7. Check
```
.venv\Scripts\python scripts\check_amd.py --role evolus
```

## How CROMO calls Evolus (for reviewers)
- REST `https://api.evolus.ai/api/v1` with `X-ApiKey` + `X-Application-Id` (`backend/cromo/evolus.py`):
  - `POST /workflows/{id}/execute` (multipart; parameters as JSON) → `GET /workflows/{id}/executions/{executionId}`
  - `POST /ai-tools/compare/run`
  - `POST /agents/{agentId}/json/{extractorId}/ask-file?useWebhook=false` (image PDF of the scan)
  - `POST /memories/{libraryId}/documents?language=en|it`
- Agent chat: `POST https://api.evolus.ai/v1/chat/completions` with `Authorization: Bearer`, `model = applicationId:agentId`.
- Webhook (optional): `POST /api/evolus/webhook?token=<CROMO_ACCESS_TOKEN>` receives workflow results when CROMO is publicly reachable; polling is the default.
