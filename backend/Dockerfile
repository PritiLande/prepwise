# ── Stage 1: builder ────────────────────────────────────────────────────────
# WHY two stages?
#   Stage 1 (builder) installs all packages including build tools.
#   Stage 2 (final) copies only what's needed to run the app.
#   This keeps the final image small — no compilers or pip caches included.

FROM python:3.11-slim AS builder

# Set a working directory inside the container.
# All subsequent commands run from here.
WORKDIR /app

# Copy only requirements first — before the rest of the code.
# WHY? Docker caches each instruction as a layer. If requirements.txt hasn't
# changed, Docker reuses the cached layer and skips reinstalling packages.
# This makes rebuilds much faster when you only changed Python source files.
COPY requirements.txt .

# Install packages into a local directory (/app/wheels) so we can copy
# them cleanly into the final stage.
RUN pip install --upgrade pip \
 && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: final runtime image ────────────────────────────────────────────

FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from the builder stage
COPY --from=builder /install /usr/local

# Copy the application source code
COPY app/ ./app/

# The app reads .env from the project root. In production (Docker) we pass
# all secrets as environment variables instead of a .env file, so we don't
# need to COPY .env here — that would bake secrets into the image.

# Tell Python not to write .pyc files (not useful in a container)
ENV PYTHONDONTWRITEBYTECODE=1
# Tell Python not to buffer stdout/stderr — logs appear in real time
ENV PYTHONUNBUFFERED=1

# Expose port 8000 so docker-compose and the host can reach the server.
# EXPOSE is documentation — it doesn't actually open the port by itself.
EXPOSE 8000

# Start the FastAPI server.
# --host 0.0.0.0 means "listen on all network interfaces inside the container"
# so requests from outside (the host machine) can reach it.
# Without this it would only listen on localhost inside the container.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
