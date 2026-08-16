---
name: planification-repas
description: Planifie la semaine de repas du foyer (menu, liste de courses, recettes, plan de batch cooking du week-end) sous contraintes santé / planète / temps / prix arbitrées dans un référentiel d'exigences versionné, avec vérification déterministe et rapport de conformité. Utiliser ce skill dès que l'utilisateur parle de menu de la semaine, planification de repas, batch cooking, meal prep, liste de courses, « qu'est-ce qu'on mange cette semaine », plan de cuisine, ou demande des idées de repas pour plusieurs jours — même s'il ne demande pas explicitement « le menu complet ».
---

# Planification hebdomadaire des repas

Ce skill produit chaque semaine, pour un foyer (taille paramétrable) : un
**menu choisi parmi trois variantes vérifiées**, les **recettes curées sur des
sources réelles**, une **liste de courses par source**, un **plan de batch
cooking** ordonnancé, et un **rapport de conformité** — livrés en **HTML + PDF
A4 portrait** imprimable.

> **Version partageable.** Les fichiers du foyer (`referentiel-repas.md`,
> `gouts.md`, `pantry.md`, `equipement.md`, la cadence ci-dessous) sont livrés
> en **gabarits vides** : la phase INIT les remplit avec l'utilisateur. Rien ici
> ne présuppose ses boutiques, son budget ou ses goûts.

## Cadence du foyer — à remplir en phase INIT

- **Jour de planification** : `<ex. jeudi soir>` — la commande de la source hebdo part dans la foulée.
- **Jour de livraison / marché** : `<ex. samedi matin>` — la semaine de menu court de ce jour au jour précédent la livraison suivante.
- **Créneau de batch** : `<ex. le week-end>` (séance ≤ 3 h, TPS-1) ; les DLC de `references/dlc-batch.md` se comptent depuis cette séance.
- **Sources garde-manger** (livraison à ~J+2-7) : commandes pluri-semaines, déclenchées quand `pantry.md` baisse, jamais pour la semaine en cours.
- **Magasins à pied** sans e-commerce : sections dédiées de la liste de courses.

## Principes non négociables

1. **La source d'autorité est `references/referentiel-repas.md`.** Le lire en premier, à chaque exécution, avant toute proposition. Ce fichier est arbitré ligne à ligne par l'utilisateur : ses règles priment sur toute intuition du modèle. Ne jamais inventer une exigence qui n'y figure pas, ne jamais en ignorer une qui y figure.
2. **Aucun arbitrage silencieux** (ARB-3). Quand deux contraintes s'opposent, appliquer la hiérarchie ARB (dures d'abord ; puis souples pondérées) et **afficher** chaque contrainte souple sacrifiée dans le rapport, avec la raison. Une violation de contrainte **dure** impose de replanifier, jamais de déroger.
3. **Le goût est l'objectif résiduel** (ARB-4) : une fois les contraintes satisfaites, maximiser l'intérêt gustatif. Le vérificateur du goût est l'utilisateur ; tout le reste passe par le vérifieur déterministe.
4. **Provenance obligatoire** (SOR-2) : chaque recette porte son origine — URL web, générée, ou adaptée (et de quoi).
5. **Rien ne persiste sans demande** (SOR-3) : les livrables sont éphémères. Si l'utilisateur demande de sauvegarder une recette ou un menu, joindre provenance + statut (« cuisinée » / « jamais testée »).
6. **L'état du réel entre dans le plan.** Le placard stable vit dans `assets/pantry.md` (lu chaque semaine, modifié seulement sur demande) ; les volatils — restes, récoltes du jardin, stocks à écouler — sont demandés chaque semaine en phase 1. Ce qui est au placard ne se rachète pas, et une recette qui ne coûte qu'une épice du placard est un levier de goût à coût nul.

## La couche adaptateurs — atelier local

