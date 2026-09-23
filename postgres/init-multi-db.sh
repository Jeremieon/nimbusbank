#!/bin/bash
# Creates one database per microservice on first cluster init.
#
# auth, accounts, and transfers are used starting Phase 1. kyc and support
# were created empty in Phase 2. cards and admin are added in Phase 3 (cards-
# service + the admin/ops dashboard and cross-service request logging) — all
# created here so a fresh cluster init has every database ready, no migration
# step to add the database itself. See README roadmap.
set -euo pipefail

for db in auth accounts transfers kyc support cards admin; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" <<-EOSQL
    SELECT 'CREATE DATABASE $db OWNER $POSTGRES_USER'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db')\gexec
EOSQL
done
