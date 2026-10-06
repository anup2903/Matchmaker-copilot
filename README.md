# Matchmaker Copilot

A small internal tool for The Date Crew matchmakers.

**Live app:** <https://matchmaker-frontend.onrender.com>
**API:** <https://matchmaker-backend-i0x2.onrender.com/docs>

> Free hosting: the first load can take ~30–60 seconds while the server wakes up.
> All data is mock data made up for this assessment.

## The problem

Matchmakers share many profiles with clients, and most get rejected. Often the reason is something the
client **already told us** ("I don't want a smoker"). Rejection reasons are written as free text, so nobody
can easily see patterns. And sometimes what a client **says** they want is different from what they
actually **choose**.

## Our solution

Help the matchmaker remember three things for every client:

1. What the client **said** they want
2. What the client has **rejected** before, and why
3. What their decisions **seem to show** over time

The AI only suggests. The matchmaker always decides. Nothing is rejected or changed automatically, and
there is no made-up "87% compatible" score.

## Features

### 1. Check a Profile

Pick a client and a candidate. You get a simple traffic light, and every reason shows the evidence behind it.

| Result | Meaning | Example |
|---|---|---|
| 🔴 **RED — Blocked** | Breaks a dealbreaker | Ananya's dealbreaker is "non-smoker". The candidate smokes. |
| 🟠 **AMBER — Review** | Something worth a second look | The candidate lives far away, and Ananya rejected 3 recent profiles because of long distance. |
| 🟢 **GREEN — Good to share** | No conflicts, strong matches | Same city, wants children, non-smoker, similar lifestyle. |

RED only comes from fixed rules, never from AI.

### 2. Structure Feedback

The matchmaker pastes a client's rejection note. AI turns it into clean, structured data.

**Input:**
> "He seemed nice, but I didn't feel we'd connect intellectually. Also I'm not sure our lifestyles would work with the distance."

**Output (two signals):**

| Category | What | Confidence | Evidence (quoted from the note) |
|---|---|---|---|
| Intellectual fit | intellectual compatibility | High | "didn't feel we'd connect intellectually" |
| Location | distance | Medium | "not sure our lifestyles would work with the distance" |

Each signal is also checked against the client's stated preferences: did it break one the client already
gave us, or is it a new signal?

The matchmaker can edit the result before saving. Vague notes are marked *unclear / low confidence*, and
notes like "asked to pause introductions for a few weeks" are marked *not a preference issue*. The AI output is always validated.
If no AI key is set, a built-in demo mode handles the sample notes.

### 3. Preference Mirror

Compares what a client **says** with what their **decisions** suggest, and shows it only when there is
enough evidence (never from just one rejection).

**Example — Ananya:**

- **What the client says:** Intellectual compatibility is important
- **What the decisions suggest:** 3 recent rejections mention intellectual fit; 2 mention college pedigree
- **Possible pattern:** College prestige may be acting as a stand-in for "intellectual fit"
- **Confidence:** Medium (2 rejection examples + 1 similar profile that was accepted)

The matchmaker chooses:

- **Confirm as soft signal** → saved as a *soft* preference (never a dealbreaker)
- **Dismiss** → saved, and the card is hidden

## Run it locally

```bash
docker compose up --build
```

- App: <http://localhost:3000>
- API docs: <http://localhost:8000/docs>

To use a real AI model, copy `.env.example` to `.env` and set `LLM_API_KEY`, `LLM_MODEL` and `LLM_BASE_URL`
(any OpenAI-compatible provider). Without a key, the app runs in demo mode.

Tests:

```bash
cd backend  && pytest
cd frontend && npm run typecheck && npm test
```

## Tech

Next.js · TypeScript · Tailwind · FastAPI · PostgreSQL · SQLAlchemy · Alembic · Pydantic
