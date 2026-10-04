"""Resout les adresses des lieux cites, via Nominatim (1 req/s, User-Agent reel).

On n'ecrit jamais une adresse de memoire : soit Nominatim la confirme, soit le
lieu est marque a verifier a la main.
"""
import json, time, urllib.parse, urllib.request, io, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
UA = "paris-ce-soir/1.0 (guide perso; contact waoile45@gmail.com)"

REQUETES = [
    ("supersonic",   "Le Supersonic, rue Biscornet, Paris",        "copains/solo - concerts gratuits"),
    ("rexclub",      "Rex Club, boulevard Poissonniere, Paris",    "copains - techno"),
    ("java",         "La Java, rue du Faubourg du Temple, Paris",  "copains - techno moins cher"),
    ("virage",       "Le Virage, Paris",                           "copains - techno"),
    ("pena17",       "La Pena, Paris 17e",                         "copains - concert"),
    ("merlemoqueur", "Le Merle Moqueur, rue de la Butte aux Cailles, Paris", "date - fin de balade"),
    ("huchette",     "Caveau de la Huchette, rue de la Huchette, Paris",     "date - jazz"),
    ("ilvolo",       "Il Volo, Montparnasse, Paris",               "date - rooftop"),
    ("pucesstouen",  "Marche aux Puces de Saint-Ouen",             "solo/date - de nuit"),
    ("mairie13",     "Mairie du 13e arrondissement, Paris",        "date - vernissages"),
    ("butteauxcailles", "rue de la Butte aux Cailles, Paris",      "date - balade street art"),
]


def cherche(q):
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "jsonv2", "limit": 3, "addressdetails": 1})
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "fr"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


out = {}
print(f"{'cle':<17} {'resultat':<58} {'coords'}")
print("-" * 100)
for cle, q, usage in REQUETES:
    try:
        res = cherche(q)
    except Exception as exc:
        res = []
        print(f"{cle:<17} ERREUR {exc}")
    if res:
        r = res[0]
        a = r.get("address", {})
        nom = r.get("display_name", "")
        rue = " ".join(filter(None, [a.get("house_number"), a.get("road")]))
        cp = a.get("postcode", "")
        ville = a.get("city") or a.get("town") or a.get("municipality") or ""
        out[cle] = {
            "requete": q, "usage": usage,
            "nomTrouve": nom.split(",")[0],
            "adresse": ", ".join(filter(None, [rue, cp, ville])),
            "coords": [round(float(r["lat"]), 6), round(float(r["lon"]), 6)],
            "aVerifier": not rue,
        }
        flag = "  <-- pas de numero de rue" if not rue else ""
        print(f"{cle:<17} {nom[:56]:<58} {out[cle]['coords']}{flag}")
    else:
        out[cle] = {"requete": q, "usage": usage, "coords": None, "aVerifier": True}
        print(f"{cle:<17} {'INTROUVABLE':<58} -")
    time.sleep(1.2)

json.dump(out, open("lieux_geocodes.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"\n{sum(1 for v in out.values() if v['coords'])} / {len(out)} resolus")
print("a verifier a la main :", [k for k, v in out.items() if v["aVerifier"]])
