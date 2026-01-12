FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY . .

# Set build-time environment variables
ARG REACT_APP_API_URL
ARG REACT_APP_DOMAIN
ENV REACT_APP_API_URL=$REACT_APP_API_URL
ENV REACT_APP_DOMAIN=$REACT_APP_DOMAIN

# Build the application
RUN npm run build

# Install serve to run the built app
RUN npm install -g serve

# Expose port
EXPOSE 3000

# Serve the built application
CMD ["serve", "-s", "build", "-l", "3000"]