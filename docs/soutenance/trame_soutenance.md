# Trame de soutenance — P12 POC Avantages Sportifs

> Support : `Le_Gall_Morgan_Option_B_1_support_062026.pptx`
> Durée cible : **15 min** de présentation (+/- 5), puis 10 min de discussion, 5 min débrief.
> Option B : l'évaluateur joue **Juliette** (cofondatrice). Ton : pédagogue,
> orienté décision business, mais solide techniquement.

Pour chaque slide : **[VISUEL]** ce qui est à l'écran, **[ORAL]** ce que tu dis.

---

## Slide 1 — Titre

**[VISUEL]** POC Avantages Sportifs · Sport Data Solution · Option B · Morgan Le Gall · Juin 2026.

**[ORAL]**
« Bonjour Juliette. Comme convenu, j'ai mené le POC du système d'avantages
sportifs. En 15 minutes je te présente l'architecture, les choix techniques, les
résultats chiffrés, puis je te fais une démo live. L'objectif : te donner les
éléments pour décider si on industrialise. »

---

## Slide 2 — Contexte & mission

**[VISUEL]** Les 2 avantages : Prime sportive (5 % du brut) + 5 jours bien-être (≥15 activités/an). 3 objectifs du POC.

**[ORAL]**
« Tu veux récompenser les salariés sportifs avec deux avantages : une prime de
5 % pour ceux qui viennent au bureau en mode actif, et 5 jours bien-être pour
ceux qui pratiquent régulièrement. Le POC répond à 3 questions : est-ce
faisable techniquement, quelles données collecter, et surtout — combien ça
coûte à l'entreprise. »

---

## Slide 3 — Objectifs du POC

**[VISUEL]** 3 cartes : Faisabilité technique · Données à collecter · Impact financier.

**[ORAL]**
« Je me suis fixé ces trois livrables. Un pipeline qui tourne de bout en bout,
un modèle de données clair sur ce qu'on collecte chez les salariés — et c'est
sensible, ce sont des données RH — et un chiffrage de l'impact financier
qu'on pourra rejouer si tu changes un paramètre. »

---

## Slide 4 — Architecture

**[VISUEL]** Schéma du flux : Sources (XLSX RH + sport, générateur façon API Strava) → PostgreSQL (raw : JSON Strava → staging → marts) → validation géo + qualité → calcul → Slack + PowerBI. Kestra orchestre.

**[ORAL]**
« Voici l'architecture. Trois sources : les fichiers RH, les pratiques
sportives déclarées, et un générateur qui simule les données Strava sur 12
mois — au format JSON de l'API réelle, en attendant le branchement live. Ce
JSON atterrit dans la couche raw, puis une étape d'ingestion l'aplatit vers
staging. Tout est dans PostgreSQL, structuré en trois couches. On valide, on
calcule, et on restitue dans Slack et PowerBI. Le tout orchestré par Kestra,
qui surveille chaque exécution. »

---

## Slide 5 — Stack & justifications

**[VISUEL]** Tableau : brique → outil → pourquoi. Kestra, PostgreSQL, Python, Great Expectations, Google Maps, Slack, PowerBI, Docker.

**[ORAL]**
« Chaque choix est justifié. Kestra pour l'orchestration : il permet de rejouer
l'historique, ce que tu avais demandé. PostgreSQL plutôt qu'une base plus
simple, parce qu'on a des données RH sensibles : il me faut des rôles, du
chiffrement, de l'audit. Great Expectations pour les tests qualité. Et des
services réels — Google Maps, Slack — pour que la démo soit crédible, pas du
simulacre. »

---

## Slide 6 — Le pipeline étape par étape

**[VISUEL]** 8 étapes numérotées : extract RH → extract sport → générer activités (raw : JSON Strava) → aplatir raw→staging → valider géo → qualité GE → calculer avantages → notifier Slack.

**[ORAL]**
« Le pipeline enchaîne huit étapes. Extraction, génération des activités au
format Strava dans la couche raw, aplatissement vers staging, validation
géographique, contrôle qualité, calcul des avantages, notification Slack. Si
une étape échoue, le pipeline s'arrête et envoie une alerte — on ne calcule
jamais sur des données douteuses. »

---

## Slide 7 — Qualité des données

**[VISUEL]** 3 lignes de défense : contraintes SQL · Great Expectations · validation métier géographique. Exemple : déclaration "marche" à 50 km = anomalie.

**[ORAL]**
« La qualité, c'est trois niveaux. D'abord les contraintes en base : une
distance négative ou une date invalide est rejetée à l'entrée. Ensuite Great
Expectations qui valide des règles métier — d'ailleurs il a attrapé un vrai
bug pendant le dev, des activités datées dans le futur. Enfin, la validation
géographique : si un salarié déclare venir à pied mais habite à 50 km, Google
Maps calcule la distance réelle et on remonte l'anomalie. »

---

## Slide 8 — Sécurité & RGPD

**[VISUEL]** Données RH sensibles. 3 rôles PG, pseudonymisation (hash), Row Level Security, audit trail, secrets hors code. 8/9 CVE corrigées.

**[ORAL]**
« Ce sont des données RH, donc sensibles. J'ai cloisonné : trois rôles
distincts en base. L'analyste qui consulte les chiffres ne voit jamais les
noms ni les salaires en clair — il voit des hash et des tranches. Les
modifications sont tracées pour la conformité RGPD. Et j'ai passé un audit de
sécurité : aucun secret dans le code, dépendances à jour. »

