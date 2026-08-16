#!/usr/bin/env python3
"""rendu_semaine.py — livrable HTML d'une semaine, à partir de son menu.json.

Formalise le rendu (menu, recettes, batch, courses, rapport de conformité,
suggestions CrowdFarming) en une page unique, thème clair/sombre, prête à
publier en artefact. Orchestre le pipeline v2 :
  1. verifie_menu_v2.py  → rapport de conformité fusionné (v1 + CO2e)
  2. suggest_crowdfarming.py → suggestions garde-manger (OPTIONNEL — ignoré si absent)
  3. agrège la liste de courses depuis les ingrédients du menu
  4. rend le HTML avec le gabarit de design partagé

Usage :
    py rendu_semaine.py menu.json
    py rendu_semaine.py menu.json --sortie livrables.html --no-run
      (--no-run : réutilise les rapports déjà produits à côté du menu)
"""

import argparse
import datetime as _dt
import html
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from commun import lire_json, stdout_utf8
from catalogue_regles import CATEGORIES, TRAITEMENT_LIBELLE

ICI = Path(__file__).parent

JOUR_OFFSET = {"lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4,
               "samedi": 5, "dimanche": 6, "samedi+1": 5, "dimanche+1": 6}
# semaine à départ samedi (cadence livraison samedi matin → menu sam → ven)
JOUR_OFFSET_SAM = {"samedi": 0, "dimanche": 1, "lundi": 2, "mardi": 3,
                   "mercredi": 4, "jeudi": 5, "vendredi": 6}
JOUR_NOM = {0: "Lundi", 1: "Mardi", 2: "Mercredi", 3: "Jeudi", 4: "Vendredi", 5: "Samedi", 6: "Dimanche"}
NOMS_SEMAINE = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
MOIS_FR = ["", "janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"]

RAYON = {
    "legume": "Primeur — légumes", "fruit": "Primeur — fruits",
    "poisson": "Poisson & viande", "volaille": "Poisson & viande", "viande_rouge": "Poisson & viande",
    "oeuf": "Crèmerie", "laitage": "Crèmerie",
    "legumineuse": "Épicerie & placard", "cereale": "Épicerie & placard",
    "matiere_grasse": "Épicerie & placard", "condiment": "Épicerie & placard", "autre": "Épicerie & placard",
}
RAYON_ORDRE = ["Primeur — légumes", "Primeur — fruits", "Poisson & viande", "Crèmerie", "Épicerie & placard"]

PILL = {"conforme": ("ok", "Conforme"), "viole_souple": ("warn", "Dérogation"),
        "viole_dur": ("stop", "Violé"), "non_verifie_v1": ("neu", "Non chiffré v1")}


def e(x):
    return html.escape(str(x if x is not None else ""))


# --- Orchestration -------------------------------------------------------------

def lancer(menu_path):
    for script in ("verifie_menu_v2.py", "suggest_crowdfarming.py"):
        if not (ICI / script).exists():   # adaptateur optionnel non installé
            continue
        subprocess.run([sys.executable, str(ICI / script), str(menu_path)],
                       capture_output=True, text=True)


