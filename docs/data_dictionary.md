# Dictionnaire de données — Sport Data Solution POC

Description exhaustive de chaque table du modèle physique. Sert de référence
pour l'analyste (qui consomme `marts.*`) et pour la maintenance.

## Schéma `raw`

Tables copies 1:1 des XLSX source. **Jamais modifiées** après chargement.
Permettent de rejouer le pipeline depuis la source si une transformation a
introduit une régression.

### `raw.employees_xlsx`
| Colonne | Type | Description |
|---|---|---|
| `loaded_at` | `TIMESTAMPTZ` | Horodatage de chargement. |
| `source_file` | `TEXT` | Nom du fichier d'origine. |
| `id_salarie` | `BIGINT` | ID interne RH. |
| `nom`, `prenom` | `TEXT` | PII — visibles uniquement par `etl_writer`. |
| `date_naissance` | `DATE` | |
| `bu` | `TEXT` | Business Unit (Marketing, R&D, Ventes, Support). |
| `date_embauche` | `DATE` | |
| `salaire_brut` | `NUMERIC(12,2)` | Salaire annuel brut en EUR. |
| `type_contrat` | `TEXT` | Toujours "CDI" dans le dataset POC. |
| `jours_cp` | `INT` | Solde congés. |
| `adresse_domicile` | `TEXT` | Adresse postale. |
| `moyen_deplacement` | `TEXT` | Mode déclaratif pour venir au bureau. |

### `raw.sports_xlsx`
1000 lignes brutes — beaucoup de NULL sur `sport_pratique`.

## Schéma `staging`

Données typées + contraintes CHECK + clés étrangères. Première ligne de
défense qualité avant Great Expectations.

### `staging.employees`
- `id_employee BIGINT PRIMARY KEY`
- `nom_hash TEXT` : SHA-256 salé de `nom+prenom` → version sûre pour les analystes.
- `distance_domicile_m INT` : alimenté par `validate/geo.py` après appel Google Maps.
- `is_declaration_suspect BOOLEAN` : `TRUE` si `distance > seuil` selon le mode déclaré.
- CHECKs : `salaire_brut > 0`, `jours_cp >= 0`, `moyen_deplacement IN (enum)`.

### `staging.sports_practice`
Clé composite `(id_employee, sport_pratique)` — un salarié peut déclarer plusieurs sports.

### `staging.activities`
- `id_activity BIGSERIAL PRIMARY KEY`
- `posted_to_slack BOOLEAN` : flag d'idempotence pour Slack.
- CHECKs : `end_dt > start_dt`, `distance_m IS NULL OR >= 0`.
- Index : `id_employee`, `start_dt`.

## Schéma `marts`

Tables et vues consommées par PowerBI et les analystes.

### `marts.eligibility_prime`
- `id_employee BIGINT PRIMARY KEY`
- `prime_rate NUMERIC(5,4)` : taux utilisé pour ce calcul (audit).
- `prime_amount NUMERIC(12,2)` : `prime_rate × salaire_brut` si éligible, sinon `0`.
- `reason TEXT` : explication textuelle (utile en démo).
- `run_id TEXT` : exécution Kestra qui a produit cette ligne.

### `marts.eligibility_wellbeing`
- `activity_count INT` : nombre d'activités sur les 365 derniers jours.
- `threshold INT` : seuil appliqué (15 par défaut).
- `days_granted INT` : 5 si éligible, 0 sinon.

### `marts.kpi_by_bu` (vue)
Agrégat par BU : `nb_employees`, `nb_eligible_prime`, `nb_eligible_wellbeing`,
`total_prime_cost_eur`, `total_wellbeing_days`.

### `marts.employees_safe` (vue, pseudonymisée)
Exposée aux analystes :
- `employee_hash` (pas `nom`/`prenom`)
- `salary_band` (tranches `< 30k` / `30-50k` / `50-80k` / `> 80k`, pas la valeur exacte)
- Les autres champs non-PII.

## Schéma `audit`

### `audit.run_log`
1 ligne par étape de chaque exécution. Volumétrie + durée + statut.
Sert de source pour la page "Pipeline Health" du dashboard.

### `audit.eligibility_changes`
Trigger sur `marts.eligibility_*` : log JSONB du old / new à chaque
INSERT/UPDATE/DELETE. Conformité RGPD (qui a calculé quoi, quand).

## Schéma `cache`

### `cache.gmaps_distance`
- Clé : `(address_hash, mode)`.
- Évite de re-payer les appels Google Maps et garantit l'idempotence.
- Pas de TTL pour ce POC — les adresses des salariés bougent rarement. En
  prod, ajouter un `expires_at` avec rafraîchissement périodique.
