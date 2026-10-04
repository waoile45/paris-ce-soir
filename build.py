"""Construit events.json a partir des sources ouvertes.

Lance une fois par jour par GitHub Actions. La meteo n'est PAS recuperee ici :
elle est appelee en direct par le navigateur, sinon elle serait perimee.

Sources (toutes sans cle d'API) :
  - Que Faire a Paris  : opendata.paris.fr, evenements parisiens
  - OpenAgenda Sevres  : agenda municipal 1007085
"""

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

UA = "paris-ce-soir/1.0 (guide perso; +https://github.com/waoile45/paris-ce-soir)"
HORIZON_JOURS = 21          # on ne garde pas ce qui est trop loin
PARIS_API = "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/que-faire-a-paris-/records"
SEVRES_API = "https://openagenda.com/agendas/1007085/events.json"

# Budgets declares, en euros, par profil
BUDGETS = {"solo": 20, "date": 40, "copains": 45}   # date = par personne (80 EUR a deux)


def get(url, params=None):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


def strip_html(s):
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"&nbsp;?", " ", s)
    s = re.sub(r"&amp;", "&", s)
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------- classement

DEHORS = ["balade", "promenade", "randonn", "jardin", "parc ", "terrasse", "rooftop",
          "peniche", "péniche", "quai", "plein air", "plein-air", "exterieur", "extérieur",
          "marche de", "marché de", "pique-nique", "berges", "canal", "velo", "vélo",
          "course a pied", "running", "street art", "parcours"]

DEDANS = ["musee", "musée", "exposition", "concert", "theatre", "théâtre", "cinema",
          "cinéma", "atelier", "conference", "conférence", "lecture", "spectacle",
          "projection", "bibliotheque", "bibliothèque", "danse", "club", "bar"]

HAUTE_ENERGIE = ["concert", "soiree", "soirée", "dj", "techno", "club", "festival",
                 "bal ", "danse", "live", "fete", "fête"]
BASSE_ENERGIE = ["exposition", "musee", "musée", "lecture", "conference", "conférence",
                 "visite", "projection", "atelier", "degustation", "dégustation"]

# Le sport collectif gratuit est le meilleur levier du profil solo : on le nomme a part.
SPORT = ["sport", "foot", "futsal", "basket", "volley", "running", "course a pied",
         "course à pied", "marche sportive", "multisport", "yoga", "escalade",
         "natation", "fitness", "gym", "randonn", "velo", "vélo", "skate", "boxe"]

# Un creneau ou debarquer seul est normal
SOLO_OK = SPORT + [
    "atelier", "rencontre", "langue", "conversation", "club de", "initiation",
    "cours", "benevol", "bénévol", "visite", "parcours", "jeu", "lecture",
    "conference", "conférence", "balade", "promenade", "street art", "repair",
    "repare", "répare", "entretien", "fabrique", "decouverte", "découverte",
    "debat", "débat", "permanence", "troc", "atelier-", "stage"]

COPAINS_OK = ["concert", "soiree", "soirée", "dj", "techno", "club", "festival", "live",
              "bal ", "quiz", "jeu", "biere", "bière", "danse", "guinguette", "karaoke",
              "karaoké", "blind test", "peniche", "péniche"]

DATE_OK = ["exposition", "expo", "musee", "musée", "concert", "cinema", "cinéma",
           "balade", "promenade", "degustation", "dégustation", "spectacle", "theatre",
           "théâtre", "projection", "jardin", "visite", "parcours", "street art",
           "cimetiere", "cimetière", "architecture", "patrimoine", "jazz", "classique"]

# Public qui n'est pas le sien (23 ans) : on ecarte franchement plutot que par hasard.
PUBLIC_HORS_CIBLE = ["bebe", "bébé", "creche", "crèche", "jeune public", "tout-petits",
                     "petite enfance", "0-3 ans", "3-6 ans", "6-10 ans", "enfants",
                     "senior", "retraite", "scolaire", "parentalite", "parentalité",
                     "famille", "maternelle", "periscolaire", "périscolaire"]

# Le jeu de donnees contient aussi des articles de la redaction, pas des evenements.
ARTICLE = [r"^o[uù] ", r"^que faire", r"^comment ", r"^pourquoi ", r"^quand ",
           r"^on a vu", r"^notre s[ée]lection", r"^top \d", r"^les .* [àa] faire",
           r"^c'est quoi", r"\?$"]


def est_article(titre):
    t = (titre or "").strip().lower()
    return any(re.search(p, t) for p in ARTICLE)


def any_in(mots, texte):
    return any(m in texte for m in mots)


def classe_meteo(texte):
    dehors, dedans = any_in(DEHORS, texte), any_in(DEDANS, texte)
    if dehors and not dedans:
        return "dehors"
    if dedans and not dehors:
        return "dedans"
    return "indifferent"


def classe_energie(texte):
    if any_in(HAUTE_ENERGIE, texte):
        return "haute"
    if any_in(BASSE_ENERGIE, texte):
        return "basse"
    return "moyenne"


