#!/usr/bin/env python3
"""monmarche.py — adaptateur mon-marché.fr : prix du panier (PRX-1) et quantités
en unités de vente. API REST interne accessible en HTTP (pas de WAF, testé 2026-08-14).

- Recherche : GET /api/search2?type=PRODUCT&text=<terme> → {count, items[]}
- Produit : name, sku, origin, labels (bio), itemPrice (centimes), weightPrice.unitPrice
  (centimes/kg), itemDefinition {type, terminology, weight}, availableQuantity.

Appariement (hiérarchie ARB-2 : santé > bio > CO2e > prix > local) : bio d'abord,
puis prix au kilo le plus bas, puis origine France en départage (PLA-2).

Chiffrage : la liste de courses (grammes agrégés depuis le menu) est convertie en
unité de vente du produit — au poids (kg/g) ou à la pièce (ceil grammes / poids pièce) —
et sommée. Verdict PRX-1 vs l'intervalle PAR-4 (100-130 €/sem).

Note : prix du catalogue standard (zone de livraison parisienne) ; la dispo peut
varier légèrement par secteur. Cache disque pour éviter de re-requêter à chaque rendu.

Usage :
    py monmarche.py --recherche "tomate"
    py monmarche.py menu.json            # → panier chiffré + PRX-1
"""

import argparse
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from commun import DOSSIER_DATA, ecrire_json, get_json, lire_json, normalise, stdout_utf8
from agribalyse import en_kg

BASE = "https://www.mon-marche.fr/api/search2?type=PRODUCT&modelVersion=ordinal_df&text="
CAT = "https://www.mon-marche.fr/api/category/"
CACHE = DOSSIER_DATA / "monmarche_cache.json"
CATALOGUE = DOSSIER_DATA / "catalogue_monmarche.json"

# rayons capturés pour la planification (le reste — entretien, bébé, alcool… — est hors périmètre)
RAYONS_CAPTURE = ["legumes", "fruits", "viandes", "poissons", "cremerie",
                  "fromages", "charcuterie", "epicerie", "boulangerie-en-ligne"]
# sous-catégories marketing/doublons à ne pas parcourir (promotions* : les produits
# y doublonnent leur vraie catégorie et fausseraient le classement)
SLUGS_IGNORES = {"recettes-du-primeur", "nos-meilleures-recettes",
                 "nos-meilleures-offres", "anti-gaspi"}


def _slug_ignore(slug):
    return slug in SLUGS_IGNORES or slug.startswith("promotions")

PRX_MIN, PRX_MAX = 100.0, 130.0   # PAR-4 €/sem pour 2

RAYON = {
    "legume": "Fruits & Légumes", "fruit": "Fruits & Légumes",
    "poisson": "Boucherie & Poissonnerie", "volaille": "Boucherie & Poissonnerie",
    "viande_rouge": "Boucherie & Poissonnerie",
    "oeuf": "Crèmerie", "laitage": "Crèmerie",
    "legumineuse": "Épicerie", "cereale": "Épicerie", "matiere_grasse": "Épicerie",
    "condiment": "Épicerie", "autre": "Épicerie",
}
RAYON_ORDRE = ["Fruits & Légumes", "Boucherie & Poissonnerie", "Crèmerie", "Épicerie"]


def _simplifier(it):
    idf = it.get("itemDefinition") or {}
    term = idf.get("terminology") or {}
    poids = (idf.get("weight") or {}).get("value")
    wp = it.get("weightPrice") or {}
    origin = it.get("origin") or ""
    return {
        "nom": it.get("name"), "sku": it.get("sku"), "origine": origin,
        "bio": any("bio" in (l.get("label") or "").lower() for l in (it.get("labels") or [])),
        "france": "france" in normalise(origin),
        "itemPrice_c": it.get("itemPrice"), "prix_kg_c": wp.get("unitPrice"),
        "type": idf.get("type"), "poids_piece": poids,
        "unite_s": term.get("singular"), "unite_p": term.get("plural"),
        "dispo": it.get("availableQuantity", 0),
    }


def _cache():
    return lire_json(CACHE) if CACHE.exists() else {}


# qualificatifs à retirer pour une 2e recherche si la 1re ne donne rien d'exploitable
QUALIF = ("surgeles", "surgele", "surgelee", "surgelees", "completes", "complet",
          "complete", "semi", "hache", "hachee", "frais", "fraiche", "en conserve")

