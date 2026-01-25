.PHONY: help install dev db-up db-down migrate migrate-new migrate-apply migrate-status

help:
	@echo "DuckCoin Presale Backend"
	@echo ""
	@echo "Usage:"
	@echo "  make install        Install Python dependencies"
	@echo "  make dev            Run development server"
	@echo "  make db-up          Start database containers"
	@echo "  make db-down        Stop database containers"
	@echo "  make migrate-new    Create a new migration (requires Atlas)"
	@echo "  make migrate-apply  Apply pending migrations"
	@echo "  make migrate-status Check migration status"

install:
	pip install -r requirements.txt

dev:
	python run.py

# Database commands
db-up:
	docker compose -f ../docker-compose.yaml up -d

db-down:
	docker compose -f ../docker-compose.yaml down

# Atlas migration commands
# Install Atlas: curl -sSf https://atlasgo.sh | sh
# All Atlas commands run from the atlas/ directory

migrate-new:
	@read -p "Migration name: " name; \
	cd atlas && atlas migrate diff $$name --env local

migrate-apply:
	cd atlas && atlas migrate apply --env local

migrate-status:
	cd atlas && atlas migrate status --env local

migrate-hash:
	cd atlas && atlas migrate hash --env local

# Generate schema from current database (useful for initial setup)
schema-inspect:
	cd atlas && atlas schema inspect --env local > schema_current.sql

# Validate schema
schema-validate:
	cd atlas && atlas schema validate --env local
