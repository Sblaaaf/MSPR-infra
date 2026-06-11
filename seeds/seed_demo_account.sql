-- =====================================================================
-- Seed reproductible : repas + métriques pour le compte de démo HealthAI.
--
-- But : peupler le compte démo (par défaut id 7790, camille.martin@healthai.demo)
-- avec ~90 jours d'historique réaliste orienté "perte de poids", afin que les
-- features IA (bilan nutritionnel du jour, stats, page fitness) soient pleines.
--
-- IDEMPOTENT : on purge d'abord les données seedées précédentes (repas marqués
-- notes='seed_demo' + métriques source='seed_demo') puis on réinsère.
-- DÉTERMINISTE : setseed() fige l'aléa -> deux exécutions donnent le même résultat.
--
-- Usage (depuis MSPR-infra/) :
--   docker compose exec -T db psql -U postgres -d healthai < seeds/seed_demo_account.sql
--
-- Pour cibler un autre utilisateur : changer v_uid ci-dessous.
-- =====================================================================
DO $$
DECLARE
    v_uid           integer := 7790;       -- <-- compte démo cible
    v_days          integer := 90;         -- profondeur d'historique
    v_w_now         numeric := 66.1;        -- poids aujourd'hui (kg)
    v_w_start       numeric := 71.7;        -- poids il y a v_days jours
    v_bf_now        numeric := 23.9;        -- % gras aujourd'hui
    v_bf_start      numeric := 26.0;        -- % gras il y a v_days jours
    v_height_m      numeric := 1.68;

    -- ids d'aliments (résolus par nom -> robuste à un reseed du catalogue)
    v_oat       integer; v_banana  integer; v_yogurt integer; v_almond integer;
    v_chicken   integer; v_rice    integer; v_brice  integer; v_broc   integer;
    v_salmon    integer; v_spotato integer; v_tuna   integer; v_apple  integer;

    n        integer;
    v_date   date;
    v_poids  numeric;
    v_bf     numeric;
    v_jid    integer;
