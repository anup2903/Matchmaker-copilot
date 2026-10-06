# Matchmaker Copilot — The Date Crew assessment prototype

> Give matchmakers a better memory of what each client **says** they want, what they have **rejected**, and what their
> decisions **appear to reveal** over time — while keeping the matchmaker in control.

**AI suggests → matchmaker reviews → matchmaker confirms → system learns.**
This is not a compatibility scorer and nothing is rejected or changed automatically.

All data is mock data invented for this assessment.

## Run it

### Option A — everything in Docker (one command)

```bash
docker compose up --build
```

Postgres starts, the backend runs migrations, **seeds the mock data (only if the DB is empty)** and serves the API;
the frontend builds and serves the UI.

- App: <http://localhost:3000>
- API docs: <http://localhost:8000/docs> · health: <http://localhost:8000/health>

Reset the demo data at any time:

```bash
docker compose exec backend python /seed/seed.py --reset
```

### Option B — local dev (Postgres in Docker)

```bash
docker compose up -d db

# backend (Python 3.12+)
cd backend
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
python ../seed/seed.py --reset
uvicorn app.main:app --reload --port 8000

# frontend (new terminal)
cd frontend
npm install
npm run dev                                              # http://localhost:3000
```

The browser only talks to Next.js; `/api/*` is proxied to the backend (`BACKEND_URL`, default `http://localhost:8000`).

### Turn on the AI (structuring rejection notes)

Structure Feedback is AI-powered: a language model reads the note and returns validated JSON. Point the backend at
any OpenAI-compatible chat-completions provider. Copy `.env.example` to `.env` (never commit it) and fill in:

```bash
LLM_API_KEY=your-key
LLM_MODEL=your-model-id
LLM_BASE_URL=            
```

Then restart the backend (`docker compose up -d --build backend`, or restart uvicorn). The key stays on the backend; the
browser never sees it. With **no key** the app falls back to a deterministic demo extractor, a "Demo mode" tag shows in
the header and on the result, and the page explains how to connect the AI.

### Tests and checks

```bash
cd backend  && pytest                       # 100+ tests: checker, structurer, mirror, API smoke, seed
cd frontend && npm run typecheck && npm test
```

## 2-minute demo path

Open <http://localhost:3000>.

1. **Check Profile** (sidebar) → click the demo chips:
   - *Ananya + smoker* → **RED — BLOCKED**: "Candidate smokes" · Source: Dealbreaker · Evidence: "Non-smoker".
   - *Ananya + long distance* → **AMBER — REVIEW**: "Client rejected 3 recent profiles citing long distance" with the quoted rejections.
   - *Ananya + strong match* → **GREEN — GOOD TO SHARE** with positive matches and their evidence.
   - *Ananya + mirror pattern* → AMBER via an unconfirmed Preference Mirror pattern.
2. **Preference Mirror** (shown under every result, or open **Clients → Ananya**): says *Intellectual compatibility is
   important* vs. *3 recent rejections mention intellectual fit; 2 mention college pedigree* → "Education prestige may be
   acting as a proxy…" · Confidence **Medium** · *2 rejection examples + 1 similar accepted profile*.
   Don't click anything yet — the matchmaker decides. Then **Confirm as soft signal** (creates a *soft* preference,
   stored with evidence IDs + timestamp; "Rey D." now shows "Confirmed soft signal") or **Dismiss** (persisted, evidence kept).
3. **Structure Feedback** → pick client *Ananya* → sample *Intellect + distance* → **Structure feedback** → two
   signals (category, attribute, stated-preference violation, confidence, evidence) → edit if you like → **Save feedback**.
   Try *Ambiguous* (→ unclear / low) and *Unrelated / timing* (→ not a preference violation).

Other seeded behaviours: *Rohan + Zara P.* (children dealbreaker → RED), *Rohan + Veer A.* (strong location
preference + 3 distance rejections → AMBER), *Priya + Kiran M.* (weak soft mismatch → stays GREEN with a note),
*Priya + Veer A.* (matchmaker-confirmed soft signal → AMBER), *Ananya + Jai O.* (unknown smoking status →
flagged for verification, never guessed), *Meera* (Preference Mirror with **Mixed evidence**), *Rohan* (no card: not enough evidence).

