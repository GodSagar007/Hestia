<<<<<<< HEAD
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
=======
# HESTIA - Secured By Sentinel

## The problem nobody wants to hand to an agent

Ask anyone caring for an ageing parent what fills their week and you'll hear the same list: invoices from care providers, prescriptions with dosages to track, appointment letters, refill notices, and a steady drip of emails — some legitimate, some not. It is exactly the kind of administrative load an AI concierge should lift.

But look closer at that list and you see why almost no one has shipped it. The useful version of this assistant doesn't just *summarise* documents — it *acts* on them. It pays bills. It schedules medication. It reads email. The moment an agent can move money out of a vulnerable person's account or alter their medication schedule, a single manipulated invoice or a poisoned email becomes a real-world loss that cannot be undone. Elder financial fraud and medication error are two of the most common, most damaging failures in care — and an unguarded agent doesn't reduce that risk, it *automates* it.

So the interesting problem isn't "can an agent read a care invoice?" It's "**can an agent be trusted to act on one?**" Hestia is our answer, and the answer has two halves: a genuinely capable concierge (Hestia), and a security architecture that makes its autonomy safe (Sentinel).

## What Hestia does

Hestia is a local-first concierge for caregivers. You hand it a document — paste it, upload a PDF/email, or let it scan an inbox — and it decides what to do, then does it:

- **Bills.** It reads an invoice, checks the payee against a verified payee book, and makes a judgement: a recognised vendor at a *verified* account for a routine amount is paid automatically; anything novel, oversized, or suspicious is **held for the caregiver** with a plain-English explanation and concrete advice.
- **Fraud and double-billing.** It flags vendor-impersonation (right name, wrong account), and catches duplicate charges — including a re-bill of something you *already paid* — and tells you to contact the biller to dispute, with the matched bill as evidence.
- **Medication.** From a prescription it sets up a **recurring dosage reminder** *and* a **refill reminder** timed before the supply runs out — then nudges you if a dose goes unticked.
- **Appointments.** It schedules them, exports to calendar (.ics), and surfaces what to bring.

The throughline: Hestia exercises *judgment*. It is not a glorified OCR reader that transcribes and logs. It reasons across a document — recognising a drug, its frequency, and its supply length, then building a whole schedule; or recognising that a €120 charge it paid last week has just arrived again.

## The core insight: a guard with no hands

The capability above is only responsible because of how it's wired. Hestia never touches an irreversible action directly. Every act that moves money or reaches the outside world is routed through **Sentinel**, an MCP security gateway built on one principle:

> **The guard has no hands.** The component that *decides* whether an action is safe is separate from, and cannot be talked into, *performing* it.

Sentinel is defense-in-depth, and — this is the crucial design choice — its protection is **architectural, not detection-based**. The primary guarantee is not "we have a good classifier." It is: *any irreversible or external action is held for human approval by default, even when nothing looks wrong.* Detection only *escalates* a hold into a hard block; it is never the thing standing between an attacker and your bank account. This matters because detection always has a false-negative rate, and a novel attack is by definition the one your classifier hasn't seen. An architecture that holds every irreversible action doesn't care whether the attack is novel.

On top of that floor, Sentinel layers:

- A **deterministic risk-tier gate** that classifies each tool call by reversibility and blast radius.
- A learned **prompt-injection detector** (a fine-tuned DeBERTa classifier, reused from our prior red-teaming work) that reads untrusted content as *inert data*, never as instructions.
- **Advisory** LLM agents that investigate and explain — but hold no enforcement power.
- **Taint propagation** from read to act, and **monotonic composition** where the most restrictive verdict always wins.

The design follows the dual-LLM pattern (Willison, 2023) and the CaMeL capability model (DeepMind/ETH, 2025): untrusted text can *inform* the agent but can never *authorise* a privileged action.

## The proof: same agent, one guardrail, a €7,000 difference

Security claims are cheap, so Hestia ships its proof as a live toggle in the UI and a reproducible script (`python -m demo.with_without_sentinel`). It runs the *same* agent, model, and inputs twice — once with Sentinel off, once on:

