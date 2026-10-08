# Prepwise

An AI-powered interview prep web app. Upload a resume PDF and paste a job
description — Prepwise returns a match score, skill gaps, resume wording
tips, and 10 tailored interview questions with honest answer outlines.

**Live demo:** _deploy and add link here_

---

## What it does

1. You upload a resume PDF and paste a job description.
2. The backend extracts the resume text with `pdfplumber`.
3. It calls the Groq LLM API with a carefully designed prompt.
4. The LLM returns a structured JSON result validated by Pydantic.
5. The frontend displays the match score, gaps, tips, and questions.
6. If you are logged in, the result is saved to your history.

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, Pydantic, pydantic-settings |
| PDF parsing | pdfplumber |
| LLM | Groq API (`openai/gpt-oss-20b`) |
| Auth | Supabase Auth (ES256 JWT, verified via JWKS) |
| Database | Supabase PostgreSQL with Row Level Security |
| Rate limiting | slowapi |
| Frontend | React 18, Vite, plain CSS |
| Testing | pytest (backend), Vitest + React Testing Library (frontend) |
| Containers | Docker + docker-compose (config written; not yet verified on Linux) |

---

## Project structure

```
prepwise/
├── backend/
│   ├── app/
│   │   ├── api/routes/     # health, resume, analyze, history
│   │   ├── core/           # config, limiter, supabase_client
│   │   ├── dependencies/   # auth.py — ES256/JWKS JWT verification
│   │   ├── prompts/        # LLM prompt templates
│   │   ├── schemas/        # Pydantic models
│   │   └── services/       # pdf_service, llm_service, db_service
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/     # AnalyzeForm, ResultView, HistoryView, AuthForm
│   │   ├── context/        # AuthContext (Supabase session)
│   │   ├── App.jsx
│   │   ├── api.js
│   │   └── index.css
│   └── package.json
├── scripts/                # try_analyze.py — manual smoke test
├── docker-compose.yml
├── .env.example
└── .gitignore
```

---

