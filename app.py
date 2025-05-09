import os
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta

# Inicialização do Firebase direto do arquivo secreto do Render
if not firebase_admin._apps:
    cred = credentials.Certificate("/etc/secrets/firebase_credentials.json")
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

        # Verifica se o evento é de pagamento confirmado
        if event_type in ["charge.paid", "order.paid"]:
            charge_id = charge_data.get("id")
            order_id = charge_data.get("order", {}).get("id") or charge_data.get("id")

            print(f"✅ Pagamento confirmado para pedido {order_id}, charge {charge_id}")

            # Ativa assinatura no Firestore
            validade = datetime.utcnow() + timedelta(days=30)
            db.collection("assinaturas").document(order_id).update({
                "ativo": True,
                "assinaturaValidaAte": validade.isoformat()
            })
            print(f"🔓 Assinatura ativada com validade até {validade} para pedido {order_id}")

            # Salva log de pagamento
            db.collection("pagamentos_confirmados").document(order_id).set({
                "charge_id": charge_id,
                "order_id": order_id,
                "timestamp": firestore.SERVER_TIMESTAMP
            })

            return jsonify({"status": "sucesso", "order_id": order_id}), 200

        print(f"⚠️ Evento ignorado: {event_type}")
        return jsonify({"status": "ignorado"}), 200

    except Exception as e:
        print("❌ Erro no webhook:", e)
        return jsonify({"erro": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=False)
