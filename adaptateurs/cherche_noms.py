#!/usr/bin/env python3
"""cherche_noms.py — outil de curation : liste les noms Agribalyse contenant un terme."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from commun import lire_json, normalise, stdout_utf8
from agribalyse import CACHE

stdout_utf8()
aliments = lire_json(CACHE)["aliments"]
for terme in sys.argv[1:]:
    t = normalise(terme)
    hits = [a for a in aliments if t in a["nom_norm"]]
    hits.sort(key=lambda a: len(a["nom_norm"]))
    print(f"--- {terme} ({len(hits)}) ---")
    for a in hits[:6]:
        print(f"  {a['nom']}  | ciqual {a['ciqual']} | {a['co2e_kg']} kg | avion={a['avion']}")