## Local setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- A free [Groq API key](https://console.groq.com)
- A free [Supabase](https://supabase.com) project

### 1. Clone and create your `.env`

```bash
git clone https://github.com/your-username/prepwise.git
cd prepwise
cp .env.example .env
# Fill in GROQ_API_KEY, SUPABASE_URL, SUPABASE_KEY in .env
```

### 2. Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows
# source .venv/bin/activate          # macOS / Linux
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend runs at **http://127.0.0.1:8000**  
Interactive API docs: **http://127.0.0.1:8000/docs**

### 3. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend runs at **http://localhost:5173**

> **Avast / corporate proxy users:** if `npm install` hangs, run once:
> `npm config set strict-ssl false`

### 4. Supabase database schema

Run this in your Supabase **SQL Editor → New query**:

```sql
CREATE TABLE public.profiles (
  id         UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email      TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE public.analyses (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  company_name TEXT NOT NULL,
  -- resume_text and job_description are nullable and intentionally not stored.
  -- Personal data is not persisted beyond what is needed to show history.
  resume_text     TEXT,       -- always NULL; column kept for schema compatibility
  job_description TEXT,       -- always NULL; column kept for schema compatibility
  match_score  INTEGER NOT NULL,
  result_json  JSONB NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_analyses_user_id ON public.analyses(user_id, created_at DESC);
ALTER TABLE public.analyses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own analyses"
  ON public.analyses FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own analyses"
  ON public.analyses FOR INSERT WITH CHECK (auth.uid() = user_id);
```

Then run the auto-profile trigger so a row is created on every signup:

```sql
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  INSERT INTO public.profiles (id, email) VALUES (NEW.id, NEW.email)
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
```

---

## Environment variables

### Backend (root `.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GROQ_API_KEY` | ✅ | — | Groq API key from console.groq.com |
| `GROQ_MODEL` | — | `openai/gpt-oss-20b` | Groq model ID. Change here if Groq retires the model. |
| `MAX_JD_CHARS` | — | `8000` | Max job description characters sent to the LLM |
| `LLM_TIMEOUT_SECONDS` | — | `30` | Seconds before a Groq call times out |
| `LLM_MAX_RETRIES` | — | `2` | Extra retries on bad LLM output |
| `LLM_MAX_TOKENS` | — | `8192` | Max completion tokens (raise if you get empty responses) |
| `LLM_REASONING_EFFORT` | — | `low` | Reasoning effort for gpt-oss models: `low` / `medium` / `high` |
| `SUPABASE_URL` | ✅ | — | Your Supabase project URL (from Settings → General) |
| `SUPABASE_KEY` | ✅ | — | Supabase API key. Use the **legacy `eyJ...` anon key** (Settings → API Keys → "anon" or "legacy"). The newer `sb_publishable_...` format is not supported by the Python SDK used here. |
| `JWKS_CACHE_TTL_SECONDS` | — | `3600` | How long to cache JWKS public keys (seconds) |
| `RATE_LIMIT_ANALYZE` | — | `5/minute` | Max POST /analyze calls per IP per minute |
| `ALLOWED_ORIGINS` | — | `http://localhost:5173` | Comma-separated CORS origins |
| `MAX_UPLOAD_MB` | — | `5` | Max resume PDF size |
| `USE_SYSTEM_CERTS` | — | `false` | Set `true` if antivirus intercepts HTTPS (Avast, Zscaler) |

### Frontend (`frontend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_URL` | ✅ | Backend URL, e.g. `http://127.0.0.1:8000` |
| `VITE_SUPABASE_URL` | ✅ | Same as backend `SUPABASE_URL` |
| `VITE_SUPABASE_ANON_KEY` | ✅ | Same as backend `SUPABASE_KEY` |

---

## Running tests

### Backend (pytest)

```powershell
cd backend
.venv\Scripts\Activate.ps1
pytest tests/ -v
```

Expected: **67 passed**

### Frontend (Vitest)

```powershell
cd frontend
npm test
```

Expected: **26 passed**

---

## API endpoints

All endpoints respond with JSON. Interactive docs at `/docs` when the server is running.

### `GET /health`
Returns `{"status": "ok"}`. No auth required.

---

### `POST /resume/parse`
Parse a resume PDF and return its extracted text. No auth required.

**Form fields:** `file` (PDF, max 5 MB)

**Response:**
```json
{ "text": "...", "page_count": 1, "char_count": 3894 }
```

---

### `POST /analyze`
Analyse a resume against a job description. No auth required.
If a valid Bearer token is provided, the result is saved to history.

**Form fields:** `resume` (PDF), `job_description` (text), `company_name` (text)

**Response:**
```json
{
  "match_score": 72,
  "matched_skills": ["Python", "FastAPI"],
  "skill_gaps": [{ "skill": "Docker", "tip": "..." }],
  "resume_wording_tips": ["Add 'pytest' — resume shows testing activity"],
  "questions": [{ "question": "...", "category": "technical", "answer_outline": "..." }]
}
```

**Error codes:** 400 (bad input/file), 413 (too large), 422 (scanned PDF),
429 (rate limit), 500 (LLM config error), 502 (bad LLM output), 504 (timeout)

---

### `GET /analyses`
Return the authenticated user's saved analyses, newest first. **Requires auth.**

**Headers:** `Authorization: Bearer <token>`  
**Query params:** `limit` (default 20, max 100), `offset` (default 0)

**Response:**
```json
{ "analyses": [{ "id": "uuid", "company_name": "Acme", "match_score": 72, "created_at": "..." }], "total": 1 }
```

---

### `GET /analyses/{analysis_id}`
Return the full stored result for one analysis. **Requires auth.**
Returns 404 if the id is unknown, invalid, or belongs to another user —
existence is never leaked.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "id": "uuid",
  "company_name": "Acme",
  "match_score": 72,
  "created_at": "...",
  "result_json": { ... }
}
```

Note: `resume_text` and `job_description` are never returned — they are
not stored after the analysis completes.

---

## Limitations

**Docker not yet verified on this machine.**
The `Dockerfile` and `docker-compose.yml` are written and correct but have
not been tested locally because hardware virtualisation is disabled in BIOS.
They follow standard multi-stage build patterns and should work on any Linux
host or cloud build system (Render, Railway, GitHub Actions).

**Free hosting cold starts.**
On Render's free tier, the backend spins down after 15 minutes of inactivity.
The first request after a cold start takes 30–60 seconds. This is normal for
free hosting. Upgrade to a paid plan ($7/month) for always-on behaviour.

**Match score is an LLM estimate.**
The score (0–100) is generated by the language model from the prompt rules,
not by a deterministic algorithm. It is a useful signal but not a precise
measurement. Two runs on the same inputs may produce slightly different scores
depending on the model's internal reasoning.

**Question quality depends on the model.**
The LLM is instructed not to invent experience, but it can occasionally
produce generic answer outlines. Always review the outlines for accuracy
against your actual resume before using them in an interview.

**Token expiry is not handled in the frontend.**
Supabase access tokens expire after 1 hour. The Supabase JS client refreshes
them silently in most cases, but if a refresh fails the user will see a
generic "Please log in" error. Refreshing the page resolves it.

**History pagination.**
The backend supports `limit`/`offset` pagination but the frontend fetches
only the first 20 results with no "load more" button.

---

## Security notes

- JWT tokens are verified using ES256 + JWKS (asymmetric signing).
  No shared secret is used. `python-jose` was replaced with `PyJWT 2.15.1`
  after three unpatched CVEs were found in `python-jose 3.3.0`.
- Row Level Security is enabled on the `analyses` table. Users can only
  read and write their own rows, enforced at the database level.
- `resume_text` and `job_description` are **not stored** in the database.
  The columns exist for schema compatibility but are always `NULL`.
- Rate limiting (5 requests/minute per IP by default) protects the Groq
  free-tier quota.

---

## License

MIT — see [LICENSE](LICENSE).
