#!/usr/bin/env python3
"""extract_recipe.py — extraction déterministe d'une recette schema.org/Recipe.

Usage :
    python extract_recipe.py <url-ou-fichier-html> [--out sortie.json]

Rôle (phase 2 du skill) : récupérer le balisage JSON-LD de type Recipe présent
sur la plupart des sites de recettes, et le convertir en squelette du schéma
pivot (references/schema-pivot.md). La partie déterministe s'arrête là : la
structuration fine des ingrédients (catégories, tags de vérification) est le
travail du modèle, pas de ce script.

Dépendances : bibliothèque standard uniquement (portabilité self-hosted).
"""

import argparse
import json
import re
import sys
import unicodedata
import urllib.request
from html.parser import HTMLParser

UA = "Mozilla/5.0 (compatible; planification-repas-skill/1.0; usage personnel)"


class LdJsonCollector(HTMLParser):
    """Collecte le contenu des balises <script type="application/ld+json">."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self._in_ldjson = False
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "script":
            attrs = dict(attrs)
            if (attrs.get("type") or "").strip().lower() == "application/ld+json":
                self._in_ldjson = True
                self._buf = []

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self._in_ldjson:
            self._in_ldjson = False
            self.blocks.append("".join(self._buf))

    def handle_data(self, data):
        if self._in_ldjson:
            self._buf.append(data)


def fetch(source: str) -> str:
    if source.startswith("http://") or source.startswith("https://"):
        req = urllib.request.Request(source, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    with open(source, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def iter_json_objects(blocks):
    for raw in blocks:
        raw = raw.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                yield node
                if "@graph" in node:
                    stack.extend(node["@graph"] if isinstance(node["@graph"], list) else [node["@graph"]])


def is_recipe(node: dict) -> bool:
    t = node.get("@type")
    types = t if isinstance(t, list) else [t]
    return any(isinstance(x, str) and x.lower() == "recipe" for x in types)


def iso8601_minutes(value):
    """PT1H30M -> 90 ; retourne None si non interprétable."""
    if not isinstance(value, str):
        return None
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:\d+S)?", value.strip())
    if not m:
        return None
    days, hours, minutes = (int(g) if g else 0 for g in m.groups())
    return days * 1440 + hours * 60 + minutes


def instructions_to_steps(instr):
    steps = []

    def walk(node):
        if node is None:
            return
        if isinstance(node, str):
            txt = node.strip()
            if txt:
                steps.append(txt)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            t = node.get("@type", "")
            if t == "HowToSection":
                walk(node.get("itemListElement"))
            else:
                txt = (node.get("text") or node.get("name") or "").strip()
                if txt:
                    steps.append(txt)

    walk(instr)
    return steps


def yield_to_portions(y):
    if isinstance(y, list) and y:
        y = y[0]
    if isinstance(y, (int, float)):
        return int(y)
    if isinstance(y, str):
        m = re.search(r"\d+", y)
        if m:
            return int(m.group())
    return None


def to_pivot(recipe: dict, source_url: str) -> dict:
    name = recipe.get("name") or "recette-sans-titre"
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:60] or "recette"
    return {
        "id": slug,
        "titre": name,
        "provenance": {"type": "web", "url": source_url, "adapte_de": None},
        "portions_base": yield_to_portions(recipe.get("recipeYield")),
        "ingredients_bruts": [i for i in (recipe.get("recipeIngredient") or []) if isinstance(i, str)],
        "ingredients": [],
        "etapes": instructions_to_steps(recipe.get("recipeInstructions")),
        "temps": {
            "prep_min": iso8601_minutes(recipe.get("prepTime")),
            "cuisson_min": iso8601_minutes(recipe.get("cookTime")),
            "actif_min": None,
            "total_min": iso8601_minutes(recipe.get("totalTime")),
        },
        "batch": {"batchable": None, "composants": []},
        "tags": {},
        "_a_completer_par_le_modele": [
            "ingredients (structurés, catégories, bio, frais_saisonnier)",
            "portions -> adapter à PAR-1", "temps.actif_min", "batch", "tags de vérification",
        ],
    }


def main():
    ap = argparse.ArgumentParser(description="Extrait une recette schema.org/Recipe vers le schéma pivot")
    ap.add_argument("source", help="URL http(s) ou chemin d'un fichier HTML local")
    ap.add_argument("--out", help="Fichier de sortie JSON (défaut: stdout)")
    args = ap.parse_args()

    html = fetch(args.source)
    collector = LdJsonCollector()
    collector.feed(html)

    recipes = [n for n in iter_json_objects(collector.blocks) if is_recipe(n)]
    if not recipes:
        print("Aucun balisage schema.org/Recipe trouvé — extraction manuelle nécessaire (phase 2).", file=sys.stderr)
        sys.exit(2)

    pivot = to_pivot(recipes[0], args.source if args.source.startswith("http") else None)
    out = json.dumps(pivot, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out + "\n")
        print(f"Écrit : {args.out}", file=sys.stderr)
    else:
        print(out)


if __name__ == "__main__":
    main()
