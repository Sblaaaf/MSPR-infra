#!/usr/bin/env python3
"""
Seed d'un profil de démonstration HealthAI — utilisateur assidu premium_plus.

Génère ~4,5 mois d'historique réaliste (repas, pesées, objectifs) pour ne pas
arriver sur une application vide lors des démos / tests.

Usage :
    # Génère le SQL ET l'exécute dans le conteneur Postgres (par défaut)
    python3 seed_demo.py

    # Génère uniquement le SQL sur stdout (sans toucher à la base)
    python3 seed_demo.py --sql-only > seed.sql

Idempotent : relancer le script supprime puis recrée le profil de démo
(repérage par email + aliments `source_dataset = 'seed_demo'`).

Identifiants du compte créé :
    email    : camille.martin@healthai.demo
    password : Test1234
"""
import argparse
import random
import subprocess
import sys
from datetime import date, timedelta
from hashlib import sha256

# ---------------------------------------------------------------------------
# Paramètres du profil
# ---------------------------------------------------------------------------
EMAIL = "camille.martin@healthai.demo"
PASSWORD = "Test1234"
NOM, PRENOM, SEXE = "Martin", "Camille", "femme"
DATE_NAISSANCE = "1992-03-14"
TAILLE_CM = 168
POIDS_INITIAL = 72.0
PERTE_KG = 5.5                    # perte de poids totale sur la période
DAYS = 132                       # ~4,3 mois d'historique
SEED = 42                        # graine -> données reproductibles

# Conteneur Postgres (docker compose) et identifiants base
DB_SERVICE = "db"
DB_USER = "postgres"
DB_NAME = "healthai"


def esc(s: str) -> str:
    return s.replace("'", "''")


