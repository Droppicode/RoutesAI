import threading
import time
from scripts.collect_data import start_data_loop
from scripts.collect_traffic import start_traffic_loop

def main():
    print("="*60)
    print("INICIANDO ORQUESTRADOR GLOBAL (Veículos + Trânsito)")
    print("="*60)
    
    # Dicionário compartilhado em memória
    # O collect_data atualiza esse dicionário e o collect_traffic lê
    # para saber se deve ou não buscar trânsito para a linha
    shared_active_status = {}
    
    # Cria as Threads
    thread_veiculos = threading.Thread(
        target=start_data_loop, 
        args=(shared_active_status,),
        name="Thread-Veiculos",
        daemon=True # Daemon significa que a thread morre se o programa principal morrer
    )
    
    thread_transito = threading.Thread(
        target=start_traffic_loop,
        args=(shared_active_status,),
        name="Thread-Transito",
        daemon=True
    )
    
    # Inicia as Threads
    thread_veiculos.start()
    
    # Dá um tempinho pequeno para o collect_data preencher o shared_active_status inicial
    time.sleep(2)
    
    thread_transito.start()
    
    # Mantém o script principal vivo e monitorando as threads
    try:
        while True:
            # Verifica a cada minuto se alguma thread morreu inesperadamente
            time.sleep(60)
            if not thread_veiculos.is_alive():
                print("ALERTA: A thread de veículos parou!")
            if not thread_transito.is_alive():
                print("ALERTA: A thread de trânsito parou!")
                
    except KeyboardInterrupt:
        print("\n[ORQUESTRADOR] Sinal de interrupção recebido. Desligando as coletas...")
        # Como são threads daemon, elas vão morrer assim que o main acabar.
        print("Até logo!")

if __name__ == "__main__":
    main()
