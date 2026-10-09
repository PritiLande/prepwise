# PrepWise

**AI-powered resume and job analysis platform that helps candidates understand their job fit and prepare for interviews.**

PrepWise analyzes a candidate's resume against a job description and provides an AI-generated match score, matched skills, skill gaps, resume wording suggestions, and tailored interview questions with answer outlines.

## 🚀 Live Demo

* **Frontend:** https://prepwise-frontend-p5b6.onrender.com
* **Backend API:** https://prepwise-backend-cb6i.onrender.com
* **API Documentation:** https://prepwise-backend-cb6i.onrender.com/docs

**Deployment:** Frontend and backend hosted on Render; authentication and database powered by Supabase; AI analysis powered by Groq.

---

## 🎯 What Problem Does PrepWise Solve?

Job seekers often apply to many positions without knowing:

* How closely their resume matches the job
* Which skills they are missing
* Which parts of their resume could be improved
* What questions they may be asked in an interview

PrepWise turns a resume and job description into a practical preparation report.

### Input

**Resume PDF + Job Description + Company Name**

### Output

**Match Score → Matched Skills → Skill Gaps → Resume Tips → Interview Questions**

---

## ✨ Key Features

### 🤖 AI-Powered Resume Analysis

* Extracts text from uploaded PDF resumes
* Compares resume content with a job description
* Uses Groq LLM for intelligent analysis
* Produces a match score from 0–100

### 📊 Skill Gap Analysis

* Identifies skills already present in the resume
* Highlights missing or weak skills
* Provides suggestions for improving job readiness

### 📝 Resume Improvement

* Generates targeted resume wording suggestions
* Suggestions are based on the job description and existing resume content

### 🎤 Interview Preparation

* Generates 10 tailored interview questions
* Questions are categorized by type
* Provides answer outlines without intentionally inventing candidate experience

### 🔐 Authentication

* Supabase authentication
* JWT verification using ES256 + JWKS
* Protected history endpoints
* User-specific analysis access

### 📚 Analysis History

Authenticated users can:

* View previous analyses
* Open an individual analysis
* See company name, match score, and analysis results

### 🛡️ Security

* Supabase Row Level Security
* User-level database access control
* JWT validation
* API rate limiting
* Secrets stored in environment variables
* Resume and job-description content is not persisted after analysis

### 🧪 Automated Testing

* Backend: **67 tests passing**
* Frontend: **26 tests passing**
* **Total: 93 automated tests passing**

---

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

---

## 🛠️ Tech Stack

| Layer                       | Technology                     |
| --------------------------- | ------------------------------ |
| Backend                     | Python 3.11+, FastAPI          |
| Validation                  | Pydantic                       |
| Configuration               | pydantic-settings              |
| PDF Parsing                 | pdfplumber                     |
| AI / LLM                    | Groq API                       |
| Authentication              | Supabase Auth                  |
| JWT Verification            | PyJWT + JWKS                   |
| Database                    | Supabase PostgreSQL            |
| Database Security           | Row Level Security             |
| Rate Limiting               | slowapi                        |
| Frontend                    | React 18                       |
| Build Tool                  | Vite                           |
| Styling                     | CSS                            |
| Backend Testing             | pytest                         |
| Frontend Testing            | Vitest + React Testing Library |
| Containers                  | Docker + Docker Compose        |
| Backend Deployment          | Render (Docker)                |
| Frontend Deployment         | Render                         |

---

## 🏗️ Architecture

### Backend

The FastAPI backend is responsible for:

* Resume PDF validation and parsing
* Job-description processing
* LLM communication
* Structured response validation
* Authentication and authorization
* Analysis history
* Rate limiting
* API error handling

### Frontend

The React frontend provides:

* Authentication
* Resume upload
* Job-description input
* Analysis results
* Match score display
* Skill-gap display
* Resume improvement suggestions
* Interview questions
* Analysis history

### Database

Supabase PostgreSQL stores authenticated-user analysis history.

Row Level Security ensures users can only access their own saved analyses.

---

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

---

# 🚀 Getting Started

## Prerequisites

Install:

