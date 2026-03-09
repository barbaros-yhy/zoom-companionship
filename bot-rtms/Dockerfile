FROM node:20-slim

WORKDIR /app

COPY package*.json ./

# Install ALL deps (including devDeps for build)
RUN npm ci

COPY . .

RUN npm run build

# Remove devDependencies after build
RUN npm prune --production

EXPOSE 8080 8765

USER node

CMD ["node", "dist/index.js"]
