.DEFAULT_GOAL := help
.PHONY: help dev down test db-start db-stop db-new db-link db-push infra-apply infra-destroy gh-setup

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

dev: ## Run frontend (:5173) + backend (:8000) with hot reload
	docker compose up --build

down: ## Stop the dev stack
	docker compose down

test: ## Lint + test backend and frontend (see backend/tests/test_supabase.py for e2e)
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest
	cd frontend && npm run lint && npm run build

db-start: ## Local Supabase: Postgres :54322, API :54321, Studio :54323
	supabase start

db-stop: ## Stop local Supabase
	supabase stop

db-new: ## New migration file: make db-new name=add_things
	supabase migration new $(name)

db-link: ## Link the repo to your hosted project (once, after `supabase login`)
	supabase link

db-push: ## Apply pending migrations to the linked hosted project
	supabase db push

infra-apply: ## Create/update the Hetzner server + Cloudflare DNS record
	terraform -chdir=infra init -input=false
	terraform -chdir=infra apply

infra-destroy: ## Tear the demo server down
	terraform -chdir=infra destroy

gh-setup: ## Wire GitHub Actions to the server (needs gh, infra applied, .env.production)
	gh variable set DEMO_DOMAIN --body "$$(terraform -chdir=infra output -raw domain)"
	terraform -chdir=infra output -raw deploy_private_key | gh secret set DEPLOY_SSH_KEY
	gh secret set PROD_ENV < .env.production
	@echo "Paste a Supabase access token (supabase.com/dashboard/account/tokens):"
	gh secret set SUPABASE_ACCESS_TOKEN
	@echo "Paste the hosted project's database password:"
	gh secret set SUPABASE_DB_PASSWORD
