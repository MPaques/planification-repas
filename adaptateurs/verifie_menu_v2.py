#!/usr/bin/env python3
"""verifie_menu_v2.py — vérification v2 : compose le vérifieur v1 du skill
(intouché — indépendance générateur/vérifieur, fiche Q4) avec la chaîne CO2e
Agribalyse, et fusionne les deux en un seul rapport de conformité.

Usage (phase 4 du skill — remplace l'appel direct à verify_menu.py) :
    py verifie_menu_v2.py menu.json                       # auto-découvre verify_menu.py
    py verifie_menu_v2.py menu.json --verifieur <chemin>\\verify_menu.py
    py verifie_menu_v2.py menu.json --rapport-v1 menu_rapport.json   # rapport v1 déjà produit
    VERIFY_MENU=<chemin> py verifie_menu_v2.py menu.json  # via variable d'env

Fusion :
- l'entrée PLA-1 « non_verifie_v1 » du rapport v1 est remplacée par le verdict
  chiffré (kg CO2e/pers/sem, seuils 20/30) ;
- PLA-4 (fret aérien, dur) est ajouté depuis le signal `code_avion` — indicatif,
  à croiser avec la provenance réelle (le détail le dit) ;
- le statut global est recalculé ; couverture massique et ingrédients non
  appariés sont joints (ARB-3 : rien de silencieux).

Code de sortie : 0 = conforme/dérogations ; 1 = violation(s) dure(s).
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agribalyse import chiffrer_menu
from saisonnalite import verifier_pla3
from ciqual import verifier_nutrition
from composition import verifier_san5, verifier_san6, verdict_san12
from monmarche import chiffrer_courses
from commun import ecrire_json, lire_json, stdout_utf8


NOMS = {
    "PAR-2": "Couverture des repas", "PAR-6": "Nitrites (charcuterie)",
    "SAN-1": "Légumineuses en base", "SAN-2": "Viande rouge & charcuterie", "SAN-2b": "Charcuterie",
    "SAN-3": "Poisson (dont gras)", "SAN-3 (EPA+DHA)": "Oméga-3 marins (EPA+DHA)",
    "SAN-4": "Fruits & légumes", "SAN-7": "Sucres libres", "SAN-8": "Ultra-transformés (NOVA 4)",
    "SAN-9": "Oméga-3 végétal (ALA)", "SAN-10": "Sel", "SAN-11": "Part bio du panier",
    "SAN-5": "Féculents complets", "SAN-6": "Fruits à coque", "SAN-12": "Charge glycémique",
    "SAN-8/PAR-6": "NOVA & additifs (nitrites)",
    "GOU-1": "Variété — plats non répétés", "GOU-1b": "Variété — bases distinctes",
    "TPS-1": "Batch cooking (durée)", "TPS-2": "Assemblage d'un dîner", "TPS-3": "Part issue du batch",
    "SEC-1": "Durées de vie des composants", "PLA-1": "Empreinte CO₂e", "PLA-3": "Saisonnalité France",
    "PLA-4": "Fret aérien", "PRX-1": "Prix du panier",
}


def trouver_verifieur():
    """Localise scripts/verify_menu.py du skill sans chemin explicite.
    Ordre : variable d'env VERIFY_MENU, puis glob sous les sessions skills-plugin
    (le plus récent). Retourne None si introuvable."""
    env = os.environ.get("VERIFY_MENU")
    if env and Path(env).is_file():
        return Path(env)
    racines = [
        Path(os.environ.get("APPDATA", "")) / "Claude" / "local-agent-mode-sessions",
        Path.home() / ".claude",
    ]
    trouves = []
    for racine in racines:
        if racine.is_dir():
            trouves += racine.glob("**/planification-repas/scripts/verify_menu.py")
    return max(trouves, key=lambda p: p.stat().st_mtime) if trouves else None


def rapport_v1(menu, chemin_verifieur):
    sortie = Path(tempfile.gettempdir()) / "rapport_v1_tmp.json"
    r = subprocess.run([sys.executable, str(chemin_verifieur), str(menu),
                        "--rapport", str(sortie)],
                       capture_output=True, text=True)
    if not sortie.exists():
        raise SystemExit(f"Vérifieur v1 en échec :\n{r.stdout}\n{r.stderr}")
    return lire_json(sortie)


def main():
    stdout_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("menu")
    ap.add_argument("--verifieur", help="chemin de verify_menu.py (skill)")
    ap.add_argument("--rapport-v1", dest="v1", help="rapport v1 déjà produit")
    ap.add_argument("--rapport", help="sortie fusionnée (défaut: *_rapport_v2.json)")
    args = ap.parse_args()

    if args.v1:
        v1 = lire_json(args.v1)
    else:
        verifieur = Path(args.verifieur) if args.verifieur else trouver_verifieur()
        if not verifieur or not verifieur.is_file():
            ap.error("verify_menu.py introuvable — passer --verifieur <chemin> "
                     "ou définir VERIFY_MENU, ou --rapport-v1 <rapport déjà produit>")
        print(f"Vérifieur v1 : {verifieur}")
        v1 = rapport_v1(args.menu, verifieur)

    chemin_pla1 = Path(tempfile.gettempdir()) / "rapport_pla1_tmp.json"
    chiffrer_menu(args.menu, str(chemin_pla1))
    co2e = lire_json(chemin_pla1)

    menu = lire_json(args.menu)
    pla3_regle, pla3_det = verifier_pla3(menu)          # saisonnalité France (DAT-3)
    nutri_regles, nutri_det = verifier_nutrition(menu)  # sucres/sel/oméga-3 via CIQUAL (par code Ciqual)
    san5 = verifier_san5(menu)                          # féculents complets (+ garde-fou bio)
    san6 = verifier_san6(menu)                          # fruits à coque g/j
    courses = chiffrer_courses(menu)                    # panier mon-marché par SKU → PRX-1

    # retire les entrées désormais chiffrées (PLA-1, PLA-3, PRX-1, SAN-11) et le bloc combiné SAN-*
    remplacees = {("PLA-1", "non_verifie_v1"), ("PLA-3", "non_verifie_v1"),
                  ("PRX-1", "non_verifie_v1"), ("SAN-11", "non_verifie_v1")}
    regles = [r for r in v1["regles"]
              if (r["id"], r["statut"]) not in remplacees
              and r["id"] not in ("SAN-5/6/7/9/10/12", "SAN-5/6/12")]
    regles.append(co2e["regle"])
    regles.append(co2e["regle_pla4"])
    regles.append(pla3_regle)
    regles.extend(nutri_regles)                         # SAN-7, SAN-10, SAN-9 (ALA), SAN-3 (EPA+DHA)
    regles.append(san5)
    regles.append(san6)
    regles.append(courses["prx1"])
    regles.append(courses["san11"])

    # SAN-12 par synergie (l'IG n'est pas dans CIQUAL) : dépend de SAN-1/5/7
    statuts = {r["id"]: r["statut"] for r in regles}
    regles.append(verdict_san12(menu, statuts))

    # ce qui reste hors machine : additifs/NOVA (SAN-8/PAR-6) → OFF par code-barres (emballés)
    regles.append({"id": "SAN-8/PAR-6", "statut": "non_verifie_v1", "valeur": None, "seuil": None,
                   "detail": "NOVA & additifs/nitrites — Open Food Facts par code-barres, sur les "
                             "produits emballés, au moment des courses"})

    for r in regles:                                    # noms lisibles (les acronymes seuls sont opaques)
        r["nom"] = NOMS.get(r["id"], "")

    dures = [r for r in regles if r["statut"] == "viole_dur"]
    souples = [r for r in regles if r["statut"] == "viole_souple"]
    statut = "violations_dures" if dures else ("derogations" if souples else "conforme")

    fusion = {
        "statut_global": statut,
        "regles": regles,
        "derogations": [{"regle": r["id"], "raison": r.get("detail") or str(r["valeur"])}
                        for r in souples],
        "compteurs": {**v1.get("compteurs", {}),
                      "co2e_kg_pp_sem": co2e["regle"]["valeur"],
                      "couverture_massique_co2e": co2e["couverture_massique"]},
        "co2e_non_apparies": co2e["non_apparies"],
        "pla3_saisonnalite": pla3_det,
        "nutrition_ciqual": nutri_det,
        "source_co2e": co2e["source"],
        "courses_monmarche": courses,
    }
    sortie = args.rapport or args.menu.replace(".json", "_rapport_v2.json")
    ecrire_json(sortie, fusion)

    print(f"\nStatut global v2 : {statut.upper()}")
    for r in regles:
        if r["statut"] not in ("conforme", "non_verifie_v1"):
            print(f"  [{r['statut']}] {r['id']} — {r['valeur']} (seuil {r['seuil']})")
    print(f"Rapport fusionné : {sortie}")
    sys.exit(1 if dures else 0)


if __name__ == "__main__":
    main()
