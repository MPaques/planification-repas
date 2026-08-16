#!/usr/bin/env python3
"""ciqual.py — connecteur CIQUAL (ANSES) : nutrition des ingrédients bruts.

OFF est indexé par code-barres → inutile pour les aliments bruts sans EAN. La
composition nutritionnelle des aliments génériques, elle, vit dans **CIQUAL**
(table ANSES), indexée par **code Ciqual** — celui que l'on a déjà pour chaque
ingrédient via l'appariement Agribalyse (Agribalyse est bâtie sur Ciqual).

Ce module chiffre, sans aucun code-barres :
- **SAN-7** (sucres libres, cible < 20 g/j) — ne compte que les sucres des
  ingrédients « sources de sucres libres » (miel, sucre, sirop, jus, confiture,
  chocolat…), pas les sucres intrinsèques des fruits entiers / laitages nature
  (définition OMS des sucres libres) ;
- **SAN-10** (sel, viser < 5 g/j) — sel intrinsèque des ingrédients (fromage,
  conserves, pain, olives) ; le sel de cuisson ajouté n'est pas mesuré (règle
  de plan : pas de resalage systématique) ;
- **fibres** (g/j) en information — appui de SAN-13 (rampe) et SAN-12.

Reste hors CIQUAL : SAN-8/PAR-6 (NOVA, additifs, nitrites) = angle « produit
transformé » → Open Food Facts **par EAN**, au moment des courses, sur les seuls
articles emballés. SAN-5 (complet), SAN-6 (fruits à coque), SAN-9 (olive/ALA) =
règles de composition, tranchées à la conception.

Usage :
    py ciqual.py --maj-cache        # (re)construit data/ciqual_nutrition.json depuis le ZIP CIQUAL
    py ciqual.py menu.json          # → verdicts SAN-7 / SAN-10 + fibres
"""

import argparse
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from commun import DOSSIER_DATA, ecrire_json, lire_json, normalise, stdout_utf8
from agribalyse import apparier, charger as charger_agribalyse, en_kg

ZIP = DOSSIER_DATA / "ciqual_2020.zip"
CACHE = DOSSIER_DATA / "ciqual_nutrition.json"
URL_CIQUAL = "https://ciqual.anses.fr/cms/sites/default/files/inline-files/XML_2020_07_07.zip"

CONST = {"10004": "sel", "32000": "sucres", "34100": "fibres",
         "41833": "ala", "42053": "epa", "42263": "dha"}  # g/100 g

SEUIL_SAN7 = 20.0   # sucres libres g/j (cible) ; alerte 40
ALERTE_SAN7 = 40.0
SEUIL_SAN10 = 5.0   # sel g/j (OMS)
SEUIL_ALA = 1.0     # ALA g/j — plancher garde-fou (ANC ANSES ~2 g/j) — SAN-9
SEUIL_EPADHA = 0.25  # EPA+DHA g/j (ANSES ANC 250 mg) — appui SAN-3

# ingrédients « sources de sucres libres » (OMS) — sinon sucres intrinsèques non comptés
SUCRE_LIBRE = ("miel", "sucre", "sirop", "confiture", "gelee", "jus", "chocolat",
               "cassonade", "agave", "datte", "compote sucree", "nectar", "bonbon")


def _teneur(txt):
    s = (txt or "").strip()
    if not s or s == "-":
        return None
    if "trace" in s.lower():
        return 0.0
    m = re.search(r"[-+]?\d+(?:,\d+)?", s)       # « < 2,2 » → 2,2 (borne haute, prudent)
    return float(m.group().replace(",", ".")) if m else None


def _xml(nom):
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(ZIP) as z:
        txt = z.read(nom).decode("cp1252", "replace")
    txt = txt.split("?>", 1)[1] if "?>" in txt[:80] else txt
    txt = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", txt)          # contrôles invalides
    txt = re.sub(r"&(?!(?:amp|lt|gt|quot|apos|#\d+);)", "&amp;", txt)  # & nus
    txt = re.sub(r"<(?![a-zA-Z/!?])", "&lt;", txt)                  # « < » non-balise (teneurs)
    return ET.fromstring(txt)


def maj_cache():
    if not ZIP.exists():
        import urllib.request
        req = urllib.request.Request(URL_CIQUAL, headers={"User-Agent": "Mozilla/5.0 planification-repas/2.0"})
        with urllib.request.urlopen(req, timeout=90) as r:
            ZIP.write_bytes(r.read())
    compo = _xml("compo_2020_07_07.xml")
    table = {}
    for row in compo:
        ch = {c.tag: (c.text or "").strip() for c in row}
        code = re.sub(r"\D", "", ch.get("alim_code", ""))
        const = re.sub(r"\D", "", ch.get("const_code", ""))
        if not code or const not in CONST:
            continue
        table.setdefault(code, {})[CONST[const]] = _teneur(ch.get("teneur"))
    ecrire_json(CACHE, {"source": "CIQUAL 2020 (ANSES)", "n": len(table), "nutrition": table})
    print(f"Cache CIQUAL écrit : {CACHE} ({len(table)} aliments)")


