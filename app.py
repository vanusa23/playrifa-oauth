import os
import sys
import hmac
import hashlib
import json
import requests # Importar requests para chamar a captura (simulação)
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, send_from_directory, request, jsonify, abort

# --- Configuração do Firebase Admin SDK ---
try:
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        print("Erro: Variável de ambiente GOOGLE_APPLICATION_CREDENTIALS não definida.")
        sys.exit(1)
    
    if not os.path.exists(cred_path):
        print(f"Erro: Arquivo de credenciais não encontrado em: {cred_path}")
        sys.exit(1)

    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
    db_firestore = firestore.client()
    print("Firebase Admin SDK inicializado com sucesso.")

except Exception as e:
    print(f"Erro ao inicializar Firebase Admin SDK: {e}")
    sys.exit(1)
# ----------------------------------------

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'fallback_secret_key_for_dev')

# --- Constantes e Configurações ---
PAGARME_API_BASE_URL = 'https://api.pagar.me/core/v5'
PLATFORM_RECIPIENT_ID = 're_cma2rrrwg1g8s0l9t2pvl9abx' # ID da plataforma (5%)
# ----------------------------------

# --- Validação do Webhook Pagar.me ---
def validate_pagarme_signature(request):
    signature_header = request.headers.get('X-Hub-Signature')
    if not signature_header:
        print("Erro Validação: Cabeçalho X-Hub-Signature ausente.")
        return False
    try:
        method, signature = signature_header.split('=')
    except ValueError:
        print(f"Erro Validação: Formato inválido do cabeçalho X-Hub-Signature: {signature_header}")
        return False
    if method != 'sha1':
        print(f"Erro Validação: Método de assinatura não suportado: {method}")
        return False
    pagarme_api_key = os.environ.get('PAGARME_API_KEY')
    if not pagarme_api_key:
        print("Erro Validação: Variável de ambiente PAGARME_API_KEY não definida.")
        return False 
    mac = hmac.new(pagarme_api_key.encode('utf-8'), msg=request.data, digestmod=hashlib.sha1)
    calculated_signature = mac.hexdigest()
    if hmac.compare_digest(calculated_signature, signature):
        print("Validação da assinatura do Webhook Pagar.me bem-sucedida.")
        return True
    else:
        print("Erro Validação: Assinatura inválida.")
        print(f"  Recebida: {signature}")
        print(f"Calculada: {calculated_signature}")
        return False
# -------------------------------------

# --- Funções Auxiliares ---
def buscar_dados_para_captura(charge_id):
    """Busca os dados necessários para a captura no Firestore."""
    try:
        doc_ref = db_firestore.collection('pagamentos_pendentes').document(charge_id)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            vendedor_id = data.get('vendedorRecipientId')
            valor = data.get('valor') # Valor em Reais (float/double)
            status_atual = data.get('status')
            
            if vendedor_id and valor is not None:
                print(f"Dados encontrados para {charge_id}: Vendedor={vendedor_id}, Valor={valor}, Status={status_atual}")
                # Retorna também o status para evitar recapturas
                return {'vendedorRecipientId': vendedor_id, 'valor': valor, 'status': status_atual}
            else:
                print(f"Erro: Dados incompletos no Firestore para {charge_id}. VendedorID={vendedor_id}, Valor={valor}")
                return None
        else:
            print(f"Erro: Documento não encontrado no Firestore para charge_id: {charge_id}")
            return None
    except Exception as e:
        print(f"Erro ao buscar dados no Firestore para {charge_id}: {e}")
        return None

def atualizar_status_pagamento(charge_id, novo_status, error_message=None):
    """Atualiza o status do pagamento no Firestore."""
    try:
        doc_ref = db_firestore.collection('pagamentos_pendentes').document(charge_id)
        update_data = {'status': novo_status, 'atualizadoEm': firestore.SERVER_TIMESTAMP}
        if error_message:
            update_data['erroCaptura'] = error_message
        doc_ref.update(update_data)
        print(f"Status do pagamento {charge_id} atualizado para {novo_status}.")
    except Exception as e:
        print(f"Erro ao atualizar status no Firestore para {charge_id}: {e}")

