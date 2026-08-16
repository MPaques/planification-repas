#!/usr/bin/env python3
"""agribalyse.py — connecteur Agribalyse (ADEME) : chiffre PLA-1 (CO2e).

Usage :
    py agribalyse.py --maj-cache                 # télécharge la synthèse en local
    py agribalyse.py --ingredient "lentilles"    # debug de matching
    py agribalyse.py menu.json [--rapport pla1_rapport.json]

Convention de calcul (à maintenir en phase avec le référentiel) :
- CO2e d'une recette = Σ (quantité ingrédient convertie en kg × kg CO2e/kg
  Agribalyse) pour `portions_base` convives ; chaque occurrence dans
  menu.repas compte une fois ; total hebdo par personne = Σ / portions_base.
- Aucun arbitrage silencieux (ARB-3) : les ingrédients non appariés ou non
  convertibles sont listés dans le rapport et le total est marqué « partiel »
  si la couverture massique < 90 %.
- Seuils PLA-1 (référentiel v0.3) : ≤ 20 kg CO2e/pers/sem, alerte > 30.

Le matching passe par data/alias_ciqual.json (curaté, versionné) puis par
recherche floue sur le cache. Les quantités en « unite » (œuf, oignon…)
exigent un poids_g dans la table d'alias.
"""

import argparse
import difflib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from commun import (DOSSIER_DATA, ecrire_json, encode_qs, get_json, lire_json,
                    normalise, stdout_utf8)

# Agribalyse 4 (migration 2026-08-14) — l'id 3.1 lisible était "agribalyse-31-synthese" ;
# la v4 comble des trous (mangue bateau, champignon) et révise les facteurs.
DATASET_ID = "shxqzuee9i461wn9lmdsbnvr"
VERSION = "Agribalyse 4 (ADEME)"
BASE = f"https://data.ademe.fr/data-fair/api/v1/datasets/{DATASET_ID}/lines"
CACHE = DOSSIER_DATA / "agribalyse_synthese.json"
ALIAS = DOSSIER_DATA / "alias_ciqual.json"

SEUIL_PLA1 = 20.0   # kg CO2e / personne / semaine
ALERTE_PLA1 = 30.0
COUVERTURE_MIN = 0.90

EN_KG = {"g": 0.001, "kg": 1.0, "mg": 0.000001, "ml": 0.001, "cl": 0.01, "l": 1.0}


# --- Cache ---------------------------------------------------------------------

def _cle(candidats, ligne):
    for k in ligne:
        if normalise(k) in candidats:
            return k
    return None


def maj_cache():
    premiere = get_json(BASE + "?size=1")
    ligne = premiere["results"][0]
    k_nom = _cle({"nom du produit en francais"}, ligne)
    k_ciqual = _cle({"code ciqual"}, ligne)
    k_co2 = _cle({"changement climatique"}, ligne)
    k_dqr = _cle({"dqr"}, ligne)
    k_groupe = _cle({"groupe d aliment"}, ligne)
    k_avion = _cle({"code avion"}, ligne)
    k_saison = _cle({"code saison"}, ligne)
    if not (k_nom and k_co2):
        raise SystemExit(f"Colonnes introuvables dans la réponse ADEME : {sorted(ligne)}")

    aliments, url = [], BASE + "?" + encode_qs(size=1000, select=",".join(
        filter(None, [k_nom, k_ciqual, k_co2, k_dqr, k_groupe, k_avion, k_saison])))
    while url:
        page = get_json(url)
        for r in page["results"]:
            aliments.append({
                "nom": r.get(k_nom),
                "ciqual": r.get(k_ciqual),
                "co2e_kg": r.get(k_co2),
                "dqr": r.get(k_dqr),
                "groupe": r.get(k_groupe),
                "avion": r.get(k_avion),   # 1 = fret aérien → PLA-4 [dur]
                "saison": r.get(k_saison),
                "nom_norm": normalise(r.get(k_nom)),
            })
        url = page.get("next")
    ecrire_json(CACHE, {"source": BASE, "version": VERSION, "total": len(aliments),
                        "aliments": aliments})
    print(f"Cache écrit : {CACHE} ({len(aliments)} aliments, {VERSION})")


# --- Matching ------------------------------------------------------------------

def charger():
    if not CACHE.exists():
        raise SystemExit("Cache absent — lancer d'abord : py agribalyse.py --maj-cache")
    aliments = lire_json(CACHE)["aliments"]
    alias = lire_json(ALIAS) if ALIAS.exists() else {"alias": {}}
    return aliments, alias["alias"]


def apparier(nom, aliments, alias):
    """→ (aliment | None, methode, poids_g | None)"""
    n = normalise(nom)
    entree = alias.get(n)
    if entree and entree.get("requete") is None:  # veto curaté : mieux vaut « non chiffré » que faux
        return None, f"veto_alias ({entree.get('raison', 'sans raison')})", None
    poids_g = entree.get("poids_g") if entree else None
    cible = normalise(entree["requete"]) if entree else n

    exact = [a for a in aliments if a["nom_norm"] == cible]
    if exact:
        return exact[0], "alias" if entree else "exact", poids_g

    mots = set(cible.split())
    candidats = [a for a in aliments if mots <= set(a["nom_norm"].split())]
    if not candidats:
        candidats = [a for a in aliments if cible in a["nom_norm"]]
    if candidats:
        # priorité : commence par la cible (le fruit avant son nectar), puis le
        # moins verbeux (évite « lentille » → plats cuisinés), puis similarité
        candidats.sort(key=lambda a: (not a["nom_norm"].startswith(cible),
                                      len(a["nom_norm"].split()),
                                      -difflib.SequenceMatcher(None, cible, a["nom_norm"]).ratio()))
        return candidats[0], f"approx({'alias→' if entree else ''}sous-mots)", poids_g

    scores = [(difflib.SequenceMatcher(None, cible, a["nom_norm"]).ratio(), a) for a in aliments]
    score, meilleur = max(scores, key=lambda t: t[0])
    if score >= 0.72:
        return meilleur, f"approx(flou {score:.2f})", poids_g
    return None, "non_apparie", poids_g


