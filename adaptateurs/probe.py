#!/usr/bin/env python3
"""probe.py — sonde de connectivité des sources v2 (hors navigateur).

Vérifie ce que chaque API accepte depuis un client HTTP nu, pour trancher
l'architecture de chaque adaptateur : appel direct ou capture via navigateur.
"""

import json
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) planification-repas/2.0"

CIBLES = [
    # CrowdFarming : le WAF 403 tout client scripté — la capture passe par le navigateur (crowdfarming.py)
    ("crowdfarming_catapi", "https://laruchequiditoui.fr/services/catapi/v2/projects?country=fr&lang=fr&limit=23&sort=relevance&path=en%2Fdirect-from-farmer"),
    ("ademe_agribalyse", "https://data.ademe.fr/data-fair/api/v1/datasets/agribalyse-31-synthese/lines?q=lentille&size=2"),
    ("off_produit", "https://world.openfoodfacts.org/api/v2/product/3268270003534.json?fields=product_name,nova_group,additives_tags"),
]


def sonde(nom, url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            corps = r.read(2000).decode("utf-8", errors="replace")
            try:
                json.loads(corps if corps.rstrip().endswith(("}", "]")) else corps[:corps.rfind("}") + 1])
                type_corps = "json"
            except Exception:
                type_corps = "html/autre"
            return nom, r.status, type_corps
    except urllib.error.HTTPError as e:
        return nom, e.code, "http-error"
    except Exception as e:
        return nom, None, f"{type(e).__name__}: {e}"


if __name__ == "__main__":
    for nom, url in CIBLES:
        n, statut, detail = sonde(nom, url)
        print(f"{n:26s} -> {statut} ({detail})")