def prix_depuis_texte(price_type, detail):
    """Retourne (gratuit, prix_max_estime, texte). None quand le prix est inconnu.

    price_type vaut gratuit, payant, ou "gratuit sous condition" (adhesion ou
    inscription sur place, souvent a prix libre) : cette derniere valeur compte
    comme gratuite, sinon on jette des ateliers qui ne coutent rien.
    """
    detail = strip_html(detail)
    pt = (price_type or "").lower()
    if pt == "gratuit":
        return True, 0.0, "gratuit"
    if pt.startswith("gratuit"):
        return True, 0.0, detail[:120] or "gratuit, sous condition"
    montants = [float(m.replace(",", ".")) for m in re.findall(r"(\d+[,.]?\d*)\s*€", detail)]
    if not montants:
        montants = [float(m.replace(",", ".")) for m in
                    re.findall(r"(\d+[,.]?\d*)\s*euros?", detail, re.I)]
    if montants:
        # Ce qui decide pour le budget, c'est la place la MOINS chere qu'on peut
        # acheter, pas le tarif prestige. On ignore les tarifs reduits a 0 (gratuit
        # pour un public particulier) qui feraient passer n'importe quoi.
        reels = [m for m in montants if m > 0] or montants
        return False, min(reels), detail[:120]
    return False, None, detail[:120] or "payant"


def profils_pour(texte, gratuit, prix_max, titre=""):
    """Un evenement peut servir plusieurs profils. Le budget et le public eliminent."""
    if est_article(titre) or any_in(PUBLIC_HORS_CIBLE, texte):
        return []

    out = []
    budget = 0.0 if gratuit else (prix_max if prix_max is not None else 0.0)
    inconnu = (not gratuit) and prix_max is None

    # Solo : budget serre (20 EUR). Un prix inconnu passe quand meme, on l'affiche tel quel.
    if any_in(SOLO_OK, texte) and (gratuit or inconnu or budget <= BUDGETS["solo"]):
        out.append("solo")
    if any_in(DATE_OK, texte) and (gratuit or inconnu or budget <= BUDGETS["date"]):
        out.append("date")
    if any_in(COPAINS_OK, texte) and (gratuit or inconnu or budget <= BUDGETS["copains"]):
        out.append("copains")
    return out


def tard(date_fin):
    """Se termine apres minuit : a eviter en semaine, travail le lendemain."""
    try:
        h = datetime.fromisoformat(date_fin.replace("Z", "+00:00")).astimezone()
        return h.hour >= 0 and h.hour < 6
    except Exception:
        return False


# ---------------------------------------------------------------- sources

def fetch_paris(limite=600):
    """Pagine l'open data de la Ville de Paris sur les evenements a venir."""
    horizon = (datetime.now(timezone.utc) + timedelta(days=HORIZON_JOURS)).strftime("%Y-%m-%d")
    champs = ("title,lead_text,description,date_start,date_end,date_description,"
              "address_name,address_street,address_zipcode,address_city,lat_lon,"
              "price_type,price_detail,access_type,url,cover_url,updated_at")
    out, offset = [], 0
    while offset < limite:
        page = get(PARIS_API, {
            "limit": 100,
            "offset": offset,
            "select": champs,
            "where": f'date_end>=now() and date_start<="{horizon}"',
            "order_by": "date_start",
        })
        res = page.get("results", [])
        if not res:
            break
        out.extend(res)
        offset += 100
        time.sleep(0.3)
    return out


def fetch_sevres():
    out, offset = [], 0
    while True:
        page = get(SEVRES_API, {"limit": 100, "offset": offset})
        evs = page.get("events", [])
        if not evs:
            break
        out.extend(evs)
        offset += 100
        if offset >= page.get("total", 0):
            break
        time.sleep(0.3)
    return out


# ---------------------------------------------------------------- normalisation

def norm_paris(e):
    titre_chapo = " ".join(filter(None, [e.get("title", ""), e.get("lead_text", "")])).lower()
    texte = (titre_chapo + " " + strip_html(e.get("description", ""))[:400]).lower()
    gratuit, prix_max, prix_txt = prix_depuis_texte(e.get("price_type"), e.get("price_detail"))
    profils = profils_pour(titre_chapo, gratuit, prix_max, e.get("title", ""))
    if not profils:
        return None
    ll = e.get("lat_lon") or {}
    return {
        "id": "paris-" + str(e.get("id")),
        "titre": e.get("title"),
        "resume": e.get("lead_text") or strip_html(e.get("description", ""))[:180],
        "debut": e.get("date_start"),
        "fin": e.get("date_end"),
        "quand": strip_html(e.get("date_description", ""))[:160],
        "lieu": e.get("address_name"),
        "adresse": " ".join(filter(None, [e.get("address_street"), e.get("address_zipcode"),
                                          e.get("address_city")])),
        "coords": [ll.get("lat"), ll.get("lon")] if ll.get("lat") else None,
        "gratuit": gratuit,
        "prixDes": prix_max,
        "prixTexte": prix_txt,
        "reservation": e.get("access_type") == "obligatoire",
        "meteo": classe_meteo(texte),
        "energie": classe_energie(texte),
        "profils": profils,
        "finitTard": tard(e.get("date_end", "")),
        "url": e.get("url"),
        "image": e.get("cover_url"),
        "source": "Que Faire à Paris",
        "zone": "paris",
    }


