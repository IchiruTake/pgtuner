FROM python:3.12-alpine
# Load the environment variables in /conf/web.prod.env by executing bash shell command
COPY /conf /conf
RUN bash -c 'source ./conf/web.prod.env'

# Copy and Install the depenedencies first
COPY requirements.bump.web.txt .
RUN pip install --upgrade pip && pip install -r requirements.bump.web.txt

# Copy the rest of the files
COPY /.pgtuner_dba /.pgtuner_dba
COPY /log /log
COPY /conf /conf
COPY /src /src
COPY /ui /ui
COPY /web /web
COPY /web.py /web.py
COPY ./cicd_codegen_minifier.py /cicd_codegen_minifier.py

# Expose or override the port using $PORT environment variable
ENV PORT=8001
EXPOSE $PORT

# Execute the UI deployment script
RUN python cicd_codegen_minifier.py
CMD ["python", "web.py"]