def exporter_pdf(html_path, pdf_path):
    """PDF A4 portrait via Edge/Chrome headless — le bloc @page du gabarit
    (size: A4, racine 12.5px, thème clair forcé) pilote la mise en page."""
    import os
    import shutil
    candidats = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        shutil.which("msedge"), shutil.which("chrome"),
    ]
    exe = next((c for c in candidats if c and Path(c).exists()), None)
    if not exe:
        print("PDF non produit : ni Edge ni Chrome trouvés (l'HTML reste imprimable via Ctrl+P).")
        return False
    html_uri = Path(html_path).resolve().as_uri()
    r = subprocess.run(
        [exe, "--headless", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={Path(pdf_path).resolve()}", html_uri],
        capture_output=True, text=True, timeout=120)
    if Path(pdf_path).exists():
        print(f"PDF : {pdf_path}")
        return True
    print(f"PDF non produit (code {r.returncode}) : {r.stderr.strip()[:300]}")
    return False


# --- Agrégations ---------------------------------------------------------------

def date_semaine(semaine_du):
    try:
        d = _dt.date.fromisoformat(semaine_du)
        return d
    except Exception:
        return None


def libelle_jour(offset, debut):
    if debut:
        j = debut + _dt.timedelta(days=offset)
        return NOMS_SEMAINE[j.weekday()], f"{j.day} {MOIS_FR[j.month]}"
    return JOUR_NOM[offset], ""


def fmt_qte(total, unite):
    if unite in ("g", "ml"):
        if total >= 1000:
            v = total / 1000
            return (f"{v:.1f}".rstrip("0").rstrip(".")) + (" kg" if unite == "g" else " L")
        return f"{total:g} {unite}"
    if unite in ("unite", "unites", "u"):
        return f"{total:g}"
    return f"{total:g} {unite}"


def courses(menu):
    recettes = menu["recettes"]
    compte = {}
    for r in menu["repas"]:
        compte[r["recette_id"]] = compte.get(r["recette_id"], 0) + 1
    agg = {}  # (rayon, nom, unite) -> [total, categorie]
    for rid, n in compte.items():
        for ing in recettes[rid]["ingredients"]:
            ray = RAYON.get(ing.get("categorie"), "Épicerie & placard")
            cle = (ray, ing["nom"], ing.get("unite") or "")
            agg.setdefault(cle, 0.0)
            agg[cle] += (ing.get("quantite") or 0) * n
    par_rayon = {r: [] for r in RAYON_ORDRE}
    for (ray, nom, unite), total in agg.items():
        par_rayon.setdefault(ray, []).append((nom, fmt_qte(total, unite)))
    for ray in par_rayon:
        par_rayon[ray].sort(key=lambda t: t[0].lower())
    return par_rayon


def fmt_valeur(v):
    if isinstance(v, dict):
        return " · ".join(f"{k} {vv}" for k, vv in v.items())
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    return str(v)


# --- Rendu HTML ----------------------------------------------------------------

def bloc_menu(menu):
    debut = date_semaine(menu.get("semaine_du"))
    # si la semaine démarre un samedi (nouvelle cadence), l'ordre suit la livraison
    mapping = JOUR_OFFSET_SAM if (debut and debut.weekday() == 5) else JOUR_OFFSET
    jours = {}
    for r in menu["repas"]:
        off = mapping.get(r["jour"])
        if off is None:
            continue
        jours.setdefault(off, {}).setdefault(r["moment"], []).append(r["recette_id"])
    titres = {rid: menu["recettes"][rid]["titre"] for rid in menu["recettes"]}
    lignes = []
    for off in sorted(jours):
        nom, date = libelle_jour(off, debut)
        d = jours[off]
        def cell(moment):
            ids = d.get(moment)
            if not ids:
                return '<span>—</span>'
            return " · ".join(f"<b>{e(titres[i])}</b>" for i in ids)
        col = d.get("dejeuner")
        dej = cell("dejeuner")
        if not col and d.get("collation"):
            dej = '<span>collation : ' + e(titres[d["collation"][0]]) + '</span>'
        lignes.append(
            f'<tr><td class="day">{e(nom)}<small>{e(date)}</small></td>'
            f'<td class="meal">{cell("petit_dejeuner")}</td>'
            f'<td class="meal">{dej}</td>'
            f'<td class="meal">{cell("diner")}</td></tr>')
    return "\n".join(lignes)


def bloc_conformite(rapport):
    """TOUTES les exigences du référentiel, groupées par catégorie. Les verdicts
    machine viennent du rapport ; le reste affiche son mode de traitement."""
    verdicts = {r["id"]: r for r in rapport["regles"]}
    lignes = []
    for cat, regles in CATEGORIES:
        lignes.append(f'<tr class="cathead"><th colspan="4">{e(cat)}</th></tr>')
        for rc in regles:
            ids = rc.get("rapport") or []
            trouves = [verdicts[i] for i in ids if i in verdicts]
            if trouves:
                # une règle peut agréger plusieurs verdicts machine (SAN-3, GOU-1…)
                for k, r in enumerate(trouves):
                    cls, label = PILL.get(r["statut"], ("neu", r["statut"]))
                    val = e(fmt_valeur(r.get("valeur")))
                    seuil = e(fmt_valeur(r.get("seuil")) if r.get("seuil") is not None else r.get("detail", ""))
                    if k == 0:
                        regle = (f'<b>{e(rc["id"])}</b><span class="rnom">{e(rc["nom"])}</span>'
                                 f'<span class="rex">{e(rc["exigence"])}</span>')
                    else:
                        sous = r.get("nom") or r["id"]
                        regle = f'<span class="rnom">↳ {e(sous)}</span>'
                    lignes.append(
                        f'<tr><td class="regle">{regle}</td><td><span class="pill {cls}">{e(label)}</span></td>'
                        f'<td>{val}</td><td>{seuil}</td></tr>')
            else:
                label, cls = TRAITEMENT_LIBELLE.get(rc.get("traitement", "info"), ("—", "neu"))
                regle = (f'<b>{e(rc["id"])}</b><span class="rnom">{e(rc["nom"])}</span>'
                         f'<span class="rex">{e(rc["exigence"])}</span>')
                lignes.append(
                    f'<tr><td class="regle">{regle}</td><td><span class="pill {cls}">{e(label)}</span></td>'
                    f'<td>—</td><td>{e(rc.get("note", ""))}</td></tr>')
    return "\n".join(lignes)


def tags_recette(t):
    out = []
    if t.get("legumineuse"):
        out.append("légumineuse")
    if t.get("poisson_gras"):
        out.append("poisson gras")
    elif t.get("poisson"):
        out.append("poisson")
    if t.get("viande_rouge_g"):
        out.append(f"viande rouge {t['viande_rouge_g']} g")
    if t.get("nova4"):
        out.append("NOVA 4")
    if t.get("cg_basse"):
        out.append("CG basse")
    return out[:4]


def bloc_recettes(menu):
    compte, moments = {}, {}
    for r in menu["repas"]:
        compte[r["recette_id"]] = compte.get(r["recette_id"], 0) + 1
        moments.setdefault(r["recette_id"], set()).add(r["moment"])
    MOMENT_FR = {"diner": "Dîner", "dejeuner": "Déjeuner", "petit_dejeuner": "Petit-déjeuner", "collation": "Collation"}
    cartes = []
    for rid, rec in menu["recettes"].items():
        n = compte.get(rid, 0)
        mo = " / ".join(MOMENT_FR.get(m, m) for m in sorted(moments.get(rid, [])))
        prov = rec.get("provenance", {}).get("type", "générée")
        reg = rec.get("tags", {}).get("registre", "")
        suffixe = f" (×{n})" if n > 1 else ""
        ings = "".join(
            f'<li>{e(i["nom"])} <span class="qty">{e(i.get("quantite",""))} {e(i.get("unite",""))}</span></li>'
            for i in rec["ingredients"])
        etapes = e(rec.get("resume") or " ".join(rec.get("etapes", [])))
        tags = "".join(f'<span class="tag">{e(x)}</span>' for x in tags_recette(rec.get("tags", {})))
        cartes.append(
            f'<article class="card"><p class="prov">{e(mo)}{e(suffixe)} · {e(reg)} · {e(prov)}</p>'
            f'<h3>{e(rec["titre"])}</h3><ul>{ings}</ul>'
            f'<p class="steps">{etapes}</p><div class="tagrow">{tags}</div></article>')
    return "\n".join(cartes)


def bloc_recettes_detail(menu, cm):
    """onglet « Recettes pas à pas » : étapes numérotées, ingrédients avec le
    produit épinglé (SKU), temps, batch. Pour 2 personnes."""
    produits = {}
    if cm:
        for its in cm.get("par_rayon", {}).values():
            for it in its:
                produits[it["sku"]] = it["produit"]
    compte, moments = {}, {}
    for r in menu["repas"]:
        compte[r["recette_id"]] = compte.get(r["recette_id"], 0) + 1
        moments.setdefault(r["recette_id"], set()).add(r["moment"])
    MOMENT_FR = {"diner": "Dîner", "dejeuner": "Déjeuner", "petit_dejeuner": "Petit-déjeuner", "collation": "Collation"}
    arts = []
    for rid, rec in menu["recettes"].items():
        n = compte.get(rid, 0)
        mo = " / ".join(MOMENT_FR.get(m, m) for m in sorted(moments.get(rid, [])))
        suffixe = f" ×{n} cette semaine" if n > 1 else ""
        t = rec.get("temps", {})
        temps = (f'{t.get("prep_min", "?")} min prép · {t.get("cuisson_min", "?")} min cuisson '
                 f'· {t.get("actif_min", "?")} min actives')
        lis = []
        for i in rec["ingredients"]:
            prod = produits.get(i.get("sku"))
            sous = f'<span class="pd">{e(prod)}</span>' if prod else ""
            lis.append(f'<li><span>{e(i["nom"])}{sous}</span>'
                       f'<span class="qty">{e(i.get("quantite", ""))} {e(i.get("unite", ""))}</span></li>')
        etapes = "".join(f"<li>{e(x)}</li>" for x in rec.get("etapes", []))
        bat = rec.get("batch", {})
        comps = ", ".join(f'{e(c["nom"])} ({e(c["famille_dlc"])})' for c in bat.get("composants", []))
        note_batch = (f'<p class="note"><b>Batch.</b> Composants préparés le dimanche : {comps}.</p>'
                      if bat.get("batchable") and comps else "")
        tags = "".join(f'<span class="tag">{e(x)}</span>' for x in tags_recette(rec.get("tags", {})))
        arts.append(
            f'<article class="rdet"><header><p class="prov">{e(mo)}{e(suffixe)} · '
            f'{e(rec.get("tags", {}).get("registre", ""))} · {e(rec.get("provenance", {}).get("type", "générée"))} '
            f'· pour 2</p><h3>{e(rec["titre"])}</h3><p class="tps">{e(temps)}</p></header>'
            f'<div class="rcols"><div><h4>Ingrédients</h4><ul class="ring">{"".join(lis)}</ul></div>'
            f'<div><h4>Préparation</h4><ol class="rsteps">{etapes}</ol>{note_batch}</div></div>'
            f'<div class="tagrow">{tags}</div></article>')
    return "\n".join(arts)


def bloc_batch(menu):
    pb = menu.get("plan_batch", {})
    taches = "".join(
        f'<li><span>{e(t["description"])}</span>'
        f'<span class="dur">{e(t.get("duree_min","?"))} min · {e(t.get("ressource","-"))}</span></li>'
        for t in pb.get("taches", []) if t.get("duree_min"))
    aff = "".join(
        f'{e(a["composant"])} → {", ".join(e(j) for j in a.get("consomme_le", []))} '
        f'<span style="color:var(--faint)">({e(a["famille_dlc"])})</span> · '
        for a in pb.get("affectations", []))
    return taches, aff, pb.get("duree_totale_min", "?")


def bloc_courses(par_rayon):
    """repli sans chiffrage : liste grammée (utilisé si courses_monmarche absent)."""
    blocs = []
    for ray in RAYON_ORDRE:
        items = par_rayon.get(ray) or []
        if not items:
            continue
        lis = "".join(f'<li><span>{e(nom)}</span><span class="q">{e(q)}</span></li>' for nom, q in items)
        blocs.append(f'<div class="rayon"><h3>{e(ray)}</h3><ul>{lis}</ul></div>')
    return "\n".join(blocs)


def bloc_courses_mm(cm):
    """panier mon-marché : ingrédient + produit épinglé (SKU), quantité en unité
    de vente, coût à l'achat. L'écart ingrédient/produit rend les substitutions
    visibles (ARB-3 : rien de silencieux)."""
    blocs = []
    for ray, items in cm["par_rayon"].items():
        if not items:
            continue
        lis = "".join(
            f'<li><span>{e(it["ingredient"])}'
            f'<span class="pd">{e(it["produit"])}{" · bio" if it.get("bio") else ""}</span></span>'
            f'<span class="q">{e(it["quantite"])} · {it["cout"]:.2f} €</span></li>'
            for it in items)
        sous_total = sum(it["cout"] for it in items)
        blocs.append(f'<div class="rayon"><h3>{e(ray)} · {sous_total:.2f} €</h3><ul>{lis}</ul></div>')
    return "\n".join(blocs)


def txt_budget(cm, prx1):
    ok = prx1 and prx1.get("statut") == "conforme"
    pill = ("<b>conforme PAR-4</b>" if ok else "<b>dépasse la cible PAR-4</b>")
    placard = ""
    if cm.get("du_placard"):
        placard = (' <b>Du placard, non facturé</b> (pantry.md) : '
                   + ", ".join(e(x) for x in cm["du_placard"]) + ".")
    return (f'<b>Budget (Prix du panier — PRX-1).</b> Semaine consommée : '
            f'<b>{cm["total_conso_eur"]:.2f} €</b> — {pill} (cible 100–130 €/sem pour 2). '
            f'Panier encaissé : {cm["total_eur"]:.2f} € — l\'écart, ce sont les packs '
            f'garde-manger entamés (huiles, légumineuses, flocons…) amortis sur les semaines '
            f'suivantes. Prix réels mon-marché.fr par SKU, '
            f'chiffrés par le pipeline v2.{placard}')


def bloc_crowdfarming(cf):
    def prix(s):
        pu = f'{s["prix_au_kg"]:.2f} €/{s.get("unite_prix","kg")}' if s.get("prix_au_kg") else ""
        return f'{s["prix"]:.2f} €<br>{pu}' if s.get("prix") else ""
    gm = "".join(
        f'<div class="cf-item"><span class="nm">{e(s["produit"])} '
        f'<span class="og">{e(s.get("unite",""))}{" · bio" if s.get("bio") else ""}</span></span>'
        f'<span class="pr">{prix(s)}</span></div>'
        for s in cf.get("garde_manger", []))
    def pill_fruit(s):
        if s.get("origine_iso") == "fr":
            return '<span class="pill ok">Conforme</span>'
        return '<span class="pill warn">Dérogation</span>'
    def orig(s):
        iso = s.get("origine_iso")
        ville = s.get("origine_ville")
        return f'{e(ville)} ({e(iso)})' if iso else "Europe présumée · à confirmer"
    corb = "".join(
        f'<div class="cf-item"><span class="nm">{e(s["produit"])} '
        f'<span class="og">{orig(s)}</span></span>{pill_fruit(s)}</div>'
        for s in cf.get("corbeille_fruits", []))
    excl = ""
    if cf.get("exclus_pla3"):
        noms = ", ".join(e(x.get("produit") or x.get("ingredient")) for x in cf["exclus_pla3"])
        excl = (f'<p class="note">Exclu du frais par PLA-3 (hors-UE) : {noms} '
                f'<span class="pill stop">Exclu</span> → conserve / surgelé / séché.</p>')
    return gm, corb, excl


def rendre(menu, rapport, cf, css):
    lundi = date_semaine(menu.get("semaine_du"))
    if lundi:
        titre_date = f"Semaine du {lundi.day} {MOIS_FR[lundi.month]} {lundi.year}"
    else:
        titre_date = f"Semaine du {menu.get('semaine_du','?')}"
    c = rapport.get("compteurs", {})
    rampe = menu.get("rampe_semaine")
    rampe_txt = f"rampe fibres <b>semaine {rampe}</b>" if rampe else "hors rampe"
    statut = rapport.get("statut_global", "?")
    statut_txt = {"conforme": "Conforme", "derogations": "Dérogations", "violations_dures": "Violations dures"}.get(statut, statut)
    n_regles = sum(1 for r in rapport["regles"] if r["statut"] != "non_verifie_v1")
    n_exigences = sum(len(regles) for _, regles in CATEGORIES)
    taches, aff, duree = bloc_batch(menu)
    gm, corb, excl = bloc_crowdfarming(cf)
    cm = rapport.get("courses_monmarche")
    if cm and cm.get("par_rayon"):
        courses_html = bloc_courses_mm(cm)
        prx1 = next((r for r in rapport["regles"] if r["id"] == "PRX-1"), None)
        budget = txt_budget(cm, prx1)
    else:
        courses_html = bloc_courses(courses(menu))
        budget = ("<b>Budget.</b> Cible PAR-4 : <b>100–130 €/semaine</b>. "
                  "Panier non chiffré (pas de SKU épinglés dans ce menu).")
    return TEMPLATE.format(
        css=css, titre_date=e(titre_date), rampe_txt=rampe_txt,
        statut_cls={"conforme": "ok", "derogations": "warn", "violations_dures": "stop"}.get(statut, "neu"),
        statut_txt=e(statut_txt), n_regles=n_regles, n_exigences=n_exigences,
        co2e=e(c.get("co2e_kg_pp_sem", "?")), leg=e(c.get("legumineuses_occ", "?")),
        poisson=e(c.get("poisson_occ", "?")), gras=e(c.get("poisson_gras_occ", "?")),
        viande=e(c.get("viande_rouge_g_pp", "?")), part_batch=e(round((c.get("part_batch") or 0) * 100)),
        menu_rows=bloc_menu(menu), conf_rows=bloc_conformite(rapport),
        batch_taches=taches, batch_aff=aff, batch_duree=e(duree),
        courses=courses_html, budget_txt=budget, recettes=bloc_recettes(menu),
        recettes_detail=bloc_recettes_detail(menu, cm),
        cf_gm=gm, cf_corb=corb, cf_excl=excl,
        semaine_du=e(menu.get("semaine_du", "")))


# --- Gabarit (CSS + structure partagés) ---------------------------------------

CSS = (ICI / "gabarit_semaine.css")
TEMPLATE = (ICI / "gabarit_semaine.html")


def main():
    stdout_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("menu")
    ap.add_argument("--sortie")
    ap.add_argument("--no-run", action="store_true")
    ap.add_argument("--pdf", action="store_true",
                    help="produit aussi le PDF A4 portrait imprimable (Edge/Chrome headless)")
    args = ap.parse_args()

    menu_path = Path(args.menu)
    if not args.no_run:
        lancer(menu_path)
    menu = lire_json(menu_path)
    rapport = lire_json(str(menu_path).replace(".json", "_rapport_v2.json"))
    try:
        cf = lire_json(str(menu_path).replace(".json", "_crowdfarming.json"))
    except FileNotFoundError:            # pas d'adaptateur garde-manger : section vide
        cf = {}

    global TEMPLATE
    css = CSS.read_text(encoding="utf-8")
    TEMPLATE = TEMPLATE.read_text(encoding="utf-8")

    html_out = rendre(menu, rapport, cf, css)
    sortie = args.sortie or str(menu_path).replace(".json", "_livrables.html")
    Path(sortie).write_text(html_out, encoding="utf-8")
    print(f"Livrable écrit : {sortie}")
    if args.pdf:
        exporter_pdf(sortie, str(sortie).replace(".html", ".pdf"))
    print("Publier via l'outil Artifact pour le relire / partager.")


if __name__ == "__main__":
    main()
