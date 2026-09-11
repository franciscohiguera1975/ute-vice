# =====================================================================
# Frontend UTE-VICE — imagen multietapa
# =====================================================================
ARG NODE_VERSION=22

FROM node:${NODE_VERSION}-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

# ------------------------- development -------------------------------
FROM node:${NODE_VERSION}-alpine AS development
WORKDIR /app
ENV NODE_ENV=development
COPY --from=deps /app/node_modules ./node_modules
COPY . .
EXPOSE 4200
# --poll: los cambios en un volumen montado no siempre emiten eventos inotify.
CMD ["npm", "start"]

# --------------------------- builder ---------------------------------
FROM node:${NODE_VERSION}-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# -------------------------- production -------------------------------
FROM nginx:1.27-alpine AS production
COPY --from=builder /app/dist/ute-vice/browser /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
