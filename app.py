import os
import json
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta

# Lê o arquivo secreto no caminho correto para Render
if not firebase_admin._apps:
    cred_path = "/etc/secrets/firebase_credentials.json"
    if not os.path.exists(cred_path):
        raise FileNotFoundError(f"Arquivo de credenciais não encontrado em: {cred_path}")

    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()
app = Flask(__name__)

@app.route("/")
def index():
    return "Webhook do PlayRifa ativo com sucesso!", 200

@app.route("/pagarme", methods=["POST"])
def webhook_pagarme():
    data = request.get_json()
    print("Webhook recebido:", data) # Adicionado para depuração

    try:
        event_type = data.get("type")
        # Ajuste para pegar 'data' de dentro do objeto principal, comum em webhooks do Pagar.me v2
        transaction_data = data.get("data", {})
        if not transaction_data and "transaction" in data: # Fallback para estrutura antiga ou diferente
            transaction_data = data.get("transaction", {})
        
        # Tentativa de obter order_id de diferentes locais possíveis no payload do Pagar.me
        order_info = transaction_data.get("order", {})
        order_id = order_info.get("id") # Padrão para API v2

        if not order_id:
            # Em alguns casos, o ID da transação pode ser usado como order_id se não houver um ID de pedido explícito
            # ou se o ID do pedido estiver em 'metadata' ou diretamente na transação.
            order_id = transaction_data.get("id") # ID da cobrança/transação
            if not order_id and "id" in data: # Se o ID estiver no nível raiz do evento (menos comum para 'data')
                order_id = data.get("id")

        # Se o order_id ainda não foi encontrado, verificar metadata
        if not order_id:
            metadata = transaction_data.get("metadata", {})
            order_id = metadata.get("order_id") # Supondo que você envie 'order_id' no metadata

        print(f"Evento: {event_type}, Order ID extraído: {order_id}") # Log para depuração

        if event_type in ["charge.paid", "order.paid"] and order_id:
            print(f"Pagamento confirmado para evento {event_type}, order_id {order_id}")

            # Verifica se o documento existe antes de tentar atualizar
            doc_ref = db.collection("assinaturas").document(order_id)
            doc = doc_ref.get()

            validade = datetime.utcnow() + timedelta(days=30)
            update_data = {
                "ativo": True,
                "assinaturaValidaAte": validade.isoformat(),
                "statusPagamento": event_type # Adiciona o tipo de evento para rastreio
            }

            if doc.exists:
                print(f"Documento {order_id} encontrado. Atualizando...")
                doc_ref.update(update_data)
            else:
                print(f"Documento {order_id} NÃO encontrado. Criando com dados...")
                # Se o documento não existe, pode ser necessário criá-lo.
                # Se a lógica de criação inicial com 'ativo: false' é em outro lugar,
                # esta parte pode precisar ser ajustada ou removida.
                # Por ora, vamos assumir que ele deveria existir ou será criado aqui.
                # Se o email e uid são fixos como no print, isso não funcionaria para novos usuários.
                # Idealmente, esses dados viriam do metadata do Pagar.me ou de uma consulta prévia.
                initial_data = {
                    "ativo": True, # Já define como ativo
                    "assinaturaValidaAte": validade.isoformat(),
                    "statusPagamento": event_type,
                    "email": transaction_data.get("customer", {}).get("email", "email_padrao@exemplo.com"), # Tenta pegar do customer
                    "order_id": order_id, # Garante que o order_id está no documento
                    "timestamp": firestore.SERVER_TIMESTAMP,
                    # uid precisaria vir de algum lugar, talvez metadata
                    "uid": transaction_data.get("metadata", {}).get("user_id", "uid_padrao") 
                }
                doc_ref.set(initial_data) # Usar set para criar se não existe

            # Registrar pagamento confirmado em uma coleção separada também é uma boa prática
            db.collection("pagamentos_confirmados").document(order_id).set({
                "charge_id": transaction_data.get("id"), # ID da cobrança
                "order_id": order_id,
                "event_type": event_type,
                "timestamp": firestore.SERVER_TIMESTAMP,
                "payload_recebido": data # Salva o payload completo para auditoria
            })

            print(f"Firestore atualizado/criado para order_id: {order_id}")
            return jsonify({"status": "sucesso", "order_id": order_id}), 200
        elif not order_id:
            print(f"Order ID não encontrado no payload para evento {event_type}. Payload: {data}")
            return jsonify({"status": "erro", "mensagem": "Order ID não encontrado no payload"}), 400
        else:
            print(f"Evento ignorado: {event_type} para order_id: {order_id}")
            return jsonify({"status": "ignorado", "event_type": event_type}), 200

    except Exception as e:
        print(f"Erro no webhook: {e}")
        import traceback
        traceback.print_exc() # Imprime o stack trace completo do erro
        return jsonify({"erro": str(e)}), 500

if __name__ == "__main__":
    # Para debug local, pode ser útil rodar com debug=True
    # No Render, o Gunicorn vai gerenciar isso, e debug=False é o padrão para produção.
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)), debug=False)
