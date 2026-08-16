# Référentiel d'exigences — planification hebdomadaire des repas (GABARIT)

> v0.0 · **Gabarit à arbitrer** — ce fichier est une proposition initiale complète,
> à passer **ligne à ligne** avec l'utilisateur en phase INIT : chaque règle est
> validée, modifiée ou supprimée par lui ; les champs `<…>` se remplissent à
> l'interview. L'arbitrage est clos quand plus aucune ligne ne porte
> `[proposé]`. Ensuite, toute évolution passe par **avenant versionné** au
> journal.
> Ce fichier est la **source d'autorité** du système : le générateur le lit en
> entrée ; les vérifieurs, indépendants du générateur, contrôlent chaque menu
> contre lui. Chaque règle porte : énoncé testable · statut **[dur]** /
> **[souple]** · source ou rationale.
> Convention : ARB arbitrage · PAR paramètres · SAN santé · PLA planète · TPS temps · PRX prix · GOU goût · SEC sécurité · SOR sorties · DAT données.

## 0 · Hiérarchie d'arbitrage (ARB)

- ARB-1 [dur] [proposé] — Les contraintes **dures** sont non négociables : un plan qui en viole une est **replanifié**, jamais dérogé. Sont dures : SEC-*, les planchers/plafonds désignés [dur] ci-dessous, les exclusions PAR-6.
- ARB-2 [proposé] — Les contraintes **souples** sont pondérées dans un ordre à arbitrer, par exemple : **santé > bio > CO2e > prix > local (départage)**.
- ARB-3 [dur] [proposé] — **Aucun arbitrage silencieux** : toute violation d'une contrainte souple est affichée au rapport de conformité (SOR-1), avec la règle sacrifiée et la raison.
- ARB-4 [proposé] — Le **goût est l'objectif résiduel** : maximisé une fois les contraintes satisfaites ; son vérificateur est humain.

## 1 · Paramètres d'entrée (PAR)

