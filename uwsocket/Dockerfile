FROM node:20-slim
WORKDIR /app
COPY uws/package*.json ./
RUN npm install
COPY uws/ .

CMD ["node", "server.js"]