Les connecteurs qui chiffrent ce que le skill vérifie (catalogues et prix des
boutiques, CO2e Agribalyse, nutrition CIQUAL, NOVA/additifs Open Food Facts)
vivent dans un **dossier atelier local** : `<chemin à renseigner en phase INIT>`
— son `README.md` est la doc de référence (commandes, état des connecteurs,
pièges d'API). Si l'atelier est inaccessible dans la session : le dire, dérouler
le workflow en mode dégradé (sans catalogues, prix, CO2e) et marquer la
dégradation au rapport.

## Phase INIT — premier lancement (ou nouveau foyer, nouvelle source)

Le workflow hebdomadaire suppose un système initialisé. Dérouler d'abord cette
phase si l'un de ces marqueurs manque : référentiel non arbitré (pas
d'« arbitrage clos » au journal des versions), atelier introuvable,
`gouts.md` / `pantry.md` / `equipement.md` vides, aucune source connectée.
Elle est **ré-entrante**, source par source.

1. **Cadrage des exigences.** Interviewer l'utilisateur, puis proposer un
   référentiel initial complet (santé / planète / temps / prix / goût /
   sécurité — bases : EAT-Lancet, recommandations nationales type PNNS/ANSES,
   OMS) et le faire **arbitrer ligne à ligne** : chaque règle validée, modifiée
   ou supprimée par lui, statut dur/souple explicite, journal des versions tenu.
   Le référentiel n'est acquis qu'à l'arbitrage clos ; ensuite, toute évolution
   passe par avenant versionné.
2. **Paramètres du foyer.** Convives (PAR-1), couverture des repas (PAR-2),
   équipement (PAR-5 → `assets/equipement.md`), budget (PAR-4), et la **cadence
   réelle** (jour de planification, livraison, créneau de batch) — l'inscrire en
   tête de ce fichier.
3. **Sources d'approvisionnement.** Demander où le foyer achète réellement :
   courses hebdo fraîches, garde-manger en ligne, magasins à pied. Pour chaque
   site marchand nommé, **explorer l'accès catalogue** par sondes HTTP (API JSON
   interne ? PrestaShop → `?from-xhr` sur une page catégorie ? Shopify →
   `/products.json` ? sinon capture navigateur si WAF) puis **construire
   l'adaptateur** dans l'atelier (capture → normalisation → intégration au
   digest des disponibilités) et le tester bout en bout. Un magasin physique
   sans e-commerce exploitable devient une section dédiée de la liste de
   courses.
4. **Fichiers du foyer.** Amorcer `assets/gouts.md` (registres, préférences
   graduées), `assets/pantry.md` (placard stable par rayon) et
   `assets/equipement.md` (matériel détaillé, usages à créditer) avec
   l'utilisateur — des lignes à faire valider, jamais des inventions
   silencieuses.
5. **Première semaine.** Activer la rampe SAN-13 (montée progressive en fibres)
   et annoncer que budget et CO2e se calibrent sur les 4 premières semaines.

## Workflow hebdomadaire

### Phase 0 — Disponibilités

- Rafraîchir le catalogue de la source hebdo (`py adaptateurs/<source>.py --capture`) à chaque planification ; les catalogues garde-manger à cadence mensuelle.
- Générer le digest des disponibilités (`py adaptateurs/disponibilites.py`) et **le lire avant toute composition** : les frais s'y piochent avec leur identifiant produit (sku/ref), reporté dans `menu.json` pour un chiffrage exact.

### Phase 1 — État du réel (placard, restes, jardin, matériel)

- Lire `assets/pantry.md`, `assets/gouts.md` et `assets/equipement.md` — une version fournie en conversation prime.
- Demander en **une seule salve** : restes à écouler, récoltes du jardin, niveaux du garde-manger, retours sur la semaine passée.
- Les réponses deviennent des contraintes de composition — un reste à écouler est un ingrédient imposé, une récolte du jardin est prioritaire sur tout achat. Proposer la mise à jour de `pantry.md` si un écart apparaît.

### Phase 2 — Cadrage de la semaine (questionnaire)

