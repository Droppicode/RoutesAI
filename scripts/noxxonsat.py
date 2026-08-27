import requests
import urllib3
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

base_url = "https://rest-emtu.noxxonsat.com.br/rest/"

# Uma lista massiva de tentativas comuns em APIs de transporte e frotas
endpoints = [
    "all", "todos", "frota", "fleet", "vehicles", "veiculos", 
    "veiculosAtivos", "active", "activeVehicles", "map", "mapa", 
    "positions", "posicoes", "onibus", "buses", "gps", "location", 
    "localizacao", "linhasAtivas", "rotas", "routes", "getAll", 
    "getAllVehicles", "vehiclePositions", "realtime", "live", 
    "linhas/todas", "monitoramento", "emtu"
]

print(f"Iniciando varredura em {len(endpoints)} possíveis rotas na API...")
print("OBS: Mostrando apenas rotas que NÃO retornaram 404 ou 405 (Not Found / Method Not Allowed).\\n")

for ep in endpoints:
    url = f"{base_url}{ep}"
    try:
        # Usando timeout curto para passar mais rápido
        res = requests.get(url, verify=False, timeout=5)
        
        # Ignorar 404 (Não Encontrado) e 405 (Método não permitido)
        if res.status_code not in [404, 405]:
            print(f"[STATUS {res.status_code}] Encontrado: {url}")
            if res.status_code == 200:
                print(" -> SUCESSO! Conteúdo:")
                print(" " + str(res.text)[:150] + "...\\n")
            elif res.status_code == 400:
                print(" -> A rota existe, mas pede algum parâmetro!\\n")
    except Exception as e:
        pass # Silencia erros de timeout
    
    # Delay pequeno para não derrubar a API deles
    time.sleep(1)

print("\\nVarredura concluída!")