from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# __file__ is the absolute path of this config.py file.
# .parent goes up to app/core/, .parent again to app/, .parent to backend/,
# .parent once more to the project root (prepwise/).
# This means .env is found correctly no matter which folder you run uvicorn from.
_ENV_FILE = Path(__file__).parent.parent.parent.parent / ".env"


class Settings(BaseSettings):
    # pydantic-settings reads variables from a .env file automatically.
    # We pass the absolute path so it never depends on the working directory.
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    # APP_NAME is just a friendly label for our API.
    # The value on the right is the default if the variable isn't in .env.
    APP_NAME: str = "Prepwise"

    # DEBUG controls whether FastAPI shows detailed error pages.
    DEBUG: bool = False

    # Maximum allowed upload size in megabytes.
    # Keeping this low protects the server from memory exhaustion.
    MAX_UPLOAD_MB: int = 5

    # Maximum number of characters we store from a resume.
    # Resumes longer than this are truncated before we process them.
    MAX_RESUME_CHARS: int = 20000

    # -----------------------------------------------------------------------
    # Groq / LLM settings
    # -----------------------------------------------------------------------

    # The secret key from console.groq.com — must live in .env, never in code.
    # Optional[str] with a None default lets the app start without it;
    # llm_service.py raises a clear error if it is missing at call time.
    GROQ_API_KEY: str = ""

    # Model name is read from .env so we can swap it without editing code.
    # Groq retires models often — keeping this in .env means a one-line fix
    # instead of a code change and redeployment.
    GROQ_MODEL: str = "openai/gpt-oss-20b"

    # Maximum characters from the job description sent to the LLM.
    # JDs can be long; this keeps token costs predictable.
    MAX_JD_CHARS: int = 8000

    # How long (seconds) to wait for Groq before giving up.
    LLM_TIMEOUT_SECONDS: int = 30

    # How many extra attempts after the first failure before raising an error.
    LLM_MAX_RETRIES: int = 2

    # Maximum tokens for the LLM completion (reasoning + reply combined).
    # Some models spend many tokens on internal chain-of-thought reasoning
    # before producing visible output, so this must be generous.
    LLM_MAX_TOKENS: int = 8192

    # -----------------------------------------------------------------------
    # Rate limiting
    # -----------------------------------------------------------------------

    # How many calls one IP address can make to POST /analyze per minute.
    # Keeps Groq free-tier costs predictable and prevents abuse.
    RATE_LIMIT_ANALYZE: str = "5/minute"

    # Set to true if your machine's antivirus or corporate proxy intercepts
    # HTTPS and presents its own certificate (e.g. Avast, Zscaler, Fiddler).
    # When true, main.py calls truststore.inject_into_ssl() at startup so
    # Python uses the OS certificate store instead of its own bundled CA bundle.
    # Leave false in production cloud environments — they use standard certs.
    USE_SYSTEM_CERTS: bool = False


# Create a single shared instance so every module imports the same object.
settings = Settings()
