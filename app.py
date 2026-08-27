from flask import Flask, render_template, jsonify, request
import requests
import urllib3
import sqlite3
import json

# Oculta avisos de certificado SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/visualizador')
def visualizador():
    return render_template('visualizador.html')

def query_db(db_name, query, args=(), one=False):
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv

@app.route('/api/linhas_db')
def api_linhas_db():
    linhas = query_db('data/emtu_transito.db', "SELECT DISTINCT linha_codigo FROM transito_historico ORDER BY linha_codigo")
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(linhas)
    return jsonify([row['linha_codigo'] for row in linhas])

@app.route('/api/horarios/<linha>')
def api_horarios(linha):
    # Converte os timestamps para localtime na hora de agrupar
    horarios = query_db('data/emtu_transito.db', "SELECT DISTINCT strftime('%Y-%m-%d %H:%M', datetime(timestamp, 'localtime')) as ts FROM transito_historico WHERE linha_codigo = ? ORDER BY timestamp DESC", (linha,))
    return jsonify([row['ts'] for row in horarios])

@app.route('/api/dados_mapa')
def api_dados_mapa():
    linha = request.args.get('linha')
    horario = request.args.get('horario') # Formato 'YYYY-MM-DD HH:MM'
    sentido = request.args.get('sentido') # Opcional: '0' ou '1'
    
    if not linha or not horario:
        return jsonify({"erro": "Linha e horario sao obrigatorios"}), 400

    # Busca trânsito: pegamos tudo que começa com aquele minuto em localtime
    if sentido:
        transito_rows = query_db('data/emtu_transito.db', "SELECT * FROM transito_historico WHERE linha_codigo = ? AND datetime(timestamp, 'localtime') LIKE ? AND sentido = ?", (linha, f"{horario}%", sentido))
    else:
        transito_rows = query_db('data/emtu_transito.db', "SELECT * FROM transito_historico WHERE linha_codigo = ? AND datetime(timestamp, 'localtime') LIKE ?", (linha, f"{horario}%"))
        
    transito = [dict(row) for row in transito_rows]

    # Busca veículos: tenta achar o registro de veículos mais próximo no tempo para aquela linha
    # Pegamos o primeiro dentro de um raio de +/- 5 minutos ou no mesmo minuto em localtime
    veiculos_rows = query_db('data/emtu_veiculos.db', "SELECT veiculos_json FROM veiculos_historico WHERE linha_codigo = ? AND datetime(timestamp, 'localtime') LIKE ? LIMIT 1", (linha, f"{horario}%"))
    veiculos = json.loads(veiculos_rows[0]['veiculos_json']) if veiculos_rows else []

    return jsonify({"transito": transito, "veiculos": veiculos})

@app.route('/todas_linhas')
def todas_linhas():
    from scripts.gtfs_handler import get_todas_as_linhas
    linhas = get_todas_as_linhas()
    return jsonify({"linhas": linhas})

@app.route('/api/linha/<linha_id>')
def get_linha(linha_id):
    url = f"https://rest-emtu.noxxonsat.com.br/rest/lineDetails?linha={linha_id}"
    try:
        # Usa verify=False para ignorar SSL expirado da API da Noxxonsat
        resposta = requests.get(url, verify=False, timeout=10)
        
        if resposta.status_code == 200:
            return jsonify(resposta.json())
        else:
            return jsonify({"erro": f"Erro na API: {resposta.status_code}"}), resposta.status_code
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
