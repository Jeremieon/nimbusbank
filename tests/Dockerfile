FROM python:3.12-slim

WORKDIR /tests

# Install test deps first for layer caching; the test code is bind-mounted at
# run time (see the `tests` service in docker-compose.yml) so edits don't need
# a rebuild, and also COPYed here so the image works standalone.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Inside the compose network the gateway is reachable as http://gateway:80.
ENV BASE_URL=http://gateway:80

ENTRYPOINT ["pytest", "-q"]
