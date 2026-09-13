# Build context is the repository root, not this folder: the app imports itself
# as `api.main`, so the package has to sit one level below the working dir.
#
#   docker build -f api/Dockerfile .

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Requirements first, so a code change does not reinstall every dependency.
COPY api/requirements.txt api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt

COPY api/ ./api/

# Nothing here needs root, and a judge poking at a public deployment should not
# find a container running as one.
RUN useradd --create-home --uid 1000 zonego
USER zonego

# Hosts hand the port over in an environment variable rather than letting the
# image choose. 8000 is the default so `docker run` still works with nothing set.
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import httpx,os,sys; sys.exit(0 if httpx.get(f\"http://127.0.0.1:{os.environ.get('PORT','8000')}/health\").status_code == 200 else 1)"

# Shell form on purpose: $PORT has to be expanded at run time, and the exec form
# would pass the literal string to uvicorn. `exec` then replaces the shell, so
# uvicorn is PID 1 and gets the SIGTERM a host sends on redeploy — without it
# the shell swallows the signal and every deploy ends by killing connections
# mid-request.
CMD exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT}
