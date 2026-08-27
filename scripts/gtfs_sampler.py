import csv
import os
import math

# O __file__ agora é scripts/gtfs_sampler.py, então a raiz é um nível acima
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
GTFS_DIR = os.path.join(PROJECT_ROOT, 'artesp_gtfs')
ROUTES_FILE = os.path.join(GTFS_DIR, 'routes.txt')
TRIPS_FILE = os.path.join(GTFS_DIR, 'trips.txt')
SHAPES_FILE = os.path.join(GTFS_DIR, 'shapes.txt')
STOP_TIMES_FILE = os.path.join(GTFS_DIR, 'stop_times.txt')
STOPS_FILE = os.path.join(GTFS_DIR, 'stops.txt')

def haversine(lat1, lon1, lat2, lon2):
    """Calcula a distância em metros entre duas coordenadas."""
    R = 6371000 # Raio da Terra em metros
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

def calculate_bearing(lat1, lon1, lat2, lon2):
    """Calcula o azimute (bearing) entre duas coordenadas."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)
    
    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - \
        math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
        
    theta = math.atan2(y, x)
    return (math.degrees(theta) + 360) % 360

def shift_point_right(lat, lon, bearing, distance_m=10):
    """Desloca a coordenada 'distance_m' metros para a direita ortogonalmente ao azimute."""
    R = 6371000 # Raio da Terra em metros
    
    right_bearing = (bearing + 90) % 360
    
    brng = math.radians(right_bearing)
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    
    new_lat = math.asin(math.sin(lat_rad)*math.cos(distance_m/R) + 
                        math.cos(lat_rad)*math.sin(distance_m/R)*math.cos(brng))
    
    new_lon = lon_rad + math.atan2(math.sin(brng)*math.sin(distance_m/R)*math.cos(lat_rad), 
                                   math.cos(distance_m/R) - math.sin(lat_rad)*math.sin(new_lat))
                                   
    return math.degrees(new_lat), math.degrees(new_lon)

def get_shapes_for_lines(target_lines=["746", "5501", "953", "016", "288"]):
    """Obtém um dicionário mapeando cada linha (short_name) para seus shape_ids e trip_ids."""
    route_ids = {}
    
    if not os.path.exists(ROUTES_FILE):
        print(f"ALERTA: Arquivo {ROUTES_FILE} não encontrado!")
        return {}, {}

    with open(ROUTES_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            short_name = row.get('route_short_name')
            if short_name in target_lines:
                route_ids[row['route_id']] = short_name

    shapes_by_line = {line: {} for line in target_lines} 
    trips_by_line = {line: {} for line in target_lines}
    
    with open(TRIPS_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            r_id = row.get('route_id')
            if r_id in route_ids:
                short_name = route_ids[r_id]
                direction = row.get('direction_id', '0')
                shape_id = row.get('shape_id')
                trip_id = row.get('trip_id')
                
                if shape_id and direction not in shapes_by_line[short_name]:
                    shapes_by_line[short_name][direction] = shape_id
                    trips_by_line[short_name][direction] = trip_id

    return shapes_by_line, trips_by_line

def load_shape_points(shape_ids):
    """Carrega as coordenadas do shape."""
    shape_data = {s_id: [] for s_id in shape_ids}
    with open(SHAPES_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            s_id = row.get('shape_id')
            if s_id in shape_data:
                shape_data[s_id].append({
                    'lat': float(row['shape_pt_lat']),
                    'lon': float(row['shape_pt_lon']),
                    'seq': int(row['shape_pt_sequence'])
                })
    for s_id in shape_data:
        shape_data[s_id] = sorted(shape_data[s_id], key=lambda x: x['seq'])
    return shape_data

def get_stops_for_trips(trip_ids):
    """Retorna lista ordenada de coordenadas das paradas para cada trip_id."""
    stops_order = {t_id: [] for t_id in trip_ids}
    all_target_stops = set()
    
    with open(STOP_TIMES_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            t_id = row.get('trip_id')
            if t_id in stops_order:
                stops_order[t_id].append({
                    'seq': int(row['stop_sequence']),
                    'stop_id': row['stop_id']
                })
                all_target_stops.add(row['stop_id'])
                
    for t_id in stops_order:
        stops_order[t_id] = sorted(stops_order[t_id], key=lambda x: x['seq'])

    stop_coords = {}
    with open(STOPS_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            s_id = row.get('stop_id')
            if s_id in all_target_stops:
                stop_coords[s_id] = {'lat': float(row['stop_lat']), 'lon': float(row['stop_lon'])}

    trip_stop_coords = {}
    for t_id, ordered_stops in stops_order.items():
        coords = []
        for s in ordered_stops:
            if s['stop_id'] in stop_coords:
                coords.append(stop_coords[s['stop_id']])
        trip_stop_coords[t_id] = coords
        
    return trip_stop_coords

def sample_hybrid_points(shape_points, stop_points, interval_meters=400):
    """
    Combina paradas obrigatórias com pontos espaçados a cada 'interval_meters'.
    """
    if not shape_points:
        return []
        
    # 1. Encontrar o índice mais próximo no shape para cada parada
    stop_indices = set()
    for stop in stop_points:
        min_dist = float('inf')
        best_idx = 0
        for i, sp in enumerate(shape_points):
            dist = haversine(stop['lat'], stop['lon'], sp['lat'], sp['lon'])
            if dist < min_dist:
                min_dist = dist
                best_idx = i
        # Se a parada estiver razoavelmente perto da rota (ex: < 100m)
        if min_dist < 100:
            stop_indices.add(best_idx)

    # 2. Percorrer o shape e preencher apenas com as paradas (Aplicando o Deslocamento Ortogonal)
    sampled = []
    
    for i in range(len(shape_points)):
        if i in stop_indices:
            curr_p = shape_points[i]
            
            if i > 0:
                prev_p = shape_points[i-1]
                bearing = calculate_bearing(prev_p['lat'], prev_p['lon'], curr_p['lat'], curr_p['lon'])
            elif i < len(shape_points) - 1:
                next_p = shape_points[i+1]
                bearing = calculate_bearing(curr_p['lat'], curr_p['lon'], next_p['lat'], next_p['lon'])
            else:
                bearing = 0
                
            new_lat, new_lon = shift_point_right(curr_p['lat'], curr_p['lon'], bearing, distance_m=2.5)
            
            sampled.append({
                'lat': new_lat,
                'lon': new_lon,
                'seq': curr_p['seq']
            })
            
    # Garantir o primeiro e o último ponto do shape (também deslocados)
    if not sampled or sampled[0]['seq'] != shape_points[0]['seq']:
        p = shape_points[0]
        bearing = calculate_bearing(p['lat'], p['lon'], shape_points[1]['lat'], shape_points[1]['lon']) if len(shape_points) > 1 else 0
        new_lat, new_lon = shift_point_right(p['lat'], p['lon'], bearing, distance_m=2.5)
        sampled.insert(0, {'lat': new_lat, 'lon': new_lon, 'seq': p['seq']})
        
    if sampled[-1]['seq'] != shape_points[-1]['seq']:
        p = shape_points[-1]
        bearing = calculate_bearing(shape_points[-2]['lat'], shape_points[-2]['lon'], p['lat'], p['lon']) if len(shape_points) > 1 else 0
        new_lat, new_lon = shift_point_right(p['lat'], p['lon'], bearing, distance_m=2.5)
        sampled.append({'lat': new_lat, 'lon': new_lon, 'seq': p['seq']})
            
    return sampled

def get_sampled_routes(target_lines=["746", "5501", "953", "016", "288"]):
    shapes_by_line, trips_by_line = get_shapes_for_lines(target_lines)
    
    all_shape_ids = [s_id for dirs in shapes_by_line.values() for s_id in dirs.values()]
    all_trip_ids = [t_id for dirs in trips_by_line.values() for t_id in dirs.values()]
    
    raw_shapes = load_shape_points(all_shape_ids)
    trip_stops = get_stops_for_trips(all_trip_ids)
    
    sampled_routes = {}
    for line, directions in shapes_by_line.items():
        sampled_routes[line] = {}
        for d, s_id in directions.items():
            t_id = trips_by_line[line][d]
            pts = raw_shapes.get(s_id, [])
            stops = trip_stops.get(t_id, [])
            
            sampled_routes[line][d] = sample_hybrid_points(pts, stops)
            
    return sampled_routes

if __name__ == "__main__":
    linhas = ["746", "5501", "953", "016", "288"]
    res = get_sampled_routes(linhas)
    for linha in linhas:
        for d in res.get(linha, {}):
            pts = res[linha][d]
            print(f"Linha {linha} (Sentido {d}): {len(pts)} pontos (Apenas STOPS + Pontas).")
