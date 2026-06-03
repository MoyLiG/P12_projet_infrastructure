# Journal de bord — P12 POC Avantages Sportifs

> Log chronologique tenu au fil de l'eau pendant la construction du projet.
> Objectif : permettre à un lecteur (toi, un évaluateur, ou moi dans 6 mois) de
> retracer **chaque décision technique** et **pourquoi** elle a été prise — pas
> seulement le résultat final visible dans le code.

Format des entrées : date, contexte, décision, alternatives écartées, raison.

---

## 2026-06-01 — Cadrage initial

### Contexte
Réception du brief : POC Sport Data Solution (Sport Data Solution, fictif). Juliette
veut tester la faisabilité d'un système de prime sportive + jours bien-être pour
ses 162 salariés. Données fournies : 2 XLSX (RH + pratique sportive). À générer :
~3-5k activités sportives sur 12 mois (style Strava).

### Décisions structurantes prises au cadrage

1. **Option B** retenue pour la soutenance.
   - **Pourquoi** : meilleur exercice (l'évaluateur joue Juliette → je m'entraîne à
     défendre les choix techniques face à un sponsor business, pas juste un
     évaluateur neutre). C'est aussi plus représentatif d'un vrai projet en
     entreprise.

2. **Stack Kestra + PostgreSQL + Python**.
   - **Alternatives écartées** :
     - *Airflow* : standard du marché mais courbe d'apprentissage et lourdeur
       inutiles pour 162 salariés.
     - *Debezium + Kafka + Spark + Delta* (l'archi exemple du PDF) :
       surdimensionnée. L'objectif d'un POC c'est de prouver la faisabilité, pas
       de déployer du big data sur un dataset de 162 lignes.
     - *DuckDB* : pas multi-utilisateur, pas de rôles, pas de RLS. Ne convient
       pas à des données RH sensibles.
   - **Pourquoi PG** : rôles + Row Level Security + chiffrement at-rest + audit
     log natifs. Standard attendu sur le marché Data Engineering.
   - **Pourquoi Kestra** : orchestrateur déclaratif (flow YAML versionné, pas de
     DAG Python à maintenir), UI de monitoring claire, support du *replay*
     explicitement demandé par Juliette dans le brief.

3. **Services externes réels** (pas de mocks complets) :
   - Google Maps Distance Matrix API (clé gratuite, 162 appels = quasi 0 €).
   - Slack Incoming Webhook (workspace de test perso).
   - PowerBI Desktop pour le `.pbix`.
   - **Pourquoi** : la note de cadrage exige une démo live. Mocker rendrait la
     soutenance moins crédible — autant payer le coût d'avoir des services
     réels qui marchent vraiment.

4. **Tests qualité via Great Expectations**.
   - Explicitement cité dans la note de cadrage. Alternative envisagée : Soda
     (aussi citée). GE retenu car suite déclarative en JSON/YAML versionnable
     + docs HTML auto-générées.

5. **Trois schémas PostgreSQL séparés** : `raw` / `staging` / `marts` (pattern
   inspiré dbt). Plus un schéma `audit` pour le monitoring et `cache` pour
   les distances Google Maps.
   - **Pourquoi** : audit trail clair (raw = jamais transformée), séparation
     responsabilités, possibilité de donner à l'analyste un rôle qui ne lit que
     les marts (pas les PII).

### Analyse rapide des données fournies

- **Données+RH.xlsx** : 162 lignes × 11 colonnes. PII fortes :
  `Nom`, `Prénom`, `Date de naissance`, `Salaire brut`, `Adresse du domicile`.
  Champ critique pour la prime : `Moyen de déplacement` (déclaratif employé).
- **Données+Sportive.xlsx** : 1000 lignes × 2 colonnes (`ID salarié`,
  `Pratique d'un sport`). Beaucoup de NULL → stratégie d'imputation à
  documenter (probablement : NULL = pas de sport déclaré).

### Risques identifiés dès le cadrage

| Risque | Mitigation prévue |
|---|---|
| Quota Google Maps en démo | Cache PG des distances après 1er appel + fallback haversine |
| Webhook Slack qui expire | Test la veille + fallback log fichier |
| PowerBI ne joint pas PG le jour J | Tester sur machine de soutenance avant |
| Données générées incohérentes | Le générateur lit la pratique sportive du salarié |

---

## 2026-06-01 — Lot 1 : Infrastructure

### Contexte
Démarrage du build. Création de la base technique avant tout code métier :
arborescence, docker-compose, schémas SQL, gestion des secrets, README initial.

### Décisions du Lot 1

1. **Deux bases PostgreSQL séparées** dans docker-compose : une pour les données
   métier (`postgres` → `sport_data`), une pour Kestra (`kestra-db` → `kestra`).
   - **Pourquoi** : isolation. Si on doit `down -v` Kestra pour une raison
     opérationnelle, on ne perd pas les données métier. Pattern reproductible
     en prod.

2. **Cinq schémas** : `raw`, `staging`, `marts`, `audit`, `cache`.
   - `raw` reçoit les XLSX bruts avec `loaded_at` + `source_file`, **jamais
     modifié** → c'est l'audit trail de la source.
   - `staging` typé strict avec CHECKs (salaire > 0, dates cohérentes,
     moyen_déplacement dans un enum fermé). C'est la **première ligne de
     défense qualité avant Great Expectations**.
   - `marts.eligibility_prime` et `marts.eligibility_wellbeing` ont chacune un
     champ `run_id` → on peut comparer entre runs (utile pour la démo : avant
     vs après changement du taux de prime).
   - `marts.kpi_by_bu` est une **vue** (pas une table) → toujours synchrone
     avec staging, pas besoin de re-matérialiser à chaque run.

3. **Trois rôles PG** : `etl_writer`, `analyst_reader`, `powerbi_reader`.
   - L'analyste **ne voit pas** la table `staging.employees` (RLS qui ne le
     laisse pas passer + il n'a même pas le `USAGE` sur le schéma `staging`).
   - Il lit la vue `marts.employees_safe` qui expose `nom_hash` (SHA-256 salé)
     et `salary_band` (tranches), pas les valeurs en clair.
   - **Belt-and-suspenders** : RLS *ET* défaut de GRANT → si jamais on rajoute
     l'analyste au `USAGE` par erreur, la RLS bloque encore la lecture.

4. **Triggers d'audit** sur les marts d'éligibilité → table
   `audit.eligibility_changes` avec JSONB old/new + user + timestamp.
   - **Pourquoi** : conformité RGPD. On doit pouvoir répondre à "qui a calculé
     que tel salarié n'était pas éligible, quand, à partir de quels paramètres".

5. **Cache Google Maps** en table PG (`cache.gmaps_distance`), keyé par
   `(address_hash, mode)`.
   - **Pourquoi** : 1) ne pas re-payer 162 appels à chaque run de test ;
     2) idempotence (relancer le pipeline donne le même résultat) ; 3) éviter
     une dépendance externe pendant la soutenance (si l'API est en panne).

6. **`pydantic-settings`** pour la config plutôt que `os.getenv` direct.
   - **Pourquoi** : typage strict (`prime_rate_default: float` + `ge=0, le=1`),
     validation à l'import, `SecretStr` pour ne pas leak les mots de passe dans
     les logs en cas de `repr()`.

7. **Driver Postgres `psycopg` v3** (et non v2).
   - **Pourquoi** : v3 est le futur, supporte mieux async, et c'est celui que
     SQLAlchemy 2.0+ recommande. Pas de raison de partir sur v2 pour un projet
     neuf en 2026.

### Sortie du Lot 1
- Arborescence créée
- `docker-compose.yml` : 4 services (postgres, kestra-db, kestra, kestra-init)
- 4 fichiers SQL exécutés en auto-init (volume `/docker-entrypoint-initdb.d`)
- `.env.example`, `.gitignore`, `requirements.txt`, `config.py`, `README.md`

---

## 2026-06-01 — Lot 2 : Extraction & génération

### Contexte
Construction des modules `extract/` (XLSX → staging) et `generate/` (Strava-like).

### Décisions

1. **Pattern `with step("nom_etape") as ctx`** dans `monitoring/metrics.py`.
   - Chaque étape Python écrit une ligne dans `audit.run_log` avec
     `rows_in`, `rows_out`, `duration_ms`, `status`, `message`.
   - **Pourquoi un context manager** plutôt qu'un décorateur : on a souvent
     besoin de mettre à jour `rows_out` après avoir vu le résultat. Avec un
     décorateur, on devrait passer par un side-channel — pas pratique.

2. **Insert dans `raw` AVANT staging**.
   - `raw.employees_xlsx` reçoit la copie 1:1 du XLSX. Si on découvre plus
     tard qu'une transformation introduit un bug, on rejoue depuis raw
     sans avoir à relire le fichier source.

3. **`_normalize_transport`** ne masque pas les valeurs inconnues.
   - Si on reçoit "Vélo (électrique)" → c'est renvoyé tel quel → la CHECK
     SQL crashe → le pipeline s'arrête. C'est voulu : on veut découvrir
     les valeurs inattendues, pas les normaliser silencieusement vers
     "Autres" (qui masquerait des erreurs d'entrée).

4. **Générateur d'activités calé sur la `sport_practice` du salarié**.
   - Pour chaque salarié, on tire le nombre d'activités selon une loi de
     Poisson (lam=25 par défaut), puis chaque activité prend un sport
     déclaré par le salarié.
   - Distance et durée par sport : **log-normales** (asymétriques vers le
     haut, jamais négatives).
   - **Sports sans distance** (Yoga, Crossfit, Tennis, Escalade, Football) :
     `distance_m = NULL` — cohérent avec la note de cadrage qui mentionne
     "à laisser vide pour l'escalade".
   - **Seed fixe** depuis `.env` → la suite GE valide des chiffres
     déterministes → tests reproductibles.

5. **Le seul lien `staging.activities → staging.employees` est FK**.
   - Pas de dénormalisation (nom dans la table activities). Si on change
     le nom d'un salarié, pas de désynchronisation.

---

## 2026-06-01 — Lot 3 : Validation géo + qualité

### Contexte
- `validate/geo.py` : Google Maps Distance Matrix avec cache PG + fallback.
- `validate/quality.py` : Great Expectations sur employees et activities.

### Décisions

1. **Cache des appels Google Maps en table PG** plutôt qu'en fichier JSON.
   - **Pourquoi PG** : partagé entre runs Kestra (sinon, chaque conteneur
     démarrait avec un cache vide), survit aux redémarrages, queryable
     pour debug. Coût ~0 (162 lignes max).
   - Clé : `(sha256(adresse), mode)`. Le mode change la route prise par
     Maps → on cache séparément `walking` et `bicycling`.

2. **Fallback haversine en cas de panne API** mais marqué `is_suspect=TRUE`
   par défaut.
   - Si on n'a ni cache ni API qui répond, on ne peut pas trancher. On
     préfère un faux positif (déclaration "suspecte" à investiguer) plutôt
     qu'un faux négatif silencieux (prime versée à tort).

3. **Suite Great Expectations en mode "ephemeral"**.
   - Pas de `Data Context` persistant sur disque — la suite est dans le
     code, versionnée. Le rapport JSON est écrit dans `data/ge_docs/` avec
     un timestamp → traçabilité par run.
   - **Pourquoi pas la version "filesystem"** : ça crée 15 dossiers, des
     `uncommitted/`, c'est lourd pour un POC. Le mode ephemeral est très
     bien pour des suites simples comme la nôtre.

4. **Échec GE = exception levée**, donc Kestra marque l'exécution FAILED.
   - Mail d'alerte. Si on garde "WARN", le pipeline continue et calcule des
     marts sur des données non validées → pas acceptable.

---

## 2026-06-01 — Lot 4 : Calculs métier

### Contexte
`transform/advantages.py` applique les deux règles. Tout est en SQL paramétré
(UPSERT) pour performance et atomicité.

### Décisions

1. **Calculs en SQL pur** (`INSERT ... SELECT ... ON CONFLICT UPDATE`)
   plutôt qu'en pandas.
   - **Pourquoi** : 162 employés, 3-5k activités → trivial pour PG. Le SQL
     reste lisible, les agrégations comme `COUNT(...) FILTER (WHERE ...)`
     sont natives.
   - Plus rapide qu'un aller-retour Python (charge 5k lignes, calcule,
     remonte).

2. **Paramètres `prime_rate` et `wellbeing_threshold` en CLI**.
   - `argparse` → permet aussi de scripter la démo (`demo.sh` change le
     taux sans toucher au flow Kestra à chaud).

3. **`run_id` stocké dans les marts**.
   - On peut comparer deux runs côte à côte (5 % vs 7 %) → utile pour le
     reporting "et si on change le taux ?".

4. **`reason TEXT`** explicite dans `eligibility_prime`.
   - "KO — déclaration suspecte" vs "KO — transport non actif" : permet à
     l'analyste de comprendre **pourquoi** un salarié n'est pas éligible
     sans rejoindre 3 tables.

---

## 2026-06-01 — Lot 5 : Slack + monitoring

### Décisions

1. **Idempotence par `posted_to_slack BOOLEAN`** sur `staging.activities`.
   - Au moment où on poste, on flague. Rerun = pas de doublon dans la
     channel. C'est le **plus simple** moyen de garantir l'idempotence
     pour ce type de side-effect.

2. **Fallback fichier `slack_outbox.jsonl`** si le webhook répond 4xx.
   - Le pipeline ne casse pas, on continue. Le fichier sert de DLQ
     (dead-letter queue) qu'on peut rejouer plus tard.

3. **Plafond `slack_post_limit=50` par run** (input Kestra).
   - Évite le flood en démo. La première vraie exécution post-historique
     en aurait 3-5k à publier d'un coup.

4. **4 templates de message** au lieu d'un seul.
   - Variété = pas l'aspect "bot mort". `random.choice` sans seed →
     non-déterministe entre runs, c'est OK pour ce side-effect.

---

## 2026-06-01 — Lot 6 : Tests

### Décisions

1. **Marqueur `@pytest.mark.integration`** + ENV `RUN_INTEGRATION=1`.
   - Sépare tests unitaires (rapides, lancés en CI) des tests DB
     (nécessitent Postgres). Pattern simple, sans dépendance externe.

2. **Golden values manuelles** pour `compute_prime`.
   - 3 cas câblés à la main : actif+OK, actif+suspect, non-actif.
   - Permet de valider **la règle métier**, pas juste le SQL.

3. **Test de la sensibilité du hash au sel** (`test_hash_pii_changes_with_salt`).
   - Garantit qu'un changement de sel invalide les hashes existants — utile
     si on doit faire tourner le sel (compromission).

---

## 2026-06-01 — Lot 7 : Flow Kestra + PowerBI

### Décisions

1. **Inputs Kestra** `prime_rate`, `wellbeing_threshold`, etc.
   - Pris au moment du `Execute` dans l'UI ou via API. C'est ce qui rend la
     démo soutenance possible : changer le taux **sans toucher au code**.

2. **Trigger cron `0 9 1 * *`** (1er du mois 9h).
   - Cohérent avec un cycle RH mensuel (calcul de la prime à passer en paie).

3. **Pip install dans `beforeCommands`** au lieu d'une image custom.
   - **Trade-off** : redémarrage de tâche = re-pip = ~30 s de pénalité par
     étape. Mais pas besoin de rebuilder une image custom → plus simple
     pour un POC. En prod, on construit une image `sport-data-etl:1.0` qui
     inclut tout.

4. **PowerBI non versionné en `.pbix`** (binaire opaque).
   - Versionner les **requêtes SQL** dans `powerbi/queries.sql` + un README
     qui décrit la structure cible. Le `.pbix` lui-même reste un livrable
     mais pas la source de vérité.

---

## 2026-06-01 — Lot 8 : Documentation

### Contexte
Génération des deux livrables documentaires demandés par Morgan : ce
`journal.md` (déjà tenu au fil de l'eau) et un `.docx` synthétique.

### Décisions

1. **Le `.docx` est généré par script** (`scripts/build_report_docx.py`) via
   `python-docx`, pas écrit à la main.
   - **Pourquoi** : si on doit le régénérer (changement de chiffres, nouvelle
     section), on relance le script en 2 secondes. Le contenu source est en
     Python → diffable en git, contrairement au binaire `.docx`.
   - **Trade-off** : on ne contrôle pas le rendu visuel pixel-perfect comme
     dans Word. Pour un rapport de soutenance c'est acceptable.

2. **Séparation `journal.md` (détaillé) / `.docx` (synthétique)**.
   - Le journal contient les alternatives écartées, les pourquoi, les
     trade-offs → utile pour la **discussion de soutenance** où l'évaluateur
     challenge les choix techniques.
   - Le `.docx` est le livrable formel : 10-12 pages, structuré, lisible
     en 15 min.

3. **`data_dictionary.md`** à part dans `docs/`.
   - Document de référence consulté par l'analyste qui découvre la base.
     Hors du rapport pour ne pas alourdir, mais facilement accessible.

### État final du projet

- 19 modules Python (~600 lignes hors blancs).
- 4 fichiers SQL d'init (schémas, tables, rôles, triggers).
- 1 flow Kestra YAML (7 tâches + trigger cron + error handler).
- 5 modules de tests pytest (unitaires + intégration).
- 4 documents : README, journal.md, rapport .docx, dictionnaire.
- Stack reproductible en une commande : `docker compose up -d --build`.

### Reste à faire (next steps post-POC)

- Créer le `.pbix` dans PowerBI Desktop (manuel — pas scriptable).
- Préparer le support de présentation `.pdf` pour la soutenance.
- Tester end-to-end avec docker compose démarré.
- Ouvrir le repo GitHub et faire le premier push.
- Bouger les XLSX de `data/` vers `data/raw/` (le code attend ce chemin).

---

## 2026-06-01 — Lot 9 : Mise en route runtime + débogage end-to-end

### Contexte
Permissions élargies → on lance vraiment la stack. Objectif : prouver le
pipeline de bout en bout (DB + Google Maps + Slack réels) puis via Kestra.

### Déroulé (validé)
1. **venv Python 3.11** (version cible — le système avait 3.14, incompatible
   avec les wheels pandas/GE).
2. Pipeline exécuté **étape par étape en local** (connexion directe
   `localhost:5432`) — c'est le chemin le plus rapide pour déboguer.
3. Puis orchestration **Kestra** validée.

### Bugs trouvés et corrigés (détail dans tasks/lessons.md)
Le code écrit "à sec" cachait 7 bugs, tous révélés au premier run réel :
a) privilège TRUNCATE manquant ; b) RESTART IDENTITY exige ownership ;
c) enum `moyen_deplacement` faux (vraie valeur = `Vélo/Trottinette/Autres`) ;
d) NaN pandas → colonne INT ; e) activités générées dans le futur (attrapé
par GE — exactement son rôle) ; f) Kestra Docker runner → Process runner ;
g) input `slack_post_limit` non câblé.

