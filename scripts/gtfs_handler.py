import csv
import os

GTFS_ROUTES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'artesp_gtfs', 'routes.txt')

def get_todas_as_linhas():
    linhas = []
    
    if not os.path.exists(GTFS_ROUTES_FILE):
        return linhas
        
    try:
        with open(GTFS_ROUTES_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Vamos retornar apenas as que tem short_name (ex: 746)
                if row.get('route_short_name') and row.get('route_long_name'):
                    linhas.append({
                        "id": row['route_short_name'],
                        "nome": f"{row['route_short_name']} - {row['route_long_name']}"
                    })
    except Exception as e:
        print(f"Erro ao ler GTFS: {e}")
        
    # Remove duplicatas baseadas no ID, já que algumas podem ter variações (ex: 746, 746EX1) mas a API EMTU usa o número base para busca
    # ou podemos mandar todas. Vamos mandar todas para o dropdown.
    return linhas
