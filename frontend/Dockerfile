# Use an official Node.js runtime as a parent image
FROM node:20-slim

# Set the working directory in the container
WORKDIR /app

# Copy package.json and package-lock.json
COPY package*.json ./

# Install app dependencies
# We still need this to ignore the React 19 conflict
RUN npm ci --legacy-peer-deps

# Copy the rest of the application code
COPY . .
COPY .env /app/.env

# Expose port 3000
EXPOSE 3000

# The command to run the development server
# We are skipping `npm run build` entirely
CMD ["npm", "run", "dev"]