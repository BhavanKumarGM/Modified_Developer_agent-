FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

# Dev server, not a production build — this project's target audience runs
# it locally; --host is required so the container's published port actually
# reaches Vite (it defaults to binding localhost-only, same rationale as
# the backend's HOST setting).
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
