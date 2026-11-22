FROM node:26-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# Used by docker-compose.yml for local development (Vite dev server + HMR).
FROM deps AS dev
COPY . .
CMD ["npm", "run", "dev"]

FROM deps AS build
COPY . .
RUN npm run build

FROM nginx:1.29-alpine AS prod
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY docker/40-env-js.sh /docker-entrypoint.d/40-env-js.sh
COPY --from=build /app/dist /usr/share/nginx/html
