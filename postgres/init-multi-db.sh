#!/bin/bash
# Creates one database per microservice on first cluster init.
#
# auth, accounts, and transfers are used starting Phase 1. kyc and support
# are created empty now so their services can be dropped in later (Phase 2)
# without a migration step to add the database itself — see README roadmap.
set -euo pipefail

for db in auth accounts transfers kyc support; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" <<-EOSQL
    SELECT 'CREATE DATABASE $db OWNER $POSTGRES_USER'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db')\gexec
EOSQL
done
