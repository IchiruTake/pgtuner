FROM python:3.11-alpine
ENV PORT 8001
ENV PYTHONUNBUFFERED 1
ENV PYTHONOPTIMIZE 2
ENV PGTUNER_DBA_WEB 1
# Install dependencies
RUN python -m pip install -r requirements.bump.cli.txt && \
    python -m pip install -r requirements.bump.web.txt

CMD ["python", "web.py"]