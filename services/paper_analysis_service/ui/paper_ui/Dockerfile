FROM node:16.16.0-alpine

# Create app directory
WORKDIR /app/

COPY package.json ./
COPY package-lock.json ./

RUN npm install

# Bundle app source
COPY . .

EXPOSE 3003
CMD [ "npm", "run", "dev" ]