* Python 3.11+
* Node.js 18+
* Git
* A Groq API key
* A Supabase project

---

## 1. Clone the Repository

```bash
git clone https://github.com/PritiLande/prepwise.git
cd prepwise
```

Create your local environment file:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Add your local API credentials to `.env`.

**Never commit `.env` to GitHub.**

---

# ⚙️ Backend Setup

Move into the backend directory:

```powershell
cd backend
```

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Start the FastAPI server:

```powershell
uvicorn app.main:app --reload
```

Backend:

```text
http://127.0.0.1:8000
```

Interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

---

# 💻 Frontend Setup

Open another terminal and move to:

```powershell
cd frontend
```

Install dependencies:

```powershell
npm install
```

Start the development server:

```powershell
npm run dev
```

Frontend:

```text
http://localhost:5173
```

---

# 🗄️ Supabase Setup

Create a Supabase project and configure authentication and PostgreSQL.

The application uses:

* Supabase Auth
* Supabase PostgreSQL
* Row Level Security
* User profiles
* Analysis history

### Database tables

```text
profiles
analyses
```

The `analyses` table stores:

* Analysis ID
* User ID
* Company name
* Match score
* Structured analysis result
* Creation timestamp

Resume text and job-description text are not persisted after analysis.

### Row Level Security

Analysis records are protected using PostgreSQL Row Level Security.

Users can only:

* Read their own analyses
* Insert analyses belonging to their own user ID

---

# 🔑 Environment Variables

## Backend

The backend uses a root `.env` file.

```text
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-20b

SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_api_key

RATE_LIMIT_ANALYZE=5/minute
MAX_UPLOAD_MB=5

ALLOWED_ORIGINS=http://localhost:5173,https://prepwise-frontend-p5b6.onrender.com
```

Additional configuration is available in `.env.example`.

## Frontend

Create:

```text
frontend/.env
```

Example:

```text
VITE_API_URL=http://127.0.0.1:8000
VITE_SUPABASE_URL=your_supabase_project_url
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
```

For production, set `VITE_API_URL` to `https://prepwise-backend-cb6i.onrender.com` in the Render frontend environment settings. The backend's `ALLOWED_ORIGINS` configuration must include `https://prepwise-frontend-p5b6.onrender.com`.


---

# 🧪 Testing

PrepWise currently has **93 automated tests**, all passing.

## Backend

From the `backend` directory:

```powershell
.venv\Scripts\Activate.ps1
pytest tests/ -v
```

Current verified result:

```text
67 passed
```

## Frontend

From the `frontend` directory:

```powershell
npm test
```

Current verified result:

```text
26 passed
```

### Total

```text
Backend:   67 passed
Frontend:  26 passed
----------------------
Total:     93 passed
```

---

# 🔌 API Endpoints

## Health

```http
GET /health
```

Returns:

```json
{
  "status": "ok"
}
```

No authentication required.

---

## Resume Parsing

```http
POST /resume/parse
```

Accepts a PDF resume and extracts its text.

Example response:

```json
{
  "text": "...",
  "page_count": 1,
  "char_count": 3894
}
```

---

## Resume & Job Analysis

```http
POST /analyze
```

Inputs:

* Resume PDF
* Job description
* Company name

Example response:

```json
{
  "match_score": 72,
  "matched_skills": [
    "Python",
    "FastAPI"
  ],
  "skill_gaps": [
    {
      "skill": "Docker",
      "tip": "..."
    }
  ],
  "resume_wording_tips": [
    "..."
  ],
  "questions": [
    {
      "question": "...",
      "category": "technical",
      "answer_outline": "..."
    }
  ]
}
```

---

## Analysis History

```http
GET /analyses
```

Requires authentication.

Returns the authenticated user's saved analyses.

Supports:

```text
limit
offset
```

---

## Analysis Details

```http
GET /analyses/{analysis_id}
```

Requires authentication.

Returns the full stored result for an analysis belonging to the authenticated user.

An invalid, unknown, or another user's analysis ID returns `404`.

---

# 🐳 Docker

The project includes Docker configuration for the backend and local full-stack development.

```text
backend/Dockerfile
frontend/Dockerfile
docker-compose.yml
```

