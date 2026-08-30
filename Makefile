# HealthAI — orchestration de la stack.
# Déploiement, données de démo, sauvegarde et remise à zéro en commandes uniques.
# Aide : `make` ou `make help`.

COMPOSE := docker compose
DB_SERVICE := db

.DEFAULT_GOAL := help
.PHONY: help up build down ps logs wait-db seed demo reset clean backup restore mode-offline mode-online mode-performance mode-full

MONITORING_SERVICES := grafana prometheus alertmanager loki promtail

help: ## Affiche cette aide
	@echo "HealthAI — cibles disponibles :"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

up: ## Build + démarre toute la stack en arrière-plan
	$(COMPOSE) up --build -d

build: ## (Re)build les images sans démarrer
	$(COMPOSE) build

down: ## Arrête la stack (CONSERVE les données)
	$(COMPOSE) down

ps: ## État des services
	$(COMPOSE) ps

logs: ## Suit les logs de tous les services (Ctrl-C pour quitter)
	$(COMPOSE) logs -f

wait-db: ## Attend que PostgreSQL soit "healthy"
	@echo "Attente de PostgreSQL ($(DB_SERVICE))..."
	@i=0; until [ "$$($(COMPOSE) ps -q $(DB_SERVICE) | xargs -r docker inspect -f '{{.State.Health.Status}}' 2>/dev/null)" = "healthy" ]; do \
		i=$$((i+1)); \
		if [ $$i -gt 60 ]; then echo " timeout (la DB n'est pas prête)"; exit 1; fi; \
		printf '.'; sleep 2; \
	done; echo " OK"

seed: ## Injecte le compte de démo (Camille Martin)
	python3 seed_demo.py

demo: up wait-db seed ## Déploiement COMPLET en 1 commande : up + DB prête + données démo
	@echo "✓ Stack déployée et seedée."
	@echo "  API gateway : http://localhost:8000   |   Adminer : http://localhost:8080"

reset: ## REMISE À ZÉRO : arrête + SUPPRIME tous les volumes (données perdues)
	$(COMPOSE) down -v

clean: ## reset + purge des images locales et conteneurs orphelins du projet
	$(COMPOSE) down -v --rmi local --remove-orphans

mode-offline: ## Bascule en config OFFLINE (analyse photo simulée, aucun appel réseau)
	@sed -i 's/^VISION_PROVIDER=.*/VISION_PROVIDER=mock/' .env
	@$(COMPOSE) up -d kcal
	@echo "✓ Mode offline actif — l'analyse photo ne fait plus aucun appel réseau."

mode-online: ## Restaure la config complète (IA connectée : Claude/HuggingFace)
	@sed -i 's/^VISION_PROVIDER=.*/VISION_PROVIDER=claude/' .env
	@$(COMPOSE) up -d kcal
	@echo "✓ Mode complet actif — analyse photo via IA connectée."

mode-performance: ## Ébauche config PERFORMANCE : coupe le monitoring (Grafana/Prometheus/Loki/Promtail/Alertmanager, ~200 Mo)
	@$(COMPOSE) stop $(MONITORING_SERVICES)
	@echo "✓ Mode performance actif — monitoring désactivé (~200 Mo de RAM libérés)."
	@echo "  Les services applicatifs restent inchangés."

mode-full: ## Réactive le monitoring complet (annule mode-performance)
	@$(COMPOSE) up -d $(MONITORING_SERVICES)
	@echo "✓ Monitoring complet réactivé."

backup: ## Sauvegarde Postgres + Mongo + modèles (scripts/backup.sh)
	./scripts/backup.sh

restore: ## Restaure la dernière sauvegarde (scripts/restore.sh)
	./scripts/restore.sh
