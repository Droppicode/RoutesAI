import sqlite3
import requests
import time
import json
import os
from datetime import datetime
from scripts.gtfs_sampler import get_sampled_routes, haversine
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

DB_NAME = 'data/emtu_transito.db'
TOMTOM_API_KEY = os.environ.get('TOMTOM_API_KEY') 
TOMTOM_URL = "https://api.tomtom.com/routing/1/calculateRoute/{}/json"

def setup_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transito_historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            linha_codigo TEXT,
            sentido TEXT,
            shape_origem_lat REAL,
            shape_origem_lon REAL,
            shape_destino_lat REAL,
            shape_destino_lon REAL,
            distancia_metros INTEGER,
            duracao_normal_segundos INTEGER,
            duracao_transito_segundos INTEGER,
            duracao_atraso_segundos INTEGER
        )
    ''')
    conn.commit()
    return conn

def fetch_traffic_for_route(conn, linha, sentido, points):
    if not points or len(points) < 2:
        return
        
    # TomTom espera: lat,lon:lat,lon
    locations = ":".join([f"{p['lat']},{p['lon']}" for p in points])
    
    url = TOMTOM_URL.format(locations)
    params = {
        'key': TOMTOM_API_KEY,
        'computeTravelTimeFor': 'all',
        'traffic': 'true',
        'routeRepresentation': 'summaryOnly',
        'travelMode': 'bus'
    }
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Solicitando trânsito para linha {linha} (Sentido {sentido}) - {len(points)} pontos...")
    
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            routes = data.get('routes', [])
            if not routes:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Aviso: Rota não encontrada na resposta.")
                return 0
                
            legs = routes[0].get('legs', [])
            
            # legs terá o tamanho de len(points) - 1
            if len(legs) != (len(points) - 1):
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Aviso: Número de pernas retornado ({len(legs)}) não bate com os pontos esperados ({len(points)-1}).")
            
            cursor = conn.cursor()
            for i, leg in enumerate(legs):
                # Caso a API retorne menos legs do que os pontos
                if i >= len(points) - 1:
                    break
                    
                p_origem = points[i]
                p_destino = points[i+1]
                
                summary = leg.get('summary', {})
                length_meters = summary.get('lengthInMeters', 0)
                travel_time = summary.get('travelTimeInSeconds', 0)
                
                no_traffic = summary.get('noTrafficTravelTimeInSeconds', travel_time)
                with_traffic = summary.get('liveTrafficIncidentsTravelTimeInSeconds', travel_time)
                delay_traffic = summary.get('trafficDelayInSeconds', 0)
                
                cursor.execute('''
                    INSERT INTO transito_historico (
                        linha_codigo, sentido, 
                        shape_origem_lat, shape_origem_lon,
                        shape_destino_lat, shape_destino_lon,
                        distancia_metros, duracao_normal_segundos, duracao_transito_segundos, duracao_atraso_segundos
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    linha, sentido,
                    p_origem['lat'], p_origem['lon'],
                    p_destino['lat'], p_destino['lon'],
                    length_meters, no_traffic, with_traffic, delay_traffic
                ))
            
            conn.commit()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Sucesso: Trânsito salvo para {len(legs)} segmentos da linha {linha} ({sentido}).")
            return 1
            
        elif response.status_code in [429, 403]:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ALERTA ({response.status_code}): Limite da API TomTom atingido!")
            return -429
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro na API TomTom: Status {response.status_code}")
            return -1
            
    except requests.exceptions.Timeout:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Timeout ao acessar a API TomTom para a linha {linha}.")
    except requests.exceptions.ConnectionError:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro de Conexão com a TomTom na linha {linha}.")
    except json.JSONDecodeError:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro: Resposta da TomTom não é um JSON válido.")
    except sqlite3.Error as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro no Banco de Dados: {e}")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro inesperado {linha}: {e}")
    
    return -1

def start_traffic_loop(shared_status):
    print("Iniciando coletor de trânsito TomTom com resiliência...")
    
    if TOMTOM_API_KEY == 'SUA_CHAVE_AQUI':
        print("ALERTA: Chave da API TomTom não configurada. O script provavelmente falhará.")
    
    print("Lendo e amostrando GTFS (Apenas Paradas Físicas)...")
    try:
        sampled_routes = get_sampled_routes(["746", "5501", "953", "016", "288"])
    except Exception as e:
        print(f"Falha fatal ao amostrar GTFS: {e}")
        return
        
    conn = setup_db()
    
    try:
        while True:
            try:
                hora_atual = datetime.now().hour
                limite_atingido = False
                
                for linha, sentidos in sampled_routes.items():
                    if limite_atingido:
                        break
                        
                    # VERIFICAÇÃO CHAVE DO ORQUESTRADOR GLOBAL
                    if not shared_status.get(linha, True):
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Trânsito ignorado para {linha}: Linha inativa segundo coletor EMTU.")
                        continue
                        
                    for sentido, points in sentidos.items():
                        status = fetch_traffic_for_route(conn, linha, sentido, points)
                        
                        if status == -429:
                            limite_atingido = True
                            break
                            
                        # Respeita limite da API de aprox 5 requests por segundo (usamos 1 seg pra garantir)
                        time.sleep(1)
                
                if limite_atingido:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Pausando o script por 15 minutos (Prevenção de Ban TomTom)...")
                    time.sleep(15 * 60)
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Ciclo concluído com sucesso. Aguardando 15 minutos...")
                    time.sleep(15 * 60)
                    
            except Exception as loop_err:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro crítico no loop principal do trânsito: {loop_err}")
                print("Recuperando em 60 segundos...")
                time.sleep(60)
                
    except KeyboardInterrupt:
        print("\nColeta interrompida pelo usuário.")
    finally:
        conn.close()
        print("Conexão com o banco encerrada no coletor de trânsito.")

if __name__ == "__main__":
    start_traffic_loop({})