### Deux problèmes d'infra Kestra
- **OutOfMemoryError** : la JVM standalone manquait de heap (~1.8 Go par
  défaut). Corrigé : `JAVA_OPTS=-Xms1g -Xmx3g` + `mem_limit: 4g`.
- **Secrets vides** : Kestra v0.19 exige les secrets `SECRET_*` en **base64**.
  Corrigé : `scripts/gen_secrets_b64.py` génère les variantes base64 dans
  `.env`, injectées dans le conteneur. `{{ secret('X') }}` les décode.

### Résultat final — RUN KESTRA EN SUCCESS
Run `5GirRJtSuAO8syY65bUYvU`, 18 étapes toutes OK dans `audit.run_log` :
- 161 employés, 95 pratiques, 3948 activités
- validation géo : 0 déclaration suspecte (cache Google Maps réel)
- Great Expectations : 100 % validé
- **68 primes** (172 482,50 €), **44 bien-être** (220 jours)
- **5 messages Slack postés via webhook** (pas de fallback)

### Chiffres clés du POC (prime 5 %, seuil 15)
| KPI | Valeur |
|---|---|
| Salariés | 161 |
| Éligibles prime | 68 |
| Coût annuel prime | 172 482,50 € |
| Éligibles bien-être | 44 |
| Jours bien-être accordés | 220 |
| Déclarations suspectes | 0 |

