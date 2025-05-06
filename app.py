import os
from flask import Flask, request, jsonify

app = Flask(__name__)

# Verificar a variável de ambiente
platform_recipient_id = os.getenv("PLATFORM_RECIPIENT_ID")
print(f"🔍 PLATFORM_RECIPIENT_ID carregado: {platform_recipient_id}")

if not platform_recipient_id:
    raise RuntimeError("❌ ERRO CRÍTICO: Variável de ambiente PLATFORM_RECIPIENT_ID não definida!")

@app.route("/", methods=["GET"])
def index():
    return "Webhook do PlayRifa está ativo!"

@app.route("/pagarme", methods=["POST"])
def pagarme_webhook():
    data = request.get_json()
    print("📦 Webhook recebido:", data)

    if data.get("type") == "charge.paid":
        charge = data["data"]
        order_id = charge["order"]["id"]
        print(f"✅ Pagamento confirmado para o pedido {order_id}")
        # Aqui você pode fazer atualizações no Firebase, salvar em banco, etc.

    return jsonify({"status": "ok"}), 200
