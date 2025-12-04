FROM node:20-alpine AS frontend-build

WORKDIR /app

# Install pnpm globally
RUN npm install -g pnpm

# Copy package files first for better caching
COPY package.json ./
COPY pnpm-lock.yaml ./
COPY pnpm-workspace.yaml ./
COPY frontend/package.json ./frontend/

# Install dependencies (cached if package.json doesn't change)
RUN pnpm install --frozen-lockfile

# Copy pre-built static files
COPY static/ ./static/

# Backend build stage
FROM python:3.13-slim AS backend-build

RUN pip install uv

WORKDIR /app

# Copy dependency files first for better caching
COPY backend/pyproject.toml backend/uv.lock ./

# Install Python dependencies (cached if pyproject.toml/uv.lock don't change)
RUN uv sync --frozen --no-install-project

# Now copy the backend source code
COPY backend/ ./backend/

# Create __init__.py files for all directories containing Python files
RUN find backend/ -name "*.py" -exec dirname {} \; | xargs -I {} touch {}/__init__.py


# Activate virtual environment
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PYTHONPATH=/app/backend

# Expose port
EXPOSE 5611

# Set working directory back to root for final copy
WORKDIR /app


# Set working directory for the app
WORKDIR /app/backend

# Start the application
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5611"]
