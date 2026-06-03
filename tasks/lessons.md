# Lessons — P12

Leçons tirées des corrections, pour ne pas refaire les mêmes erreurs.

---

## 2026-06-01 — Conflit de versions pandas / great-expectations

**Erreur** : `requirements.txt` pinnait `pandas==2.2.3` + `numpy==2.1.3`, mais
`great-expectations 1.2.4` exige `pandas<2.2`. `pip install` a échoué
(`ResolutionImpossible`).

**Cause racine** : j'ai choisi les versions des libs data indépendamment, sans
vérifier la contrainte transitive imposée par Great Expectations. GE est un
gros paquet avec des bornes serrées sur ses dépendances.

**Correction** :
- `pandas==2.1.4` (respecte `<2.2`)
- `numpy==1.26.4` (pandas 2.1.x ne supporte pas numpy 2.x — le support numpy 2
  est arrivé avec pandas 2.2.2)
- Corrigé à DEUX endroits : `requirements.txt` ET `flows/sport_advantages_etl.yaml`
  (le `pip_install` du flow), sinon le conflit reviendrait à l'exécution Kestra.

**Règle pour la suite** :
- Quand un projet inclut une lib "lourde" à bornes serrées (great-expectations,
  airflow, dbt...), épingler les autres deps **après** avoir vérifié ses
  contraintes, pas avant.
- Vérifier la cohérence numpy↔pandas : numpy 2.x exige pandas ≥ 2.2.2.
- Toute version de lib dupliquée entre `requirements.txt` et un flow Kestra
  doit être tenue synchrone (source unique de vérité idéale = un fichier
  contraintes partagé, à faire en next step).

---

## 2026-06-01 — Noms de fichiers accentués sous Windows/bash

**Erreur** : `cp "data/Données+RH.xlsx"` échoue en bash (`cannot stat`) à cause
de la normalisation Unicode du `é` (NFC vs NFD) mal gérée par le shell.

**Correction** : passer par PowerShell avec un wildcard (`data\*.xlsx`) plutôt
qu'avec le nom littéral accentué.

**Règle** : pour manipuler des fichiers à noms accentués sous Windows,
privilégier PowerShell + wildcard, ou les chemins via Glob.
**Décision** : fichiers d'entrée renommés en ASCII (`donnees_rh.xlsx`,
`donnees_sportive.xlsx`) — plus de galère cross-plateforme, plus pro.

---

## 2026-06-01 — Série de bugs runtime au premier run end-to-end

Le code écrit "à sec" (sans DB) cachait plusieurs erreurs révélées dès qu'on
a lancé le pipeline contre une vraie base. Leçon générale : **un POC n'est
pas validé tant qu'il n'a pas tourné de bout en bout sur la vraie infra**.

### a) Privilège TRUNCATE manquant
`etl_writer` avait `SELECT/INSERT/UPDATE/DELETE` mais TRUNCATE est un
privilège PostgreSQL **distinct**. Le code utilisait TRUNCATE → `permission
denied`. Corrigé dans `sql/003` (ajout TRUNCATE au GRANT + ALTER DEFAULT).

