#!/usr/bin/env python3
"""commun.py — socle des adaptateurs v2 (planification-repas).

Contrat : les adaptateurs sont jetables, le schéma pivot ne l'est pas
(references/schema-pivot.md). Ce module ne contient que la plomberie
partagée : HTTP avec en-têtes navigateur (CloudFront rejette les clients
nus devant laruchequiditoui.fr), normalisation de texte pour le matching,
chemins des données. Stdlib uniquement.
"""

import json
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

DOSSIER_DATA = Path(__file__).parent / "data"

# En-têtes complets : condition d'accès à lrqdo-api (testé probe2.py 2026-08-14)
ENTETES = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


def get_json(url, referer=None, essais=3, pause_s=1.5):
    """GET JSON avec retries doux. Lève RuntimeError après épuisement."""
    entetes = dict(ENTETES)
    if referer:
        entetes["Referer"] = referer
    derniere = None
    for i in range(essais):
        try:
            req = urllib.request.Request(url, headers=entetes)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # HTTPError, URLError, JSONDecodeError
            derniere = e
            if i < essais - 1:
                time.sleep(pause_s * (i + 1))
    raise RuntimeError(f"GET {url} en échec après {essais} essais : {derniere}")


def normalise(texte):
    """minuscules, sans accents, espaces simples — clé de matching."""
    if not texte:
        return ""
    t = texte.replace("œ", "oe").replace("Œ", "Oe").replace("æ", "ae").replace("Æ", "Ae")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(t.lower().replace("'", " ").replace("-", " ").replace("_", " ").split())


def ecrire_json(chemin, objet):
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(objet, f, ensure_ascii=False, indent=2)


def lire_json(chemin):
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def stdout_utf8():
    """Console Windows : force UTF-8 pour les noms accentués."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def encode_qs(**params):
    return urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
