# ── Stage 1: builder ────────────────────────────────────────────────────────
# Build the static React app (HTML, CSS, JS files in /dist).

FROM node:20-slim AS builder

WORKDIR /app

# Copy package files first so npm install is cached separately from source.
# If only src/ changes, Docker reuses the cached node_modules layer.
COPY package.json package-lock.json ./

# Install ALL dependencies (including devDependencies like vite).
# --frozen-lockfile ensures we use exactly the versions in package-lock.json.
RUN npm ci --frozen-lockfile

# Copy the rest of the source code
COPY . .

# Vite needs the env variables at BUILD time to bake VITE_* values into
# the JS bundle. We pass them as build args and convert to env vars.
# The values come from docker-compose.yml → build → args.
ARG VITE_API_URL
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY

ENV VITE_API_URL=$VITE_API_URL
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL
ENV VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY

# Build the production bundle — outputs to /app/dist
RUN npm run build


# ── Stage 2: production web server ──────────────────────────────────────────
# Serve the static /dist files with nginx — a lightweight, fast web server.
# WHY nginx instead of Vite's preview server?
#   Vite's preview is for local testing only, not production traffic.
#   nginx handles caching headers, gzip, and high concurrency properly.

FROM nginx:1.27-alpine

# Remove the default nginx placeholder page
RUN rm -rf /usr/share/nginx/html/*

# Copy our built app into the nginx web root
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy a custom nginx config that handles React's client-side routing.
# WHY needed? React is a Single Page App — every URL (/analyses, /history)
# is handled by React, not by real files on disk. Without this config,
# nginx would return 404 for any URL that isn't /index.html.
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# nginx starts automatically — no CMD needed (the base image provides it)