def en_kg(quantite, unite, poids_g):
    u = normalise(unite or "")
    if u in EN_KG:
        return quantite * EN_KG[u]
    if u in {"unite", "unites", "piece", "pieces", "u"} and poids_g:
        return quantite * poids_g / 1000.0
    return None


# --- Menu → PLA-1 --------------------------------------------------------------

def chiffrer_menu(chemin_menu, chemin_rapport):
    menu = lire_json(chemin_menu)
    aliments, alias = charger()
    recettes = menu.get("recettes", {})
    occurrences = [r["recette_id"] for r in menu.get("repas", [])]

    detail_recettes, problemes, avions = {}, [], []
    masse_totale = masse_couverte = 0.0

    for rid, rec in recettes.items():
        lignes, co2e = [], 0.0
        for ing in rec.get("ingredients", []):
            aliment, methode, poids_g = apparier(ing["nom"], aliments, alias)
            kg = en_kg(ing.get("quantite", 0), ing.get("unite"), poids_g)
            ligne = {"ingredient": ing["nom"], "kg": kg, "methode": methode}
            if kg is None:
                ligne["probleme"] = f"unité non convertible : {ing.get('unite')} (poids_g manquant ?)"
                problemes.append({"recette": rid, **ligne})
            else:
                masse_totale += kg
                if aliment:
                    ligne.update({"apparie": aliment["nom"], "ciqual": aliment["ciqual"],
                                  "co2e_kg": aliment["co2e_kg"], "dqr": aliment["dqr"],
                                  "co2e": round(kg * aliment["co2e_kg"], 3)})
                    if aliment.get("avion"):
                        ligne["avion"] = True
                        avions.append({"recette": rid, "ingredient": ing["nom"],
                                       "apparie": aliment["nom"]})
                    co2e += kg * aliment["co2e_kg"]
                    masse_couverte += kg
                else:
                    ligne["probleme"] = "aucun aliment Agribalyse apparié"
                    problemes.append({"recette": rid, **ligne})
            lignes.append(ligne)
        detail_recettes[rid] = {
            "co2e_total": round(co2e, 3),
            "co2e_par_personne": round(co2e / rec.get("portions_base", 2), 3),
            "ingredients": lignes,
        }

    hebdo_pp = sum(detail_recettes[rid]["co2e_par_personne"] for rid in occurrences
                   if rid in detail_recettes)
    couverture = (masse_couverte / masse_totale) if masse_totale else 0.0

    if hebdo_pp <= SEUIL_PLA1:
        statut = "conforme"
    else:
        statut = "viole_souple"
    detail = f"couverture massique {couverture:.0%}"
    if couverture < COUVERTURE_MIN:
        detail += " — TOTAL PARTIEL, compléter les appariements"
    if hebdo_pp > ALERTE_PLA1:
        detail += f" — ALERTE : > {ALERTE_PLA1} kg"

    rapport = {
        "regle": {"id": "PLA-1", "statut": statut, "valeur": round(hebdo_pp, 2),
                  "seuil": f"<= {SEUIL_PLA1} kg CO2e/pers/sem (alerte > {ALERTE_PLA1})",
                  "detail": detail},
        "regle_pla4": {"id": "PLA-4", "statut": "viole_dur" if avions else "conforme",
                       "valeur": avions or "aucun ingrédient à fret aérien détecté",
                       "seuil": "0 fret aérien (signal Agribalyse code_avion, indicatif : "
                                "l'appariement peut viser une variante avion d'un produit bateau)"},
        "couverture_massique": round(couverture, 3),
        "non_apparies": problemes,
        "recettes": detail_recettes,
        "source": f"{VERSION}, cache local",
    }
    ecrire_json(chemin_rapport, rapport)
    print(f"PLA-1 : {statut.upper()} — {hebdo_pp:.1f} kg CO2e/pers/sem "
          f"(seuil {SEUIL_PLA1}, couverture {couverture:.0%})")
    for a in avions:
        print(f"  [PLA-4 !] {a['recette']} / {a['ingredient']} apparié sur du fret aérien : {a['apparie']}")
    for p in problemes:
        print(f"  [non chiffré] {p['recette']} / {p['ingredient']} — {p['probleme']}")
    print(f"Rapport : {chemin_rapport}")


def main():
    stdout_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("menu", nargs="?")
    ap.add_argument("--maj-cache", action="store_true")
    ap.add_argument("--ingredient")
    ap.add_argument("--rapport")
    args = ap.parse_args()

    if args.maj_cache:
        maj_cache()
    elif args.ingredient:
        aliments, alias = charger()
        aliment, methode, poids_g = apparier(args.ingredient, aliments, alias)
        if aliment:
            print(f"{args.ingredient} -> {aliment['nom']} (ciqual {aliment['ciqual']}) "
                  f"{aliment['co2e_kg']} kg CO2e/kg, DQR {aliment['dqr']} [{methode}]"
                  + (f", poids unitaire {poids_g} g" if poids_g else ""))
        else:
            print(f"{args.ingredient} -> AUCUN APPARIEMENT")
    elif args.menu:
        chiffrer_menu(args.menu, args.rapport or args.menu.replace(".json", "_pla1.json"))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
