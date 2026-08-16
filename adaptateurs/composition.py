#!/usr/bin/env python3
"""composition.py — règles de composition machine-vérifiables sur les tags/noms
du menu (pas de donnée externe) : SAN-5, SAN-6, et le verdict de synthèse SAN-12.

- SAN-5 [souple] : ≥ moitié des féculents en complet/semi-complet. Le complet est
  **préféré bio** (le son concentre cadmium ET résidus de pesticides — lien SAN-11) :
  un féculent complet non-bio est signalé. Le pain **maison au levain** est exclu du
  décompte (arbitrage personnel T65/T80/T110 fibres ↔ cadmium, hors vérifieur).
- SAN-6 [souple, v0.5] : fruits à coque non salés ~50 g/j (EAT-Lancet ; plancher poignée ~30 g).
- SAN-12 [souple] : charge glycémique basse — le référentiel la scope en heuristique
  par classes (l'IG n'est pas dans CIQUAL). Verdict **par synergie** : conforme si
  SAN-1 (légumineuses), SAN-5 (complet) et SAN-7 (sucres libres) le sont et qu'aucun
  jus de fruit ne se substitue au fruit entier.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from commun import normalise
from agribalyse import en_kg

SEUIL_SAN6 = 50.0   # g/j fruits à coque (EAT-Lancet, avenant v0.5 ; plancher poignée 30)

COMPLET = ("complet", "complete", "semi complet", "integral", "boulgour", "avoine",
           "flocons", "quinoa", "sarrasin", "seigle", "orge", "epeautre", "levain")
RAFFINE_MARQUE = ("blanc", "blanche")  # « riz blanc », « pâtes » nues = raffiné par défaut
COQUE = ("noix", "amande", "noisette", "pistache", "cajou", "pecan", "macadamia",
         "graine", "graines", "courge", "chanvre", "tournesol", "sesame", "lin",
         "cacahuete", "arachide", "chataigne")


def _grammes(ing):
    kg = en_kg(ing.get("quantite", 0), ing.get("unite"), None)
    return kg * 1000 if kg is not None else None


def _token_match(nom_norm, mots):
    """mot-clé présent comme token entier (pluriel toléré) — évite courgette~courge."""
    toks = nom_norm.split()
    return any(t == k or t == k + "s" or t + "s" == k for t in toks for k in mots)


def _occurrences(menu):
    c = {}
    for r in menu["repas"]:
        c[r["recette_id"]] = c.get(r["recette_id"], 0) + 1
    return c


def _est_feculent(ing):
    n = normalise(ing["nom"])
    if ing.get("categorie") == "cereale":
        return True
    if ing.get("categorie") == "legume" and ("pomme de terre" in n or "patate douce" in n):
        return True
    return False


def _est_complet(nom_norm):
    return any(k in nom_norm for k in COMPLET)


def verifier_san5(menu):
    """→ regle SAN-5 (ratio complet + garde-fou bio)."""
    occ = _occurrences(menu)
    complets = raffines = 0
    non_bio_complets = []
    for rid, rec in menu["recettes"].items():
        n_occ = occ.get(rid, 0)
        for ing in rec["ingredients"]:
            if not _est_feculent(ing):
                continue
            nom = normalise(ing["nom"])
            if "pain" in nom and "levain" in nom:   # pain maison au levain : hors vérifieur
                continue
            if _est_complet(nom):
                complets += n_occ
                if not ing.get("bio"):
                    non_bio_complets.append(ing["nom"])
            else:
                raffines += n_occ
    total = complets + raffines
    ratio = complets / total if total else 1.0
    statut = "conforme" if ratio >= 0.5 else "viole_souple"
    detail = f"{complets}/{total} portions complètes/semi-complètes (pain maison exclu)"
    if statut == "conforme" and non_bio_complets:
        detail += f" ; complet non-bio : {sorted(set(non_bio_complets))} — préférer bio (son = Cd + pesticides)"
    return {"id": "SAN-5", "statut": statut, "valeur": round(ratio, 2),
            "seuil": "≥ 0,5 complet/semi-complet", "detail": detail}


def verifier_san6(menu):
    """→ regle SAN-6 (fruits à coque g/j)."""
    occ = _occurrences(menu)
    grammes_pp = 0.0
    for rid, rec in menu["recettes"].items():
        pb = rec.get("portions_base", 2)
        n_occ = occ.get(rid, 0)
        for ing in rec["ingredients"]:
            nom = normalise(ing["nom"])
            if "huile" in nom:                       # huiles (lin, colza…) ≠ fruit à coque
                continue
            if not _token_match(nom, COQUE):         # token entier (courgette ≠ courge)
                continue
            g = _grammes(ing)
            if g is not None:
                grammes_pp += g * n_occ / pb
    par_jour = grammes_pp / 7.0
    statut = "conforme" if par_jour >= SEUIL_SAN6 else "viole_souple"
    return {"id": "SAN-6", "statut": statut, "valeur": round(par_jour, 1),
            "seuil": f"~ {SEUIL_SAN6:.0f} g/j (EAT-Lancet, v0.5)",
            "detail": "fruits à coque non salés (hors huiles)"}


def _a_des_jus(menu):
    for rec in menu["recettes"].values():
        for ing in rec["ingredients"]:
            n = normalise(ing["nom"])
            if "jus" in n and ing.get("categorie") == "fruit":
                return True
    return False


def verdict_san12(menu, statuts):
    """SAN-12 par synergie SAN-1 / SAN-5 / SAN-7 (+ drapeau jus). statuts: {id: statut}."""
    appuis = ["SAN-1", "SAN-5", "SAN-7"]
    ko = [a for a in appuis if statuts.get(a) not in ("conforme", None)]
    jus = _a_des_jus(menu)
    conforme = not ko and not jus
    detail = "synergie SAN-1 (légumineuses) + SAN-5 (complet) + SAN-7 (sucres libres), fruits entiers"
    if ko:
        detail = f"appuis non conformes : {ko}"
    elif jus:
        detail = "jus de fruit présent — préférer le fruit entier"
    return {"id": "SAN-12", "statut": "conforme" if conforme else "viole_souple",
            "valeur": "synergie OK" if conforme else "à revoir",
            "seuil": "heuristique par classes (IG hors CIQUAL)", "detail": detail}


if __name__ == "__main__":
    from commun import lire_json, stdout_utf8
    stdout_utf8()
    menu = lire_json(sys.argv[1])
    s5 = verifier_san5(menu)
    s6 = verifier_san6(menu)
    for r in (s5, s6):
        print(f"{r['id']} : {r['statut'].upper()} — {r['valeur']} ({r['seuil']}) — {r['detail']}")
