# ============================================================
# FinSage-Lite Frontend — Multi-stage Dockerfile
# Stage "development" : Vite dev server with hot-reload
# Stage "builder"     : Static production build
# Stage "production"  : nginx serving dist/
# ============================================================

# ── Stage 1: development ────────────────────────────────────
FROM node:20-alpine AS development

WORKDIR /app

# npm install (not ci) so the stage works even before package-lock.json is
# committed to git. A lock file is generated here and inherited by builder.
COPY package*.json ./
RUN npm install

# Copy source (overridden by volume mount in docker-compose dev)
COPY . .

EXPOSE 5173

# --host exposes to the Docker network (required)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ── Stage 2: builder ────────────────────────────────────────
# Inherits installed node_modules from development — just run the build.
FROM development AS builder

RUN npm run build

# ── Stage 3: production ─────────────────────────────────────
FROM nginx:alpine AS production

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# SPA + API proxy config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
