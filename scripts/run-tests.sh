#!/bin/bash

# Exit on error
set -e

echo "Starting test environment..."

# Clean up any existing environment
docker-compose down -v

# Start PostgreSQL and wait for it to be ready
echo "Starting PostgreSQL..."
docker-compose up -d postgres
sleep 5  # Give PostgreSQL time to initialize and create test database

# Start Redis and wait for it to be ready
echo "Starting Redis..."
docker-compose up -d redis
sleep 2  # Give Redis time to initialize

# Run the tests
echo "Running tests..."
docker-compose run --rm test

# Clean up
echo "Tests completed. Cleaning up..."
docker-compose down 