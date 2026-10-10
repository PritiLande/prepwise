# PrepWise

AI-powered resume and job analysis platform that helps candidates understand their job fit and prepare for interviews.

PrepWise analyzes a candidate's resume against a job description and provides an AI-generated match score, matched skills, skill gaps, resume wording suggestions, and tailored interview questions with answer outlines.

<!--
SCREENSHOTS: add 2-3 images or a short GIF to docs/screenshots/ and uncomment below.

![PrepWise results page](docs/screenshots/results.png)
![PrepWise analysis history](docs/screenshots/history.png)
-->

## 🚀 Live Demo

- **Frontend:** https://prepwise-frontend-p5b6.onrender.com
- **Backend API:** https://prepwise-backend-cb6i.onrender.com
- **API Documentation:** https://prepwise-backend-cb6i.onrender.com/docs

> **Note:** Both services run on Render's free tier, so the first request after a period of inactivity can take 30-60 seconds (cold start). Please give it a moment on first load.

**Deployment:** Frontend and backend are hosted on Render; authentication and database are powered by Supabase; AI analysis is powered by Groq.

## 🎯 What Problem Does PrepWise Solve?

Job seekers often apply to many positions without knowing:

- How closely their resume matches the job
- Which skills they are missing
- Which parts of their resume could be improved
- What questions they may be asked in an interview

PrepWise turns a resume and job description into a practical preparation report.

**Input:** Resume PDF + Job Description + Company Name

**Output:** Match Score → Matched Skills → Skill Gaps → Resume Tips → Interview Questions

## ✨ Key Features

### 🤖 AI-Powered Resume Analysis
- Extracts text from uploaded PDF resumes
- Compares resume content with a job description
- Uses a Groq-hosted LLM for analysis
- Produces a match score from 0-100

### 📊 Skill Gap Analysis
- Identifies skills already present in the resume
- Highlights missing or weak skills
- Provides suggestions for improving job readiness

### 📝 Resume Improvement
- Generates targeted resume wording suggestions
- Suggestions are based on the job description and existing resume content

### 🎤 Interview Preparation
- Generates 10 tailored interview questions
- Questions are categorized by type
- Provides answer outlines without intentionally inventing candidate experience

### 🔐 Authentication
- Supabase authentication
- JWT verification using ES256 + JWKS
- Protected history endpoints
- User-specific analysis access

### 📚 Analysis History
Authenticated users can:
- View previous analyses
- Open an individual analysis
- See company name, match score, and analysis results

### 🧪 Automated Testing
- Backend: 67 tests passing
- Frontend: 26 tests passing
- **Total: 93 automated tests passing**

## 🔄 How PrepWise Works

```text
                Resume PDF
                    │
                    ▼
             PDF Text Extraction
                    │
                    ▼
              FastAPI Backend
                    │
       ┌────────────┴────────────┐
       │                         │
       ▼                         ▼
 Job Description             Company Name
       │                         │
       └────────────┬────────────┘
                    ▼
                 Groq LLM
                    │
                    ▼
          Structured AI Analysis
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
   Match Score   Skill Gaps   Resume Tips
                    │
                    ▼
          Interview Questions
                    │
                    ▼
             React Frontend
                    │
                    ▼
          Supabase History
```

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI |
| Validation | Pydantic |
| Configuration | pydantic-settings |
| PDF Parsing | pdfplumber |
| AI / LLM | Groq API |
| Authentication | Supabase Auth |
| JWT Verification | PyJWT + JWKS |
| Database | Supabase PostgreSQL |
| Database Security | Row Level Security |
| Rate Limiting | slowapi |
| Frontend | React 18 |
| Build Tool | Vite |
| Styling | CSS |
| Backend Testing | pytest |
| Frontend Testing | Vitest + React Testing Library |
| Containers | Docker + Docker Compose |
| Backend Deployment | Render (Docker) |
| Frontend Deployment | Render |

## 🏗️ Architecture

### Backend
The FastAPI backend is responsible for:
- Resume PDF validation and parsing
- Job-description processing
- LLM communication
- Structured response validation
- Authentication and authorization
- Analysis history
- Rate limiting
- API error handling

