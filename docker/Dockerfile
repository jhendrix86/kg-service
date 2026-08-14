FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Sibling package this engine depends on via an editable install (see
# requirements.txt's "-e ../autonomy-events" line). The build context is
# the workspace root (see docker-compose.yml's `context: ../..`)
# specifically so this is reachable - COPY can't reach outside its build
# context. Copied to /app/autonomy-events so it sits exactly one level up
# from WORKDIR below, matching pip's real resolution rule for "-e ../X":
# relative to the process's cwd at install time, not to requirements.txt's
# own location (verified empirically, see governance-engine's Dockerfile).
COPY autonomy-events/ /app/autonomy-events/

WORKDIR /app/kg-service
COPY kg-service/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY kg-service/app/ ./app/

# Expose port
EXPOSE 8034

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8034"]
