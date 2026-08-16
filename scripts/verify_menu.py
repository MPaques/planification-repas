#!/usr/bin/env python3
"""verify_menu.py — vérifieur déterministe d'un menu hebdomadaire.

Usage :
    python verify_menu.py menu.json [--rapport rapport.json]

Contrôle un menu au schéma pivot (references/schema-pivot.md) contre les règles
encodables du référentiel. Indépendant du générateur (fiche de cadrage, Q4) :
ce script ne propose rien, il compte et il tranche.

Code de sortie : 0 = conforme ou dérogations souples ; 1 = violation(s) dure(s).

SEUILS DÉRIVÉS DU RÉFÉRENTIEL v0.3 — maintenir en phase par avenant, ne pas
éditer à la volée. Non couvert en v1 (dit explicitement dans le rapport) :
PLA-1 (CO2e, attend Agribalyse), PRX-1 (prix, attend les adaptateurs),
PLA-3 (saisonnalité : vérification humaine en phase 2-3 via saisonnalite-fr.md),
SAN-5/6/7/9/10/12 (nécessitent des données nutritionnelles fines — v2 avec OFF).
"""

import argparse
import json
import sys

# --- Seuils (référentiel v0.3) -------------------------------------------------
S = {
    "SAN1_plancher_dur": 4,      # occurrences légumineuses / sem (hors rampe)
    "SAN1_cible": 6,
    "SAN1_rampe_min": 3,         # semaines 1-4 : plancher suspendu, cible 3-4
    "SAN2_rouge_souple_g": 100,  # par personne / sem
    "SAN2_rouge_dur_g": 500,     # backstop PNNS
    "SAN2_charcuterie_occ": 1,
    "SAN3_poisson_occ": 2,
    "SAN3_gras_occ": 1,
    "SAN4_fl_par_jour": 3.5,     # prorata du périmètre planifié (approximation v1)
    "SAN8_nova4_occ": 1,
    "TPS1_batch_min": 180,
    "TPS2_actif_min": 20,
    "TPS3_part_batch": 0.70,
    "GOU1_bases_min": 3,
}

DLC_JOURS = {  # miroir de references/dlc-batch.md
    "riz_cuit": 2, "cereales_cuites": 3, "legumineuses_cuites": 3,
    "viandes_cuites": 3, "poisson_cuit": 2, "oeufs_durs": 3,
    "soupes_sauces": 3, "legumes_rotis": 3, "crudites": 2,
    "sauces_crues": 2, "lacto_fermente": 999, "congele": 999,
}

JOUR_IDX = {"samedi": 0, "dimanche": 1, "lundi": 2, "mardi": 3, "mercredi": 4,
            "jeudi": 5, "vendredi": 6, "samedi+1": 7, "dimanche+1": 8}

COUVERTURE = {"diner": 7, "dejeuner": 2, "petit_dejeuner": 7}  # PAR-2 ; collations libres


