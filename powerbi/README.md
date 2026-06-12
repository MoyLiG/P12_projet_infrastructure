# Dashboard PowerBI — Sport Data Solution

Le fichier `.pbix` se construit dans PowerBI Desktop (Windows). Ce guide donne
la marche à suivre exacte. La base expose des **vues prêtes à l'emploi** dans
le schéma `marts` — rien à coder côté SQL.

## 1. Connexion à PostgreSQL

`Accueil → Obtenir les données → Base de données PostgreSQL`

| Champ | Valeur |
|---|---|
| Serveur | `localhost` |
| Base de données | `sport_data` |
| Connectivité | **Importer** (recommandé pour la démo) |

Identifiants (onglet « Base de données ») :

| Champ | Valeur |
|---|---|
| Nom d'utilisateur | `powerbi_reader` |
| Mot de passe | `change-me-pbi-pwd` *(valeur du POC ; cf. sql/003)* |

> Première connexion : si PowerBI demande le connecteur **Npgsql**, accepter
> l'installation. Le rôle `powerbi_reader` ne voit que le schéma `marts` —
> tentative de lire les noms/salaires = accès refusé (RGPD).

## 2. Tables à charger (Navigateur)

Cocher uniquement ces vues du schéma `marts` :

- `v_kpi_global` — cartes de synthèse (1 ligne)
- `kpi_by_bu` — agrégat par Business Unit
- `v_activities_by_sport` — pratique sportive
- `v_prime_detail` — détail prime par salarié
- `v_wellbeing_detail` — détail bien-être
- `v_pipeline_health` — monitoring du pipeline

Puis **Charger**.

## 3. Pages du rapport

### Page 1 — Synthèse
- 6 **cartes** depuis `v_kpi_global` : nb_salaries, nb_eligibles_prime,
  `cout_prime_eur` (format € sans décimale), nb_eligibles_bienetre,
  jours_bienetre, nb_declarations_suspectes.
- **Histogramme** `kpi_by_bu` : axe = bu, valeur = `total_prime_cost_eur`.
- **Anneau** `v_activities_by_sport` : légende = sport, valeur = nb_activites.

### Page 2 — Détail Prime
- **Table** `v_prime_detail` : **id_salarie**, bu, tranche_salaire,
  moyen_deplacement, eligible, montant_prime_eur, motif.
- **Segment** (filtre) sur `bu` et sur `eligible`.

> `id_salarie` est l'**ID salarié RH** et l'unique identifiant de la table :
> clé d'identification dont les RH ont besoin pour verser la prime. C'est un
> identifiant interne pseudonyme — opaque pour un analyste non-RH, et que seul
> le service RH peut relier à un nom + IBAN via sa table de correspondance. Pas
> de hash redondant ; le salaire exact reste hors du dashboard (minimisation RGPD).

### Page 3 — Détail Bien-être
- **Histogramme** distribution `nb_activites` (depuis `v_wellbeing_detail`).
- **Carte** : SUM(`jours_accordes`).
- Segment sur `eligible`.

### Page 4 — Anomalies
- **Table** `v_prime_detail` filtrée sur motif contenant « suspecte »
  (ou ajouter la colonne `is_declaration_suspect` via `employees_safe`).

### Page 5 — Pipeline Health
- **Table** `v_pipeline_health` : etape, statut, lignes_entree, lignes_sortie,
  duree_ms, demarre_a.
- **Graphe** durée par étape (barres).

## 4. Paramètre dynamique « taux de prime » (pour la démo)

`Modélisation → Nouveau paramètre → Champs` (ou paramètre numérique) :

- Nom : `Taux_Prime_Affichage`, type décimal, min 0.01, max 0.15, pas 0.005, défaut 0.05.
- Mesure DAX de projection :
  ```DAX
  Cout_Projeté =
  SUMX(
      FILTER('v_prime_detail', 'v_prime_detail'[eligible] = TRUE()),
      ( 'v_prime_detail'[montant_prime_eur] / 'v_prime_detail'[taux] ) * [Taux_Prime_Affichage]
  )
  ```
  → permet de simuler « et si le taux passait à X % ? » sans relancer le pipeline.

> Pour un **vrai** recalcul (pas une projection visuelle) : relancer le flow
> Kestra avec un autre `prime_rate`, puis **Accueil → Actualiser** dans PowerBI.

## 5. Démo soutenance

- **Scénario A** : relancer le flow Kestra avec `prime_rate=0.07` → Actualiser
  PowerBI → les cartes et l'histogramme évoluent.
- **Scénario B** : insérer une activité (script/SQL) → Actualiser → elle
  apparaît dans `v_activities_by_sport` et `v_wellbeing_detail`.

## 6. Export du livrable

`Fichier → Exporter → PDF` pour le dépôt, et sauvegarder le `.pbix` sous
`powerbi/Le_Gall_Morgan_Option_B_2_pbix_062026.pbix`.
