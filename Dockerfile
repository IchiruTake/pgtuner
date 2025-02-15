FROM python:3.12-alpine
# Load the environment variables in /conf/web.prd.env by executing bash shell command
COPY /conf /conf
RUN bash -c 'source ./conf/web.prd.env'

# Copy and Install the depenedencies first
COPY requirements.bump.web.txt .
RUN pip install --upgrade pip && pip install -r requirements.bump.web.txt

# Copy the rest of the files
COPY /.pgtuner_dba /.pgtuner_dba
COPY /log /log
COPY /conf /conf
COPY /src /src
COPY /web /web
COPY /web.py /web.py
COPY ./ui_deployment.py /ui_deployment.py

# Expose or override the port using $PORT environment variable
ENV PORT=8001
EXPOSE $PORT

# Execute the UI deployment script
RUN python ui_deployment.py
CMD ["python", "web.py"]