- Un questionnaire structuré unique (AskUserQuestion si l'outil existe, sinon une seule question groupée) : ① soirs hors périmètre (absences, invités) ; ② envies et registres de la semaine, produit star éventuel ; ③ paramètres si écart au référentiel ; ④ demandes particulières.
- Lire `references/saisonnalite-fr.md` pour le mois courant avant de composer.

### Phase 3 — Trois variantes de menu

- Composer **trois variantes contrastées** — pas trois nuances du même menu : faire varier le registre dominant, la structure du batch, le produit star. Chacune couvre PAR-2, respecte les contraintes de composition, pioche les frais dans le digest et mobilise le placard.
- **Tirer crédit du matériel** (`assets/equipement.md`) : chaque appareil est un levier, pas seulement une contrainte de faisabilité — cuisson longue autonome en parallèle du four (c'est ce qui fait tenir TPS-1), appareils spécialisés exploités. Une variante qui exploite un appareil sous-utilisé le mentionne dans sa signature.
- **Chaque variante passe le vérifieur avant d'être présentée** (`py adaptateurs/verifie_menu_v2.py variante_X.json` — ou `scripts/verify_menu.py` en mode dégradé). Violation dure → recomposer, jamais déroger (ARB-1).
- Présenter compact : par variante, un tableau jours × moments + trois lignes de signature (registre, logique de batch, coût estimé / CO2e) + les dérogations souples assumées. Laisser choisir ; l'adaptation par prompt est bienvenue — toute adaptation repasse le vérifieur.

### Phase 4 — Curage des recettes (variante choisie seulement)

- Pour chaque plat : chercher 1-2 recettes réelles en ligne (recherche web ; `scripts/extract_recipe.py <url>` extrait le balisage schema.org/Recipe) et s'en servir pour fiabiliser techniques, proportions, temps et tours de main.
- **Adapter chaque recette au matériel réel** (`assets/equipement.md`) — temps et températures de l'appareil, pas ceux de la source. L'adaptation compte comme adaptation SOR-2.
- Provenance SOR-2 : « adaptée de <URL> » — ou « générée » si rien de probant.
- Si le curage change des ingrédients ou des quantités : mettre à jour `menu.json` et **re-vérifier**.

### Phase 5 — Livrables (HTML + PDF imprimable)

- Le point d'entrée de rendu de l'atelier (ex. `py adaptateurs/rendu_semaine.py menu.json --pdf`) produit une page HTML unique **et** un PDF A4 portrait : menu, plan de batch ordonnancé (durées, dépendances, ressources, consignes SEC-2), liste de courses, recettes avec provenance, rapport de conformité SOR-1.
- Publier l'HTML en artifact si l'outil existe ; envoyer le PDF en fichier.
- La liste de courses se présente **par source et par échéance** : source hebdo (à commander au jour de planification), magasins à pied, garde-manger à recommander **seulement si le niveau pantry est bas**.

### Phase 6 — Clôture

- Rappeler en une ligne que rien n'est sauvegardé sauf demande.
- Retour de goût → proposer `gouts.md` ; commande garde-manger passée ou pot fini → proposer `pantry.md` ; recette à garder → corpus avec provenance + statut.

## Ce que le système ne vérifie pas (dire vrai)

- Les listings de certaines boutiques n'exposent **ni stock ni code-barres** : produit listé = présumé commandable ; contrôle NOVA/additifs par EAN (Open Food Facts) à l'achat.
- Les repas hors périmètre PAR-2 échappent au contrôle : les cibles journalières s'évaluent au prorata du périmètre planifié.
- Le bio de certaines sources est une heuristique sur le nom (un plancher, pas une certitude).

## Références — quand lire quoi

- `references/referentiel-repas.md` — **toujours, en premier** (gabarit à arbitrer en phase INIT).
- `assets/pantry.md` + `assets/gouts.md` + `assets/equipement.md` — phase 1 ; fichiers de l'utilisateur, ne jamais les modifier sans demande.
- `references/saisonnalite-fr.md` — phases 2-3, mois courant (calendrier France ; à remplacer si autre zone).
- `references/schema-pivot.md` — phases 3-4, pour construire recettes et menu.json.
- `references/dlc-batch.md` — phase 3, affectation des composants batch ; le vérifieur embarque la même table.
- `README.md` de l'atelier — commandes et état des connecteurs.
