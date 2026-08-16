# Durées de vie des composants batchés — SEC-1 / SEC-2

**Statut : ordres de grandeur prudents, à consolider sur sources officielles (ANSES / DGAL) avant que le vérifieur fasse foi** (question ouverte du référentiel). En attendant, appliquer tel quel — l'erreur est du côté sûr.

Conditions de base (SEC-2, dures) : refroidissement en moins de **2 h** après cuisson, contenants plats (≤ 5 cm d'épaisseur) pour refroidir vite, réfrigérateur à **< 4 °C**. Réchauffer à cœur avant service ; réchauffer ne remet **pas** le compteur à zéro.

| Famille (`famille_dlc`) | Frigo max après production | Congélation | Notes |
|---|---|---|---|
| `riz_cuit` | **2 jours** | oui — le jour même | Bacillus cereus : refroidir vite, pas d'exception |
| `cereales_cuites` (pâtes, quinoa, orge, sarrasin…) | 3 jours | oui | |
| `legumineuses_cuites` | 3 jours | oui | l'eau de cuisson à part se congèle aussi |
| `viandes_cuites` (volaille incluse) | 3 jours | oui | |
| `poisson_cuit` | **2 jours** | correct mais texture dégradée | privilégier conserves pour le tard-semaine |
| `oeufs_durs` | 3 jours (écalés) | non | |
| `soupes_sauces` (soupes, currys, sauces cuites, fonds) | 3 jours | oui — excellent | |
| `legumes_rotis` | 3 jours | oui | |
| `crudites` (lavées, coupées) | 2 jours | non | laver/couper au plus tard la veille |
| `sauces_crues` (pesto, vinaigrettes maison…) | 2 jours | pesto : oui | |
| `lacto_fermente` (aboutis, en saumure) | hors décompte | inutile | l'acidité protège — garder au frais |
| `congele` | hors décompte | — | décongélation la veille au réfrigérateur, jamais à l'air ambiant ; ne jamais recongeler un produit décongelé |

Règle d'affectation (vérifiée par `scripts/verify_menu.py`, violation **dure**) : un composant produit le week-end ne peut être assigné à un jour au-delà de sa durée frigo — au-delà, passer par la congélation dès le jour de production, avec décongélation planifiée la veille.

Conséquence pratique pour la composition (phase 3) : le riz et le poisson cuits vivent en début de semaine ; les soupes, currys, légumineuses et rôtis tiennent jusqu'à mercredi/jeudi ; le jeudi et le vendredi s'appuient sur congelé planifié, conserves (sardines, maquereaux), lacto-ferments, ou assemblage minute ≤ 20 min.
