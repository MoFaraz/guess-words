FROM python:3.13-slim


# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create non-root user for security
RUN adduser --disabled-password --gecos "" app_user && \
    chown -R app_user:app_user /app
USER app_user

# Run gunicorn
CMD ["gunicorn", "--bind", "127.0.0.1:8000", "config.wsgi:application"]