# Sentinel — an MCP security gateway for AI agents

> **Hestia** is a caregiver-first care-concierge AGENT (Gemini via ADK) that reads documents and emails and decides what to do — scheduling reminders, recording bills, flagging fraud and double-billing — built on **Sentinel**, the MCP security gateway. The agent cannot move money or do anything irreversible without caregiver approval. Run the product: `pip install -e ".[web,adk]"` then `python -m hestia.web.server`. Set `HESTIA_USE_LLM=1` with a Gemini key to run the real agent; without one it falls back to a deterministic reader.


Sentinel is a policy-enforcement proxy that sits between an AI agent and its
tools. Every tool call is intercepted, classified by risk, and screened for
prompt injection before it can run. Dangerous actions are blocked or paused for
a human — *the guard has no hands*, so a jailbroken model can never talk it down.

## The problem

AI agents are being handed real power over people's lives — reading mail, paying
bills, managing medications — faster than we're securing them. The dangerous
attack is **indirect prompt injection**: poison hidden in data the agent *reads*
(an email, a web page) hijacks it into a harmful action it was never asked to
take. The malicious instruction never appears in the harmful call's own
arguments, so naive input filtering misses it.

## The design: layered defense-in-depth

Three layers, composed so each can only *add* restriction, never remove it
(`verdict.compose` = most-restrictive-wins):

1. **Deterministic risk gate** (`risk.py`) — hardcoded capability tiers
   (read-only / reversible / irreversible / external-comm). Un-talk-out-of-able.
2. **Learned detector** (`detectors/`) — a fine-tuned DeBERTa injection
   classifier (a heuristic stand-in ships today; the model slots into the same
   interface).
3. **LLM reasoner** — open-ended context judgment, but with **no authority to
   unblock**. It can only escalate caution.

**Taint propagation** (`session.py`) links the poisoned read to the later
blocked action: once a session ingests flagged content, high-stakes actions in
that session are escalated until a human clears it.

Lineage: the dual-LLM pattern (Willison, 2023) and CaMeL (DeepMind/ETH, 2025).
This is defense-in-depth — it raises attacker cost and shrinks the attack
surface; it is not a formal guarantee.

## The agents (why this is an Agents-for-Good project)

Sentinel is a multi-agent system around a deterministic safety floor:

- **Eldercare assistant** (ADK `LlmAgent`) — the protected agent. It reads mail
  and pays bills on the user's behalf, and connects to the world only through
  Sentinel's MCP gateway. Deliberately naive: the security must not depend on it
  behaving well.
- **Fraud investigator** (ADK `LlmAgent`) — the for-good heart. When a payment is
  held, it autonomously investigates (multi-step, tool-using): does the IBAN
  match the vendor's verified account, is there payment history, what's the
  reputation — then gives the user a plain-language APPROVE / REJECT
  recommendation with evidence. Advisory only: read-only skills, no power to pay.
- **The gateway** — deterministic, not an agent (on purpose). It guarantees no
  agent can be talked into an irreversible action.

So agents do the judgement work; the deterministic floor provides the guarantee.
For an at-risk user, that means: not a cryptic "BLOCKED", but an agent that did
the detective work and explained, in plain words, why an invoice looks wrong.

## Deploy to Google Cloud Run

Hestia ships with a `Dockerfile` and a `deploy.sh` helper. The container serves the
FastAPI app on Cloud Run's injected `$PORT` and runs the keyless rule-based reader +
mock inbox by default — no secrets needed for a working live demo.

Test the container locally first (optional):

    docker build -t hestia .
    docker run -p 8123:8080 hestia      # open http://localhost:8123

Deploy (needs the gcloud CLI, a GCP project with billing, and `gcloud auth login`):

    ./deploy.sh YOUR_PROJECT_ID            # region defaults to europe-west1

That runs `gcloud run deploy --source .`, which builds the Dockerfile on Cloud Build
and returns a public HTTPS URL. To enable the real Gemini agent on the live service,
store the key in Secret Manager and set the env vars (commands printed by deploy.sh):

    echo -n "YOUR_GEMINI_KEY" | gcloud secrets create gemini-key --data-file=-
    gcloud run services update hestia --region europe-west1 \
      --set-env-vars HESTIA_USE_LLM=1,GOOGLE_GENAI_USE_VERTEXAI=FALSE \
      --set-secrets GOOGLE_API_KEY=gemini-key:latest

## Connect real email & the live agent (optional)

Copy `.env.example` to `.env` and fill in what you want — Hestia reads it on
startup. With nothing set, it runs the keyless rule-based reader and a mock inbox.

- **Real agent:** set `HESTIA_USE_LLM=1` and `GOOGLE_API_KEY=...`. The header chip
  switches to "Agent (Gemini)".
- **Real Gmail (for "Scan inbox"):** use a dedicated throwaway Gmail, enable IMAP,
  create an App password (Google Account -> Security -> 2-Step -> App passwords),
  and set `IMAP_HOST/IMAP_USER/IMAP_PASS`. "Scan inbox" then reads real mail; a
  poisoned email is the best on-camera proof of Sentinel.

## Dashboard (command center)

`dashboard/index.html` is a self-contained visual console — open it in any
browser, click **Run scenario**, and watch a tool call travel the interception
lane, the irreversible transfer get **held** at the gate, and the investigator
agent reason through its checks live before recommending REJECT. It can also
replay a real `gateway_trace.jsonl` via "Load real trace". No server, no build.

## Setup (once)

```bash
pip install -e .            # security core + MCP gateway (no API key needed)
pip install -e ".[dev]"     # + pytest, to run the test suite
pip install -e ".[adk]"     # + the ADK agent framework (needs a Gemini key to run)
```

No `PYTHONPATH` needed on any OS — the editable install puts `sentinel` on the path.

## Run (no cloud, no API key)

```bash
pytest -q                        # 8 tests, incl. the jailbreak + taint guarantees
python -m demo.attack_demo       # offline: the injection-driven transfer gets blocked
python demo/mcp_attack_demo.py   # the same attack, over real MCP transport
```

## Run the ADK agents (needs a Gemini key)

```bash
# macOS/Linux:                         Windows (cmd) uses `set` instead of `export`
export GOOGLE_API_KEY=...              # from https://aistudio.google.com/apikey
export GOOGLE_GENAI_USE_VERTEXAI=FALSE
python demo/adk_attack_demo.py         # assistant gets blocked; reasoner explains
```

## Status

- [x] Security core: risk tiers, monotonic verdict composition, policy engine
- [x] Taint propagation across the read→act chain
- [x] Human-in-the-loop hold: irreversible actions require approval even when nothing is detected
- [x] Mock tools + end-to-end attack demo + property tests
- [x] Wrap as a real MCP server (gateway/mcp_server.py) + MCP client demo
- [x] ADK multi-agent core: protected assistant (LlmAgent + MCP client) + advisory reasoner
- [x] Autonomous fraud investigator agent (multi-step, tool-using, advisory) — the Agents-for-Good centerpiece
- [ ] Swap heuristic detector for the fine-tuned DeBERTa classifier
- [x] LLM reasoner sub-agent (advisory, read-only skills, no action authority)
- [ ] Cloud Run deployment + live decision-feed UI for the video
