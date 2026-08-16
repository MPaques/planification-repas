# adaptateurs/ — la couche de chiffrage du skill

Les adaptateurs branchent le skill sur le réel : catalogues et prix de vos
boutiques, CO2e, nutrition, degré de transformation. **Contrat : les
adaptateurs sont jetables, le schéma pivot ne l'est pas**
(`../references/schema-pivot.md`) — toute évolution de structure se fait dans
le schéma, jamais dans un adaptateur. Python stdlib uniquement, aucune
dépendance à installer.

## Vérifieurs sur données ouvertes (fournis complets, avec leurs caches)

| Module | Règles | Source de données |
|---|---|---|
| `agribalyse.py` | PLA-1 (CO2e/menu), signal PLA-4 (fret aérien) | [Agribalyse 4](https://agribalyse.ademe.fr/) (ADEME, API data-fair ouverte) — cache `data/agribalyse_synthese.json` fourni, à régénérer via `--maj-cache` |
| `ciqual.py` | SAN-7 (sucres libres), SAN-10 (sel), SAN-9 (ALA), SAN-3 (EPA+DHA), fibres | [CIQUAL](https://ciqual.anses.fr/) (ANSES, licence ouverte) — cache `data/ciqual_nutrition.json` fourni |
| `off.py` | SAN-8 (NOVA), PAR-6 (nitrites E249-E252) par code-barres | [Open Food Facts](https://world.openfoodfacts.org/) (ODbL, API publique) |
| `saisonnalite.py` | PLA-3 (saisonnalité France, dure) | calendrier DAT-3 versionné avec le skill |
| `composition.py` | SAN-5 (complets), SAN-6 (fruits à coque), SAN-12 (charge glycémique) | heuristiques par classes d'aliments |
| `verifie_menu_v2.py` | **orchestrateur** : vérifieur v1 du skill + tout ce qui précède + chiffrage courses → un seul rapport | `--verifieur <chemin>` ou env `VERIFY_MENU` pour pointer `scripts/verify_menu.py` |

`data/alias_ciqual.json` est la table curée ingrédient → nom Agribalyse/Ciqual
(~100 entrées génériques : légumes, légumineuses, poissons, laitages…).
Complétez-la pour vos ingrédients (`cherche_noms.py` aide à trouver le nom
canonique, `valide_alias.py` contrôle que la table résout exactement).

## Boutiques (un exemple complet + un socle réutilisable)

- `monmarche.py` — **exemple complet d'API JSON interne** : capture du
  catalogue par rayon (`--capture`), recherche, et chiffrage du panier d'un
  `menu.json` par SKU (exact, zéro appariement flou) avec coût consommé vs
  encaissé (PRX-1) et part bio (SAN-11). Utile tel quel si vous êtes client
  mon-marché.fr ; sinon, c'est le modèle à imiter.
- `prestashop.py` — **socle générique PrestaShop 1.7** : les pages catégorie
  répondent en JSON au paramètre `?from-xhr` (produits, prix, pagination).
  Écrivez un adaptateur de quelques lignes par boutique PrestaShop.
- `probe.py` — sonde de connectivité pour explorer une nouvelle boutique
  (la phase INIT du skill documente la démarche : API interne ? PrestaShop ?
  Shopify `/products.json` ? capture navigateur en dernier recours).

Les **catalogues capturés ne sont pas distribués** (données de marchands,
prix périssables) : chacun régénère les siens en local (`--capture`, ~1 min),
ils restent hors git (`.gitignore`).

## Digest et rendu

- `disponibilites.py` — fusionne vos catalogues en un digest `disponibilites.md`
  lu AVANT de composer les recettes (pipeline inversé : l'ingrédient est un
  produit dès la conception). Point d'extension commenté pour vos sources.
- `rendu_semaine.py` + `gabarit_semaine.{html,css}` — le livrable : une page
  HTML (thème clair/sombre) et un PDF A4 portrait imprimable
  (`--pdf`, via Edge/Chrome headless) : menu, plan de batch, courses par
  source, recettes, rapport de conformité complet.

## Produire une semaine

```bash
py adaptateurs/monmarche.py --capture          # vos catalogues, à chaque planification
py adaptateurs/disponibilites.py               # → disponibilites.md (digest phase 0)
# ... composer menu.json en piochant dans le digest (voir SKILL.md) ...
py adaptateurs/verifie_menu_v2.py menu.json    # rapport de conformité fusionné
py adaptateurs/rendu_semaine.py menu.json --pdf  # → HTML + PDF
```

Essai immédiat sans boutique : `py adaptateurs/verifie_menu_v2.py
exemples/menu_demo.json --verifieur scripts/verify_menu.py` puis
`py adaptateurs/rendu_semaine.py exemples/menu_demo.json --no-run`.
