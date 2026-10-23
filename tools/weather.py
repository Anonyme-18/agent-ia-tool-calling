import requests
from .registry import tool, ToolError
from .common import env, check, TIMEOUT


def _fmt_current(d):
    c, loc = d["current"], d["location"]
    return {"lieu": f"{loc['name']}, {loc['country']}", "heure_locale": loc["localtime"],
            "temperature_c": c["temp_c"], "ressenti_c": c["feelslike_c"], "conditions": c["condition"]["text"],
            "humidite_pct": c["humidity"], "vent_kmh": c["wind_kph"]}


@tool("meteo", "Météo actuelle et prévisions (jusqu'à 3 jours) pour une ou plusieurs villes (WeatherAPI). Utiliser plusieurs villes pour comparer.",
      {"type": "object", "properties": {
          "villes": {"type": "array", "items": {"type": "string"}, "description": "Liste de villes, ex. ['Lomé']"},
          "jours_prevision": {"type": "integer", "description": "0 = actuel seulement, 1 à 3 = prévisions", "default": 0}},
       "required": ["villes"]})
def meteo(villes, jours_prevision=0, _context=None):
    if not villes:
        raise ToolError("Aucune ville indiquée.")
    key, out = env("WEATHER_API_KEY"), []
    days = max(0, min(int(jours_prevision), 3))
    for v in villes[:5]:
        url = "https://api.weatherapi.com/v1/" + ("forecast.json" if days else "current.json")
        params = {"key": key, "q": v, "lang": "fr"}
        if days:
            params["days"] = days
        r = requests.get(url, params=params, timeout=TIMEOUT)
        if r.status_code == 400:
            out.append({"ville": v, "erreur": "Ville introuvable."})
            continue
        d = check(r)
        item = _fmt_current(d)
        if days:
            item["previsions"] = [{"date": f["date"], "min_c": f["day"]["mintemp_c"], "max_c": f["day"]["maxtemp_c"],
                                   "conditions": f["day"]["condition"]["text"],
                                   "pluie_pct": f["day"].get("daily_chance_of_rain")} for f in d["forecast"]["forecastday"]]
        out.append(item)
    return {"meteo": out}