def regle(regles, rid, statut, valeur, seuil, detail=""):
    regles.append({"id": rid, "statut": statut, "valeur": valeur, "seuil": seuil, "detail": detail})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("menu")
    ap.add_argument("--rapport", default=None)
    args = ap.parse_args()

    with open(args.menu, encoding="utf-8") as f:
        menu = json.load(f)

    recettes = menu.get("recettes", {})
    repas = menu.get("repas", [])
    rampe = menu.get("rampe_semaine")
    regles, derogations = [], []

    def tags(rid_):
        return recettes.get(rid_, {}).get("tags", {})

    # --- Couverture PAR-2 ---
    compte = {}
    for r in repas:
        compte[r["moment"]] = compte.get(r["moment"], 0) + 1
    ecarts = {m: (compte.get(m, 0), att) for m, att in COUVERTURE.items() if compte.get(m, 0) != att}
    regle(regles, "PAR-2", "viole_souple" if ecarts else "conforme",
          {m: compte.get(m, 0) for m in COUVERTURE}, COUVERTURE,
          f"écarts: {ecarts}" if ecarts else "couverture nominale")

    # --- SAN-1 légumineuses ---
    leg = sum(1 for r in repas if tags(r["recette_id"]).get("legumineuse"))
    if rampe in (1, 2, 3, 4):
        ok = leg >= S["SAN1_rampe_min"]
        regle(regles, "SAN-1", "conforme" if ok else "viole_souple", leg,
              f"rampe s{rampe}: >= {S['SAN1_rampe_min']} (plancher dur suspendu)")
    else:
        if leg < S["SAN1_plancher_dur"]:
            regle(regles, "SAN-1", "viole_dur", leg, f">= {S['SAN1_plancher_dur']} (plancher dur)")
        elif leg < S["SAN1_cible"]:
            regle(regles, "SAN-1", "viole_souple", leg, f"cible >= {S['SAN1_cible']}")
        else:
            regle(regles, "SAN-1", "conforme", leg, f"cible >= {S['SAN1_cible']}")

    # --- SAN-2 viande rouge / charcuterie / nitrites (PAR-6) ---
    rouge = sum(tags(r["recette_id"]).get("viande_rouge_g", 0) for r in repas)
    charc = sum(1 for r in repas if tags(r["recette_id"]).get("charcuterie"))
    nitrites = [r["recette_id"] for r in repas if tags(r["recette_id"]).get("nitrites")]
    if rouge > S["SAN2_rouge_dur_g"]:
        regle(regles, "SAN-2", "viole_dur", rouge, f"<= {S['SAN2_rouge_dur_g']} g (backstop PNNS)")
    elif rouge > S["SAN2_rouge_souple_g"]:
        regle(regles, "SAN-2", "viole_souple", rouge, f"<= {S['SAN2_rouge_souple_g']} g (EAT-Lancet)")
    else:
        regle(regles, "SAN-2", "conforme", rouge, f"<= {S['SAN2_rouge_souple_g']} g")
    if charc > S["SAN2_charcuterie_occ"]:
        regle(regles, "SAN-2b", "viole_souple", charc, f"<= {S['SAN2_charcuterie_occ']} occurrence")
    if nitrites:
        regle(regles, "PAR-6", "viole_dur", nitrites, "0 charcuterie nitritée (E249-E252)")

    # --- SAN-3 poisson ---
    poisson = sum(1 for r in repas if tags(r["recette_id"]).get("poisson"))
    gras = sum(1 for r in repas if tags(r["recette_id"]).get("poisson_gras"))
    ok = poisson >= S["SAN3_poisson_occ"] and gras >= S["SAN3_gras_occ"]
    regle(regles, "SAN-3", "conforme" if ok else "viole_souple", {"poisson": poisson, "gras": gras},
          f">= {S['SAN3_poisson_occ']} dont {S['SAN3_gras_occ']} gras")

    # --- SAN-4 fruits & légumes (approximation prorata) ---
    fl = sum(tags(r["recette_id"]).get("portions_fl", 0) for r in repas) / 7.0
    regle(regles, "SAN-4", "conforme" if fl >= S["SAN4_fl_par_jour"] else "viole_souple",
          round(fl, 1), f">= {S['SAN4_fl_par_jour']}/j (prorata périmètre, approximation v1)")

    # --- SAN-8 NOVA 4 ---
    nova = sum(1 for r in repas if tags(r["recette_id"]).get("nova4"))
    regle(regles, "SAN-8", "conforme" if nova <= S["SAN8_nova4_occ"] else "viole_souple",
          nova, f"<= {S['SAN8_nova4_occ']}")

    # --- GOU-1 variété (dîners) ---
    diners = [r["recette_id"] for r in repas if r["moment"] == "diner"]
    doublons = sorted({d for d in diners if diners.count(d) > 1})
    bases = {tags(d).get("base") for d in diners if tags(d).get("base")}
    if doublons:
        regle(regles, "GOU-1", "viole_souple", doublons, "aucun plat principal répété")
    regle(regles, "GOU-1b", "conforme" if len(bases) >= S["GOU1_bases_min"] else "viole_souple",
          sorted(bases), f">= {S['GOU1_bases_min']} bases distinctes")

    # --- TPS ---
    batch = menu.get("plan_batch", {})
    duree = batch.get("duree_totale_min", 0)
    regle(regles, "TPS-1", "conforme" if duree <= S["TPS1_batch_min"] else "viole_dur",
          duree, f"<= {S['TPS1_batch_min']} min")
    trop_longs = [(r["jour"], r.get("actif_min_assemblage")) for r in repas
                  if r["moment"] == "diner" and (r.get("actif_min_assemblage") or 0) > S["TPS2_actif_min"]]
    regle(regles, "TPS-2", "viole_dur" if trop_longs else "conforme",
          trop_longs or "tous <= seuil", f"<= {S['TPS2_actif_min']} min actives / dîner")
    jours_couverts = set()
    for a in batch.get("affectations", []):
        jours_couverts.update(a.get("consomme_le", []))
    part = len({r["jour"] for r in repas if r["moment"] == "diner"} & jours_couverts) / 7.0
    regle(regles, "TPS-3", "conforme" if part >= S["TPS3_part_batch"] else "viole_souple",
          round(part, 2), f">= {S['TPS3_part_batch']}")

    # --- SEC-1 DLC ---
    for a in batch.get("affectations", []):
        dlc = DLC_JOURS.get(a.get("famille_dlc"), None)
        if dlc is None:
            regle(regles, "SEC-1", "viole_dur", a.get("famille_dlc"), "famille DLC inconnue", a["composant"])
            continue
        p = JOUR_IDX.get(a.get("produit_le"))
        for j in a.get("consomme_le", []):
            c = JOUR_IDX.get(j)
            if p is None or c is None:
                regle(regles, "SEC-1", "viole_dur", (a.get("produit_le"), j), "jour illisible", a["composant"])
            elif c - p > dlc:
                regle(regles, "SEC-1", "viole_dur", f"{a['composant']}: {a['produit_le']} -> {j} (J+{c-p})",
                      f"<= J+{dlc} ({a['famille_dlc']})", "congeler le jour même ou réaffecter")
    if not any(r["id"] == "SEC-1" for r in regles):
        regle(regles, "SEC-1", "conforme", "toutes affectations dans les DLC", "voir dlc-batch.md")

    # --- Non vérifié en v1 ---
    for rid, note in [("PLA-1", "CO2e — attend Agribalyse (v2)"),
                      ("PRX-1", "prix — attend les adaptateurs plateformes (v2)"),
                      ("PLA-3", "saisonnalité — vérification humaine phase 2-3 (saisonnalite-fr.md)"),
                      ("SAN-5/6/7/9/10/12", "données nutritionnelles fines — v2 avec Open Food Facts")]:
        regle(regles, rid, "non_verifie_v1", None, None, note)

    # --- Synthèse ---
    dures = [r for r in regles if r["statut"] == "viole_dur"]
    souples = [r for r in regles if r["statut"] == "viole_souple"]
    statut = "violations_dures" if dures else ("derogations" if souples else "conforme")
    rapport = {
        "statut_global": statut,
        "regles": regles,
        "derogations": [{"regle": r["id"], "raison": r["detail"] or str(r["valeur"])} for r in souples],
        "compteurs": {"legumineuses_occ": leg, "poisson_occ": poisson, "poisson_gras_occ": gras,
                      "viande_rouge_g_pp": rouge, "nova4_occ": nova, "part_batch": round(part, 2)},
    }

    out = args.rapport or args.menu.replace(".json", "_rapport.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2)

    print(f"Statut global : {statut.upper()}")
    for r in regles:
        if r["statut"] != "conforme":
            print(f"  [{r['statut']}] {r['id']} — valeur {r['valeur']} (seuil {r['seuil']}) {r['detail']}")
    print(f"Rapport : {out}")
    sys.exit(1 if dures else 0)


if __name__ == "__main__":
    main()
