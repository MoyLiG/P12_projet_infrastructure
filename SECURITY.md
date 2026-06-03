# Audit de sécurité — POC Avantages Sportifs (P12)

> Audit réalisé le 2026-06-01 sur le code, la configuration et les dépendances.
> Périmètre : POC ETL **local** (pas d'exposition Internet). Les phases réseau
> classiques (DNS, scan de ports, TLS, XSS web) ne s'appliquent pas — ce n'est
> pas une web app. L'audit cible : secrets, injections SQL, permissions DB,
> exposition PII, configuration Docker, dépendances (CVE), RGPD.

Outils : **bandit** (SAST), **pip-audit** (CVE), analyse manuelle.

---

## Synthèse

| Sévérité | Nombre | Statut |
|---|---|---|
| 🔴 Critical | 0 | — |
| 🟠 High | 1 | ✅ Corrigé |
| 🟡 Medium | 3 | 2 corrigés / 1 documenté |
| 🔵 Low | 3 | Documentés (acceptés pour le POC) |

**Bandit** : 0 issue Medium/High sur 1031 lignes. Code propre.

---

## 🟠 HIGH — Socket Docker monté dans Kestra  ✅ CORRIGÉ

**Catégorie** : CWE-250 (exécution avec privilèges inutiles) / évasion conteneur.
**Affecté** : `docker-compose.yml` (volume `/var/run/docker.sock`).

**Description** : le montage du socket Docker donnait au conteneur Kestra un
contrôle total du démon Docker de l'hôte (équivalent root hôte). Une exécution
de code arbitraire dans Kestra aurait permis une évasion vers la machine.

**Pourquoi c'était là** : prévu pour le *Docker task runner* Kestra. Or on est
passé au *Process runner* → le socket est devenu **inutile**.

**Remédiation appliquée** : montage retiré du `docker-compose.yml`. Les tâches
tournent en Process runner, sans accès Docker.

---

## 🟡 MEDIUM — Dépendances vulnérables (CVE)  ✅ CORRIGÉ

**Catégorie** : OWASP A06 (composants vulnérables).

`pip-audit` a relevé 9 CVE. Les actionnables (utilisés en runtime) :

| Paquet | CVE | Fix appliqué |
|---|---|---|
| requests 2.32.3 | CVE-2024-47081 + CVE-2026-25645 | → **2.33.0** |
| setuptools 65.5.0 | CVE-2024-6345 (RCE via package index) | → **≥78.1.1** |
| python-dotenv 1.0.1 | CVE-2026-28684 | → **≥1.2.2** |

**Résultat** : **8 CVE sur 9 corrigées** (pip-audit re-passé). `requirements.txt`
+ flow Kestra mis à jour (requests 2.33.0), imports vérifiés compatibles
(googlemaps, great-expectations).

**CVE restante** : `pytest 8.3.3` (CVE-2025-71176, fix 9.0.3) — dépendance de
**test uniquement**, jamais exécutée en runtime/prod. Non bloquant. Bump vers
pytest 9.x différé (saut majeur, à tester séparément).

---

## 🟡 MEDIUM — Mots de passe DB en clair dans le SQL versionné  📝 DOCUMENTÉ

**Affecté** : `sql/003_grants_roles.sql` (`CREATE ROLE ... PASSWORD '...'`).

**Description** : les mots de passe des rôles (`etl_writer`, etc.) sont en dur
dans un fichier versionné. Acceptable pour un POC **local** (valeurs `change-me-*`
non sensibles), inacceptable en production.

**Remédiation recommandée (prod)** : générer les rôles via un script qui lit les
mots de passe depuis l'environnement / un secret manager (Vault, AWS Secrets
Manager), jamais en dur dans le SQL. Rotation périodique.

---

## 🟡 MEDIUM — UI Kestra sans authentification  📝 DOCUMENTÉ

**Affecté** : `docker-compose.yml` (`basicAuth: enabled: false`).

**Description** : l'UI Kestra (port 8080) est ouverte sans authentification.
Sur `localhost` en POC c'est sans risque ; exposée sur un réseau, ce serait
une porte ouverte sur les exécutions et les logs (qui contiennent de la PII).

**Remédiation recommandée (prod)** : activer `basicAuth` (ou SSO/OIDC), ne pas
publier le port 8080 hors du réseau interne, mettre Kestra derrière un reverse
proxy avec TLS.

---

## 🔵 LOW — `TRUNCATE` construit en f-string  📝 ACCEPTÉ

**Affecté** : `src/load/db.py` (`f"TRUNCATE {targets} CASCADE"`).

**Description** : construction SQL par concaténation (bandit B608). **Non
exploitable** : `truncate_tables()` n'est appelé qu'avec des littéraux codés en
dur (`"raw.employees_xlsx"`, `"raw.sports_xlsx"`), jamais avec une entrée
externe. Tout le reste du code utilise des requêtes **paramétrées** (`text()` +
`:params`).

**Remédiation recommandée (defense in depth)** : valider `qualified_names`
contre une liste blanche de tables autorisées avant interpolation.

---

## 🔵 LOW — PII envoyée à Slack (service externe)  📝 RGPD

**Affecté** : `src/load/slack.py`.

**Description** : les messages d'encouragement contiennent le prénom + nom du
salarié et son activité. Ces données transitent vers Slack (sous-traitant).
C'est **fonctionnellement voulu** (la note de cadrage demande des messages
nominatifs), mais cela a des implications RGPD.

**Remédiation / conformité** :
- Documenter Slack comme sous-traitant dans le registre de traitement.
- Base légale : intérêt légitime / consentement du salarié à la publication.
- Prévoir un opt-out (un salarié peut refuser la publication nominative).

---

## 🔵 LOW — PostgreSQL exposé sur 0.0.0.0:5432  📝 ACCEPTÉ

**Description** : le port 5432 est publié sur l'hôte (nécessaire pour PowerBI
Desktop en démo). Accessible depuis le réseau local de la machine. Acceptable
en POC ; en prod, restreindre au réseau interne / VPN.

---

## ✅ Points forts (sécurité bien traitée)

- **SQL paramétré** partout (SQLAlchemy `text()` + bind params) — pas d'injection.
- **Moindre privilège** : 3 rôles PG distincts ; l'analyste/PowerBI ne lit que
  `marts` et **jamais** les PII de `staging.employees`.
- **Row Level Security** active sur `staging.employees`.
- **Pseudonymisation** : `nom_hash` = SHA-256 **salé** (sel secret via env,
  `SecretStr`) — keyed hashing, pas un simple hash ré-identifiable.
- **Audit trail RGPD** : triggers sur `marts.eligibility_*` →
  `audit.eligibility_changes` (qui/quoi/quand).
- **Secrets hors code** : `.env` git-ignored, `.env.example` en placeholders,
  secrets Kestra en base64, aucun secret en dur (vérifié bandit + grep).
- **Cache géo** : pas de PII dans `cache.gmaps_distance` (clé = hash d'adresse).

---

## Recommandations prioritaires pour une mise en production

1. Secrets DB via secret manager (pas dans le SQL).
2. Activer l'authentification Kestra + TLS + reverse proxy.
3. Ne pas publier 5432/8080 hors réseau interne.
4. Faire tourner le sel PII (`PII_HASH_SALT`) et le garder ≥ 32 octets aléatoires.
5. Intégrer `pip-audit` + `bandit` dans une CI (GitHub Actions) — fail si CVE High.
6. Chiffrement at-rest du volume PostgreSQL (déjà documenté : BitLocker).
