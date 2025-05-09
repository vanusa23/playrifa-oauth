import os
import json
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta

# Inicialização do Firebase usando variável de ambiente
if not firebase_admin._apps:
    firebase_cred_json = os.getenv("FIREBASE_CREDENTIALS")
    if not firebase_cred_json:
        raise ValueError("❌ Variável de ambiente FIREBASE_CREDENTIALS não encontrada.")
    
    cred_dict = json.loads(firebase_cred_json)
    cred = credentials.Certificate(cred_dict)
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
        user_id = metadata.get("userId")  # Vem do metadata no momento da criação do pedido

        # Verifica se o evento é de pagamento confirmado
        if event_type in ["charge.paid", "order.paid"]:
            charge_id = charge_data.get("id")
            order_id = charge_data.get("order", {}).get("id") or charge_data.get("id")

            print(f"✅ Pagamento confirmado para pedido {order_id}, charge {charge_id}")

            # Ativa assinatura no Firestore
            if user_id:
                validade = datetime.utcnow() + timedelta(days=30)
                db.collection("users").document(user_id).update({
                    "assinaturaAtiva": True,
                    "assinaturaValidaAte": validade.isoformat()
                })
                print(f"🔓 Assinatura ativada com validade até {validade} para UID {user_id}")
            else:
                print("⚠️ UID ausente no metadata. Assinatura não foi ativada.")

            # Salva log de pagamento
            db.collection("pagamentos_confirmados").document(order_id).set({
                "charge_id": charge_id,
                "order_id": order_id,
                "user_id": user_id,
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