# formes transformées à écarter pour un ingrédient brut (« tomate » ≠ jus de tomate)
EXCLUS_PREP = {"jus", "compote", "compotes", "seche", "sechee", "seches", "sechees",
               "grille", "grillee", "grilles", "grillees", "boisson", "chausson", "chaussons",
               "houmous", "snack", "sauce", "sirop", "confit", "dinosaure", "dinosaures",
               "enfant", "enfants", "aperitif", "aperitives", "moutarde", "marine", "marinee",
               "pane", "panee", "farci", "farcie", "cocktail", "petillant", "nectar", "glace",
               "tarte", "tartelette", "pizza", "gratin", "veloute", "soupe", "puree", "chips",
               "biscuit", "gateau", "barre", "creme", "confiture", "smoothie", "poudre",
               "cuit", "cuits", "cuite", "cuites", "concassee", "concassees", "burger"}
SEED_OK = ("graine", "graines", "lin", "courge", "chanvre", "tournesol", "sesame")


def chercher(terme, cache=None):
    """produits mon-marché pour un terme (ordre de pertinence mon-marché ; cache disque)."""
    cache = cache if cache is not None else _cache()
    cle = normalise(terme)
    if cle in cache:
        return cache[cle]
    try:
        d = get_json(BASE + terme.replace(" ", "%20"))
        items = [_simplifier(x) for x in (d.get("items") or [])]
    except Exception:
        items = []
    cache[cle] = items
    ecrire_json(CACHE, cache)
    time.sleep(0.3)
    return items


def _terme_court(nom):
    """retire les qualificatifs (« épinards surgelés » → « épinards ») pour un repli."""
    toks = [t for t in normalise(nom).split() if t not in QUALIF and t != "de" and t != "d"]
    return " ".join(toks[:2])


def apparier(nom, cache=None):
    """meilleur produit en **respectant la pertinence mon-marché** : parmi les premiers
    résultats dont le nom contient le mot-tête, préférer le bio ; repli sur terme court."""
    ARTICLES = {"le", "la", "les", "l", "du", "des", "de", "un", "une", "au", "aux"}

    def _sans_article(nom_norm):
        toks = nom_norm.split()
        while toks and toks[0] in ARTICLES:
            toks = toks[1:]
        return toks

    def choisir(prods):
        n = normalise(nom)
        tete = n.split()[0] if n.split() else n
        graine_ok = any(k in n for k in SEED_OK)
        dispo = [(i, p) for i, p in enumerate(prods)
                 if p.get("dispo", 0) > 0 and (p.get("prix_kg_c") or p.get("itemPrice_c"))]
        # exige TOUS les mots significatifs (les qualificatifs complet/haché/surgelé
        # sont distinctifs → gardés ; pas de match approximatif)
        req = [t for t in _sans_article(n) if len(t) >= 3]

        def couvre(p):
            pt = set(normalise(p["nom"]).split())
            return all(any(t == q or t == q + "s" or t + "s" == q for q in pt) for t in req)

        cible = [(i, p) for i, p in dispo if couvre(p)]

        def transforme(p):
            toks = set(normalise(p["nom"]).split())
            if "graines" in toks and not graine_ok:
                return True
            return bool(toks & EXCLUS_PREP)

        def commence(p):   # nom (après article) commence par l'ingrédient → signal fort
            t0 = _sans_article(normalise(p["nom"]))
            return bool(t0) and (t0[0] == tete or t0[0] == tete + "s")

        pool = cible                               # pas de repli arbitraire : match franc ou rien
        if not pool:
            return None
        # 1. commence par l'ingrédient · 2. non-transformé · 3. bio · 4. nom nu · 5. pertinence
        pool.sort(key=lambda ip: (not commence(ip[1]), transforme(ip[1]), not ip[1]["bio"],
                                  len(normalise(ip[1]["nom"]).split()), ip[0]))
        return pool[0][1]

    return choisir(chercher(nom, cache))            # match franc ou None (honnête)


def capturer_catalogue():
    """parcourt l'arbre /api/category des rayons utiles → catalogue dédupliqué par SKU.

    Les feuilles portent les produits (même format que search2) ; les nœuds listent
    leurs sous-catégories par slug. Un produit peut apparaître dans plusieurs
    sous-catégories (bio, saison…) — première occurrence conservée."""
    vus_slugs, produits = set(), {}   # sku -> produit simplifié
    for rayon in RAYONS_CAPTURE:
        pile = [rayon]
        while pile:
            slug = pile.pop(0)
            if slug in vus_slugs or _slug_ignore(slug):
                continue
            vus_slugs.add(slug)
            try:
                d = get_json(CAT + slug)
            except Exception:
                continue
            time.sleep(0.3)
            for sc in d.get("subcategories") or []:
                if isinstance(sc, dict) and sc.get("slug"):
                    pile.append(sc["slug"])
            for it in d.get("items") or []:
                if it.get("type") != "PRODUCT":
                    continue
                sku = it.get("sku")
                if not sku or sku in produits:
                    continue
                p = _simplifier(it)
                p["rayon"] = rayon
                p["sous_categorie"] = d.get("slug")
                p["pim"] = it.get("pimCategoryName")
                produits[sku] = p
        print(f"  {rayon:22} → {sum(1 for p in produits.values() if p['rayon'] == rayon)} produits")
    cat = {"source": "mon-marche.fr /api/category", "rayons_captures": RAYONS_CAPTURE,
           "produits": produits}
    ecrire_json(CATALOGUE, cat)
    print(f"Catalogue : {len(produits)} produits ({CATALOGUE.name})")
    return cat


