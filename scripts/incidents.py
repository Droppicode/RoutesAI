import requests
import json

import os
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

API_KEY = os.environ.get("TOMTOM_API_KEY")
# Bounding box ao redor da grande São Paulo (sempre tem acidentes/obras)
# formato: minLon,minLat,maxLon,maxLat
bbox = "-46.8,-23.7,-46.4,-23.4"
url = f"https://api.tomtom.com/traffic/services/5/incidentDetails?key={API_KEY}&bbox={bbox}&fields={{incidents{{geometry{{coordinates}},properties{{delay,events{{description}},magnitudeOfDelay}}}}}}"

print("Buscando incidentes ativos em São Paulo na TomTom...")
response = requests.get(url)

if response.status_code == 200:
    data = response.json()
    incidents = data.get('incidents', [])
    print(f"Total de incidentes encontrados na região: {len(incidents)}")
    
    # Vamos procurar um incidente que tenha um atraso (delay) maior que zero
    for inc in incidents:
        props = inc.get('properties', {})
        delay = props.get('delay')
        delay = delay if delay is not None else 0
        
        # Filtra por incidentes com atraso > 120 segundos (2 minutos)
        if delay > 120:
            events = props.get('events', [])
            desc = events[0]['description'] if events else "Desconhecido"
            
            coords = inc.get('geometry', {}).get('coordinates', [])
            if coords:
                # Pegar o primeiro e o último ponto do incidente
                start = coords[0]
                end = coords[-1]
                
                print("\nINCIDENTE ENCONTRADO!")
                print(f"Tipo: {desc}")
                print(f"Atraso reportado: {delay} segundos")
                print(f"Latitude/Longitude Origem: {start[1]}, {start[0]}")
                print(f"Latitude/Longitude Destino: {end[1]}, {end[0]}")
                
                # MÁGICA: Em vez de mandar só a origem e destino, vamos mandar TODOS os pontos da rua!
                # É exatamente isso que fazemos no collect_traffic.py com os shapes do ônibus.
                # Limite de waypoints da TomTom é 150, então pegamos até 149.
                waypoints = ":".join([f"{c[1]},{c[0]}" for c in coords[:149]])
                
                # Vamos injetar essas coordenadas no teste da API de Rotas
                route_url = f"https://api.tomtom.com/routing/1/calculateRoute/{waypoints}/json"
                route_params = {
                    'key': API_KEY,
                    'computeTravelTimeFor': 'all',
                    'traffic': 'true',
                    'routeRepresentation': 'polyline'
                }
                print(f"\nTestando Rota através desse incidente...")
                r_resp = requests.get(route_url, params=route_params)
                if r_resp.status_code == 200:
                    r_data = r_resp.json()
                    route = r_data['routes'][0]
                    summary = route['summary']
                    
                    # Pegando os pontos da rota desviada (juntando todas as "legs" entre os waypoints)
                    route_pts = []
                    for leg in route['legs']:
                        route_pts.extend(leg['points'])
                    
                    print(f"  Tempo Normal: {summary.get('noTrafficTravelTimeInSeconds')}s")
                    print(f"  Tempo com Trânsito (Total): {summary.get('liveTrafficIncidentsTravelTimeInSeconds')}s")
                    print(f"  Atraso do Incidente (Traffic Delay): {summary.get('trafficDelayInSeconds')}s")
                    
                    print(f"\n--- PROVA DO DESVIO ---")
                    print(f"O Incidente reportado tinha {len(coords)} pontos de geometria na avenida principal.")
                    print(f"A Rota traçada pela TomTom tem {len(route_pts)} pontos de geometria.")
                    
                    # Checando se a rota foge da via do acidente
                    # Pegamos o ponto central do acidente
                    meio_acidente = coords[len(coords)//2]
                    
                    # Procuramos se esse ponto existe na rota traçada
                    passou_pelo_meio = any(
                        abs(p['latitude'] - meio_acidente[1]) < 0.0001 and 
                        abs(p['longitude'] - meio_acidente[0]) < 0.0001 
                        for p in route_pts
                    )
                    
                    if passou_pelo_meio:
                        print("Surpreendente! A rota passou pelo meio do acidente, talvez seja outra coisa.")
                    else:
                        print("Confirmado! A rota passou longe do centro do acidente, contornando-o por outras ruas.")
                        
                    # --- GERAÇÃO DO MAPA VISUAL ---
                    html_content = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Mapa do Incidente vs Rota TomTom</title>
                        <meta charset="utf-8" />
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
                        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
                        <style>
                            #map {{ height: 100vh; width: 100%; }}
                            body {{ margin: 0; padding: 0; }}
                        </style>
                    </head>
                    <body>
                        <div id="map"></div>
                        <script>
                            var map = L.map('map').setView([{start[1]}, {start[0]}], 15);
                            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                                maxZoom: 19,
                                attribution: '© OpenStreetMap'
                            }}).addTo(map);

                            // Incidente (Vermelho)
                            var incidentCoords = { [[c[1], c[0]] for c in coords] };
                            var incidentLine = L.polyline(incidentCoords, {{color: 'red', weight: 8, opacity: 0.7}}).addTo(map);
                            incidentLine.bindPopup('<b>Incidente Reportado</b><br>Atraso: {delay}s');

                            // Rota TomTom (Azul tracejado)
                            var routeCoords = { [[p['latitude'], p['longitude']] for p in route_pts] };
                            var routeLine = L.polyline(routeCoords, {{color: 'blue', weight: 5, dashArray: '10, 10'}}).addTo(map);
                            routeLine.bindPopup('<b>Rota TomTom (Desvio)</b><br>Tempo Normal: {summary.get('noTrafficTravelTimeInSeconds')}s<br>Com Trânsito: {summary.get('liveTrafficIncidentsTravelTimeInSeconds')}s');

                            map.fitBounds(routeLine.getBounds());
                        </script>
                    </body>
                    </html>
                    """
                    with open("outputs/mapa_incidente.html", "w", encoding="utf-8") as f:
                        f.write(html_content)
                    print("\n[+] Arquivo 'outputs/mapa_incidente.html' gerado com sucesso! Abra no navegador para visualizar o mapa.")
                break
else:
    print(f"Erro ao buscar incidentes: {response.text}")

