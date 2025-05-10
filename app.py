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
    return "🔥 Webhook do PlayRifa ativo com sucesso!", 200

@app.route("/pagarme", methods=["POST"])
def webhook_pagarme():
    data = request.get_json()
    print("📦 Webhook recebido:", data)

    try:
        event_type = data.get("type")
        charge_data = data.get("data", {})
        metadata = charge_data.get("metadata", {})

        if event_type in ["charge.paid", "order.paid"]:
            charge_id = charge_data.get("id")
            order_id = charge_data.get("order", {}).get("id") or charge_data.get("id")

            print(f"✅ Pagamento confirmado para pedido {order_id}, charge {charge_id}")

            validade = datetime.utcnow() + timedelta(days=30)

            # Atualiza ou cria a assinatura com merge=True
            update_data = {
                "ativo": True,
                "assinaturaValidaAte": validade.isoformat(),
                "statusPagamento": event_type,
                "timestamp": firestore.SERVER_TIMESTAMP,
                "email": charge_data.get("customer", {}).get("email", "email_padrao@exemplo.com"),
                "uid": metadata.get("user_id", "uid_padrao")
            }

            doc_ref = db.collection("assinaturas").document(order_id)
            doc_ref.set(update_data, merge=True)
            print(f"🔄 Assinatura {order_id} atualizada com sucesso.")

            db.collection("pagamentos_confirmados").document(order_id).set({
                "charge_id": charge_id,
                "order_id": order_id,
                "event_type": event_type,
                "timestamp": firestore.SERVER_TIMESTAMP,
                "payload_recebido": data
            })

            return jsonify({"status": "sucesso", "order_id": order_id}), 200

        print(f"⚠️ Evento ignorado: {event_type}")
        return jsonify({"status": "ignorado"}), 200

    except Exception as e:
        print("❌ Erro no webhook:", e)
        import traceback
        traceback.print_exc()
        return jsonify({"erro": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)), debug=False)