# --- Função de Captura (será chamada pelo webhook) ---
# Esta função simula a chamada à API Pagar.me para capturar
# Idealmente, você pode mover a lógica de `capturarPagamentoComSplit` 
# do seu app Flutter para cá ou para uma biblioteca compartilhada.
def chamar_api_captura_pagarme(charge_id, valor_total_reais):
    """Chama a API do Pagar.me para capturar a cobrança."""
    pagarme_api_key = os.environ.get('PAGARME_API_KEY')
    if not pagarme_api_key:
        print("Erro Captura API: Variável de ambiente PAGARME_API_KEY não definida.")
        return False, "Chave da API não configurada no backend"

    try:
        basic_auth = base64.b64encode(f"{pagarme_api_key}:".encode('utf-8')).decode('utf-8')
        headers = {
            'Authorization': f'Basic {basic_auth}',
            'Content-Type': 'application/json',
        }
        # O corpo precisa apenas do valor a ser capturado
        body = json.dumps({
            "amount": int(valor_total_reais * 100) # Valor em centavos
        })
        capture_url = f"{PAGARME_API_BASE_URL}/charges/{charge_id}/capture"
        
        print(f"Chamando API de Captura: POST {capture_url}")
        # print(f"Body Captura: {body}") # Descomente para depurar

        response = requests.post(capture_url, headers=headers, data=body, timeout=30) # Timeout de 30s

        print(f"Resposta da API de Captura ({charge_id}): Status={response.status_code}")
        # print(f"Resposta Body: {response.text}") # Descomente para depurar

        if response.status_code == 200:
            print(f"Captura da cobrança {charge_id} realizada com sucesso pela API.")
            return True, None
        else:
            error_msg = f"Erro {response.status_code} ao chamar API de captura Pagar.me."
            try:
                error_details = response.json()
                error_msg += f" Detalhes: {error_details}"
            except json.JSONDecodeError:
                error_msg += f" Resposta não JSON: {response.text}"
            print(error_msg)
            return False, error_msg

    except requests.exceptions.RequestException as e:
        error_msg = f"Exceção ao chamar API de captura Pagar.me para {charge_id}: {e}"
        print(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Erro inesperado ao preparar chamada de captura para {charge_id}: {e}"
        print(error_msg)
        return False, error_msg

# --- Endpoint do Webhook Pagar.me ---
@app.route('/pagarme', methods=['POST'])
def pagarme_webhook():
    print("\n--- Webhook Pagar.me Recebido ---")
    if not validate_pagarme_signature(request):
        print("Falha na validação da assinatura. Abortando.")
        abort(401)

    try:
        data = request.json
        if not data:
             print("Erro: Corpo da requisição JSON vazio ou inválido.")
             return jsonify({"status": "error", "message": "Invalid JSON body"}), 400
             
        # print(f"Dados recebidos (validados): {json.dumps(data, indent=2)}") # Log verboso
        
        event_type = data.get('type')
        charge_data = data.get('data', {})
        charge_id = charge_data.get('id')
        charge_status_webhook = charge_data.get('status') # Status vindo do webhook

        print(f"Evento: {event_type}, Charge ID: {charge_id}, Status Webhook: {charge_status_webhook}")

        # Processar apenas eventos 'charge.paid'
        if event_type == 'charge.paid' and charge_id:
            print(f"Processando 'charge.paid' para {charge_id}...")
            
            # 1. Buscar dados no Firestore
            dados_compra = buscar_dados_para_captura(charge_id)
            
            if dados_compra:
                vendedor_id = dados_compra['vendedorRecipientId']
                valor_reais = dados_compra['valor']
                status_firestore = dados_compra['status']

                # 2. Verificar se já foi capturado ou se houve erro anterior
                if status_firestore == 'capturado':
                    print(f"Cobrança {charge_id} já consta como 'capturado' no Firestore. Ignorando.")
                elif status_firestore == 'erro_captura':
                     print(f"Cobrança {charge_id} já consta como 'erro_captura' no Firestore. Ignorando.")
                elif status_firestore == 'aguardando_autorizacao' or status_firestore is None: # Permite capturar se status for inicial ou nulo
                    print(f"Iniciando captura para {charge_id} (Status Firestore: {status_firestore})...")
                    
                    # 3. Chamar a API de Captura Pagar.me
                    # Passar o valor total que foi salvo no Firestore
                    sucesso_captura, erro_captura = chamar_api_captura_pagarme(charge_id, valor_reais)
                    
                    # 4. Atualizar status no Firestore
                    if sucesso_captura:
                        atualizar_status_pagamento(charge_id, 'capturado')
                    else:
                        atualizar_status_pagamento(charge_id, 'erro_captura', erro_captura)
                else:
                    print(f"Status inesperado '{status_firestore}' no Firestore para {charge_id}. Nenhuma ação de captura será tomada.")

            else:
                print(f"Não foi possível encontrar/processar dados no Firestore para {charge_id}. Captura não realizada.")
                # Considerar logar isso como um erro mais sério ou notificar admin
        else:
            print(f"Evento '{event_type}' recebido para {charge_id}, não requer ação de captura.")

    except Exception as e:
        print(f"Erro GERAL ao processar webhook: {e}")
        # Retornar 500 Internal Server Error pode fazer o Pagar.me tentar reenviar
        # Retornar 200 evita retentativas, mas pode mascarar o erro.
        # Escolha depende da sua estratégia de tratamento de erros.
        return jsonify({"status": "error", "message": "Internal server error processing webhook"}), 500

    # Retorna 200 OK para o Pagar.me confirmar o recebimento
    return jsonify({"status": "received"}), 200
# -----------------------------------------------------------

# Rota para servir arquivos estáticos (mantida do template)
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    # ... (código para servir estáticos mantido como antes) ...
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404
    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "Backend Webhook Pagar.me está rodando.", 200

# Importar base64 no início do arquivo
import base64

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    print(f"Iniciando servidor Flask em 0.0.0.0:{port} (Debug: {debug_mode})")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
