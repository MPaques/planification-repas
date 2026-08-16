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
| `adaptateurs/` | La couche de chiffrage : vérifieurs sur données ouvertes (Agribalyse, CIQUAL, Open Food Facts), socle PrestaShop, exemple complet mon-marché.fr, digest multi-sources, rendu HTML + PDF — voir [`adaptateurs/README.md`](adaptateurs/README.md) |
| `exemples/menu_demo.json` | Menu de démonstration au schéma pivot (essai immédiat du vérifieur et du rendu) |

Aucune donnée personnelle : tous les fichiers du foyer sont des gabarits vides
que la phase INIT remplit chez vous.

## La couche adaptateurs (fournie en grande partie)

Le chiffrage réel passe par les adaptateurs du dossier
[`adaptateurs/`](adaptateurs/README.md) :

- **Fournis complets, prêts à l'emploi** : les vérifieurs sur données ouvertes —
  CO2e ([Agribalyse](https://agribalyse.ademe.fr/), ADEME), nutrition
  ([CIQUAL](https://ciqual.anses.fr/), ANSES), NOVA/additifs
  ([Open Food Facts](https://world.openfoodfacts.org/)) — avec leurs caches,
  l'orchestrateur de rapport `verifie_menu_v2.py`, le digest de disponibilités
  et le rendu HTML + PDF.
- **Fournis en exemples** : `monmarche.py` (API JSON interne complète, catalogue
  + panier par SKU) et `prestashop.py` (socle générique `?from-xhr` pour toute
  boutique PrestaShop 1.7). Vos autres enseignes se branchent en phase INIT sur
  ces modèles ; les **catalogues capturés restent en local** (jamais dans git).

Sans aucune boutique branchée, le skill fonctionne déjà : menus vérifiés
(règles + CO2e + nutrition + saisonnalité), sans prix. Python stdlib
uniquement, aucune dépendance à installer.

## Licence

[MIT](LICENSE).
