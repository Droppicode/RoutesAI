import requests
import json

import os
API_KEY = os.environ.get("TOMTOM_API_KEY")
points = [
    {"lon": -47.22564, "lat": -22.86701},
    {"lon": -47.21222, "lat": -22.8728},
    {"lon": -47.19955, "lat": -22.86603},
    {"lon": -47.18688, "lat": -22.85892},
    {"lon": -47.17744, "lat": -22.84818}
]

locations = ":".join([f"{p['lat']},{p['lon']}" for p in points])
url = f"https://api.tomtom.com/routing/1/calculateRoute/{locations}/json"

params = {
    'key': API_KEY,
    'computeTravelTimeFor': 'all',
    'traffic': 'true',
    'routeRepresentation': 'summaryOnly'
}

print(f"Testando URL: {url}")
response = requests.get(url, params=params)

print(f"Status Code: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print("\nResposta JSON (resumo leg):")
    routes = data.get('routes', [])
    if routes:
        route = routes[0]
        legs = route.get('legs', [])
        for i, leg in enumerate(legs):
            ls = leg.get('summary', {})
            print(f" Leg {i+1}:")
            print(f"   Distância: {ls.get('lengthInMeters')}m")
            print(f"   Tempo normal: {ls.get('noTrafficTravelTimeInSeconds')}s")
            print(f"   Tempo histórico: {ls.get('historicTravelTimeInSeconds')}s")
            print(f"   Tempo live trânsito: {ls.get('liveTrafficIncidentsTravelTimeInSeconds')}s")
            print(f"   Tempo atraso: {ls.get('trafficDelayInSeconds')}s")
            print(f"   Tempo total (Travel Time): {ls.get('travelTimeInSeconds')}s")
else:
    print(f"Erro: {response.text}")
