# TODO — Refacto raw.activities + Purge P10

## Contexte
Deux chantiers demandés après revue d'architecture (Council) :
1. **Refacto `raw.activities`** : combler l'incohérence du modèle (les activités
   sautaient la couche `raw`). Le générateur produit un payload JSON façon API
   Strava dans `raw.activities (JSONB)`, puis un `transform` aplatit vers
   `staging.activities`. Gain : couche raw cohérente + contrat Strava +
   distinction `moving_time`/`elapsed_time` + mapping documenté.
2. **Purge P10** : supprimer toute mention du projet précédent (P10 / BottleNeck)
   dans le code, les commentaires et la doc.

⚠️ Le projet n'est **pas** sous git → pas de retour arrière. Snapshot de
sécurité à décider avant de toucher au pipeline déjà validé.

---

## Chantier 1 — Refacto raw.activities

### SQL
- [ ] `sql/002_create_tables.sql` : créer `raw.activities` (payload `JSONB` +
  `loaded_at`, `source` = 'strava_sim'). Ajouter `staging.activities.moving_time_s INT`
  (nullable, CHECK >= 0).

### Python
- [ ] `src/generate/activities.py` : la génération produit désormais un **payload
  Strava-shaped** (`id`, `athlete.id`, `type`, `sport_type`, `distance`,
  `moving_time`, `elapsed_time`, `start_date`, `start_date_local`, `timezone`,
  `comment`) inséré dans `raw.activities`. `moving_time` = `elapsed_time` × ratio
  pauses (0.85–0.97, RNG seedé). Reproductibilité conservée (seed inchangé).
- [ ] `src/transform/activities.py` (nouveau) : lit `raw.activities`, aplatit le
  JSON → `staging.activities` (mapping payload → 7 colonnes + `moving_time_s`).
  TRUNCATE staging avant insert (idempotent).
- [ ] `src/generate/activities.py::load_activities` → ne fait plus que l'écriture raw.

### Validation / monitoring
- [ ] `src/validate/checks.py` : `check_activities_generated` vérifie raw ET staging.
- [ ] `src/validate/quality.py` : expectation supplémentaire `moving_time <= elapsed`.

### Orchestration
- [ ] `flows/sport_advantages_etl.yaml` : insérer `transform_activities`
  (raw→staging) entre `generate_activities` et `test_activities_generated`.

### Doc / livrables
- [ ] `data/sample_strava_activity.json` : 1 payload au format API Strava réel +
  entête expliquant que le pipeline projette vers le schéma imposé par la note.
- [ ] `docs/data_dictionary.md` : section `raw.activities` + colonne `moving_time_s`.
- [ ] `README` : tableau mapping API Strava → colonnes staging.

### Tests
- [ ] `tests/test_generate.py` : adapter au payload Strava-shaped.
- [ ] Re-run pytest (unit + intégration) + run Kestra E2E (Docker) → SUCCESS.

---

## Chantier 2 — Purge P10
- [ ] `src/validate/checks.py:8` — retirer "Inspiré du pattern P10".
- [ ] `journal.md:35,39` — retirer "utilisé en P10" / "déjà mis en place en P10".
- [ ] `tasks/lessons.md:147,149,154,165` — reformuler sans P10 (garder la leçon).
- [ ] `docs/soutenance/build_pptx_p10style.py` — sort à décider (suppression ?).
- [ ] Conserver : `db.py:56` et `lessons.md:65` ("continuité" = surrogate IDs, pas P10).

---

## Review — FAIT le 2026-06-03

### Chantier 1 — raw.activities ✅
- `raw.activities (JSONB)` créée ; `staging.activities` + `source_activity_id`
  (lignage) + `moving_time_s` + 2 CHECK (`>=0`, `<= elapsed`).
- Générateur → payloads façon API Strava (athlete.id, sport_type EN,
  moving_time ≠ elapsed_time, start_date/start_date_local) dans raw.
- `src/transform/activities.py` : aplatissement SQL set-based raw → staging.
- Flow Kestra : tâche `transform_activities` intercalée (generate → transform → test).
- GE : expectation `elapsed >= moving_time` (paire de colonnes). README + dico
  data + `data/sample_strava_activity.json` (mapping documenté).

### Chantier 2 — Purge P10 ✅
- Commentaires/journaux nettoyés : `checks.py`, `journal.md`, `lessons.md`.
- « déjà mis en place en P10 » → justification technique de Kestra.
- `build_pptx_p10style.py` → renommé `build_pptx_dark.py`, refs P10/BottleNeck
  retirées ; ancien `.pptx p10style` régénéré en `_dark_` et supprimé.
- Reste « P10 » uniquement dans ce todo.md (méta : décrit la purge elle-même).

### Vérification
- Tests : **25 passed** (22 unit + 3 intégration).
- E2E Kestra (exec B0x9SCsVWxcsOjZr6JETc) : **SUCCESS 12/12 tâches**.
- Données : raw=staging=3948 (lossless), 0 violation moving≤elapsed, lignage 100 %.
- **Chiffres POC inchangés : 68 primes / 44 bien-être** (reproductibilité seed=42 OK).

### Note infra
Volume Postgres existant migré à chaud (DDL manuelle). Sur un reset propre
(`docker compose down -v && up`), le script `sql/002` recrée tout — aucune
migration séparée nécessaire.
