#!/usr/bin/env python3
"""off.py — connecteur Open Food Facts (DAT-1) : NOVA, additifs (nitrites
E249-E252 → PAR-6 dur), sucres et sel /100 g, labels bio.

Usage :
    py off.py --ean 3017624010701
    py off.py --ean 3017624010701 --ean 7622210449283
    py off.py --recherche "sardines huile olive"    # trouver un EAN

Sortie : bloc « off » de l'objet Produit du schéma pivot + verdicts.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from commun import ecrire_json, encode_qs, get_json, stdout_utf8

BASE = "https://world.openfoodfacts.org"
CHAMPS = ("product_name,brands,nova_group,nutriscore_grade,ecoscore_grade,"
          "additives_tags,labels_tags,nutriments,quantity")
NITRITES = {"en:e249", "en:e250", "en:e251", "en:e252"}


def fiche(ean):
    try:
        d = get_json(f"{BASE}/api/v2/product/{ean}.json?fields={CHAMPS}")
    except RuntimeError as e:
        return {"ean": ean, "erreur": f"introuvable ou API en échec ({e})"}
    p = d.get("product") or {}
    additifs = p.get("additives_tags") or []
    nutr = p.get("nutriments") or {}
    labels = p.get("labels_tags") or []
    nova = p.get("nova_group")
    resultat = {
        "ean": ean,
        "nom": p.get("product_name"),
        "marque": p.get("brands"),
        "quantite": p.get("quantity"),
        "off": {
            "nova": nova,
            "additifs": [a.removeprefix("en:").upper() for a in additifs],
            "nutriscore": (p.get("nutriscore_grade") or "").upper() or None,
            "greenscore": (p.get("ecoscore_grade") or "").upper() or None,
        },
        "nitrites_e249_252": bool(NITRITES & set(additifs)),
        "bio_label": any("organic" in l or "ab-agriculture-biologique" in l for l in labels),
        "sucres_g_100g": nutr.get("sugars_100g"),
        "sel_g_100g": nutr.get("salt_100g"),
        "verdicts": {},
    }
    v = resultat["verdicts"]
    if resultat["nitrites_e249_252"]:
        v["PAR-6"] = "viole_dur — nitrites/nitrates ajoutés (E249-E252)"
    if nova == 4:
        v["SAN-8"] = "compte dans le plafond NOVA 4 (<= 1 occurrence/sem)"
    if nova is None:
        v["donnees"] = "NOVA absent de la fiche OFF — tag nova4 à renseigner à la main"
    return resultat


def recherche(termes):
    q = encode_qs(search_terms=termes, page_size=5, json=1,
                  fields="code,product_name,brands,nova_group")
    d = get_json(f"{BASE}/cgi/search.pl?{q}")
    return [{"ean": p.get("code"), "nom": p.get("product_name"),
             "marque": p.get("brands"), "nova": p.get("nova_group")}
            for p in d.get("products", [])]


def main():
    stdout_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--ean", action="append", default=[])
    ap.add_argument("--recherche")
    ap.add_argument("--rapport")
    args = ap.parse_args()

    if args.recherche:
        for r in recherche(args.recherche):
            print(f"  {r['ean']}  {r['nom']} ({r['marque']}) NOVA {r['nova']}")
        return
    if not args.ean:
        ap.error("--ean <code-barres> ou --recherche <termes> requis")

    fiches = [fiche(e) for e in args.ean]
    for f in fiches:
        if "erreur" in f:
            print(f"{f['ean']} : {f['erreur']}")
            continue
        o = f["off"]
        print(f"{f['ean']}  {f['nom']} ({f['marque']}, {f['quantite']})")
        print(f"  NOVA {o['nova']} | Nutri-Score {o['nutriscore']} | Green-Score {o['greenscore']} | "
              f"sucres {f['sucres_g_100g']} g | sel {f['sel_g_100g']} g /100g | bio {f['bio_label']}")
        if o["additifs"]:
            print(f"  additifs : {', '.join(o['additifs'])}")
        for regle, verdict in f["verdicts"].items():
            print(f"  [{regle}] {verdict}")
    if args.rapport:
        ecrire_json(args.rapport, fiches)
        print(f"Rapport : {args.rapport}")


if __name__ == "__main__":
    main()
