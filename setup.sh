#!/bin/bash

# Create directory structure
mkdir -p traefik/config/dynamic
mkdir -p traefik/certs
mkdir -p traefik/logs

# Make log files
touch traefik/logs/traefik.log
touch traefik/logs/access.log

# Set permissions
chmod 600 traefik/logs/traefik.log
chmod 600 traefik/logs/access.log

# Create Docker network
docker network create traefik-network

echo "Directory structure and network created successfully!"
echo "Next steps:"
echo "1. Edit configuration files as needed"
echo "2. Run 'docker-compose up -d' to start Traefik"