### Frontend
The React frontend provides:
- Authentication
- Resume upload and job-description input
- Analysis results: match score, skill gaps, resume suggestions, interview questions
- Analysis history

### Database
Supabase PostgreSQL stores authenticated-user analysis history. Row Level Security ensures users can only access their own saved analyses.

## 📁 Project Structure

```text
prepwise/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/
│   │   ├── core/
│   │   ├── dependencies/
│   │   ├── prompts/
│   │   ├── schemas/
│   │   └── services/
│   ├── tests/
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── context/
│   │   ├── __tests__/
│   │   ├── App.jsx
│   │   ├── api.js
│   │   └── index.css
│   └── package.json
│
├── scripts/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Git
- A Groq API key
- A Supabase project

### 1. Clone the repository

```bash
git clone https://github.com/PritiLande/prepwise.git
cd prepwise
```

### 2. Configure environment variables

The repository includes a root-level `.env.example` for the backend. Copy it to `.env` in the project root and fill in your own values (see [Environment Variables](#-environment-variables)).

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Git Bash, macOS, or Linux:

```bash
cp .env.example .env
```

The frontend uses its own `frontend/.env` file, described in [Environment Variables](#-environment-variables).

> **Security:** Never commit `.env` files, API keys, or other secrets to GitHub.

## ⚙️ Backend Setup

From the project root:

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment:

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Make sure the backend environment variables for Groq and Supabase are configured (see [Environment Variables](#-environment-variables)), then start the server:

```bash
uvicorn app.main:app --reload
```

- Backend: http://127.0.0.1:8000
- Interactive API docs: http://127.0.0.1:8000/docs

## 💻 Frontend Setup

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5173

## 🗄️ Supabase Setup

Create a Supabase project and configure authentication and PostgreSQL.

The application uses Supabase Auth, Supabase PostgreSQL, and Row Level Security, with two tables:

- `profiles`
- `analyses`

The `analyses` table stores:
- Analysis ID
- User ID
- Company name
- Match score
- Structured analysis result
- Creation timestamp

Resume text and job-description text are **not persisted** after analysis.

### Row Level Security

Analysis records are protected using PostgreSQL Row Level Security. Users can only:
- Read their own analyses
- Insert analyses belonging to their own user ID

## 🔑 Environment Variables

### Backend

The backend reads a root-level `.env` file:

```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-20b

SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_api_key

RATE_LIMIT_ANALYZE=5/minute
MAX_UPLOAD_MB=5

ALLOWED_ORIGINS=http://localhost:5173,https://prepwise-frontend-p5b6.onrender.com
```

Additional configuration is available in `.env.example`.

### Frontend

Create `frontend/.env`:

```env
VITE_API_URL=http://127.0.0.1:8000
VITE_SUPABASE_URL=your_supabase_project_url
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
```

For production, set `VITE_API_URL` to `https://prepwise-backend-cb6i.onrender.com` in the Render frontend environment settings. The backend's `ALLOWED_ORIGINS` must include `https://prepwise-frontend-p5b6.onrender.com`.

## 🧪 Testing

PrepWise has 93 automated tests, all passing.

**Backend** (from the `backend` directory, with the virtual environment active):

```bash
pytest tests/ -v
```

Verified result: **67 passed**

**Frontend** (from the `frontend` directory):

```bash
npm test
```

Verified result: **26 passed**

```text
Backend:   67 passed
Frontend:  26 passed
----------------------
Total:     93 passed
```

## 🔌 API Endpoints

### Health

`GET /health`: no authentication required.

```json
{
  "status": "ok"
}
```

### Resume Parsing

`POST /resume/parse`: accepts a PDF resume and extracts its text.

```json
{
  "text": "...",
  "page_count": 1,
  "char_count": 3894
}
```

### Resume & Job Analysis

`POST /analyze`

Inputs: resume PDF, job description, company name.