BEGIN
    PERFORM setseed(0.42);

    -- Résolution des aliments staples (plus petit id matchant, avec calories > 0)
    SELECT min(id) INTO v_oat     FROM aliment WHERE nom ILIKE 'Oatmeal%'            AND calories_100g > 0;
    SELECT min(id) INTO v_banana  FROM aliment WHERE nom = 'Banana'                  AND calories_100g > 0;
    SELECT min(id) INTO v_yogurt  FROM aliment WHERE nom ILIKE 'Greek Yogurt%'       AND calories_100g > 0;
    SELECT min(id) INTO v_almond  FROM aliment WHERE nom ILIKE 'Almonds%'            AND calories_100g > 0;
    SELECT min(id) INTO v_chicken FROM aliment WHERE nom ILIKE 'Chicken Breast%'     AND calories_100g > 0;
    SELECT min(id) INTO v_rice    FROM aliment WHERE nom ILIKE 'White Rice%'         AND calories_100g > 0;
    SELECT min(id) INTO v_brice   FROM aliment WHERE nom ILIKE 'Brown Rice%'         AND calories_100g > 0;
    SELECT min(id) INTO v_broc    FROM aliment WHERE nom ILIKE 'Steamed Broccoli%'   AND calories_100g > 0;
    SELECT min(id) INTO v_salmon  FROM aliment WHERE nom ILIKE 'Salmon%'             AND calories_100g > 0;
    SELECT min(id) INTO v_spotato FROM aliment WHERE nom ILIKE 'Sweet Potato%'       AND calories_100g > 0;
    SELECT min(id) INTO v_tuna    FROM aliment WHERE nom ILIKE 'Tuna Salad%'         AND calories_100g > 0;
    SELECT min(id) INTO v_apple   FROM aliment WHERE nom = 'Apple'                   AND calories_100g > 0;

    -- Purge des données seedées précédentes (idempotence)
    DELETE FROM journal_repas        WHERE utilisateur_id = v_uid AND notes = 'seed_demo';
    DELETE FROM metrique_quotidienne WHERE utilisateur_id = v_uid AND source = 'seed_demo';

    FOR n IN 0..v_days LOOP
        v_date := CURRENT_DATE - n;

        -- Tendances linéaires (aujourd'hui = valeur "now", passé = valeur "start") + léger bruit
        v_poids := round((v_w_now  + (n::numeric / v_days) * (v_w_start  - v_w_now)  + (random() - 0.5) * 0.3)::numeric, 1);
        v_bf    := round((v_bf_now + (n::numeric / v_days) * (v_bf_start - v_bf_now) + (random() - 0.5) * 0.2)::numeric, 1);

        -- ---- Métrique quotidienne ----
        INSERT INTO metrique_quotidienne
            (utilisateur_id, date_mesure, poids_kg, bpm_repos, bpm_max,
             heures_sommeil, steps, calories_brulees, body_fat_pct, imc_calcule, source)
        VALUES (
            v_uid, v_date, v_poids,
            (58 + (random() * 6))::int,
            (165 + (random() * 20))::int,
            round((6.5 + random() * 1.8)::numeric, 1),
            (6000 + (random() * 6000))::int,
            round((300 + random() * 400)::numeric, 0),
            v_bf,
            round((v_poids / (v_height_m * v_height_m))::numeric, 1),
            'seed_demo'
        )
        ON CONFLICT (utilisateur_id, date_mesure) DO NOTHING;

        -- ---- Repas du jour (menu alterné pair/impair pour la variété) ----

        -- Petit-déjeuner
        INSERT INTO journal_repas (utilisateur_id, date_repas, type_repas, notes)
        VALUES (v_uid, v_date, 'petit_dejeuner', 'seed_demo') RETURNING id INTO v_jid;
        IF n % 2 = 0 THEN
            INSERT INTO ligne_repas (journal_id, aliment_id, quantite_g) VALUES
                (v_jid, v_oat, 80), (v_jid, v_banana, 120);
        ELSE
            INSERT INTO ligne_repas (journal_id, aliment_id, quantite_g) VALUES
                (v_jid, v_yogurt, 170), (v_jid, v_almond, 25);
        END IF;

        -- Déjeuner
        INSERT INTO journal_repas (utilisateur_id, date_repas, type_repas, notes)
        VALUES (v_uid, v_date, 'dejeuner', 'seed_demo') RETURNING id INTO v_jid;
        INSERT INTO ligne_repas (journal_id, aliment_id, quantite_g) VALUES
            (v_jid, v_chicken, 150),
            (v_jid, CASE WHEN n % 2 = 0 THEN v_rice ELSE v_brice END, 150),
            (v_jid, v_broc, 100);

        -- Dîner
        INSERT INTO journal_repas (utilisateur_id, date_repas, type_repas, notes)
        VALUES (v_uid, v_date, 'diner', 'seed_demo') RETURNING id INTO v_jid;
        IF n % 2 = 0 THEN
            INSERT INTO ligne_repas (journal_id, aliment_id, quantite_g) VALUES
                (v_jid, v_salmon, 130), (v_jid, v_spotato, 150), (v_jid, v_broc, 80);
        ELSE
            INSERT INTO ligne_repas (journal_id, aliment_id, quantite_g) VALUES
                (v_jid, v_tuna, 120), (v_jid, v_brice, 120), (v_jid, v_broc, 80);
        END IF;

        -- Collation
        INSERT INTO journal_repas (utilisateur_id, date_repas, type_repas, notes)
        VALUES (v_uid, v_date, 'collation', 'seed_demo') RETURNING id INTO v_jid;
        INSERT INTO ligne_repas (journal_id, aliment_id, quantite_g) VALUES
            (v_jid, CASE WHEN n % 2 = 0 THEN v_almond ELSE v_apple END,
                    CASE WHEN n % 2 = 0 THEN 28 ELSE 150 END);
    END LOOP;

    RAISE NOTICE 'Seed terminé pour utilisateur % : % jours de métriques + ~% repas.',
        v_uid, v_days + 1, (v_days + 1) * 4;
END $$;