### Finition : exécution verte (SUCCESS) au lieu de WARNING
Le 1er run Kestra finissait en **WARNING** (orange) alors que toutes les
données étaient produites. Cause : le plugin Commands de Kestra a
`warningOnStdErr: true` par défaut → toute sortie stderr (barres de
progression Great Expectations, notice « pip as root ») élève l'exécution.
Corrigé :
- `warningOnStdErr: false` dans pluginDefaults (les vraies erreurs lèvent
  une exception → exit≠0 → FAILED, donc on ne masque rien de critique).
- `pip install --root-user-action=ignore` pour réduire le bruit.
**Pourquoi ça compte** : un pipeline vert en soutenance inspire davantage
confiance qu'un orange qu'il faudrait expliquer.

### Reste vraiment à faire (manuel, hors Claude)
- `.pbix` PowerBI (requêtes prêtes dans `powerbi/queries.sql`).
- Push GitHub.

---

## 2026-06-01 — Lot 10 : Support de soutenance

### Contexte
Génération du livrable 1 (support de soutenance) + trame orale.

### Décisions
1. **PowerPoint (.pptx)** plutôt que HTML — demandé par Morgan, éditable
   avant soutenance, exportable en PDF pour le livrable OC.
2. **python-pptx** et non pptxgenjs : la machine n'a ni Node ni npm. Python
   3.11 + python-pptx = chemin fiable.
3. **Design** (skill frontend-design, phase 0) : structure sandwich (slides
   sombres pour titre/résultats/conclusion, claires pour le contenu), accent
   emerald (sport/énergie) + violet secondaire, typo Trebuchet MS / Calibri.
   Motif récurrent : pastille numérotée + cards à barre latérale.
4. **Script reproductible** : `docs/soutenance/build_pptx.py` régénère le
   .pptx (comme le rapport .docx). Source diffable, pas un binaire opaque.

### Livrables
- `docs/soutenance/Le_Gall_Morgan_Option_B_1_support_062026.pptx` (14 slides)
- `docs/soutenance/trame_soutenance.md` (script oral slide par slide + Q/R)
- `docs/soutenance/build_pptx.py` (générateur)

### Limite QA
QA contenu OK (markitdown : ordre, complétude, 0 placeholder ; intégrité
relue). **QA visuelle non automatisée** : la machine n'a pas LibreOffice/
poppler pour rendre les slides en images. À valider en ouvrant le .pptx dans
PowerPoint avant la soutenance, puis export PDF pour le dépôt OC.