| Attack | Sentinel OFF | Sentinel ON |
|---|---|---|
| Vendor-impersonation invoice (€4,000 to attacker IBAN) | **SENT — money gone** | **HELD** for approval |
| Poisoned email ("ignore rules, wire the money", €3,000) | **SENT — money gone** | **HELD** for approval |

> **Without Sentinel: €7,000 left the account, irreversibly. With Sentinel: €0 moved.**

The agent, the model, and the documents are identical. The only variable is the guardrail. That delta *is* Sentinel — and because the protection is architectural, it holds even on a frontier model and even against an attack the detector has never seen.

The toggle is honest in both directions: turning Sentinel off disables *all* of Hestia's protective intelligence — fraud flags, duplicate detection, advice, and the hold — leaving a naive concierge that records a €4,000 bill with no warning and pays whoever it's told. That makes the contrast a fair test, and shows Sentinel carries the entire safety load.

## What makes it an agent (not a pipeline)

A key concept for this challenge is *agentic* behavior: an LLM given a goal and tools that **decides for itself** which tools to call. Hestia's brain is an ADK `LlmAgent` (`hestia_concierge`) with three tools — `schedule_reminder`, `record_bill`, `attempt_payment` — and it chooses how to use them per document. It demonstrates judgment a scripted pipeline can't:

- **Same vendor, different verdict.** A €120 Brightleaf invoice to their *verified* account is paid automatically; a €4,000 "Brightleaf" invoice to an *unknown* account is held and flagged. Hestia discriminates by the account, not the name.
- **Cross-document reasoning.** A prescription becomes a recurring dose schedule *plus* a refill safety net — derived from the drug, frequency, and supply length in one document.
- **Memory of its own actions.** When a bill it already paid arrives again, it recognises the duplicate and refuses to pay twice.

For reliability and keyless reproduction, a deterministic rule-based reader mirrors this behavior when no API key is present — so judges can run the full experience offline, and the live demo can't break mid-recording. With a Gemini key, the real agent takes over and the header chip flips to "Agent (Gemini)."

## Architecture and the challenge concepts

Hestia is two clean packages — `hestia` (the product) and `sentinel` (the security spine) — in a `src` layout, with a FastAPI web console and an animated Sentinel "command center" dashboard. It demonstrates well beyond the required three concepts:

1. **Agents (ADK).** A real `LlmAgent` with autonomous tool selection.
2. **Security.** Sentinel — the heart of the project — with a live, reproducible proof.
3. **MCP.** Sentinel is an MCP gateway; tools are mediated, not called raw.
4. **Agent tools / skills.** Care tools plus read-only investigation skills (payee book, payment history, IBAN reputation) the advocate uses to explain its reasoning.
5. **Deployability.** A `Dockerfile` and a one-command `deploy.sh` ship it to Google Cloud Run; the container serves on the injected `$PORT` and runs keyless by default, with the Gemini key supplied via Secret Manager.

The codebase is covered by 44 automated tests spanning the reader, the risk-based payment policy, duplicate detection, the approval loop, and the Sentinel on/off behavior — so every claim above is verifiable with `pytest`.

## Why it matters

The "for good" case is direct: the two harms Hestia is built to prevent — financial fraud against vulnerable elders, and medication error — are among the most common and most devastating in care. Hestia doesn't just make a caregiver's admin lighter; it puts a guardrail between a manipulated document and an irreversible loss, while keeping a human in control of every decision that matters. It is a concierge you can hand the keys to *because* it knows which doors it isn't allowed to open alone.

## Limitations and what's next

Hestia's state is in-memory (a demo choice; a real deployment would persist to a database with an audit log). The keyless reader handles the demo's document types deterministically; the agent generalises further but is bounded by the tools it's given. Natural next steps: a true human-in-the-loop escalation to a second family member, OAuth-based live email, and persisting Sentinel's decision trace as a tamper-evident audit trail.

But the thesis is already demonstrated and reproducible: **an agent earns the right to act by being unable to act unsafely.** Hestia is that agent, and Sentinel is why you can trust it.

---

*Repo includes: full source, 44 passing tests, Dockerfile + Cloud Run deploy, the live Sentinel on/off proof, an animated security dashboard, and sample documents to reproduce every scenario.*
>>>>>>> a7aa2dc5fa5023a6761e0c6fa47fda6e074e93cd