```json
{
  "match_score": 72,
  "matched_skills": ["Python", "FastAPI"],
  "skill_gaps": [
    {
      "skill": "Docker",
      "tip": "..."
    }
  ],
  "resume_wording_tips": ["..."],
  "questions": [
    {
      "question": "...",
      "category": "technical",
      "answer_outline": "..."
    }
  ]
}
```

### Analysis History

`GET /analyses`: requires authentication. Returns the authenticated user's saved analyses. Supports `limit` and `offset`.

### Analysis Details

`GET /analyses/{analysis_id}`: requires authentication. Returns the full stored result for an analysis belonging to the authenticated user. An invalid, unknown, or another user's analysis ID returns `404`.

## 🐳 Docker

The project includes Docker configuration for the backend and local full-stack development:

- `backend/Dockerfile`
- `frontend/Dockerfile`
- `docker-compose.yml`

**Production:** the FastAPI backend is deployed on Render using Docker, and this deployment is verified.

**Local development:** Docker Compose configuration is included for running the app in containers. Local Docker Compose execution has not been verified on the development machine because hardware virtualization is disabled, so it should be tested separately.

## ☁️ Deployment

PrepWise is deployed and accessible online.

- **Frontend:** React + Vite, hosted on Render
- **Backend:** FastAPI, hosted on Render using Docker
- **Authentication and database:** Supabase Auth and PostgreSQL
- **AI analysis:** Groq API

### Production architecture

```text
                 User
                   │
                   ▼
                Render
             React Frontend
                   │
                   │ HTTPS
                   ▼
                Render
             FastAPI Backend
                   │
          ┌────────┴────────┐
          ▼                 ▼
      Supabase            Groq API
   Auth + PostgreSQL    AI Analysis
```

### Production environment variables

The deployed backend requires:
- `GROQ_API_KEY`
- `GROQ_MODEL`
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `ALLOWED_ORIGINS`

The Render frontend requires:
- `VITE_API_URL`
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`

Set these in the relevant Render service settings. Keep secret values private and never commit real credentials to GitHub.

## 🔐 Security

PrepWise includes several security measures:

- **JWT authentication:** Supabase JWTs are verified using ES256 + JWKS. The backend does not rely on a shared JWT secret.
- **Row Level Security:** PostgreSQL RLS restricts analysis history to the authenticated user.
- **Rate limiting:** the `/analyze` endpoint is protected by IP-based rate limiting (default: 5 requests/minute).
- **Input validation:** the API validates file type, file size, empty job descriptions, PDF content, LLM response structure, match-score range, interview-question count, and answer-outline length.
- **Secrets:** API keys and credentials live in environment variables. The repository contains `.env.example` but not the real `.env`.
- **Privacy:** resume and job-description content is not persisted after analysis.

## 📌 Current Limitations

- **AI-generated match score:** the score is an LLM-generated estimate rather than a deterministic algorithm. Treat it as a useful signal, not an exact measurement.
- **AI-generated interview answers:** the system tries to avoid inventing candidate experience, but answer outlines should still be reviewed against your actual background.
- **Free hosting:** the Render free tier may cause cold starts after inactivity.
- **History pagination:** the backend supports `limit` and `offset`, but the frontend currently displays only the first page of results.
- **Token refresh:** Supabase handles token refresh in most cases, but a failed refresh may require logging in again.

## 🧠 What I Built

PrepWise is a full-stack AI application covering the complete flow from frontend input → backend processing → AI analysis → structured response → database persistence → frontend presentation.

**Key engineering concepts demonstrated:**

- REST API development
- FastAPI dependency injection
- Pydantic validation
- JWT authentication and JWKS-based token verification
- PostgreSQL and Row Level Security
- LLM API integration and prompt engineering
- Structured LLM output validation
- PDF text extraction
- API rate limiting and error handling
- React component architecture and authentication state management
- Automated testing (pytest, Vitest)
- Docker and environment-based configuration
- Git/GitHub workflow
- Cloud deployment architecture

## 📄 License

MIT License. See [LICENSE](LICENSE).

## 👩‍💻 Author

**Priti Lande**

GitHub: [PritiLande](https://github.com/PritiLande)

---

⭐ If you find PrepWise useful, consider starring the repository.
