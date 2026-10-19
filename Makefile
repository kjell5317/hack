.DEFAULT_GOAL := help
.PHONY: help dev down test db-start db-stop db-new db-push infra-apply infra-destroy gh-setup

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

dev: ## Run frontend (:5173) + backend (:8000) with hot reload
	docker compose up --build

down: ## Stop the dev stack
	docker compose down

test: ## Lint + test backend and frontend (DB tests need RUN_DB_TESTS=1)
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest
	cd frontend && npm run lint && npm run build

db-start: ## Local Supabase: Postgres :54322, API :54321, Studio :54323
	supabase start

db-stop: ## Stop local Supabase
	supabase stop

db-new: ## New migration file: make db-new name=add_things
	supabase migration new $(name)

db-push: ## Apply pending migrations to DATABASE_URL in .env (hosted project)
	supabase db push --db-url "$$(sed -n 's/^DATABASE_URL=//p' .env)"

infra-apply: ## Create/update the Hetzner server + Cloudflare DNS record
	terraform -chdir=infra init -input=false
	terraform -chdir=infra apply

infra-destroy: ## Tear the demo server down
	terraform -chdir=infra destroy

gh-setup: ## Wire GitHub Actions to the server (needs gh, infra applied, .env.production)
	gh variable set DEMO_DOMAIN --body "$$(terraform -chdir=infra output -raw domain)"
	terraform -chdir=infra output -raw deploy_private_key | gh secret set DEPLOY_SSH_KEY
	gh secret set PROD_ENV < .env.production
