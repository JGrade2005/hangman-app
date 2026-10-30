"""Gunicorn settings for production. Gunicorn loads this file by default."""

import os

# Render routes traffic to 0.0.0.0 on the port it puts in PORT.
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# Games live in this process's memory, so a second worker would not see
# them (two workers lost 8 of 100 game lookups in testing). Threads share
# memory, and GameStore's lock keeps them safe.
workers = 1
threads = 4

accesslog = "-"
