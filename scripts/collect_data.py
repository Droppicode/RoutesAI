import sqlite3
import requests
import time
import random
import json
from datetime import datetime
import urllib3

# Oculta avisos de certificado SSL (já que a API da Noxxonsat pode ter problemas de certificado)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DB_NAME = 'data/emtu_veiculos.db'
BASE_URL = 'https://rest-emtu.noxxonsat.com.br/rest/lineDetails?linha='
LINHAS = ["746", "5501", "953", "016", "288"]

# Regras de horário de funcionamento para não gastar fetch de madrugada (formato: tupla com horas válidas)
# (hora_inicio, hora_fim) onde a linha RODA. Se hora_fim < hora_inicio, passa da meia-noite.
HORARIOS_OPERACAO = {
    "746": (5, 1),    # 05h00 até ~00h45
    "5501": (5, 0),  # 05h00 até ~23h30
    "953": (5, 1),    # 05h00 até ~00h10
    "016": (5, 20),   # 05h00 até ~19h35
    "288": (4, 2)     # 04h00 até ~01h10
}

def is_operando(linha, hora_atual):
    if linha not in HORARIOS_OPERACAO:
        return True
    
    h_inicio, h_fim = HORARIOS_OPERACAO[linha]
    if h_inicio <= h_fim:
        return h_inicio <= hora_atual <= h_fim
    else:
        # Passa da meia-noite (ex: 5h às 0h significa 5, 6, ..., 23, 0)
        return hora_atual >= h_inicio or hora_atual <= h_fim

