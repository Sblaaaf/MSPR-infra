# MSPR-backend

Backend de l'application MSPR pour l'analyse nutritionnelle des repas, basé sur une architecture microservices FastAPI.

DOCUMENTATION COMPLETE :
https://satisfying-activity-4ab.notion.site/JARMY-API-329e716da2bc80fe85f0d310e12d712e?source=copy_link

---

## ✅ Prérequis

À installer sur le poste (identique sur Linux / macOS / Windows+WSL2) :

- **Docker Engine ≥ 24** et **Docker Compose v2** (`docker compose version`)
- **Git** (pour cloner les dépôts — voir `CLONE_ALL.md`)
- **Python ≥ 3.9** (uniquement pour `make seed` / `seed_demo.py`)
- **GNU Make** (fournit les commandes uniques ci-dessous ; optionnel mais recommandé)

---

## 🚀 Démarrage rapide

Avec **Make** (recommandé — commande unique de bout en bout) :

```bash
make demo     # build + démarre toute la stack, attend la DB, injecte les données démo
```

Sans Make (équivalent manuel) :

```bash
docker compose up --build -d   # démarre la stack
python3 seed_demo.py           # (optionnel) données de démo
```

### Commandes Make disponibles

| Commande | Effet |
|---|---|
| `make demo` | **Déploiement complet en 1 commande** : `up` + DB prête + données démo |
| `make up` | Build + démarre toute la stack en arrière-plan |
| `make down` | Arrête la stack (**conserve** les données) |
| `make ps` / `make logs` | État des services / suivi des logs |
| `make seed` | Injecte le compte de démo (Camille Martin) |
| `make backup` / `make restore` | Sauvegarde / restauration (voir section dédiée) |
| `make reset` | **Remise à zéro** : arrête + supprime tous les volumes (données perdues) |
| `make clean` | `reset` + purge des images locales et conteneurs orphelins |

`make` (sans argument) affiche l'aide complète.

---

## 🗂️ Services exposés

| Service      | URL principale                  | Documentation Swagger         |
|--------------|---------------------------------|------------------------------|
| Gateway      | http://localhost:8000           | http://localhost:8000/docs   |
| Kcal         | http://localhost:8001           | http://localhost:8001/docs   |
| Meal         | http://localhost:8003           | http://localhost:8003/docs   |
| Auth         | http://localhost:8004           | http://localhost:8004/docs   |
| Adminer      | http://localhost:8080           | —                            |

> **Note :** La documentation Swagger complète (avec exemples de body, schémas, etc.) est disponible sur chaque service, pas sur le gateway.

---

## 🏗️ Architecture

- **db** : PostgreSQL partagé (base `healthai`)
- **adminer** : interface web pour visualiser la base
- **etl** : pipeline ETL pour charger les données
- **gateway** : proxy centralisant les appels API
- **kcal** : analyse nutritionnelle automatique
- **meal** : gestion des repas, aliments, utilisateurs
- **auth** : authentification

---

## 🔗 Exemples d'appels API

### Authentification

```http
POST http://localhost:8000/auth/login
Content-Type: application/json

{
  "email": "jean.dupont@example.com",
  "password": "secret123"
}
```

### Création d'utilisateur

```http
POST http://localhost:8000/meal/users
Content-Type: application/json

{
  "nom": "Jean",
  "prenom": "Dupont",
  "email": "jean.dupont@example.com",
  "password": "secret123",
  "sexe": "homme"
}
```

### Ajout d'un repas

```http
POST http://localhost:8000/meal/users/1/meals
Content-Type: application/json

{
  "type_repas": "dejeuner",
  "date_repas": "2026-04-08",
  "notes": "Repas test",
  "items": [
    { "aliment_nom": "poulet grille", "quantite_g": 150, "calories_100g": 250 },
    { "aliment_nom": "riz", "quantite_g": 200, "calories_100g": 130 }
  ]
}
```

### Analyse nutritionnelle

```http
POST http://localhost:8000/kcal/predict
Content-Type: application/json
Authorization: Bearer clesecrete

{
  "text": "266g of rice and chicken and for the dessert i ate an ice cream and 50g of apple"
}
```

---

## 📝 Documentation Swagger

