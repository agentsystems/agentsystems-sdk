# Agent Platform Development Makefile
# ---------------------------------------------------
# Friendly one-word commands for spinning the entire
# platform (Langfuse + core stack) up and down.
#
# Prerequisites:
#   • docker & docker-compose plugin
#   • make (pre-installed on macOS / most Linux distros)
#
# Optional: define host-side port overrides in .env, e.g.
#   HOST_GATEWAY_PORT=8081
#   HOST_LANGFUSE_PORT=3001
# These will be picked up automatically.

# Load variables from .env if the file exists
ifneq (,$(wildcard ./.env))
  include .env
  export
endif

COMPOSE_FILES=\
	-f compose/langfuse/docker-compose.yml \
	-f compose/local/docker-compose.yml

# Unique project name so containers from different workspaces don’t clash
COMPOSE=docker compose -p agentsys $(COMPOSE_FILES)

.PHONY: help up down restart logs ps

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.* ##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.* ##"}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

up: ## Start / refresh all services (recreate containers)
	@# Ensure shared network exists so external: true succeeds
	@docker network inspect agents-net >/dev/null 2>&1 || docker network create agents-net
	$(COMPOSE) up -d --force-recreate

down: ## Stop and remove containers, networks, volumes
	$(COMPOSE) down

restart: ## Full restart (down + up)
	$(MAKE) down
	$(MAKE) up

logs: ## Tail logs for all services
	$(COMPOSE) logs -f --tail 100

ps: ## List running containers
	$(COMPOSE) ps
