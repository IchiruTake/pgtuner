FROM python:3.12-alpine
COPY . .
ENV PORT=8001
ENV PYTHONUNBUFFERED=1
ENV PYTHONOPTIMIZE=2
ENV PGTUNER_DBA_WEB=1
ENV PORT=8001
EXPOSE 8001
# Install dependencies
RUN pip install -r requirements.bump.cli.txt
RUN pip install -r requirements.bump.web.txt
CMD ["python", "web.py"]