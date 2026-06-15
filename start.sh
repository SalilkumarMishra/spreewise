#!/usr/bin/env bash
# Railway start script
# Navigate to backend directory and launch Gunicorn
cd "$(dirname "$0")/shared-expense-app/backend"
# Ensure virtual environment is used (Railway creates its own env)
exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000}