**Production deployment:** The FastAPI backend is deployed on Render using Docker.

**Local development:** Docker Compose configuration is included for running the application in containers. Local Docker Compose execution has not been verified on the development machine because hardware virtualization is disabled.

The production backend deployment is verified, but local Docker Compose execution should be tested separately.

--

# ☁️ Deployment

PrepWise is deployed and accessible online.

* **Frontend:** React + Vite, hosted on Render
* **Backend:** FastAPI, hosted on Render using Docker
* **Authentication and Database:** Supabase Auth and PostgreSQL
* **AI Analysis:** Groq API

### Live Deployment URLs

* **Frontend:** https://prepwise-frontend-p5b6.onrender.com
* **Backend API:** https://prepwise-backend-cb6i.onrender.com
* **API Documentation:** https://prepwise-backend-cb6i.onrender.com/docs

### Production Environment Configuration

The application uses environment variables to configure API access, authentication, database connectivity, AI integration, upload limits, and rate limiting.

Configure the required environment variables in the relevant Render service settings. Keep secret values, including API keys and JWT secrets, private. Never commit real credentials to GitHub.

For local development, use the project's environment example file and configure your own credentials.


### Production architecture

```text### Production architecture

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

The deployed backend will require:

```text
GROQ_API_KEY
GROQ_MODEL
SUPABASE_URL
SUPABASE_KEY
ALLOWED_ORIGINS
```

The Render frontend requires the following environment variables:

```text
VITE_API_URL
VITE_SUPABASE_URL
VITE_SUPABASE_ANON_KEY
```

After deployment, the production URLs will be added to this README.

---

# 🔐 Security

PrepWise includes several security measures:

### JWT Authentication

Supabase JWTs are verified using:

```text
ES256 + JWKS
```

The backend does not rely on a shared JWT secret.

### Row Level Security

Supabase PostgreSQL Row Level Security restricts analysis history to the authenticated user.

### Rate Limiting

The `/analyze` endpoint is protected by IP-based rate limiting.

Default:

```text
5 requests/minute
```

### Input Validation

The API validates:

* File type
* File size
* Empty job descriptions
* PDF content
* LLM response structure
* Match-score range
* Interview-question count
* Answer-outline length

### Secrets

API keys and credentials are stored in environment variables.

The repository contains `.env.example` but does not contain the real `.env`.

---

# 📌 Current Limitations

### AI-generated match score

The match score is an LLM-generated estimate rather than a deterministic scoring algorithm.

It should be treated as a useful signal rather than an exact measurement.

### AI-generated interview answers

The system attempts to avoid inventing candidate experience, but generated answer outlines should still be reviewed against the candidate's actual background.

### Free hosting

The planned Render free deployment may experience cold starts after inactivity.

### History pagination

The backend supports pagination through `limit` and `offset`, while the current frontend displays the first page of results.

### Token refresh

Supabase handles token refresh in most cases, but a failed refresh may require the user to log in again.

---

# 🧠 What I Built

PrepWise was built as a full-stack AI application combining:

* Python
* FastAPI
* React
* Groq LLM
* Supabase
* PostgreSQL
* JWT authentication
* Row Level Security
* REST APIs
* PDF processing
* Automated testing
* Docker configuration

The project covers the complete flow from **frontend input → backend processing → AI analysis → structured response → database persistence → frontend presentation**.

---

# 📚 Key Engineering Concepts Demonstrated

* REST API development
* FastAPI dependency injection
* Pydantic validation
* JWT authentication
* JWKS-based token verification
* PostgreSQL
* Row Level Security
* LLM API integration
* Prompt engineering
* Structured LLM output validation
* PDF text extraction
* API rate limiting
* Error handling
* React component architecture
* Authentication state management
* Automated testing
* Docker
* Environment-based configuration
* Git/GitHub workflow
* Cloud deployment architecture

---

# 📄 License

MIT License

See [LICENSE](LICENSE).

---

## 👩‍💻 Author

**Priti Lande**

GitHub: [PritiLande](https://github.com/PritiLande)

---

⭐ If you find PrepWise useful, consider starring the repository.
