# POC Avantages Sportifs — Sport Data Solution (P12)

> Pipeline ETL bout-en-bout calculant l'impact financier de deux avantages
> sportifs pour les salariés de Sport Data Solution (entreprise fictive).
> Projet OpenClassrooms P12 — Data Engineer — **Option B**.

---

## Quick start

```bash
# 1. Copier le template d'environnement et remplir les secrets
cp .env.example .env
# editer .env : GOOGLE_MAPS_API_KEY, SLACK_WEBHOOK_URL, mots de passe

# 2. Démarrer la stack
docker compose up -d --build
#    Postgres   -> localhost:5432
#    Kestra UI  -> http://localhost:8080

# 3. Le flow Kestra s'importe automatiquement (~10 s).
#    Lancer une exécution :
#    - UI : Flows -> company.sport_data.sport_advantages_etl -> Execute
#    - CLI :
curl -X POST http://localhost:8080/api/v1/executions/company.sport_data/sport_advantages_etl
```

**Reset complet** :
```bash
docker compose down -v && docker compose up -d --build
```

---

## Architecture

Pipeline orchestré par Kestra. Données stockées en PostgreSQL avec trois schémas
séparés (`raw` / `staging` / `marts`) inspirés du pattern dbt, plus `audit` pour
le monitoring et `cache` pour les distances Google Maps.

```
   XLSX RH +              ┌──────────┐   GE suite    ┌────────────┐
   sportives    ──► raw ──►          ├──► validate ──►  marts     │──► PowerBI
                          │ staging  │   géo + qual  │ eligibility│
   Strava-like  ──────────►          │               │ KPI        │──► Slack
   (générées)              └──────────┘               └────────────┘
                                │                          │
                                ▼                          ▼
                          audit.run_log              audit.eligibility_changes
```

Détail des choix techniques : voir `journal.md` (log de bord chronologique)
et `docs/Le_Gall_Morgan_Option_B_rapport_062026.docx` (rapport projet).

---

## Stack

| Brique | Outil | Pourquoi |
|---|---|---|
| Orchestration | Kestra 0.19 | Flow YAML versionné, replay natif, monitoring UI |
| BDD | PostgreSQL 16 | Rôles, RLS, audit triggers — adapté aux PII RH |
| Langage | Python 3.11 | pandas / SQLAlchemy / Faker / GE |
| Qualité | Great Expectations | Suite déclarative, docs HTML, intégration Kestra |
| Géo | Google Maps Distance Matrix + fallback haversine | Réel en démo, cache PG |
| Notifications | Slack Incoming Webhook | Démo live crédible |
| Restitution | PowerBI Desktop | Connecteur PG natif, paramètres dynamiques |

---

## Sécurité

- `.env` jamais versionné — `.env.example` contient des placeholders.
- 3 rôles PG : `etl_writer` (R/W pipeline), `analyst_reader` / `powerbi_reader`
  (read marts only — **pas d'accès aux PII**).
- Pseudonymisation : les analystes voient `hash(nom+prénom+salt)`, pas les noms.
- Row Level Security activée sur `staging.employees`.
- Triggers d'audit sur `marts.eligibility_*` → `audit.eligibility_changes`.
- Inserts SQL paramétrés (SQLAlchemy) — pas de string formatting.

---

## Structure du repo

```
P12/
├── flows/                Flow YAML Kestra
├── sql/                  Init DB (auto-exécuté au démarrage Postgres)
├── src/                  Pipeline Python (extract / generate / validate / transform / load)
├── tests/                Tests pytest
├── powerbi/              Dashboard .pbix
├── docs/                 Rapport .docx, support PDF, diagrammes
├── scripts/              bootstrap.sh, demo.sh
├── data/                 raw/ (XLSX, git-ignored) + generated/ (CSV)
├── docker-compose.yml
├── journal.md            ← log chronologique du build
└── README.md             ← ce fichier
```

---

## Livrables OpenClassrooms

Voir `docs/` :
- `Le_Gall_Morgan_Option_B_1_support_062026.pdf` — support de soutenance
- `Le_Gall_Morgan_Option_B_2_lien_062026.txt` — URL du repo GitHub
- `powerbi/sport_advantages.pbix` — dashboard PowerBI
