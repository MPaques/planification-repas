#!/usr/bin/env python3
"""saisonnalite.py — vérifieur PLA-3 (saisonnalité France, contrainte dure).

Lit le calendrier `references/saisonnalite-fr.md` du skill (DAT-3), détermine
le(s) mois de la semaine, et contrôle chaque ingrédient **frais** (frais_saisonnier
= true, catégorie légume/fruit) du menu :
- de saison ce mois-ci (ou disponible toute l'année) → conforme ;
- frais mais listé un autre mois → **hors-saison, violation dure** (à passer en
  conserve / surgelé / lacto-fermenté, jamais en frais importé — PLA-3) ;
- absent du calendrier → « à vérifier » (souple), pas de violation dure sur un
  simple trou de données.

Le hors-saison importé était l'angle mort du vérifieur v1 (PLA-3 laissé humain) ;
ce module le rend machine-vérifiable. Reste hors périmètre : le fret aérien
(PLA-4, couvert par agribalyse.py) et la serre chauffée (non distinguable ici).
"""

import datetime as _dt
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from commun import normalise

MOIS_FR = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"]

# Disponibles quasi toute l'année (note d'usage du calendrier)
ANNEE = ["champignon", "pomme de terre", "oignon", "ail", "echalote"]


def trouver_calendrier():
    env = os.environ.get("SAISONNALITE")
    if env and Path(env).is_file():
        return Path(env)
    racines = [Path(os.environ.get("APPDATA", "")) / "Claude" / "local-agent-mode-sessions",
               Path.home() / ".claude"]
    trouves = []
    for r in racines:
        if r.is_dir():
            trouves += r.glob("**/planification-repas/references/saisonnalite-fr.md")
    return max(trouves, key=lambda p: p.stat().st_mtime) if trouves else None


def _tokens(texte):
    """tokens significatifs (≥ 4 car.) d'un terme normalisé, parenthèses retirées."""
    sans_paren = re.sub(r"\([^)]*\)", " ", texte)
    return {t for t in normalise(sans_paren).split() if len(t) >= 4}


def _match(a, b):
    """égalité de token tolérante au pluriel FR (tomate ~ tomates)."""
    return a == b or a == b + "s" or b == a + "s" or a == b + "x" or b == a + "x"


def _terme_couvre(ing_tokens, terme_tokens):
    return any(_match(a, b) for a in ing_tokens for b in terme_tokens)


def parser_calendrier(chemin):
    """→ {mois_norm: [set(tokens), …]} pour légumes + fruits de chaque mois."""
    cal = {}
    for ligne in Path(chemin).read_text(encoding="utf-8").splitlines():
        if not ligne.strip().startswith("|"):
            continue
        cols = [c.strip() for c in ligne.strip().strip("|").split("|")]
        if len(cols) < 3:
            continue
        mois = normalise(cols[0])
        if mois not in [normalise(m) for m in MOIS_FR if m]:
            continue
        termes = []
        for bloc in (cols[1], cols[2]):
            sans_paren = re.sub(r"\([^)]*\)", "", bloc)
            for terme in sans_paren.split(","):
                tk = _tokens(terme)
                if tk:
                    termes.append(tk)
        cal[mois] = termes
    return cal


def verifier_pla3(menu, chemin=None):
    """→ (regle: dict, details: dict)."""
    chemin = Path(chemin) if chemin else trouver_calendrier()
    if not chemin or not chemin.is_file():
        return ({"id": "PLA-3", "statut": "non_verifie_v1", "valeur": None, "seuil": None,
                 "detail": "calendrier saisonnalite-fr.md introuvable — vérification humaine"}, {})

    cal = parser_calendrier(chemin)
    annee_tk = [_tokens(x) for x in ANNEE]
    tous_tk = [t for termes in cal.values() for t in termes]  # présence un mois quelconque

    # mois couverts par la semaine (début + fin, tolérant aux fins de mois)
    mois_keys = set()
    d0 = None
    try:
        d0 = _dt.date.fromisoformat(menu.get("semaine_du", ""))
    except Exception:
        pass
    if d0:
        for delta in (0, 6):
            mois_keys.add(normalise(MOIS_FR[(d0 + _dt.timedelta(days=delta)).month]))
    else:
        mois_keys = set(cal.keys())
    saison = [t for m in mois_keys for t in cal.get(m, [])] + annee_tk

    conformes, hors_saison, a_verifier = [], [], []
    for rec in menu.get("recettes", {}).values():
        for ing in rec.get("ingredients", []):
            if not ing.get("frais_saisonnier"):
                continue
            if ing.get("categorie") not in ("legume", "fruit"):
                continue
            it = _tokens(ing["nom"])
            if not it:
                continue
            if any(_terme_couvre(it, t) for t in saison):
                conformes.append(ing["nom"])
            elif any(_terme_couvre(it, t) for t in tous_tk):
                hors_saison.append(ing["nom"])            # existe, mais pas ce mois → dur
            else:
                a_verifier.append(ing["nom"])             # absent du calendrier → souple

    mois_lisibles = ", ".join(sorted({m for m in mois_keys}))
    if hors_saison:
        regle = {"id": "PLA-3", "statut": "viole_dur", "valeur": sorted(set(hors_saison)),
                 "seuil": f"frais de saison France ({mois_lisibles})",
                 "detail": "frais hors-saison — passer en conserve/surgelé/lacto (jamais frais importé)"}
    elif a_verifier:
        regle = {"id": "PLA-3", "statut": "viole_souple", "valeur": sorted(set(a_verifier)),
                 "seuil": f"frais de saison France ({mois_lisibles})",
                 "detail": "absent du calendrier — à vérifier à l'œil"}
    else:
        regle = {"id": "PLA-3", "statut": "conforme", "valeur": len(set(conformes)),
                 "seuil": f"frais de saison France ({mois_lisibles})",
                 "detail": "tous les frais de saison ce mois-ci (ou disponibles toute l'année)"}
    details = {"conformes": sorted(set(conformes)), "hors_saison": sorted(set(hors_saison)),
               "a_verifier": sorted(set(a_verifier)), "mois": sorted(mois_keys)}
    return regle, details


if __name__ == "__main__":
    from commun import lire_json, stdout_utf8
    stdout_utf8()
    if len(sys.argv) < 2:
        print("usage: py saisonnalite.py menu.json")
        sys.exit(0)
    regle, det = verifier_pla3(lire_json(sys.argv[1]))
    print(f"PLA-3 : {regle['statut'].upper()} — {regle['valeur']} ({regle['seuil']})")
    print(f"  conformes: {det.get('conformes')}")
    if det.get("hors_saison"):
        print(f"  HORS-SAISON: {det['hors_saison']}")
    if det.get("a_verifier"):
        print(f"  à vérifier: {det['a_verifier']}")
