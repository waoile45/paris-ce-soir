/* Paris ce soir.
   events.json est cuit chaque nuit ; la météo est appelée en direct, parce qu'une
   prévision vieille de douze heures ne vaut rien au moment de sortir.
   Tout le texte passe par textContent, jamais par innerHTML. */

(function () {
  "use strict";

  var PARIS = { lat: 48.8566, lon: 2.3522 };
  var PAR_PAGE = 12;

  var PROFILS = [
    { id: "solo", nom: "Solo", sous: "rencontrer" },
    { id: "date", nom: "Date", sous: "à deux" },
    { id: "copains", nom: "Copains", sous: "en bande" }
  ];

  var JOURS = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"];

  var D = null;        // events.json
  var L = null;        // lieux.json
  var lieuxParId = {};
  var meteo = null;    // { verdict, tempMax, pluieMax }
  var profil = "solo";
  var affiches = PAR_PAGE;

  function el(tag, cls, txt) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt != null) n.textContent = txt;
    return n;
  }

  // ---------- météo ----------

  // Fenêtre de sortie : ce soir de 18h à minuit, ou bien maintenant s'il est plus tard.
  function fenetreCeSoir() {
    var now = new Date();
    var debut = new Date(now);
    if (now.getHours() < 18) debut.setHours(18, 0, 0, 0);
    var fin = new Date(now);
    fin.setHours(23, 59, 0, 0);
    return [debut, fin];
  }

  function chargerMeteo() {
    var url = "https://api.open-meteo.com/v1/forecast?latitude=" + PARIS.lat +
      "&longitude=" + PARIS.lon +
      "&hourly=temperature_2m,precipitation_probability" +
      "&forecast_days=2&timezone=Europe%2FParis";
    return fetch(url).then(function (r) { return r.json(); }).then(function (j) {
      var f = fenetreCeSoir();
      var temps = [], pluies = [];
      j.hourly.time.forEach(function (t, i) {
        var h = new Date(t);
        if (h >= f[0] && h <= f[1]) {
          temps.push(j.hourly.temperature_2m[i]);
          pluies.push(j.hourly.precipitation_probability[i]);
        }
      });
      if (!temps.length) return null;
      var tempMax = Math.max.apply(null, temps);
      var pluieMax = Math.max.apply(null, pluies);
      var verdict = "mitige";
      if (pluieMax >= 45) verdict = "pluie";
      else if (pluieMax < 20 && tempMax >= 15) verdict = "beau";
      return { verdict: verdict, tempMax: tempMax, pluieMax: pluieMax };
    }).catch(function () { return null; });
  }

  function rendreMeteo() {
    var box = document.getElementById("meteo");
    box.textContent = "";
    if (!meteo) {
      box.className = "meteo";
      box.appendChild(el("span", "meteo__chargement",
        "Météo indisponible — le tri dehors / dedans est neutralisé."));
      return;
    }
    box.className = "meteo meteo--" + meteo.verdict;
    box.appendChild(el("span", "meteo__temp", Math.round(meteo.tempMax) + "°"));

    var phrases = {
      beau: ["Belle soirée. ", "Les terrasses et les rooftops passent en premier."],
      pluie: ["Il va pleuvoir (" + meteo.pluieMax + " %). ", "Tout ce qui est dehors est repoussé en bas."],
      mitige: ["Temps incertain (" + meteo.pluieMax + " % de pluie). ", "Prévois une solution de repli."]
    };
    var p = phrases[meteo.verdict];
    var v = el("span", "meteo__verdict");
    var fort = el("strong", null, p[0]);
    v.appendChild(fort);
    v.appendChild(document.createTextNode(p[1]));
    box.appendChild(v);
  }

  // ---------- profils ----------

  function rendreProfils() {
    var nav = document.getElementById("profils");
    nav.textContent = "";
    PROFILS.forEach(function (p) {
      var b = el("button", "profil");
      b.type = "button";
      b.setAttribute("aria-pressed", p.id === profil ? "true" : "false");
      b.appendChild(el("span", null, p.nom));
      b.appendChild(el("small", null, p.sous));
      b.addEventListener("click", function () {
        profil = p.id;
        affiches = PAR_PAGE;
        if (window.history.replaceState) {
          window.history.replaceState(null, "", "#" + p.id);
        }
        rendreTout();
      });
      nav.appendChild(b);
    });
  }

  // ---------- ce soir : le rituel du jour ----------

  function rituelDuJour() {
    var jour = JOURS[new Date().getDay()];
    return (L.rituels || []).filter(function (r) {
      return (r.quand || "").toLowerCase().indexOf(jour) !== -1 &&
             (r.profils || []).indexOf(profil) !== -1;
    })[0] || null;
  }

  function rendreCeSoir() {
    var bloc = document.getElementById("bloc-ce-soir");
    var box = document.getElementById("ce-soir");
    box.textContent = "";
    var r = rituelDuJour();
    if (!r) { bloc.hidden = true; return; }
    bloc.hidden = false;

    var c = el("div", "rituel");
    c.appendChild(el("p", "rituel__quand", "Ton rendez-vous " + r.quand));
    c.appendChild(el("h3", "rituel__nom", r.nom));
    if (r.quoi) c.appendChild(el("p", "rituel__quoi", r.quoi));
    if (r.pourquoi) c.appendChild(el("p", "rituel__pourquoi", r.pourquoi));

    var lieu = r.lieu ? lieuxParId[r.lieu] : null;
    if (lieu && lieu.adresse) c.appendChild(el("p", "carte__adresse", lieu.adresse));
    if (r.note) c.appendChild(el("p", "carte__adresse", r.note));

    var ets = el("div", "etiquettes");
    ets.appendChild(etiquettePrix(r.budget === 0, r.budget));
    if (r.coutSocial) ets.appendChild(el("span", "et", "on y va seul : " + r.coutSocial));
    c.appendChild(ets);
    box.appendChild(c);
  }

  // ---------- étiquettes ----------

  function etiquettePrix(gratuit, montant) {
    if (gratuit) return el("span", "et et--gratuit", "gratuit");
    if (typeof montant === "number") return el("span", "et et--prix", "~" + montant + " €");
    return el("span", "et", "prix nc");
  }

  // ---------- parcours ----------

  function rendreParcours() {
    var bloc = document.getElementById("bloc-parcours");
    var box = document.getElementById("parcours");
    box.textContent = "";

    var liste = (L.parcours || []).filter(function (p) {
      return (p.profils || []).indexOf(profil) !== -1;
    });
    if (!liste.length) { bloc.hidden = true; return; }
    bloc.hidden = false;

    document.getElementById("sous-parcours").textContent =
      "Tes meilleures soirées étaient des enchaînements, pas des lieux isolés. Ceux-là sont reproductibles.";

    liste.sort(function (a, b) { return scoreMeteo(b.meteo) - scoreMeteo(a.meteo); });

    liste.forEach(function (p) {
      var c = el("article", "carte");
      if (meteo && meteo.verdict === "pluie" && p.meteo === "dehors") c.className += " ev--rabaisse";
      c.appendChild(el("h3", "carte__nom", p.nom));
      if (p.pourquoi) c.appendChild(el("p", "carte__pourquoi", p.pourquoi));

      var ol = el("ol", "etapes");
      (p.etapes || []).forEach(function (e) {
        var lieu = lieuxParId[e.lieu];
        var li = el("li", "etape");
        li.appendChild(el("div", "etape__nom", lieu ? lieu.nom : e.lieu));
        li.appendChild(el("div", "etape__quoi", e.quoi));
        if (lieu && lieu.adresse) li.appendChild(el("div", "etape__quoi", lieu.adresse));
        ol.appendChild(li);
      });
      c.appendChild(ol);

      var ets = el("div", "etiquettes");
      if (typeof p.budgetTotal === "number") {
        ets.appendChild(el("span", "et et--prix", "~" + p.budgetTotal + " € en tout"));
      }
      if (p.meteo === "dehors") ets.appendChild(el("span", "et et--dehors", "dehors"));
      if (meteo && meteo.verdict === "pluie" && p.meteo === "dehors") {
        ets.appendChild(el("span", "et et--alerte", "compromis par la pluie"));
      }
      c.appendChild(ets);
      box.appendChild(c);
    });
  }

  // ---------- lieux ----------

  function rendreLieux() {
    var bloc = document.getElementById("bloc-lieux");
    var box = document.getElementById("lieux");
    box.textContent = "";

    var liste = (L.lieux || []).filter(function (l) {
      return (l.profils || []).indexOf(profil) !== -1;
    });
    if (!liste.length) { bloc.hidden = true; return; }
    bloc.hidden = false;

    // Un lieu dont l'adresse n'est pas confirmee ne doit jamais passer devant un
    // lieu verifie, meme si la meteo lui est favorable.
    liste.sort(function (a, b) {
      if (!!a.aVerifier !== !!b.aVerifier) return a.aVerifier ? 1 : -1;
      return scoreMeteo(b.meteo) - scoreMeteo(a.meteo);
    });

    liste.forEach(function (l) {
      var c = el("article", "carte");
      if (meteo && meteo.verdict === "pluie" && l.meteo === "dehors") c.className += " ev--rabaisse";
      c.appendChild(el("h3", "carte__nom", l.nom));
      if (l.quoi) c.appendChild(el("p", "carte__quoi", l.quoi));
      if (l.pourquoi) c.appendChild(el("p", "carte__pourquoi", l.pourquoi));
      c.appendChild(el("p", "carte__adresse", l.adresse || "adresse à confirmer"));
      if (l.note) c.appendChild(el("p", "carte__adresse", l.note));

      var ets = el("div", "etiquettes");
      ets.appendChild(etiquettePrix(l.budget === 0, l.budget));
      if (l.quartier) ets.appendChild(el("span", "et", l.quartier));
      if (l.meteo === "dehors") ets.appendChild(el("span", "et et--dehors", "dehors"));
      if (l.aVerifier) ets.appendChild(el("span", "et et--alerte", "adresse non confirmée"));
      c.appendChild(ets);
      box.appendChild(c);
    });
  }

  // ---------- évènements ----------

  // Avec de la pluie, ce qui est dehors descend ; par beau temps, il remonte.
  function scoreMeteo(m) {
    if (!meteo || m !== "dehors") return 0;
    if (meteo.verdict === "pluie") return -1;
    if (meteo.verdict === "beau") return 1;
    return 0;
  }

  function evenementsFiltres() {
    var gratuitSeul = document.getElementById("f-gratuit").checked;
    var dehorsSeul = document.getElementById("f-dehors").checked;
    var presDeMoi = document.getElementById("f-sevres").checked;

    var liste = D.events.filter(function (e) {
      if ((e.profils || []).indexOf(profil) === -1) return false;
      if (gratuitSeul && e.gratuit !== true) return false;
      if (dehorsSeul && e.meteo !== "dehors") return false;
      if (presDeMoi && e.zone !== "sevres") return false;
      return true;
    });

    liste.sort(function (a, b) {
      var s = scoreMeteo(b.meteo) - scoreMeteo(a.meteo);
      if (s) return s;
      if (a.gratuit !== b.gratuit) return a.gratuit ? -1 : 1;
      return (a.debut || "").localeCompare(b.debut || "");
    });
    return liste;
  }

  function rendreEvenements() {
    var box = document.getElementById("events");
    var vide = document.getElementById("vide");
    var plus = document.getElementById("plus");
    box.textContent = "";

    var liste = evenementsFiltres();
    document.getElementById("compte").textContent =
      liste.length + (liste.length > 1 ? " idées" : " idée");

    vide.hidden = liste.length > 0;
    liste.slice(0, affiches).forEach(function (e) {
      box.appendChild(carteEvenement(e));
    });

    plus.hidden = liste.length <= affiches;
    plus.textContent = "Voir plus (" + Math.max(0, liste.length - affiches) + ")";
  }

  function carteEvenement(e) {
    var a = el("a", "ev");
    a.href = e.url || "#";
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    if (meteo && meteo.verdict === "pluie" && e.meteo === "dehors") a.className += " ev--rabaisse";

    a.appendChild(el("h3", "ev__titre", e.titre));
    if (e.resume) a.appendChild(el("p", "ev__resume", e.resume));

    var bas = el("div", "ev__bas");
    bas.appendChild(etiquettePrix(e.gratuit === true, e.prixDes));
    if (e.meteo === "dehors") bas.appendChild(el("span", "et et--dehors", "dehors"));
    if (e.zone === "sevres") bas.appendChild(el("span", "et", "Sèvres"));
    if (e.enCours) bas.appendChild(el("span", "et", "en cours"));
    if (e.reservation) bas.appendChild(el("span", "et", "réservation"));
    if (e.lieu) bas.appendChild(el("span", "ev__lieu", e.lieu));
    a.appendChild(bas);
    return a;
  }

  // ---------- assemblage ----------

  function rendreTout() {
    document.querySelectorAll(".profil").forEach(function (b, i) {
      b.setAttribute("aria-pressed", PROFILS[i].id === profil ? "true" : "false");
    });
    rendreCeSoir();
    rendreParcours();
    rendreLieux();
    rendreEvenements();
  }

  function rendrePied() {
    var maj = D.meta && D.meta.genereLe ? new Date(D.meta.genereLe) : null;
    document.getElementById("pied-maj").textContent = maj
      ? "Évènements mis à jour le " + maj.toLocaleDateString("fr-FR", {
          day: "numeric", month: "long", hour: "2-digit", minute: "2-digit"
        })
      : "";
    var noms = (D.meta.sources || []).map(function (s) { return s.nom; }).join(" · ");
    document.getElementById("pied-sources").textContent = "Sources : " + noms;
  }

  function dateDuJour() {
    document.getElementById("date-jour").textContent =
      new Date().toLocaleDateString("fr-FR", {
        weekday: "long", day: "numeric", month: "long"
      });
  }

  // ---------- démarrage ----------

  dateDuJour();

  var hash = (window.location.hash || "").replace("#", "");
  if (PROFILS.some(function (p) { return p.id === hash; })) profil = hash;

  Promise.all([
    fetch("events.json").then(function (r) { return r.json(); }),
    fetch("lieux.json").then(function (r) { return r.json(); })
  ]).then(function (res) {
    D = res[0];
    L = res[1];
    (L.lieux || []).forEach(function (l) { lieuxParId[l.id] = l; });

    rendreProfils();
    rendrePied();
    rendreTout();                       // on affiche sans attendre la météo

    document.getElementById("filtres").addEventListener("change", function () {
      affiches = PAR_PAGE;
      rendreEvenements();
    });
    document.getElementById("plus").addEventListener("click", function () {
      affiches += PAR_PAGE;
      rendreEvenements();
    });

    return chargerMeteo();
  }).then(function (m) {
    meteo = m;
    rendreMeteo();
    rendreTout();                       // puis on retrie une fois qu'on la connaît
  }).catch(function (err) {
    var box = document.getElementById("events");
    box.textContent = "";
    box.appendChild(el("p", "vide",
      "Les données n'ont pas pu être chargées. Sers le dossier en http, pas en file://."));
    if (window.console) console.error(err);
  });
})();
