# lightweight container for beCertain sample application
# based on the simple main.py script in this folder

FROM python:3.11-slim

WORKDIR /app

# copy application sources
COPY . /app

# install any requirements if provided (not required for minimal example)
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

# default command to run
CMD ["python", "main.py"]
