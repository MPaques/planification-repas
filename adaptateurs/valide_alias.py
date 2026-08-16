#!/usr/bin/env python3
"""valide_alias.py — contrôle que chaque `requete` de la table d'alias résout
en correspondance EXACTE dans le cache Agribalyse. Sortie 1 si des trous."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from commun import lire_json, normalise, stdout_utf8
from agribalyse import ALIAS, CACHE

stdout_utf8()
aliments = lire_json(CACHE)["aliments"]
noms = {a["nom_norm"] for a in aliments}
alias = lire_json(ALIAS)["alias"]

trous = []
for cle, entree in alias.items():
    if entree.get("requete") is None:
        continue  # veto assumé, documenté dans l'entrée
    if normalise(entree["requete"]) not in noms:
        trous.append((cle, entree["requete"]))

if trous:
    print(f"{len(trous)} requêtes ne résolvent PAS exactement :")
    for cle, req in trous:
        n = normalise(req)
        proches = sorted((a["nom"] for a in aliments if n.split()[0] in a["nom_norm"]),
                         key=len)[:3]
        print(f"  {cle!r} -> {req!r} | proches : {proches}")
    sys.exit(1)
print(f"OK — {len(alias)} alias résolvent tous exactement.")