def setup_db():
    """Cria o banco de dados e a tabela caso não existam."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS veiculos_historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            linha_codigo TEXT,
            veiculos_json TEXT
        )
    ''')
    conn.commit()
    return conn

def extract_veiculos(data):
    """Tenta extrair a lista de veículos de diferentes estruturas de resposta conhecidas."""
    if isinstance(data, dict):
        if 'veiculos' in data:
            return data['veiculos']
        elif 'linhas' in data and isinstance(data['linhas'], list) and len(data['linhas']) > 0:
            if 'veiculos' in data['linhas'][0]:
                return data['linhas'][0]['veiculos']
    
    # Se não bater com nenhuma estrutura conhecida, retorna o dado bruto inteiro para não perdermos nada
    return data

def check_noxxonsat_schedule(data):
    """
    Verifica no JSON da Noxxonsat se existe alguma viagem escalada para agora (com folga de 15 min).
    """
    if not isinstance(data, dict): return False
    
    rota = None
    if 'linhas' in data and len(data['linhas']) > 0:
        linha_data = data['linhas'][0]
        if 'rotas' in linha_data and len(linha_data['rotas']) > 0:
            rota = linha_data['rotas'][0]
            
    if not rota: return False
    
    tempo_viagem = rota.get('tempo', 60.0)
    
    hoje = datetime.now()
    dia_semana = hoje.weekday()
    
    horarios_str = rota.get('horarios', "")
    if dia_semana == 5:
        horarios_str = rota.get('horariossabados', horarios_str)
    elif dia_semana == 6:
        horarios_str = rota.get('horariosdomingosferiados', horarios_str)
    else:
        horarios_str = rota.get('horariosdiasuteis', horarios_str)
        
    if not horarios_str or type(horarios_str) != str: 
        return False
        
    agora_min = hoje.hour * 60 + hoje.minute
    
    for h_str in horarios_str.split(','):
        h_str = h_str.strip()
        if not h_str: continue
        try:
            h, m = map(int, h_str.split(':'))
            saida_min = h * 60 + m
            chegada_min = saida_min + tempo_viagem
            
            if (saida_min - 15) <= agora_min <= (chegada_min + 15):
                return True
                
            if chegada_min >= 24 * 60:
                if (saida_min - 15) <= (agora_min + 24*60) <= (chegada_min + 15):
                    return True
        except:
            continue
            
    return False
    
    # Se não bater com nenhuma estrutura conhecida, retorna o dado bruto inteiro para não perdermos nada
    return data

def fetch_and_store(conn, linha):
    url = f"{BASE_URL}{linha}"
    try:
        # verify=False contorna SSL e timeout=10 evita travar se a API demorar
        response = requests.get(url, verify=False, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            veiculos = extract_veiculos(data)
            veiculos_json_str = json.dumps(veiculos, ensure_ascii=False)
            
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO veiculos_historico (linha_codigo, veiculos_json) VALUES (?, ?)',
                (linha, veiculos_json_str)
            )
            conn.commit()
            
            if isinstance(veiculos, list):
                qtd = len(veiculos)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Sucesso: {linha} -> {qtd} veículos salvos.")
                return qtd, data
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Sucesso: {linha} -> Formato Bruto salvo.")
                return 1, data
        elif response.status_code in [429, 403]:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ALERTA ({response.status_code}): O servidor está limitando as requisições na linha {linha}!")
            return -429, None
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro API {linha}: Status {response.status_code}")
            return -1, None
            
    # Corner cases: falha de rede, timeout, json inválido ou conexão fechada pelo servidor
    except requests.exceptions.Timeout:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Timeout ao acessar {linha}.")
    except requests.exceptions.ConnectionError:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro de Conexão na linha {linha}.")
    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro de Requisição {linha}: {e}")
    except json.JSONDecodeError:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro JSON na linha {linha}: Resposta não é um JSON válido.")
    except sqlite3.Error as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro no Banco de Dados: {e}")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro inesperado {linha}: {e}")
    
    return -1, None # Retorna -1 em caso de erro para não assumir que está zerado

def start_data_loop(shared_status):
    print("Iniciando coletor EMTU (Veículos)...")
    print(f"Linhas monitoradas: {' -> '.join(LINHAS)}")
    
    conn = setup_db()
    last_fetch_count = {linha: -1 for linha in LINHAS}
    
    # Inicializa o status compartilhado como True para todas
    for linha in LINHAS:
        shared_status[linha] = True
        
    try:
        while True:
            hora_atual = datetime.now().hour
            for linha in LINHAS:
                # Pula apenas se estiver fora do horário de operação E o último fetch tiver retornado 0 veículos
                if not is_operando(linha, hora_atual) and last_fetch_count[linha] == 0:
                    # Avisa o orquestrador que a linha "morreu"
                    if shared_status.get(linha, True):
                        shared_status[linha] = False
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Ignorando {linha}: Fora do horário E sem veículos rodando (Status global: Inativo).")
                else:
                    qtd, data = fetch_and_store(conn, linha)
                    if qtd == -429:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Pausando o script por 15 minutos para esfriar a conexão (Prevenção de Ban)...")
                        time.sleep(15 * 60)
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Retomando coleta após resfriamento.")
                    elif qtd != -1:
                        last_fetch_count[linha] = qtd
                        
                        # Inteligência de orquestração do trânsito usando a resposta da Noxxonsat
                        grade_ativa = check_noxxonsat_schedule(data)
                        
                        if qtd == 0 and not grade_ativa:
                            if shared_status.get(linha, True):
                                shared_status[linha] = False
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] Trânsito PAUSADO p/ {linha}: 0 veículos e sem grade prevista.")
                        else:
                            if not shared_status.get(linha, True):
                                shared_status[linha] = True
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] Trânsito LIGADO p/ {linha}: Veículo na rua ({qtd}) ou Grade Ativa ({grade_ativa}).")
                
                # Intervalo aleatório para bater com sua exigência de ~25s o ciclo total
                # ~5 segundos * 5 requisições = 25 segundos o ciclo
                sleep_time = random.uniform(4.5, 5.5)
                time.sleep(sleep_time)
                
    except KeyboardInterrupt:
        print("\nColeta interrompida pelo usuário.")
    except Exception as e:
        print(f"\nErro crítico no loop de veículos: {e}")
    finally:
        conn.close()
        print("Conexão com o banco encerrada no coletor de veículos.")

if __name__ == "__main__":
    # Permite rodar de forma isolada caso desejado
    start_data_loop({})
