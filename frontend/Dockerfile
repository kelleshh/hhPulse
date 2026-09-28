# syntax=docker/dockerfile:1.7

ARG NODE_IMAGE=node:24-alpine
ARG NGINX_IMAGE=nginxinc/nginx-unprivileged:1.27-alpine

FROM ${NODE_IMAGE} AS build

ENV NODE_OPTIONS=--dns-result-order=ipv4first

WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,id=hhpulse-npm-cache,target=/root/.npm,sharing=locked \
    npm ci --omit=dev --prefer-offline --no-audit --no-fund

COPY index.html tsconfig.json tsconfig.app.json tsconfig.node.json vite.config.ts ./
COPY src ./src
ARG VITE_DATA_MODE=api
ARG VITE_API_BASE_URL=
ENV VITE_DATA_MODE=${VITE_DATA_MODE}
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM ${NGINX_IMAGE} AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
STOPSIGNAL SIGQUIT
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/"]
