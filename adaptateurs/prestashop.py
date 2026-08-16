#!/usr/bin/env python3
"""prestashop.py — socle de capture des boutiques PrestaShop 1.7+ (labelleiloise, satsuki).

Les pages catégorie d'un thème PrestaShop 1.7 répondent en JSON natif au
paramètre `?from-xhr` (ProductListingFrontController.getAjaxResponse) :
`products` (nom, price_amount, reference, category_name, canonical_url,
description_short) + `pagination` (total_items, pages_count). Pas de WAF sur
les deux boutiques visées — HTTP direct avec en-têtes navigateur suffit.
Validé par sondes le 2026-08-15.

Limites du listing : pas de stock (`quantity` absent — un produit listé est
présumé commandable, PrestaShop masque ou marque l'indisponible) et
`unit_price` vide ou égal au prix → le €/kg est déduit du poids lu dans le nom.
"""

import json
import re
import time
import urllib.request

from commun import ENTETES, normalise

RE_MULTI = re.compile(r"(\d+)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*(kg|g|cl|ml|l)\b", re.I)
RE_POIDS = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kg|g|cl|ml|l)\b", re.I)
RE_BIO = re.compile(r"\b(bio|biologique|organic|organique)\b")
RE_TAGS = re.compile(r"<[^>]+>")

VERS_G = {"kg": 1000.0, "g": 1.0, "l": 1000.0, "cl": 10.0, "ml": 1.0}


def fetch_json(url, essais=3, pause_s=2.0):
    """GET JSON du endpoint from-xhr, retries doux."""
    entetes = dict(ENTETES)
    entetes["X-Requested-With"] = "XMLHttpRequest"
    derniere = None
    for i in range(essais):
        try:
            req = urllib.request.Request(url, headers=entetes)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            derniere = e
            if i < essais - 1:
                time.sleep(pause_s * (i + 1))
    raise RuntimeError(f"GET {url} en échec après {essais} essais : {derniere}")


def pages_categorie(url_cat, pause_s=1.2, max_pages=40):
    """Itère les listes de produits bruts d'une catégorie, page par page."""
    page = 1
    while page <= max_pages:
        sep = "&" if "?" in url_cat else "?"
        url = f"{url_cat}{sep}from-xhr" + (f"&page={page}" if page > 1 else "")
        data = fetch_json(url)
        produits = data.get("products") or []
        if not produits:
            return
        yield produits
        pagination = data.get("pagination") or {}
        if page >= (pagination.get("pages_count") or 1):
            return
        page += 1
        time.sleep(pause_s)


def poids_g_depuis_nom(nom):
    """Poids (ou volume) total en g/ml lu dans le nom du produit, sinon None.
    Gère « 3x80g », « 1kg », « 500 g », « 20cl », « 750ml »."""
    m = RE_MULTI.search(nom)
    if m:
        n, val, unite = int(m.group(1)), float(m.group(2).replace(",", ".")), m.group(3).lower()
        return n * val * VERS_G[unite]
    m = RE_POIDS.search(nom)
    if m:
        val, unite = float(m.group(1).replace(",", ".")), m.group(2).lower()
        return val * VERS_G[unite]
    return None


def normaliser_produit(brut):
    """Produit brut from-xhr → enregistrement commun du catalogue."""
    nom = (brut.get("name") or "").strip()
    desc = RE_TAGS.sub(" ", brut.get("description_short") or "")
    desc = " ".join(desc.split())
    prix = brut.get("price_amount")
    poids_g = poids_g_depuis_nom(nom)
    prix_kg = round(prix / poids_g * 1000, 2) if (prix and poids_g) else None
    return {
        "id": int(brut["id_product"]),
        "ref": brut.get("reference") or "",
        "nom": nom,
        "prix": prix,
        "poids_g": poids_g,
        "prix_kg": prix_kg,
        "bio": bool(RE_BIO.search(normalise(nom + " " + desc))),
        "categorie": (brut.get("category_name") or "").strip(),
        "url": brut.get("canonical_url") or brut.get("url") or "",
        "desc": desc[:200],
    }


def capturer(urls_categories, pause_s=1.2, verbeux=True):
    """Capture + dédup (par id_product) d'une liste de pages catégorie."""
    produits = {}
    for url_cat in urls_categories:
        avant = len(produits)
        try:
            for lot in pages_categorie(url_cat, pause_s=pause_s):
                for brut in lot:
                    p = normaliser_produit(brut)
                    produits.setdefault(p["id"], p)
        except RuntimeError as e:
            print(f"  ! {url_cat} : {e}")
            continue
        if verbeux:
            print(f"  {url_cat.rsplit('/', 1)[-1]} : +{len(produits) - avant} (total {len(produits)})")
        time.sleep(pause_s)
    return produits