def norm_sevres(e):
    def fr(v):
        return (v or {}).get("fr", "") if isinstance(v, dict) else (v or "")

    titre = fr(e.get("title"))
    titre_chapo = (titre + " " + fr(e.get("description"))).lower()
    texte = (titre_chapo + " " + strip_html(fr(e.get("longDescription")))[:400]).lower()
    # L'export OpenAgenda n'expose pas de tarif structure : on ne devine pas.
    profils = profils_pour(titre_chapo, False, None, titre)
    if not profils:
        return None
    loc = e.get("location") or {}
    timings = e.get("timings") or []
    debut = timings[0].get("begin") if timings else e.get("firstTiming", {}).get("begin")
    fin = timings[-1].get("end") if timings else e.get("lastTiming", {}).get("end")
    return {
        "id": "sevres-" + str(e.get("uid")),
        "titre": titre,
        "resume": fr(e.get("description"))[:180],
        "debut": debut,
        "fin": fin,
        "quand": "",
        "lieu": loc.get("name"),
        "adresse": " ".join(filter(None, [loc.get("address"), loc.get("city")])),
        "coords": [loc.get("latitude"), loc.get("longitude")] if loc.get("latitude") else None,
        "gratuit": None,
        "prixMax": None,
        "prixTexte": "tarif non publié",
        "reservation": False,
        "meteo": classe_meteo(texte),
        "energie": classe_energie(texte),
        "profils": profils,
        "finitTard": False,
        "url": e.get("canonicalUrl"),
        "image": (e.get("image") or {}).get("base") if isinstance(e.get("image"), dict) else None,
        "source": "Ville de Sèvres",
        "zone": "sevres",
    }


def main():
    print("Que Faire a Paris ...", flush=True)
    paris = fetch_paris()
    print(f"  {len(paris)} bruts")

    print("OpenAgenda Sevres ...", flush=True)
    try:
        sevres = fetch_sevres()
    except Exception as exc:
        print(f"  echec ({exc}) - on continue sans Sevres")
        sevres = []
    print(f"  {len(sevres)} bruts")

    events = [x for x in (norm_paris(e) for e in paris) if x]
    events += [x for x in (norm_sevres(e) for e in sevres) if x]

    # Beaucoup de fiches sont des SERIES : date_start est le debut de la serie, parfois
    # deja passe, et seule date_end est a venir. Les afficher avec leur date de debut
    # serait faux. On les marque "en cours" et on les dedoublonne sur le seul titre,
    # puisque leurs occurrences exactes ne sont pas dans le jeu de donnees.
    aujourdhui = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for e in events:
        e["enCours"] = bool(e.get("debut")) and e["debut"][:10] < aujourdhui

    # Le meme evenement revient aussi sous plusieurs ids (seances, lieux multiples).
    vus, uniques = {}, []
    for e in events:
        cle = ((e.get("titre") or "").strip().lower(),
               "" if e["enCours"] else (e.get("debut") or "")[:10])
        garni = sum(1 for v in e.values() if v not in (None, "", []))
        if cle not in vus:
            vus[cle] = len(uniques)
            uniques.append((garni, e))
        elif garni > uniques[vus[cle]][0]:
            uniques[vus[cle]] = (garni, e)
    doublons = len(events) - len(uniques)
    events = [e for _, e in uniques]
    events.sort(key=lambda e: e.get("debut") or "")
    print(f"  {doublons} doublons ecartes")

    data = {
        "meta": {
            "genereLe": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "horizonJours": HORIZON_JOURS,
            "budgets": BUDGETS,
            "sources": [
                {"nom": "Que Faire à Paris", "url": "https://opendata.paris.fr"},
                {"nom": "Ville de Sèvres (OpenAgenda)", "url": "https://openagenda.com/sevres"},
                {"nom": "Open-Meteo", "url": "https://open-meteo.com", "note": "appelée en direct par le navigateur"},
            ],
        },
        "events": events,
    }
    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    par_profil = {}
    for e in events:
        for p in e["profils"]:
            par_profil[p] = par_profil.get(p, 0) + 1
    print(f"\n{len(events)} evenements retenus")
    print("  par profil :", par_profil)
    print("  meteo      :", {m: sum(1 for e in events if e['meteo'] == m)
                             for m in ('dehors', 'dedans', 'indifferent')})
    print("  gratuits   :", sum(1 for e in events if e.get("gratuit") is True))


if __name__ == "__main__":
    sys.exit(main())
