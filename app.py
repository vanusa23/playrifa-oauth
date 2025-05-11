import os
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Webhook do PlayRifa ativo no Render!", 200

@app.route('/webhook', methods=['POST'])
def webhook_mercadopago():
    data = request.get_json()
    print("📩 Webhook recebido do Mercado Pago:", data)
    return jsonify({"status": "recebido"}), 200

@app.route('/criar_pagamento', methods=['GET'])
def criar_pagamento():
    import requests

    ACCESS_TOKEN = "SEU_ACCESS_TOKEN_AQUI"  # substitua pelo seu token de produção
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    body = {
        "items": [{
            "id": "RIFA001",
            "title": "Pagamento de Rifa",
            "description": "Ativação de rifa no PlayRifa",
            "quantity": 1,
            "currency_id": "BRL",
            "unit_price": 1.00
        }],
        "payer": {
            "first_name": "Djuliano",
            "last_name": "Freitas"
        },
        "notification_url": "https://playrifa-oauth.onrender.com/webhook",
        "external_reference": "playrifa_0001"
    }

    response = requests.post(
        "https://api.mercadopago.com/checkout/preferences",
        headers=headers,
        data=json.dumps(body)
    )

    data = response.json()
    link = data.get("init_point")

    print("🔗 Link de pagamento gerado:", link)
    return jsonify({"link_pagamento": link}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
