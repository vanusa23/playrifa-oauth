import os
import json
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
from threading import Thread

# Logs para checar o cred_path
print("🔍 Listando conteúdo de /etc/secrets/:")
try:
    print(os.listdir('/etc/secrets'))
except Exception as e:
    print(f"❌ Erro ao listar /etc/secrets/: {e}")

# Firebase
if not firebase_admin._apps:
    cred_path = "/etc/secrets/firebase_credentials.json"
    print(f"🛠 Tentando acessar cred_path: {cred_path}")
    if not os.path.exists(cred_path):
        raise FileNotFoundError(f"Arquivo de credenciais não encontrado em: {cred_path}")
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
    print("✅ Firebase inicializado com sucesso.")

db = firestore.client()
app = Flask(__name__)

@app.route("/")
def index():
    return "🔥 Webhook do PlayRifa está online!", 200

@app.route("/pagarme", methods=["POST"])
def webhook_pagarme():
    data = request.get_json()
    print("📦 Webhook recebido:", json.dumps(data, indent=2))
    print("🔐 Headers recebidos:", dict(request.headers))

    # Retorna imediatamente para não dar timeout no Pagar.me
    Thread(target=processar_pagamento, args=(data,)).start()
    return jsonify({"status": "recebido"}), 200

def processar_pagamento(data):
    try:
        event_type = data.get("type")
        charge_data = data.get("data", {})
        metadata = charge_data.get("metadata", {})

        if event_type in ["charge.paid", "order.paid"]:
            charge_id = charge_data.get("id")
            order_id = charge_data.get("order", {}).get("id") or charge_data.get("id")

            print(f"✅ Pagamento confirmado para pedido {order_id}, charge {charge_id}")
            print("📎 Metadata recebido:", metadata)

            validade = datetime.utcnow() + timedelta(days=30)
            update_data = {
                "ativo": True,
                "assinaturaValidaAte": validade.isoformat(),
                "statusPagamento": event_type,
                "timestamp": firestore.SERVER_TIMESTAMP,
                "email": charge_data.get("customer", {}).get("email", "email_padrao@exemplo.com"),
                "uid": metadata.get("user_id", "uid_padrao")
            }

            db.collection("assinaturas").document(order_id).set(update_data, merge=True)
            print(f"🔄 Assinatura {order_id} atualizada com sucesso.")

            db.collection("pagamentos_confirmados").document(order_id).set({
                "charge_id": charge_id,
                "order_id": order_id,
                "event_type": event_type,
                "timestamp": firestore.SERVER_TIMESTAMP,
                "payload_recebido": data
            })

        else:
            print(f"⚠️ Evento ignorado: {event_type}")

    except Exception as e:
        print("❌ Erro no processamento assíncrono:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)), debug=False)