- [Gateway](http://localhost:8000/docs) *(routes proxy uniquement)*
- [Kcal](http://localhost:8001/docs) *(analyse nutritionnelle, exemples détaillés)*
- [Meal](http://localhost:8003/docs) *(gestion repas, aliments, users)*
- [Auth](http://localhost:8004/docs) *(login, exemples de body)*

---

## 🛠️ Accès base de données

- Interface : [Adminer](http://localhost:8080)
- Système : PostgreSQL
- Server : `db`
- User : `postgres`
- Password : `postgres`
- Database : `healthai`

---

## 💾 Sauvegarde & restauration

Deux scripts dans `scripts/` couvrent l'ensemble des données persistantes de la stack.

| Magasin | Contenu | Outil |
|---|---|---|
| PostgreSQL (`healthai`) | utilisateurs, repas, aliments, métriques… (auth, meal, kcal, etl, admin) | `pg_dump -Fc` |
| MongoDB (`recommendation_db`) | recommandations | `mongodump --archive --gzip` |
| Volume `recommendation_models` | modèles ML entraînés *(régénérables via `train.py`)* | `tar` |

Les dumps sont produits **dans les conteneurs** puis stockés dans un dossier horodaté
`backups/<AAAAMMJJ_HHMMSS>/` (ce dossier est ignoré par git).

### Sauvegarder

```bash
docker compose up -d        # la stack doit tourner
./scripts/backup.sh
```

Chaque sauvegarde contient `postgres_healthai.dump`, `mongo_recommendation_db.archive.gz`,
`recommendation_models.tar.gz` et un `MANIFEST.txt`. Par défaut, les **7** sauvegardes les
plus récentes sont conservées (rotation automatique).

### Restaurer

```bash
./scripts/restore.sh                      # restaure la sauvegarde la plus récente
./scripts/restore.sh backups/20260611_094607   # ou un dossier précis
```

> ⚠️ La restauration **écrase** les données actuelles (Postgres `--clean`, Mongo `--drop`).
> Une confirmation est demandée ; `FORCE=1 ./scripts/restore.sh …` la contourne (utile en CI/cron).
> Après restauration des modèles ML : `docker compose restart recommendation`.

### Réglages (variables d'environnement)

| Variable | Défaut | Rôle |
|---|---|---|
| `BACKUP_ROOT` | `./backups` | répertoire des sauvegardes |
| `BACKUP_KEEP` | `7` | nombre de sauvegardes conservées (rotation) |
| `PG_SERVICE` / `PG_USER` / `PG_DB` | `db` / `postgres` / `healthai` | cible PostgreSQL |
| `MONGO_SERVICE` / `MONGO_DB` | `mongodb` / `recommendation_db` | cible MongoDB |

### Automatisation (cron)

```bash
# Sauvegarde quotidienne à 2 h du matin
0 2 * * * cd /chemin/vers/MSPR-infra && ./scripts/backup.sh >> backups/backup.log 2>&1
```

---

## 📦 Structure du projet

```text
MSPR-backend/
├── docker-compose.yml
├── README.md
├── services/
│   ├── auth/      # Service d'authentification
│   ├── gateway/   # Proxy central
│   ├── kcal/      # Analyse nutritionnelle
│   ├── meal/      # Gestion repas/aliments
│   └── etl/       # Pipeline ETL
└── ...
```

---

## ⚡ Démarrage manuel (dev)

Prérequis : Python 3.11+, pip

```bash
git clone https://github.com/Swaksm/MSPR-backend.git
cd MSPR-backend
pip install -r services/kcal/requirements.txt
pip install -r services/gateway/requirements.txt
pip install -r services/meal/requirements.txt
pip install -r services/auth/requirements.txt
```

Lancer chaque service dans un terminal dédié :

```bash
cd services/kcal && python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
cd services/gateway && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
cd services/meal && python -m uvicorn main:app --host 0.0.0.0 --port 8003 --reload
cd services/auth && python -m uvicorn main:app --host 0.0.0.0 --port 8004 --reload
```

---

## ℹ️ Notes importantes

- **La documentation Swagger complète est sur chaque service** (pas sur le gateway)
- Le token d’API pour `kcal` est : `clesecrete`
- Les exemples de requêtes sont copiables depuis chaque `/docs`
- L’ETL charge automatiquement les données d’aliments, utilisateurs, exercices, etc.

---

## 🏷️ Licence

Projet MSPR - Formation Concepteur Développeur d'Applications (RNCP36581 Bloc E6.1)
