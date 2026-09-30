# Prepwise

An AI-powered interview prep web app. Upload a resume PDF and paste a job description — Prepwise returns a match score, skill gaps, and tailored interview questions.

## Project Structure

```
prepwise/
├── backend/        # Python / FastAPI API
│   ├── app/
│   │   ├── api/routes/   # Route handlers
│   │   ├── core/         # Config and shared utilities
│   │   └── main.py       # App entry point
│   ├── tests/            # pytest tests
│   └── requirements.txt
├── frontend/       # React + Vite (coming later)
├── .env.example    # Template for environment variables
└── .gitignore
```

## Running the Backend (Phase 1)

### 1. Create and activate the virtual environment

```powershell
cd C:\dev\prepwise\backend
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Create your .env file

```powershell
Copy-Item ..\\.env.example ..\.env
```

### 4. Start the server

```powershell
uvicorn app.main:app --reload
```

Visit http://127.0.0.1:8000/health — you should see `{"status": "ok"}`.

### 5. Run the tests

```powershell
pytest tests/ -v
```

---

## API Endpoints

### GET /health
Returns `{"status": "ok"}` — confirms the server is running.

### POST /resume/parse
Upload a resume PDF and receive its extracted text.

**Request** — multipart form-data:
| Field | Type | Description |
|-------|------|-------------|
| file  | PDF file | Resume, max 5 MB |

**Success response (200):**
```json
{
  "text": "John Doe\nSkills: Python, FastAPI ...",
  "page_count": 2,
  "char_count": 1340
}
```

**Error responses:**
| Code | Reason |
|------|--------|
| 400  | Not a PDF, corrupt file, or password-protected |
| 413  | File exceeds MAX_UPLOAD_MB (default 5 MB) |
| 422  | PDF opened but contains no extractable text (scanned image) |

**Example with curl:**
```bash
curl -X POST http://127.0.0.1:8000/resume/parse \
  -F "file=@my_resume.pdf"
```

**Example with PowerShell:**
```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/resume/parse `
  -Method Post `
  -Form @{ file = Get-Item "my_resume.pdf" }
```

Interactive docs are available at http://127.0.0.1:8000/docs while the server is running.

---

### POST /analyze
Upload a resume PDF and a job description to get the full AI analysis.

**Request** — multipart form-data:
| Field | Type | Limit |
|-------|------|-------|
| resume | PDF file | max 5 MB |
| job_description | text | max 8000 chars |
| company_name | text | 1–100 chars |

**Success response (200):**
```json
{
  "match_score": 75,
  "matched_skills": ["Python", "FastAPI"],
  "skill_gaps": [
    {"skill": "Docker", "tip": "Learn Docker basics by containerising one of your projects."}
  ],
  "resume_wording_tips": [
    "Add 'pytest' to your skills section — your resume already mentions automated tests."
  ],
  "questions": [
    {
      "question": "Walk me through a FastAPI project you built.",
      "category": "technical",
      "answer_outline": "Refer to Project X: endpoints, Pydantic models, JWT auth..."
    }
  ]
}
```

**Error responses:**
| Code | Reason |
|------|--------|
| 400 | Not a PDF, corrupt/password-protected file, empty JD, company name too long |
| 413 | File exceeds MAX_UPLOAD_MB (default 5 MB) |
| 422 | PDF has no extractable text (scanned image) |
| 429 | Rate limit exceeded (default 5 requests/minute per IP) |
| 500 | AI service misconfigured (missing key or decommissioned model) |
| 502 | AI service returned an unexpected response |
| 504 | AI service timed out or unreachable |

**Example with curl:**
```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -F "resume=@my_resume.pdf" \
  -F "job_description=We need a Python backend engineer with FastAPI and Docker." \
  -F "company_name=Acme Corp"
```

**Example with PowerShell (after starting the server):**
```powershell
$form = @{
    resume         = Get-Item "Resume.pdf"
    job_description = "We need a Python backend engineer with FastAPI and Docker."
    company_name   = "Acme Corp"
}
Invoke-RestMethod -Uri http://127.0.0.1:8000/analyze -Method Post -Form $form
```

---

## Groq API Setup (Phase 3)

### 1. Get a free API key
Go to [console.groq.com](https://console.groq.com), sign up, and create an API key.

### 2. Add it to your .env
```
GROQ_API_KEY=gsk_your_real_key_here
GROQ_MODEL=openai/gpt-oss-20b
```
`GROQ_MODEL` is kept in `.env` — not hardcoded — because Groq retires models
regularly (e.g. `llama3-8b-8192` was decommissioned in 2026). When that
happens you only need to change this one line; no code edit, no redeployment.
Current models: https://console.groq.com/docs/models

### 3. Try the analysis service manually
```powershell
cd C:\dev\prepwise\backend
.venv\Scripts\Activate.ps1

# Usage: python ..\scripts\try_analyze.py <resume.pdf> <jd.txt> "Company Name"
python ..\scripts\try_analyze.py my_resume.pdf job_description.txt "Acme Corp"
```
The script parses the PDF, calls Groq, and prints the full JSON analysis.

> The key is read from `.env` — never commit that file.
