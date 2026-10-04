# Paris ce soir

Un guide personnel de sorties à Paris, pour répondre vite à une seule question :
**qu'est-ce que je fais ce soir ?** Il tient compte de qui m'accompagne, du temps
qu'il fait, de mon budget, et du fait que j'habite Sèvres.

Trois profils :

| Profil | Ce qu'il cherche |
| --- | --- |
| **Solo** | Des créneaux où débarquer seul est normal. Budget serré, moins de 20 €. |
| **Date** | De quoi se parler : calme, un plan B à côté, jusqu'à ~40 € par personne. |
| **Copains** | Ce qui encaisse une bande sans réserver trois semaines avant. Entrée + deux bières. |

## Les trois jeux de données

Ils ne se mettent pas à jour au même rythme, d'où la séparation.

| Fichier | Contenu | Mise à jour |
| --- | --- | --- |
| `events.json` | Les évènements datés | **Automatique**, chaque nuit par GitHub Actions |
| `lieux.json` | Les adresses fixes, les rituels hebdomadaires, les enchaînements | À la main |
| — | La météo | **En direct**, dans le navigateur |

La météo n'est volontairement pas mise en cache dans `events.json` : une prévision
calculée à 4 h du matin ne vaut rien au moment de décider de sortir. Elle est donc
appelée par le navigateur à chaque ouverture.

## Sources

Toutes sans clé d'API, toutes avec `Access-Control-Allow-Origin: *` :

- **[Que Faire à Paris](https://opendata.paris.fr)** — open data de la Ville de Paris
- **[OpenAgenda Sèvres](https://openagenda.com/sevres)** — agenda municipal (`1007085`)
- **[Open-Meteo](https://open-meteo.com)** — prévisions, appelées en direct

Ce qui **ne marche pas**, et pourquoi, pour éviter d'y revenir :

- *Instagram* : l'API officielle ne donne accès qu'aux comptes qu'on administre. Le
  reste est derrière un mur de login. Les lieux qui n'y publient que là sont saisis à
  la main, avec un renvoi vers leur compte.
- *Shotgun* : renvoie 429 systématiquement (anti-bot).
- *Dice* : `robots.txt` interdit `/api/`.
- *Sortiraparis* : aucun flux RSS.

## Lancer en local

`fetch()` ne lit pas les fichiers en `file://`, donc il faut servir le dossier :

```powershell
python -m http.server 8000
```

Puis <http://localhost:8000>.

Pour régénérer les évènements à la main :

```powershell
python build.py
```

## Comment `build.py` filtre

Le jeu de données parisien mélange de vrais évènements, des articles de la rédaction
et beaucoup de contenu petite enfance ou seniors. Le script :

1. écarte les **articles** (titres en question, « Où faire… », « Notre sélection… ») ;
2. écarte le **public hors cible** (crèche, jeune public, seniors, scolaire) ;
3. lit le prix. `price_type` vaut `gratuit`, `payant` ou **`gratuit sous condition`** —
   cette troisième valeur compte comme gratuite, sinon on jette des ateliers qui ne
   coûtent rien ;
4. retient le prix **minimum** et non le maximum : pour un concert à
   « Prestige 60 € / Catégorie 1 40 € », ce qui décide c'est la place la moins chère ;
5. classe par profil sur le **titre et le chapô seulement**. Chercher les mots-clés
   dans la description entière suffisait à taguer « Le tri des déchets » comme idée
   de date ;
6. marque `enCours` les séries dont la date de début est passée mais qui courent
   encore — les afficher à leur date de début serait faux ;
7. dédoublonne sur titre + jour.

Si tu changes les listes de mots-clés, **relis les rejets, pas seulement les
captures** : c'est là que se cachent les erreurs. Les quatre défauts ci-dessus ont
tous été trouvés comme ça.

## Ajouter un lieu

Dans `lieux.json`, un objet dans `lieux` :

```json
{
  "id": "monlieu",
  "nom": "Le Lieu",
  "quoi": "Une ligne sur ce que c'est.",
  "pourquoi": "Une ligne sur pourquoi il est dans la liste.",
  "adresse": "12 rue Machin, 75011 Paris",
  "quartier": "Oberkampf",
  "coords": [48.8, 2.37],
  "profils": ["copains"],
  "budget": 15,
  "meteo": "dedans",
  "energie": "haute",
  "coutSocial": "moyen",
  "aVerifier": false
}
```

- `meteo` vaut `dehors`, `dedans` ou `indifferent`. Ce qui est `dehors` descend quand
  il pleut et remonte quand il fait beau.
- `coutSocial` (`facile` / `moyen` / `difficile`) dit si on peut y arriver sans
  connaître personne. C'est le champ qui porte tout le profil solo.
- `aVerifier: true` quand l'adresse n'est pas confirmée : le lieu reste affiché mais
  passe en dernier, jamais devant un lieu vérifié.

**Les coordonnées ne s'écrivent pas de mémoire.** `geocode_lieux.py` les résout via
Nominatim, avec `viewbox` + `bounded=1` pour contraindre à l'Île-de-France — sans
cette contrainte, « La Peña du 17e » s'était résolue aux Philippines.

## Et après

L'idée d'une application « Matching Paris » (swipe d'activités selon le profil,
l'heure et le prix) réutiliserait ces mêmes fichiers tels quels : les champs
`profils`, `budget`, `meteo`, `energie`, `coutSocial` et `duree` ont été posés pour ça.

## Licence

MIT, voir `LICENSE`. Données évènementielles : Ville de Paris et OpenAgenda, sous
leurs licences respectives.