def charger():
    if not CACHE.exists():
        raise SystemExit("Cache CIQUAL absent — lancer : py ciqual.py --maj-cache")
    return lire_json(CACHE)["nutrition"]


def _grammes(ing, poids_g):
    kg = en_kg(ing.get("quantite", 0), ing.get("unite"), poids_g)
    return kg * 1000 if kg is not None else None


def verifier_nutrition(menu):
    aliments, alias = charger_agribalyse()
    nutri = charger()
    acc = dict(sucres=0.0, sel=0.0, fibres=0.0, ala=0.0, epa=0.0, dha=0.0)
    non_apparies = []
    for rec in menu.get("recettes", {}).values():
        pb = rec.get("portions_base", 2)
        for ing in rec.get("ingredients", []):
            aliment, _, poids_g = apparier(ing["nom"], aliments, alias)
            g = _grammes(ing, poids_g)
            if not aliment or g is None:
                non_apparies.append(ing["nom"])
                continue
            comp = nutri.get(str(aliment.get("ciqual")))
            if not comp:
                non_apparies.append(f"{ing['nom']} (ciqual {aliment.get('ciqual')})")
                continue
            f = g / 100.0 / pb        # par personne
            n = normalise(ing["nom"])
            # sucres : seulement les sources de sucres libres (OMS)
            if comp.get("sucres") is not None and any(k in n for k in SUCRE_LIBRE):
                acc["sucres"] += comp["sucres"] * f
            for k in ("sel", "fibres", "ala", "epa", "dha"):
                if comp.get(k) is not None:
                    acc[k] += comp[k] * f

    j = {k: v / 7.0 for k, v in acc.items()}   # /j sur le périmètre planifié
    epadha_j = j["epa"] + j["dha"]

    san7 = {"id": "SAN-7", "seuil": f"< {SEUIL_SAN7} g/j sucres libres (alerte > {ALERTE_SAN7})",
            "valeur": round(j["sucres"], 1),
            "detail": "sucres libres seulement (sources ajoutées) — sucres des fruits/laitages exclus"}
    san7["statut"] = "conforme" if j["sucres"] < SEUIL_SAN7 else "viole_souple"

    san10 = {"id": "SAN-10", "seuil": f"< {SEUIL_SAN10} g/j (OMS)", "valeur": round(j["sel"], 1),
             "detail": "sel intrinsèque des ingrédients ; sel de cuisson non mesuré (approximation v1)"}
    san10["statut"] = "conforme" if j["sel"] < SEUIL_SAN10 else "viole_souple"

    san9 = {"id": "SAN-9", "seuil": f"≥ {SEUIL_ALA} g/j ALA (garde-fou ; ANC ~2 g)", "valeur": round(j["ala"], 2),
            "detail": "oméga-3 végétal (ALA) — apport par colza/lin/noix en cru ; garde-fou de l'huile d'olive"}
    san9["statut"] = "conforme" if j["ala"] >= SEUIL_ALA else "viole_souple"

    san3o = {"id": "SAN-3 (EPA+DHA)", "seuil": f"≥ {SEUIL_EPADHA} g/j EPA+DHA (ANSES)",
             "valeur": round(epadha_j, 2),
             "detail": "oméga-3 marins des poissons gras — complète le comptage d'occurrences SAN-3"}
    san3o["statut"] = "conforme" if epadha_j >= SEUIL_EPADHA else "viole_souple"

    details = {"sucres_libres_g_j": round(j["sucres"], 1), "sel_g_j": round(j["sel"], 1),
               "fibres_g_j": round(j["fibres"], 1), "ala_g_j": round(j["ala"], 2),
               "epa_dha_g_j": round(epadha_j, 2), "non_apparies": non_apparies,
               "source": "CIQUAL 2020 (ANSES), par code Ciqual"}
    return [san7, san10, san9, san3o], details


def main():
    stdout_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("menu", nargs="?")
    ap.add_argument("--maj-cache", action="store_true")
    args = ap.parse_args()
    if args.maj_cache:
        maj_cache()
    elif args.menu:
        regles, det = verifier_nutrition(lire_json(args.menu))
        for r in regles:
            print(f"{r['id']} : {r['statut'].upper()} — {r['valeur']} ({r['seuil']})")
        print(f"  fibres ≈ {det['fibres_g_j']} g/j (info, SAN-13)")
        print(f"  ALA {det['ala_g_j']} g/j · EPA+DHA {det['epa_dha_g_j']} g/j")
        for nt in det["non_apparies"]:
            print(f"  [non chiffré] {nt}")
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