def build_sql() -> tuple[str, dict]:
    """Construit le script SQL complet. Retourne (sql, recap)."""
    random.seed(SEED)
    today = date.today()
    start = today - timedelta(days=DAYS)
    pwd_hash = sha256(PASSWORD.encode()).hexdigest()
    age = today.year - 1992
    imc_init = round(POIDS_INITIAL / (TAILLE_CM / 100) ** 2, 2)
    user = f"(SELECT id FROM utilisateur WHERE email = '{EMAIL}')"

    out = ["BEGIN;"]
    out.append("-- Nettoyage idempotent du profil de démo")
    out.append(f"DELETE FROM utilisateur WHERE email = '{EMAIL}';")
    out.append("DELETE FROM aliment WHERE source_dataset = 'seed_demo';")

    # --- utilisateur (date_inscription rétro-datée + premium_plus) ---
    out.append(f"""
INSERT INTO utilisateur
  (nom, prenom, email, mdp_hash, date_naissance, sexe,
   poids_initial_kg, taille_cm, abonnement, date_inscription, actif, imc, age)
VALUES
  ('{NOM}', '{PRENOM}', '{EMAIL}', '{pwd_hash}', '{DATE_NAISSANCE}', '{SEXE}',
   {POIDS_INITIAL}, {TAILLE_CM}, 'premium_plus', '{start} 09:12:00', TRUE,
   {imc_init}, {age});""")

    # --- objectifs ---
    for lib, offset in [("perte_de_poids", 0), ("amelioration_sommeil", 5), ("maintien_forme", 40)]:
        dd = start + timedelta(days=offset)
        out.append(
            "INSERT INTO utilisateur_objectif (utilisateur_id, objectif_id, date_debut, actif) "
            f"VALUES ({user}, (SELECT id FROM objectif WHERE libelle='{lib}'), '{dd}', TRUE);"
        )

    # --- catalogue d'aliments de démo (kcal + macros /100g) ---
    aliments = [
        ("Flocons d'avoine",      "Céréales",   389, 16.9, 66.3, 6.9, 10.6,  5,  0.0),
        ("Banane",                "Fruits",      89,  1.1, 22.8, 0.3,  2.6,  1, 12.2),
        ("Yaourt grec nature",    "Laitages",    97,  9.0,  3.6, 5.0,  0.0, 36,  3.6),
        ("Oeuf",                  "Protéines",  155, 12.6,  1.1,11.0,  0.0,124,  1.1),
        ("Pain complet",          "Féculents",  247,  9.7, 41.0, 3.4,  6.0,400,  4.3),
        ("Café noir",             "Boissons",     2,  0.1,  0.0, 0.0,  0.0,  2,  0.0),
        ("Blanc de poulet",       "Protéines",  165, 31.0,  0.0, 3.6,  0.0, 74,  0.0),
        ("Riz basmati cuit",      "Féculents",  130,  2.7, 28.0, 0.3,  0.4,  1,  0.1),
        ("Saumon",                "Protéines",  208, 20.0,  0.0,13.0,  0.0, 59,  0.0),
        ("Quinoa cuit",           "Féculents",  120,  4.4, 21.3, 1.9,  2.8,  7,  0.9),
        ("Brocoli",               "Légumes",     34,  2.8,  6.6, 0.4,  2.6, 33,  1.7),
        ("Salade verte",          "Légumes",     15,  1.4,  2.9, 0.2,  1.3, 28,  0.8),
        ("Lentilles cuites",      "Légumineuses",116,  9.0, 20.0, 0.4,  7.9,  2,  1.8),
        ("Pâtes complètes cuites","Féculents",  124,  5.3, 26.5, 0.5,  3.9,  3,  0.8),
        ("Pomme",                 "Fruits",      52,  0.3, 13.8, 0.2,  2.4,  1, 10.4),
        ("Amandes",               "Oléagineux", 579, 21.2, 21.7,49.9, 12.5,  1,  4.4),
        ("Fromage blanc 0%",      "Laitages",    47,  8.0,  4.0, 0.2,  0.0, 40,  4.0),
        ("Soupe de légumes",      "Plats",       38,  1.5,  6.5, 0.8,  1.8,310,  2.5),
        ("Cabillaud",             "Protéines",   82, 17.8,  0.0, 0.7,  0.0, 54,  0.0),
        ("Patate douce",          "Féculents",   86,  1.6, 20.1, 0.1,  3.0, 55,  4.2),
        ("Avocat",                "Fruits",     160,  2.0,  8.5,14.7,  6.7,  7,  0.7),
        ("Thon naturel",          "Protéines",  116, 26.0,  0.0, 1.0,  0.0,247,  0.0),
        ("Carotte",               "Légumes",     41,  0.9,  9.6, 0.2,  2.8, 69,  4.7),
        ("Chocolat noir 70%",     "Snacks",     598,  7.8, 45.9,42.6, 11.0, 20,34.0),
    ]
    for nom, cat, kcal, prot, gluc, lip, fib, sod, suc in aliments:
        out.append(
            "INSERT INTO aliment (nom, categorie, calories_100g, proteines_g, glucides_g, "
            "lipides_g, fibres_g, sodium_mg, sucres_g, source_dataset) VALUES "
            f"('{esc(nom)}', '{cat}', {kcal}, {prot}, {gluc}, {lip}, {fib}, {sod}, {suc}, 'seed_demo');"
        )

    def aid(nom):
        return f"(SELECT id FROM aliment WHERE nom='{esc(nom)}' AND source_dataset='seed_demo' LIMIT 1)"

    # pools par type de repas : (aliment, gramme_min, gramme_max)
    pools = {
        "petit_dejeuner": [
            ("Flocons d'avoine", 50, 80), ("Banane", 100, 130), ("Yaourt grec nature", 120, 170),
            ("Oeuf", 50, 120), ("Pain complet", 40, 80), ("Café noir", 200, 200),
            ("Fromage blanc 0%", 100, 150), ("Amandes", 15, 30),
        ],
        "dejeuner": [
            ("Blanc de poulet", 120, 180), ("Riz basmati cuit", 120, 200), ("Saumon", 110, 160),
            ("Quinoa cuit", 100, 180), ("Brocoli", 80, 150), ("Salade verte", 50, 100),
            ("Lentilles cuites", 120, 200), ("Avocat", 40, 80), ("Thon naturel", 80, 120),
            ("Patate douce", 100, 180), ("Carotte", 60, 120),
        ],
        "diner": [
            ("Soupe de légumes", 200, 300), ("Cabillaud", 120, 180), ("Pâtes complètes cuites", 120, 200),
            ("Brocoli", 80, 150), ("Salade verte", 50, 120), ("Saumon", 100, 150),
            ("Quinoa cuit", 80, 150), ("Carotte", 60, 120), ("Oeuf", 50, 100),
        ],
        "collation": [
            ("Pomme", 120, 180), ("Amandes", 20, 35), ("Yaourt grec nature", 120, 150),
            ("Banane", 100, 120), ("Chocolat noir 70%", 10, 25), ("Fromage blanc 0%", 100, 150),
        ],
    }
    notes = {
        "petit_dejeuner": ["", "Petit-déj rapide", "Avant le sport", ""],
        "dejeuner": ["", "Déjeuner au bureau", "Batch cooking", "Repas équilibré", ""],
        "diner": ["", "Dîner léger", "En famille", ""],
        "collation": ["", "Petite faim", "Post-workout", ""],
    }

    meal_count = line_count = 0
    for d in range(DAYS + 1):
        day = start + timedelta(days=d)
        if random.random() < 0.12:                   # ~88% des jours loggés
            continue
        repas = ["petit_dejeuner", "dejeuner", "diner"]
        if random.random() < 0.55:                   # collation ~1 jour sur 2
            repas.append("collation")
        if random.random() < 0.10:                   # saute parfois le petit-déj
            repas.remove("petit_dejeuner")
        for tr in repas:
            note = random.choice(notes[tr])
            note_sql = f"'{esc(note)}'" if note else "NULL"
            out.append(
                "INSERT INTO journal_repas (utilisateur_id, date_repas, type_repas, notes, created_at) "
                f"VALUES ({user}, '{day}', '{tr}', {note_sql}, '{day} 12:00:00');"
            )
            meal_count += 1
            pool = pools[tr]
            n_items = random.randint(2, 3) if tr != "collation" else random.randint(1, 2)
            for nom, gmin, gmax in random.sample(pool, min(n_items, len(pool))):
                grams = random.randint(gmin, gmax)
                out.append(
                    "INSERT INTO ligne_repas (journal_id, aliment_id, quantite_g) VALUES "
                    f"((SELECT id FROM journal_repas WHERE utilisateur_id={user} AND date_repas='{day}' "
                    f"AND type_repas='{tr}' ORDER BY id DESC LIMIT 1), {aid(nom)}, {grams});"
                )
                line_count += 1

    # --- métriques quotidiennes (poids en baisse, sommeil, bpm, pas...) ---
    metric_count = 0
    imc = imc_init
    for d in range(DAYS + 1):
        day = start + timedelta(days=d)
        if random.random() < 0.08:                   # quelques jours sans pesée
            continue
        target = POIDS_INITIAL - PERTE_KG * (d / DAYS)
        poids = round(target + random.uniform(-0.4, 0.4), 1)
        sommeil = round(random.uniform(6.4, 8.3), 1)
        bpm = random.randint(57, 65)
        steps = random.randint(5500, 13500)
        cal = round(random.uniform(280, 620), 0)
        bodyfat = round(28.0 - 4.0 * (d / DAYS) + random.uniform(-0.5, 0.5), 1)
        imc = round(poids / (TAILLE_CM / 100) ** 2, 2)
        out.append(
            "INSERT INTO metrique_quotidienne (utilisateur_id, date_mesure, poids_kg, bpm_repos, "
            "heures_sommeil, steps, calories_brulees, body_fat_pct, imc_calcule, source) VALUES "
            f"({user}, '{day}', {poids}, {bpm}, {sommeil}, {steps}, {cal}, {bodyfat}, {imc}, 'manuel');"
        )
        metric_count += 1

    out.append(f"UPDATE utilisateur SET imc = {imc} WHERE email = '{EMAIL}';")
    out.append("COMMIT;")
    recap = {"repas": meal_count, "lignes": line_count, "mesures": metric_count}
    return "\n".join(out) + "\n", recap


def run_in_db(sql: str) -> int:
    """Exécute le SQL via psql dans le conteneur Postgres (docker compose)."""
    cmd = [
        "docker", "compose", "exec", "-T", DB_SERVICE,
        "psql", "-U", DB_USER, "-d", DB_NAME, "-v", "ON_ERROR_STOP=1", "-q",
    ]
    proc = subprocess.run(cmd, input=sql, text=True, capture_output=True)
    if proc.stdout.strip():
        print(proc.stdout, end="")
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed un profil de démo HealthAI.")
    parser.add_argument("--sql-only", action="store_true",
                        help="Écrit le SQL sur stdout sans toucher à la base.")
    args = parser.parse_args()

    sql, recap = build_sql()

    if args.sql_only:
        sys.stdout.write(sql)
        return 0

    rc = run_in_db(sql)
    if rc == 0:
        print(f"✓ Profil de démo créé : {EMAIL} / {PASSWORD} (premium_plus)")
        print(f"  {recap['repas']} repas, {recap['lignes']} lignes d'aliments, "
              f"{recap['mesures']} pesées.")
    else:
        print("✗ Échec de l'insertion (voir l'erreur ci-dessus).", file=sys.stderr)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