- PAR-1 [à remplir] — Convives : `<n>` (paramétrable).
- PAR-2 [à remplir] — Couverture planifiée : `<ex. 7 dîners + 2 déjeuners de week-end + 7 petits-déjeuners + collations>`. Les repas hors périmètre échappent au contrôle ; les cibles journalières s'évaluent au prorata.
- PAR-3 [à remplir] — Budgets temps : séance batch ≤ `<3 h ?>` ; assemblage d'un dîner de semaine ≤ `<20-25 min actives ?>`.
- PAR-4 [à remplir] — Enveloppe courses : `<€/mois>` → intervalle préférentiel `<min-max €/semaine>` ; pénalité hors bande (PRX-1) ; à recalibrer sur les 4 premières semaines mesurées.
- PAR-5 [à remplir] — Équipement déclaré : l'inventaire d'autorité vit dans **`assets/equipement.md`** (maintenu par l'utilisateur). Toute recette doit être exécutable avec, et le générateur doit en **tirer crédit** comme levier de goût et de temps, pas seulement le subir comme contrainte.
- PAR-6 [dur] [à remplir] — Allergies : `<…>`. Aversions absolues : `<…>`. Exclusions produits : `<ex. charcuterie avec nitrites ajoutés E249-E252 — rationale : avis ANSES 2022, lien nitrites / cancer colorectal>`. Préférences graduées : `assets/gouts.md`.

## 2 · Santé (SAN)

Sources proposées : EAT-Lancet pour les cibles, recommandations nationales (type PNNS/ANSES pour la France) pour planchers et plafonds, OMS pour sucres et sel, NOVA pour la transformation. Portions par personne.

- SAN-1 [proposé] — Légumineuses en base quasi quotidienne : cible `<~75 g/j, ≥ 6 occ/sem>` ; plancher dur `<≥ 4 repas/sem>`. **Montée progressive** (SAN-13) les premières semaines.
- SAN-2 [proposé] — Viande rouge ≤ `<~100 g/sem (EAT-Lancet)>` et charcuterie exceptionnelle ; plafonds nationaux (`<PNNS : 500 g / 150 g>`) en backstop dur.
- SAN-3 [souple] [proposé] — Poisson `<2 repas/sem dont 1 gras>` (EPA/DHA) ; petits pélagiques et conserves bienvenus (cohérent PLA-5).
- SAN-4 [dur plancher] [proposé] — Fruits et légumes ≥ `<5 portions/j>`.
- SAN-5 [souple] [proposé] — Féculents : ≥ `<la moitié>` en complet ou semi-complet. Note : le complet apporte fibres et IG bas, mais le cadmium du blé se concentre dans les enveloppes — pour le pain maison, le choix du taux d'extraction reste un arbitrage personnel hors vérifieur.
- SAN-6 [souple] [proposé] — Fruits à coque non salés : `<~30 g/j (poignée PNNS) ou ~50 g/j (EAT-Lancet) — à arbitrer>`.
- SAN-7 [proposé] — Sucres libres : cible < `<20-25 g/j>` (OMS idéal < 5 % AET), alerte au double.
- SAN-8 [proposé] — Ultra-transformés (NOVA 4) ≤ `<1 occurrence/sem>` dans les menus planifiés.
- SAN-9 [proposé] — Matières grasses : `<ex. olive en priorité>` + **garde-fou ALA** (oméga-3 végétal) : un apport quotidien par colza/noix/lin cru — l'olive en est quasi dépourvue.
- SAN-10 [souple] [proposé] — Sel : viser < `<5 g/j>` (OMS) ; règle de plan : pas de resalage systématique.
- SAN-11 [souple] [proposé] — **Bio par défaut** sur le panier (axiome de précaution, à assumer ou supprimer) ; dérogation si indisponible ou hors budget, affichée. Indicateur : part bio en valeur, cible `<≥ 80 % ?>`.
- SAN-12 [souple] [proposé] — **Charge glycémique basse** : légumineuses en base, complets al dente, fruits entiers plutôt que jus, sucres rapides limités. Vérification heuristique par classes d'aliments.
- SAN-13 [souple] [proposé] — **Confort digestif, montée progressive** : rampe de fibres sur `<~4 semaines>` (le passage aux cibles EAT-Lancet augmente fortement les fibres) ; légumineuses préparées pour la digestibilité (trempage à eau jetée, cuisson complète, corail en début de rampe) ; pas un régime FODMAP strict.

## 3 · Planète (PLA)

- PLA-1 [souple] [proposé] — Empreinte du panier ≤ `<20 kg CO2e/pers/sem>` ; alerte au-delà de `<30>`. Vérifieur : Agribalyse. Seuil à recalibrer après 4 semaines mesurées.
- PLA-2 [souple, départage] [proposé] — À scores santé et CO2e comparables, préférer l'origine `<locale > proche > reste>` — le local départage, il n'optimise pas.
- PLA-3 [dur] [proposé] — Fruits et légumes **frais** : de saison (calendrier local du mois courant) ; le hors-saison passe par conserve, surgelé, lacto-fermenté — jamais par le frais importé ou de serre chauffée. Des dérogations bornées peuvent s'ajouter par avenant.
- PLA-4 [dur] [proposé] — Aucun produit à fret **aérien**.
- PLA-5 [souple] [proposé] — Poisson : espèces non surexploitées ; petits pélagiques et bivalves privilégiés.

## 4 · Temps (TPS)

- TPS-1 [dur] [proposé] — Plan de batch exécutable en ≤ PAR-3, ordonnancé : dépendances explicites, ressources mutualisées, parallélisation.
- TPS-2 [dur] [proposé] — Chaque dîner de semaine : ≤ `<25 min actives>` à partir des composants batchés.
- TPS-3 [souple] [proposé] — ≥ `<70 %>` des repas de semaine issus de la séance batch.

## 5 · Prix (PRX)

- PRX-1 [souple] [proposé] — Coût estimé du panier dans l'intervalle PAR-4 ; pénalité proportionnelle hors bande. Tout dépassement affiché avec sa cause.
- PRX-2 [info] [proposé] — Dérive : moyenne glissante sur 4 semaines affichée contre la baseline.

## 6 · Goût (GOU)

- GOU-1 [souple] [proposé] — Variété intra-semaine : aucun plat principal répété ; ≥ `<3>` bases différentes ; ≥ `<3>` registres culinaires.
- GOU-2 [souple] [proposé] — Respect de `gouts.md` ; seules les exclusions PAR-6 sont dures.
- GOU-3 [objectif] [proposé] — À contraintes satisfaites, maximiser l'intérêt gustatif. Vérificateur : humain.

## 7 · Sécurité du batch (SEC)

- SEC-1 [dur] [proposé] — Chaque composant batché porte une **durée de vie** ; le plan n'assigne aucun composant au-delà (table : `references/dlc-batch.md` — ordres de grandeur prudents, à consolider sur sources officielles).
- SEC-2 [dur] [proposé] — Refroidissement < 2 h avant mise au froid < 4 °C ; contenants plats ; consigne inscrite dans chaque plan de batch.

## 8 · Sorties du système (SOR)

- SOR-1 [dur] [proposé] — Chaque menu hebdo est livré avec un **rapport de conformité** : chaque règle → conforme / violée / dérogée (avec raison), plus scores CO2e, prix, part bio, temps.
- SOR-2 [dur] [proposé] — **Provenance** de chaque recette : URL source / générée / adaptée (et de quoi).
- SOR-3 [proposé] — Livrables hebdo éphémères par défaut ; entrée au corpus à la demande uniquement, avec provenance + statut « cuisinée / jamais testée ».

## 9 · Sources de données des vérifieurs (DAT)

- DAT-1 [proposé] — **Open Food Facts** (ODbL, API publique, par code-barres) : NOVA, additifs, sucres/sel par 100 g, labels.
- DAT-2 [proposé] — **Agribalyse** (ADEME) : CO2e par aliment, vérifieur de PLA-1. (Zone France ; à remplacer hors France.)
- DAT-3 [proposé] — **Calendrier de saisonnalité** par mois, vérifieur de PLA-3 — fichier statique versionné avec le référentiel.

## Questions ouvertes du référentiel

- [ ] Tous les champs `<…>` ci-dessus.
- [ ] Seuils PAR-4 (prix) et PLA-1 (CO2e) : à calibrer sur les 4 premières semaines mesurées.
- [ ] Table SEC-1 : consolidation sur sources officielles avant que le vérifieur fasse foi.

## Journal des versions

- v0.0 — gabarit initial (proposition IA, aucun arbitrage).
