FROM python:3.12-slim

WORKDIR /bots

# Install deps first for layer caching; the code is bind-mounted at run time
# (see the `bots` service in docker-compose.yml) so edits don't need a rebuild,
# and also COPYed here so the image works standalone.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Inside the compose network the gateway is reachable as http://gateway:80.
ENV NIMBUS_URL=http://gateway:80

# Default to the scripted campaign; override the command to run one script, e.g.
#   docker compose run --rm bots python3 attacks/account_scraping.py
ENTRYPOINT ["python3"]
CMD ["run_all.py"]