def _grammes(ing):
    kg = en_kg(ing.get("quantite", 0), ing.get("unite"), None)
    return kg * 1000 if kg is not None else None


def _cout_unite(p, grammes):
    """→ (cout_eur, quantite_affichee) selon le mode de vente."""
    ip = (p["itemPrice_c"] or 0) / 100.0
    pkg = (p["prix_kg_c"] or 0) / 100.0
    if grammes is None:                            # compté à la pièce → 1 unité de vente
        u = p.get("unite_s") or "pièce"
        q = f"~{round(p['poids_piece']*1000)} g" if p.get("poids_piece") and not p.get("unite_s") else f"1 {u}"
        return round(ip, 2), q
    if p["type"] in ("pieceWeight", "piece") and p.get("poids_piece"):
        n = max(1, math.ceil(grammes / (p["poids_piece"] * 1000)))
        u = p["unite_p"] if n > 1 else (p["unite_s"] or "pièce")
        return round(n * ip, 2), f"{n} {u}"
    if pkg:                                        # vendu au poids
        q = (f"{grammes/1000:.1f}".rstrip("0").rstrip(".") + " kg") if grammes >= 1000 else f"{round(grammes)} g"
        return round(grammes / 1000 * pkg, 2), q
    # vendu à la pièce/paquet sans prix au kilo → 1 unité
    u = p["unite_s"] or "pièce"
    return round(ip, 2), f"1 {u}"


def _agreger(menu):
    occ = {}
    for r in menu["repas"]:
        occ[r["recette_id"]] = occ.get(r["recette_id"], 0) + 1
    agg = {}   # nom -> [grammes|None, categorie, sku]
    placard = set()
    for rid, rec in menu["recettes"].items():
        n = occ.get(rid, 0)
        for ing in rec["ingredients"]:
            # "stock": true = ingrédient du garde-manger (pantry.md) : déjà là,
            # ne se rachète pas — listé à part pour rester visible (ARB-3)
            if ing.get("stock"):
                placard.add(ing["nom"])
                continue
            g = _grammes(ing)
            k = ing["nom"]
            # sans grammage (œufs, citron… comptés à la pièce) : gardé si un SKU
            # est épinglé — chiffré à 1 unité de vente
            if g is None and not ing.get("sku"):
                continue
            agg.setdefault(k, [None, ing.get("categorie", "autre"), None])
            if g is not None:
                agg[k][0] = (agg[k][0] or 0.0) + g * n
            if ing.get("sku"):
                agg[k][2] = ing["sku"]
    return agg, sorted(placard)


