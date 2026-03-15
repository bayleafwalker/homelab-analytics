FROM node:20-alpine AS deps

WORKDIR /app

COPY apps/web/frontend/package.json apps/web/frontend/package-lock.json ./
RUN npm ci

FROM node:20-alpine AS builder

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY apps/web/frontend ./
RUN npm run build

FROM node:20-alpine AS runner

ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
ENV PORT=8081
ENV HOMELAB_ANALYTICS_API_BASE_URL=http://api:8080

WORKDIR /app

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 8081

CMD ["node", "server.js"]