## Why this problem? Why this shape?

- Most shared profiles are not accepted; a large share of rejections cite things clients already told us;
  rejection feedback is mostly free text; clients sometimes accept profiles similar to ones they rejected.
  That points to a **weak feedback loop**, not (yet) a ranking problem.
- **Why not an ML recommender?** Limited data and a two-week MVP horizon. First structure the qualitative feedback and
  improve what matchmakers can see; that also creates the training/analytics data a future ranker would need.
- **Why human in the loop?** The data is subjective and behavioural; the product supports expert judgement, it does not
  automate a life decision.
- **Why AI at all?** Free-text notes are hard to analyse consistently. The LLM does one job — language → a validated,
  controlled schema. Everything downstream (RED/AMBER/GREEN, Mirror thresholds) is deterministic code.

## How it works

```
frontend/ (Next.js App Router, TS, Tailwind, lucide)  ──/api proxy──▶  backend/ (FastAPI)
                                                                                    │
seed/ (seed.py + data/*.json) ───────────────────────────────────────────────▶ PostgreSQL
```

| Piece | What it does | File |
|---|---|---|
| Profile checker | Pure function. RED only from a stored dealbreaker meeting a *known* attribute; AMBER for strong-preference conflicts, ≥2 recent rejections the candidate also matches, confirmed soft signals, unresolved Mirror patterns, unverifiable dealbreakers; else GREEN. Every reason carries `source` + `evidence`. No score. | `backend/app/services/profile_checker.py` |
| Feedback structurer | Provider adapter (`LLMProvider`) → OpenAI-compatible client or deterministic demo extractor. The model also picks an **observed-dimension tag** from a fixed closed list (`ObservedDimension`) — a finer label than category, e.g. `education_prestige` vs `career_ambition` — so patterns group on a stable tag, not keywords. Output validated with Pydantic, evidence must be a verbatim quote, **one** corrective retry on malformed JSON, one retry on timeouts, then a clean error with "use demo mode". Stored preferences (not the model) decide stated-vs-new and dealbreaker-vs-strong. | `services/feedback_structurer.py`, `services/llm/`, `core/preferences.py` |
| Preference Mirror | Pure engine; patterns are **data** (`MIRROR_RULES`) that match on observed-dimension tags, so adding a pattern is adding a row, not code. Thresholds: never from 1 rejection; **High** = 4+ rejections + ≥1 similar accepted; **Medium** = 2–3 + ≥1; **Low** = 2+ with none; ≥2 similar accepted profiles → "Mixed evidence" and confidence is lowered a step. Confidence/evidence/counts stay deterministic; the "possible pattern" **sentence** may be re-worded by the LLM under validation (hedged language, no invented numbers, no overclaiming) with a template fallback — so a phrasing failure can never inflate a card. Confirm → soft preference (`human_confirmed`); dismiss → persisted, hidden, resurfaces only with 2+ more supporting rejections. | `services/preference_mirror.py`, `services/mirror_phrasing.py`, `services/mirror_store.py` |

API (all under `/api`, typed Pydantic models): `GET /clients`, `GET /clients/{id}`, `GET /candidates`,
`POST /profile-check`, `POST /feedback/structure`, `POST /feedback/save`,
`GET /clients/{id}/preference-mirror`, `POST /preference-mirror/{id}/confirm|dismiss`, plus `GET /feedback/samples` and `/health`.

Safety: no LLM-decided blocks, no appearance scoring, no sensitive-attribute inference, no automatic rejection, no
silent preference changes, no API key in the browser, no `.env` committed.

## Assumptions & limitations (prototype)

- `rejection_feedback.decision_id` is nullable so a note can be logged before it is linked to a profile.
- Candidates have two extra structured fields (`education_tier`, `career_level`) so Mirror rules compare data, not prose.
- "Long distance" = more than 200 km between known cities (small lookup in `core/geo.py`); unknown cities stay unknown.
- No analytics dashboard. The scope is three product areas: Check Profile, Structure Feedback and Preference Mirror.
- No auth, queues, vector DB or agents — by design.