def chiffrer_courses(menu):
    cache = _cache()
    catalogue = (lire_json(CATALOGUE).get("produits") or {}) if CATALOGUE.exists() else {}
    # l'arbre /api/category n'est pas exhaustif (constaté : flocons d'avoine, huile
    # de lin absents) — les produits vus via la recherche complètent l'index SKU
    for prods in cache.values():
        for p in prods:
            if p.get("sku") and p["sku"] not in catalogue:
                catalogue[p["sku"]] = p
    par_rayon = {r: [] for r in RAYON_ORDRE}
    total, non_trouves = 0.0, []
    total_conso = 0.0
    agg, du_placard = _agreger(menu)
    for nom, (grammes, cat, sku) in agg.items():
        # pipeline inversé : le SKU choisi à la planification prime (exact, zéro fuzzy)
        p = catalogue.get(sku) if sku else None
        appariement = "sku" if p else "texte"
        if not p:
            p = apparier(nom, cache)
        if not p:
            non_trouves.append(nom)
            continue
        cout, q = _cout_unite(p, grammes)
        # coût consommé : prorata des grammes réellement utilisés cette semaine
        # (un pack entamé — huile, flocons, riz — s'amortit sur plusieurs semaines)
        pkg = (p["prix_kg_c"] or 0) / 100.0
        if grammes and pkg:
            conso = min(cout, round(grammes / 1000 * pkg, 2))
        else:
            conso = cout                           # compté à la pièce : consommé en semaine
        total += cout
        total_conso += conso
        ray = RAYON.get(cat, "Épicerie")
        par_rayon.setdefault(ray, []).append({
            "ingredient": nom, "produit": p["nom"], "quantite": q, "cout": cout,
            "cout_conso": conso, "categorie": cat,
            "prix_kg": round((p["prix_kg_c"] or 0) / 100.0, 2), "bio": p["bio"],
            "origine": p["origine"], "sku": p["sku"], "appariement": appariement,
        })
    for ray in par_rayon:
        par_rayon[ray].sort(key=lambda x: x["ingredient"].lower())
    total, total_conso = round(total, 2), round(total_conso, 2)
    # PRX-1 se juge sur le coût consommé (PAR-4 = budget hebdo de ce qu'on mange,
    # pas le ticket de caisse gonflé par les packs garde-manger entamés)
    statut = "conforme" if total_conso <= PRX_MAX else "viole_souple"
    detail = (f"{total_conso:.2f} € consommés sur la semaine "
              f"(panier encaissé : {total:.2f} € avec les packs entamés)")
    if total_conso > PRX_MAX:
        detail += f" — dépasse de {total_conso - PRX_MAX:.2f} €"
    prx1 = {"id": "PRX-1", "statut": statut, "valeur": total_conso,
            "seuil": f"{PRX_MIN:.0f}-{PRX_MAX:.0f} €/sem (PAR-4)", "detail": detail}
    # SAN-11 : part bio du panier **en valeur** (cible ≥ 80 %) — sur le panier encaissé.
    # Le poisson sauvage est exempté du calcul : le label AB n'existe qu'en
    # aquaculture, un maquereau de pêche ne peut pas être « bio ». (PLA-5 couvre
    # la durabilité du poisson.)
    tous = [it for its in par_rayon.values() for it in its]
    # le poisson est exempté des DEUX côtés du ratio (un saumon bio compté au
    # numérateur mais pas au dénominateur donnait > 100 %)
    bio_eur = sum(it["cout"] for it in tous if it["bio"] and it["categorie"] != "poisson")
    exempt = sum(it["cout"] for it in tous if it["categorie"] == "poisson")
    assiette = total - exempt
    part_bio = bio_eur / assiette if assiette else 0.0
    san11 = {"id": "SAN-11", "statut": "conforme" if part_bio >= 0.8 else "viole_souple",
             "valeur": f"{part_bio*100:.0f} %", "seuil": "≥ 80 % en valeur",
             "detail": f"{bio_eur:.2f} € bio sur {assiette:.2f} € éligibles "
                       f"(poisson sauvage exempté : {exempt:.2f} € — le label AB n'existe "
                       "qu'en aquaculture) ; lignes non-bio = dérogations affichées "
                       "(indisponible en bio ou hors prix)"}
    return {"par_rayon": par_rayon, "total_eur": total, "total_conso_eur": total_conso,
            "non_trouves": non_trouves, "du_placard": du_placard,
            "part_bio": round(part_bio, 3),
            "prx1": prx1, "san11": san11,
            "source": "mon-marché.fr (catalogue, zone parisienne)"}


def main():
    stdout_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("menu", nargs="?")
    ap.add_argument("--recherche")
    ap.add_argument("--capture", action="store_true",
                    help="capture le catalogue complet des rayons alimentaires")
    args = ap.parse_args()
    if args.capture:
        capturer_catalogue()
    elif args.recherche:
        for p in chercher(args.recherche)[:8]:
            pk = f"{p['prix_kg_c']/100:.2f} €/kg" if p['prix_kg_c'] else "?"
            print(f"  {'BIO' if p['bio'] else '   '} {p['nom']:45} {pk:>12}  {p['origine']}")
    elif args.menu:
        r = chiffrer_courses(lire_json(args.menu))
        print(f"Semaine consommée : {r['total_conso_eur']:.2f} € — panier encaissé {r['total_eur']:.2f} € "
              f"— PRX-1 {r['prx1']['statut'].upper()} (cible {PRX_MIN:.0f}-{PRX_MAX:.0f} €)")
        for ray in RAYON_ORDRE:
            for it in r["par_rayon"].get(ray, []):
                print(f"  [{ray[:12]:12}] {it['ingredient']:16} → {it['produit'][:34]:34} "
                      f"{it['quantite']:>10}  {it['cout']:>6.2f} € (conso {it['cout_conso']:.2f})")
        for nt in r["non_trouves"]:
            print(f"  [non trouvé] {nt}")
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
