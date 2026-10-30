"""Gunicorn settings for production. Gunicorn loads this file by default."""

import os

# Render sets PORT and routes traffic to 0.0.0.0. Without PORT this is a
# local run, so stay on localhost instead of exposing it to the network.
if "PORT" in os.environ:
    bind = f"0.0.0.0:{os.environ['PORT']}"
else:
    bind = "127.0.0.1:8000"

# Games live in this process's memory, so a second worker would not see
# them (two workers lost 8 of 100 game lookups in testing). Threads share
# memory, and GameStore's lock keeps them safe.
workers = 1
threads = 4

accesslog = "-"
