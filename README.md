# planification-repas — skill Claude de planification hebdomadaire des repas

Un skill [Claude](https://claude.com/claude-code) qui planifie la semaine de
repas d'un foyer sous contraintes **santé / planète / temps / prix**, avec :

- un **référentiel d'exigences versionné**, arbitré ligne à ligne par
  l'utilisateur (bases : EAT-Lancet, PNNS/ANSES, OMS, NOVA) — la source
  d'autorité du système ;
- un **vérifieur déterministe** (`scripts/verify_menu.py`) indépendant du
  générateur : chaque menu est contrôlé règle par règle avant d'être présenté,
  et livré avec son **rapport de conformité** (aucun arbitrage silencieux) ;
- un workflow en 7 phases : disponibilités des boutiques → état du réel
  (placard, restes, jardin, matériel) → questionnaire de cadrage → **trois
  variantes de menu contrastées et vérifiées** → choix + curage des recettes
  sur des sources web réelles → livrables **HTML + PDF imprimable** (menu,
  recettes, liste de courses par source, plan de batch cooking ordonnancé) ;
- une **phase INIT** ré-entrante qui personnalise tout au premier lancement :
  arbitrage du référentiel, cadence du foyer, connexion des sites marchands
  (exploration API + adaptateurs), inventaires goûts / placard / équipement.

## Installation

**Claude.ai / Claude Code (le plus simple)** : télécharger
[`planification-repas.skill`](planification-repas.skill) et l'importer dans vos
skills (Settings → Capabilities → Skills), ou glisser le fichier dans une
conversation et cliquer « Save skill ».

**Claude Code (manuel)** : cloner ce dépôt dans votre dossier de skills :

```bash
git clone https://github.com/MPaques/planification-repas ~/.claude/skills/planification-repas
```

Au premier lancement (« planifie ma semaine de repas »), le skill détecte
qu'aucun foyer n'est initialisé et déroule la phase INIT.

## Ce que contient ce dépôt

| Fichier | Rôle |
|---|---|
| `SKILL.md` | Le workflow complet (INIT + 7 phases hebdomadaires) |
| `references/referentiel-repas.md` | **Gabarit** du référentiel d'exigences, à arbitrer ligne à ligne |
| `references/schema-pivot.md` | Contrat de données recettes / menu / rapport (JSON) |
| `references/dlc-batch.md` | Durées de vie des composants batch (sécurité) |
| `references/saisonnalite-fr.md` | Calendrier de saisonnalité France (à remplacer selon votre zone) |
| `assets/gouts.md`, `pantry.md`, `equipement.md` | Gabarits des fichiers du foyer (préférences, garde-manger, matériel) |
| `scripts/verify_menu.py` | Vérifieur déterministe (stdlib Python uniquement) |
| `scripts/extract_recipe.py` | Extraction schema.org/Recipe d'une URL vers le schéma pivot |

Aucune donnée personnelle : tous les fichiers du foyer sont des gabarits vides
que la phase INIT remplit chez vous.

## La couche adaptateurs (construite chez vous)

Le chiffrage réel — catalogues et prix de **vos** boutiques en ligne, CO2e
([Agribalyse](https://agribalyse.ademe.fr/)), nutrition (CIQUAL), NOVA/additifs
([Open Food Facts](https://world.openfoodfacts.org/)) — passe par un « atelier »
d'adaptateurs que le skill construit **avec vous** en phase INIT, boutique par
boutique (API JSON interne, endpoints PrestaShop/Shopify, ou capture navigateur
en dernier recours). L'atelier n'est pas distribué ici : il dépend de vos
enseignes, et les adaptateurs sont jetables par conception — seul le schéma
pivot est stable. Sans atelier, le skill fonctionne en mode dégradé (menus
vérifiés, sans prix ni CO2e chiffrés).

## Licence

[MIT](LICENSE).
