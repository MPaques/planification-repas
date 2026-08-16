# Schéma pivot — contrat de données du pipeline

Le schéma pivot est le contrat que consomment le vérifieur (v1) et que rempliront les adaptateurs plateformes (v2). Fiche de cadrage : « le contrat se définit côté consommateur ». Tout est JSON, en français, unités SI.

## Recette

```json
{
  "id": "dal-corail-epinards",
  "titre": "Dal de lentilles corail aux épinards",
  "provenance": { "type": "web | generee | adaptee", "url": "https://... ou null", "adapte_de": "url ou description, si type=adaptee" },
  "portions_base": 2,
  "ingredients": [
    { "nom": "lentilles corail", "quantite": 180, "unite": "g", "categorie": "legumineuse", "bio": true, "frais_saisonnier": false }
  ],
  "etapes": ["…"],
  "temps": { "prep_min": 10, "cuisson_min": 25, "actif_min": 15 },
  "batch": {
    "batchable": true,
    "composants": [ { "nom": "dal cuit", "famille_dlc": "legumineuses_cuites" } ]
  },
  "tags": {
    "legumineuse": true,
    "poisson": false, "poisson_gras": false,
    "viande_rouge_g": 0,
    "charcuterie": false, "nitrites": false,
    "nova4": false,
    "portions_fl": 2,
    "base": "legumineuse | cereale | tubercule | autre",
    "registre": "indien",
    "cg_basse": true
  }
}
```

Notes de remplissage (phase 2) :
- `categorie` ingrédient ∈ { legumineuse, cereale, legume, fruit, viande_rouge, volaille, poisson, oeuf, laitage, matiere_grasse, condiment, autre }.
- `frais_saisonnier` : true si l'ingrédient est un fruit/légume acheté **frais** — il devra être de saison (PLA-3, dur) ; conserve/surgelé/lacto-fermenté → false.
- `portions_fl` : portions de fruits + légumes par personne apportées par la recette (SAN-4, évalué au prorata du périmètre PAR-2).
- `viande_rouge_g` : grammes **par personne** pour la recette.
- `nitrites` : true si un ingrédient charcuterie contient E249–E252 → violation dure PAR-6.

## Menu (entrée du vérifieur)

```json
{
  "semaine_du": "2026-08-17",
  "rampe_semaine": 1,
  "convives": 2,
  "recettes": { "dal-corail-epinards": { …objet Recette… } },
  "repas": [
    { "jour": "lundi", "moment": "diner", "recette_id": "dal-corail-epinards", "actif_min_assemblage": 12 }
  ],
  "plan_batch": {
    "duree_totale_min": 165,
    "taches": [ { "ordre": 1, "description": "Cuire 500 g de lentilles…", "duree_min": 30, "ressource": "plaques", "dependances": [] } ],
    "affectations": [ { "composant": "dal cuit", "famille_dlc": "legumineuses_cuites", "produit_le": "dimanche", "consomme_le": ["lundi", "mercredi"] } ]
  }
}
```

- `moment` ∈ { petit_dejeuner, dejeuner, diner, collation }. Couverture attendue (PAR-2) : 7 dîners, 2 déjeuners (samedi, dimanche), 7 petits-déjeuners, collations libres.
- `rampe_semaine` : 1–4 pendant la montée SAN-13, `null` ensuite.
- `affectations.produit_le` : « dimanche » (ou « samedi ») ; jours de consommation en clair — le vérifieur convertit en jours d'écart et compare à la famille DLC.

## Rapport de conformité (sortie du vérifieur)

```json
{
  "statut_global": "conforme | derogations | violations_dures",
  "regles": [
    { "id": "SAN-1", "statut": "conforme | viole_souple | viole_dur | non_verifie_v1", "valeur": 5, "seuil": "≥4 (rampe s1: ≥3)", "detail": "…" }
  ],
  "derogations": [ { "regle": "SAN-11", "raison": "…" } ],
  "compteurs": { "legumineuses_occ": 5, "poisson_occ": 2, "poisson_gras_occ": 1, "viande_rouge_g_pp": 90, "nova4_occ": 0, "part_batch": 0.78 }
}
```

## Produit (v2 — rempli par les adaptateurs plateformes)

```json
{
  "nom": "Lentilles corail bio 500 g", "ean": "…", "plateforme": "mon-marche | laruche | amazon | satsuki | labelleiloise",
  "prix": 2.35, "unite": "500 g", "prix_au_kg": 4.70,
  "bio": true, "origine_pays": "FR", "categorie": "legumineuse", "url": "https://…",
  "off": { "nova": 1, "additifs": [], "nutriscore": "A" }
}
```

Les adaptateurs sont jetables ; ce schéma ne l'est pas. Toute évolution du schéma se fait ici, versionnée, jamais dans un adaptateur.
