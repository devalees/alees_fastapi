FROM python:3.10-slim

WORKDIR /app

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy requirements directory
COPY requirements/ /app/requirements/

# Install dependencies
RUN pip install --no-cache-dir -r requirements/dev.txt

# Copy application code
COPY app/ /app/app/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 