---

## Slide 9 — Cycle de vie des données personnelles

**[VISUEL]** Une donnée RH suivie à travers les 3 couches : **raw** (nom + salaire + adresse en clair) → **staging** (clair + hash pseudonyme, cloisonné par Row Level Security) → **marts** (hash + tranche de salaire, zéro PII). Bandeau « qui voit quoi » : `etl_writer` vs `analyst_reader` / `powerbi_reader`.

**[ORAL]**
« Je veux te montrer concrètement comment une donnée sensible circule, parce
que c'est le cœur du sujet RH. Prends mon nom et mon salaire. En couche *raw*,
ils sont en clair — mais seul le pipeline d'ingestion y accède. En *staging*,
je calcule un hash pseudonyme à côté du nom, et l'accès est cloisonné ligne par
ligne. Enfin en *marts*, la couche qui alimente PowerBI, il ne reste que le hash
et une tranche de salaire : plus aucune donnée identifiante. Résultat : l'analyste
qui construit les tableaux de bord travaille sur des chiffres justes sans jamais
voir qui gagne combien. C'est le principe de minimisation du RGPD, appliqué
techniquement et pas seulement sur le papier. »

---

## Slide 10 — Monitoring & observabilité

**[VISUEL]** Capture/maquette de l'UI Kestra (pipeline vert, 12 tâches SUCCESS) + table audit.run_log (volumétrie, durées par étape).

**[ORAL]**
« Côté supervision, chaque exécution est tracée : volumétrie et durée par
étape, dans une table dédiée. L'interface Kestra montre l'état en temps réel.
Là tu vois un run complet, tout en vert, en une vingtaine de secondes. Si ça
casse en prod, on le sait immédiatement par mail. »

---

## Slide 11 — Résultats chiffrés

**[VISUEL]** Grands chiffres : 161 salariés · 68 éligibles prime · **172 482,50 €/an** · 44 éligibles bien-être · 220 jours · 3948 activités · 0 anomalie.

**[ORAL]**
« Voici l'impact financier, ta question principale. Sur 161 salariés, 68 sont
éligibles à la prime, pour un coût annuel de 172 482 €. 44 salariés
décrochent les 5 jours bien-être, soit 220 jours au total. Et zéro déclaration
suspecte sur ce jeu de données. Ces chiffres se recalculent en un clic si tu
changes le taux. »

---

## Slide 12 — Démo live

**[VISUEL]** 2 scénarios : (A) changer le taux 5 % → 7 % et voir le coût évoluer ; (B) insérer une activité → message Slack + reporting.

**[ORAL]**
« Je te montre en direct. Premier scénario : je passe le taux de prime de 5 à
7 %, je relance, et tu vois le coût total bouger dans PowerBI. Deuxième
scénario : j'insère une nouvelle course, et tu la vois apparaître dans Slack
et dans le reporting. »
*(→ basculer sur Kestra + Slack + PowerBI)*

---

## Slide 13 — Scalabilité & robustesse

**[VISUEL]** Points : stack conteneurisée (1 commande), idempotence, replay, cache Google Maps, image Docker reproductible. Vers la prod : API Strava réelle, CI/CD.

**[ORAL]**
« Sur la scalabilité : tout est conteneurisé, reproductible en une commande.
Le pipeline est idempotent — on peut le rejouer sans créer de doublons. Pour
passer en production, les prochaines étapes sont la connexion à la vraie API
Strava et une chaîne d'intégration continue. L'architecture est dimensionnée
pour ça sans réécriture. »

---

## Slide 14 — Conclusion

**[VISUEL]** POC validé sur les 3 objectifs. Le coût est maîtrisé et pilotable. Recommandation : industrialiser.

**[ORAL]**
« En résumé : le POC valide les trois objectifs. C'est faisable, on sait quelles
données collecter, et l'impact financier est chiffré et pilotable. Ma
recommandation : on peut industrialiser, en commençant par l'intégration
Strava. Je suis prêt pour tes questions. »

---

## Slides backup (pour la discussion)

- **B1 — Pertinence des outils** : pourquoi Kestra vs Airflow, PostgreSQL vs DuckDB, GE vs Soda.
- **B2 — Défis techniques rencontrés** : OOM Kestra (heap JVM), secrets base64, enum de transport calé sur les vraies données, Process runner vs Docker runner.
- **B3 — Qualité des flux** : détail des expectations GE + les 3 lignes de défense.
- **B4 — Modèle de données** : les 5 schémas (raw/staging/marts/audit/cache).

### Réponses préparées aux questions probables de l'évaluateur

- *« Pourquoi ne pas avoir pris l'archi du PDF (Spark/Kafka) ? »* → Surdimensionnée
  pour 162 salariés. Un POC prouve la faisabilité, pas la capacité big data. La
  stack choisie reste scalable si le volume explose.
- *« Et si le taux change tous les ans ? »* → C'est un paramètre Kestra, pas du
  code. On relance avec le nouveau taux, l'historique est conservé par run_id.
- *« Les données sont fiables ? »* → Trois lignes de défense + un cas concret de
  bug attrapé par Great Expectations.
- *« Combien ça coûte à faire tourner ? »* → Quasi rien : Google Maps gratuit à ce
  volume (et mis en cache), Slack gratuit, stack open-source.
