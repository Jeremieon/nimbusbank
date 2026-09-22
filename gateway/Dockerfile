# Build context is the repo root (see docker-compose.yml's `context: .`)
# because this stage needs the frontend/ directory; the final nginx stage
# only needs its own nginx.conf plus the built frontend/dist output.
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY gateway/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
