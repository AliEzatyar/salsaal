FROM node:20-slim

# Create non-root user
RUN groupadd -r uwsocket && useradd -r -g uwsocket uwsocket

WORKDIR /app

COPY package.json /app/
COPY package-lock.json /app/

RUN npm config set registry https://registry.npmjs.org/ && npm install

COPY . /app/

# Change ownership to non-root user
RUN chown -R uwsocket:uwsocket /app

# Switch to non-root user
USER uwsocket

CMD ["npm", "start"]