# 사내 폐쇄망이라면 FROM 주소를 사내 레지스트리 미러로 바꾸세요.
FROM node:20-alpine AS builder
WORKDIR /srv

# 사내 npm 미러(Nexus 등)를 쓸 때:
#   docker compose build --build-arg NPM_REGISTRY=https://nexus.내부/repository/npm/
ARG NPM_REGISTRY=""
RUN if [ -n "$NPM_REGISTRY" ]; then npm config set registry "$NPM_REGISTRY"; fi

COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /srv
ENV NODE_ENV=production PORT=3000
COPY --from=builder /srv/.next/standalone ./
COPY --from=builder /srv/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
