#!/usr/bin/env python3
"""disponibilites.py — phase 0 du pipeline inversé : le digest des produits
réellement disponibles sur vos connecteurs, AVANT composition des recettes.

Pipeline v2 (inversé) :
    0. capture   : <source>.py --capture pour chacune de vos boutiques
    0bis. digest : disponibilites.py → disponibilites.md   ← CE MODULE
    1. plan      : le générateur compose les recettes en piochant DANS le digest ;
                   chaque ingrédient porte son identifiant produit (sku/ref)
    2. vérif     : verifie_menu_v2.py (règles + CO₂e + nutrition + saison)
    3. chiffrage : par identifiant exact — zéro appariement flou
    4. rendu     : rendu_semaine.py

L'intérêt : plus d'appariement texte-libre → produit après coup. L'ingrédient
EST un produit dès la conception (prix, bio, origine, unité de vente connus).

Version publique : le bloc mon-marché.fr est fourni en exemple complet, et
`bloc_boutique()` sait rendre n'importe quel catalogue produit par le socle
`prestashop.py`. Ajoutez vos sources dans `generer()` — point d'extension
marqué ci-dessous.

Usage :
    py disponibilites.py                # → disponibilites.md (racine du projet)
    py disponibilites.py --sortie x.md
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from commun import DOSSIER_DATA, lire_json, stdout_utf8

CATALOGUE_MM = DOSSIER_DATA / "catalogue_monmarche.json"
SORTIE_DEFAUT = Path(__file__).parent.parent / "disponibilites.md"

TITRES_RAYON = {
    "legumes": "Légumes", "fruits": "Fruits", "viandes": "Viandes",
    "poissons": "Poissons & mer", "cremerie": "Crèmerie & œufs",
    "fromages": "Fromages", "charcuterie": "Charcuterie (SAN-8/PAR-6 : usage limité)",
    "epicerie": "Épicerie", "boulangerie-en-ligne": "Boulangerie",
}


def _nom_court(nom):
    for art in ("Les ", "Le ", "La ", "L'", "l'"):
        if nom.startswith(art):
            return nom[len(art):]
    return nom


def _ligne_mm(p):
    prix = (p["itemPrice_c"] or 0) / 100.0
    seg = [f"[{p['sku']}] {_nom_court(p['nom'])} — {prix:.2f} €"]
    if p.get("prix_kg_c"):
        seg.append(f"{p['prix_kg_c']/100:.2f} €/kg")
    if p.get("type") in ("piece", "pieceWeight") and p.get("poids_piece"):
        u = p.get("unite_s") or "pièce"
        seg.append(f"~{round(p['poids_piece']*1000)} g/{u}")
    if p.get("origine"):
        seg.append(p["origine"])
    if p.get("bio"):
        seg.append("BIO")
    return "- " + " · ".join(seg)


def bloc_monmarche(cat):
    prods = [p for p in cat["produits"].values() if p.get("dispo", 0) > 0]
    caches = len(cat["produits"]) - len(prods)
    lignes = [f"## mon-marché.fr — {len(prods)} produits disponibles",
              "",
              f"Catalogue par rayon (`/api/category`), zone de livraison du compte. "
              f"{caches} produits en rupture exclus. **Référencer le `sku` dans menu.json** "
              "pour un chiffrage exact (prix, unité de vente).", ""]
    par_rayon = {}
    for p in prods:
        par_rayon.setdefault(p["rayon"], {}).setdefault(p["sous_categorie"], []).append(p)
    for rayon, titre in TITRES_RAYON.items():
        sous = par_rayon.get(rayon)
        if not sous:
            continue
        n = sum(len(v) for v in sous.values())
        lignes += [f"### {titre} ({n})", ""]
        for sc in sorted(sous):
            ps = sorted(sous[sc], key=lambda p: _nom_court(p["nom"]).lower())
            lignes.append(f"**{sc}**")
            lignes += [_ligne_mm(p) for p in ps]
            lignes.append("")
    return lignes


def _ligne_boutique(p):
    seg = [f"[{p['ref'] or p['id']}] {p['nom']} — {p['prix']:.2f} €"]
    if p.get("poids_g"):
        g = p["poids_g"]
        seg.append(f"{g/1000:.1f} kg" if g >= 1000 else f"{g:.0f} g")
    if p.get("prix_kg"):
        seg.append(f"{p['prix_kg']:.2f} €/kg")
    if p.get("bio"):
        seg.append("BIO")
    return "- " + " · ".join(seg)


def bloc_boutique(cat, titre, chapeau, exclure=None, reporter_fin=None, titre_fin=""):
    """Bloc digest d'un catalogue produit par le socle prestashop.py.

    `exclure` / `reporter_fin` : regex compilées optionnelles sur la catégorie,
    pour écarter des rayons hors périmètre repas (boissons de bouche…) ou
    regrouper en fin de bloc les rayons à vigilance (sucré/snacks NOVA 4).
    """
    produits = [p for p in cat["produits"].values()
                if not (exclure and exclure.search(p["categorie"] or ""))]
    lignes = [f"## {titre} — {len(produits)} produits (capture du {cat['capture_du']})",
              "", chapeau, ""]
    principal, fin = {}, {}
    for p in produits:
        cible = fin if (reporter_fin and reporter_fin.search(p["categorie"] or "")) else principal
        cible.setdefault(p["categorie"] or "Divers", []).append(p)
    for groupe, entete in ((principal, None), (fin, titre_fin)):
        if entete and groupe:
            lignes += [f"### {entete}", ""]
        for categorie in sorted(groupe):
            ps = sorted(groupe[categorie], key=lambda p: (not p["bio"], p["prix_kg"] or 9e9))
            lignes.append(f"**{categorie}** ({len(ps)})")
            lignes += [_ligne_boutique(p) for p in ps]
            lignes.append("")
    return lignes


def bloc_absent(nom_source, commande):
    return [f"## {nom_source} — catalogue non capturé", "",
            f"Lancer `{commande}` puis régénérer ce digest.", ""]


def generer(sortie):
    lignes = [
        "# Disponibilités connecteurs — entrée de planification",
        "",
        "Digest de la phase 0 du pipeline v2 inversé : **composer les recettes en piochant "
        "ici**, pas l'inverse. Un ingrédient absent de ce digest ne peut pas être livré tel "
        "quel cette semaine. Priorités du référentiel : bio par défaut, origine locale "
        "(PLA-2), de saison (PLA-3), budget PAR-4.",
        "",
    ]
    if CATALOGUE_MM.exists():
        lignes += bloc_monmarche(lire_json(CATALOGUE_MM))
    else:
        lignes += bloc_absent("mon-marché.fr", "py adaptateurs/monmarche.py --capture")

    # ------------------------------------------------------------------
    # POINT D'EXTENSION — ajoutez ici vos autres sources, une par bloc.
    # Boutique PrestaShop (adaptateur bâti sur prestashop.py) :
    #
    #   CATALOGUE_X = DOSSIER_DATA / "catalogue_maboutique.json"
    #   if CATALOGUE_X.exists():
    #       lignes += bloc_boutique(lire_json(CATALOGUE_X), "Ma boutique",
    #                               "Chapeau : rôle de la source, délais, vigilances.")
    #   else:
    #       lignes += bloc_absent("Ma boutique", "py adaptateurs/maboutique.py --capture")
    # ------------------------------------------------------------------

    Path(sortie).write_text("\n".join(lignes), encoding="utf-8")
    print(f"Digest : {sortie} ({len(lignes)} lignes)")


def main():
    stdout_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", default=str(SORTIE_DEFAUT))
    args = ap.parse_args()
    generer(args.sortie)


if __name__ == "__main__":
    main()