### b) RESTART IDENTITY exige l'ownership des séquences
`TRUNCATE ... RESTART IDENTITY` fait un ALTER SEQUENCE implicite qui exige
d'être owner. Garder `postgres` owner + `etl_writer` rôle DML est le bon
modèle (least privilege) → on a retiré `RESTART IDENTITY` partout (les ID
sont des surrogates, leur continuité n'importe pas). Fichiers : `db.py`,
`extract/rh.py`, `generate/activities.py`, `tests/test_advantages.py`.

### c) Enum moyen_deplacement bâti sur des suppositions
J'avais inventé `'Vélo/Trottinette'` + `'Autres'` séparés. Les vraies données
ont **une seule** modalité `'Vélo/Trottinette/Autres'` (et une BU `Finance`
non vue à l'exploration initiale). Violation de CHECK à l'INSERT.
**Règle** : toujours lister les valeurs distinctes réelles
(`df[col].value_counts()`) AVANT d'écrire une contrainte enum, jamais sur la
base d'un échantillon de 5 lignes. Corrigé dans 5 fichiers + ALTER sur la
base live.

### d) NaN pandas → colonne INT
Les sports sans distance (escalade, tennis…) donnent `distance_m = NaN`
(pandas force la colonne en float dès qu'il y a des None). psycopg refuse
NaN dans une colonne INT. Corrigé : conversion explicite NaN→None avant
l'insert dans `generate/activities.py`.

### e) Activités générées dans le futur
Le générateur remplaçait l'heure (matin/soir) après avoir tiré une date
proche d'aujourd'hui → certaines activités tombaient à 20h alors qu'il était
13h. Great Expectations l'a **correctement détecté** (`expect_column_max...`).
C'est exactement le rôle de GE : attraper ce qu'un humain ne voit pas.
Corrigé : fenêtre [now-365j, now-1j] + garde-fou `if end > now`.

### f) Architecture Kestra : Docker runner → Process runner
Le flow utilisait un task runner Docker, mais les conteneurs de tâche
n'auraient eu ni le code `src/` ni l'accès réseau à `postgres`. Le conteneur
Kestra embarque déjà Python 3.10 + a `/app/src` et `/app/data` montés et est
sur le réseau Docker (postgres résolvable). → bascule en **Process runner**,
bien plus simple. **Règle** : pour un POC Kestra mono-machine, le Process
runner évite les pièges réseau/volumes du Docker runner.

### g) Input Kestra non câblé
`slack_post_limit` était déclaré en input du flow mais jamais passé à la
commande (`src.load.slack` n'acceptait pas `--limit`). Toujours vérifier que
chaque input déclaré est réellement consommé.

### h) Option pip non supportée (--root-user-action)
En voulant réduire le bruit stderr, j'ai ajouté `pip install
--root-user-action=ignore`. Le pip de l'image Kestra est trop ancien pour
cette option → `no such option` → exit code 2 → pipeline FAILED.
**Règle** : ne pas ajouter d'options CLI sans vérifier la version de l'outil
dans l'environnement cible. Et surtout : la bonne correction du WARNING était
`warningOnStdErr: false` côté Kestra, pas une option pip — un seul correctif
au bon niveau valait mieux que deux (dont un cassé).

### Statut WARNING vs SUCCESS dans Kestra
Le plugin `scripts.*.Commands` a `warningOnStdErr: true` par défaut : toute
sortie stderr (barres GE, notices) fait passer l'exécution en WARNING (orange)
même si tout a réussi. `warningOnStdErr: false` la garde verte. Les vraies
erreurs lèvent une exception → exit≠0 → FAILED, donc rien de critique masqué.

---

## 2026-06-01 — Optimisation coût (skill cost-reducer)

### Constat
Les fichiers auto-chargés en contexte Claude Code sont déjà sobres
(CLAUDE.md projet 328 tk, global 346 tk). Le gaspillage venait des
**patterns d'exécution** de la session, pas des fichiers.

### Patterns coûteux identifiés (et corrigés)
1. **pip install relancé 4×** dans Kestra (chaque recreate du conteneur
   perdait les deps → réinstallation de great-expectations & co, logs
   verbeux, lenteur). → **Corrigé** : image Docker custom `sds-kestra:local`
   (kestra/Dockerfile) avec deps pré-installées. Plus de `beforeCommands: pip`
   dans le flow. Gain : runs instantanés, plus de logs pip, démo robuste.
2. **Polls Kestra trop verbeux** : un poll a imprimé ~100 lignes quasi
   identiques `[Xs] WARNING...`. **Règle future** : faire émettre au poll
   uniquement les *changements* d'état, pas un tick périodique répété.
3. **Re-lecture de gros JSON** (réponse POST flow ~5k tokens dupliqués).
   **Règle** : parser/filtrer côté commande (python -c) plutôt que rapatrier
   le JSON brut.

### Règle générale
Sur un projet à infra lourde (Kestra, Spark…), figer les dépendances dans
une image dès le départ : ça économise du temps ET des tokens (moins de
debug, moins de logs d'install) sur toutes les sessions suivantes.

---

## 2026-06-03 — 5 améliorations du flow

Suite à une relecture critique du flow, 5 manques comblés dans
`flows/sport_advantages_etl.yaml` (+ `src/validate/checks.py`, `quality.py`) :

1. **Alerte réelle dans `errors:`** — avant, seul un `Log` se déclenchait sur
   échec (personne n'était notifié). Ajout d'un `SlackIncomingWebhook` qui
   poste dans #tous-sport-data-solution.
2. **`timezone: Europe/Paris`** sur le trigger Schedule — sans timezone, Kestra
   planifie en **UTC** (9h UTC = 11h Paris l'été). Toujours fixer la timezone.
3. **`retry` exponentiel Kestra** sur `extract_rh`/`extract_sport` — le retry
   tenacity intra-Python ne couvre pas une indispo de la tâche elle-même.
4. **Rapport GE en `outputFile`** — `quality.py` gagne un `--out` ; le flow
   écrit le rapport dans `$OLDPWD/ge_report.json` (= working dir Kestra, avant
   le `cd /app`) et le déclare en `outputFiles` → téléchargeable dans l'UI.
5. **Tests en tâches Kestra visibles** — nouveau module `src/validate/checks.py`
   (employees_loaded / sports_practice_loaded / activities_generated /
   advantages_computed), intercalé en tâches dédiées (vertes/rouges dans l'UI,
   tracées dans audit.run_log via `step`).

**Vérifié** : PUT du flow = 200 (plugins/retry/timezone validés), puis run réel
déclenché → **SUCCESS 11/11 tâches**, les 4 tests verts, `outputFiles=['ge_report.json']`.
Le chemin d'alerte Slack est validé structurellement (import OK) mais **pas
encore déclenché en conditions d'échec** (éviter de spammer la channel).

### Leçon réutilisable — API d'exécution Kestra
`POST /api/v1/executions/{ns}/{flow}` exige du **multipart/form-data**, même
quand tous les inputs ont des défauts. Un POST nu (ou JSON) renvoie
**422 "Invalid entity"**. Côté `requests` : passer `files={"input": (None, "val")}`
force le bon encodage. (Le PUT d'un flow, lui, prend bien `application/x-yaml`.)
