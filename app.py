import os
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore

# Inicialização do Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-key.json")  # Substitua se necessário
    firebase_admin.initialize_app(cred)
db = firestore.client()

# Carregar ID do recebedor da plataforma via variável de ambiente
PLATFORM_RECIPIENT_ID = os.getenv("PLATFORM_RECIPIENT_ID")
if not PLATFORM_RECIPIENT_ID:
    print("❌ ERRO CRÍTICO: Variável de ambiente PLATFORM_RECIPIENT_ID não definida!")
else:
    print(f"🔍 PLATFORM_RECIPIENT_ID carregado: {PLATFORM_RECIPIENT_ID}")

app = Flask(__name__)

@app.route("/")
def index():
    return "🔥 Webhook do PlayRifa ativo com sucesso!", 200

@app.route("/pagarme", methods=["POST"])
def webhook_pagarme():
    data = request.get_json()
    print("📦 Webhook recebido:", data)

    try:
        # Verifica se é um evento de pagamento confirmado
        if data["type"] == "charge.paid":
            charge_id = data["data"]["id"]
            order_id = data["data"]["order"]["id"]

            print(f"✅ Pagamento confirmado para o pedido {order_id} (charge {charge_id})")

            # Aqui você pode salvar no Firestore (exemplo)
            doc_ref = db.collection("pagamentos_confirmados").document(order_id)
            doc_ref.set({
                "charge_id": charge_id,
                "order_id": order_id,
                "timestamp": firestore.SERVER_TIMESTAMP
            })

            return jsonify({"status": "sucesso", "order_id": order_id}), 200

        else:
            print("⚠️ Evento não tratado:", data["type"])
            return jsonify({"status": "ignorado"}), 200

    except Exception as e:
        print("❌ Erro ao processar webhook:", e)
        return jsonify({"erro": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=False)
