from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

@app.route('/')
def index():
    return 'Webhook PlayRifa ativo com sucesso!'

@app.route('/criar_checkout', methods=['POST'])
def criar_checkout():
    data = request.json

    headers = {
        "Authorization": f"Bearer {os.environ['PAGARME_API_KEY']}",
        "Content-Type": "application/json"
    }

    payload = {
        "amount": int(data["valor"] * 100),
        "payment_method": "pix",
        "payment_method_options": {
            "pix": {"expires_in": 3600}
        },
        "customer": {
            "name": data["nome"],
            "email": data["email"],
            "document": data["documento"],
            "type": "individual"
        },
        "split": [
            {
                "amount": int(data["valor"] * 0.95 * 100),
                "recipient_id": data["vendedorRecipientId"],
                "type": "percentage",
                "percentage": 95
            },
            {
                "amount": int(data["valor"] * 0.05 * 100),
                "recipient_id": "re_cma2rrrwg1g8s0l9t2pvl9abx",  # ID fixo do sistema
                "type": "percentage",
                "percentage": 5
            }
        ],
        "checkout": {
            "expires_in": 3600,
            "billing_address_editable": False,
            "customer_editable": False,
            "accepted_payment_methods": ["pix", "credit_card"],
            "success_url": "https://playrifa.com/sucesso"
        }
    }

    response = requests.post(
        "https://api.pagar.me/core/v5/charges",
        headers=headers,
        json=payload
    )

    if response.status_code == 200:
        return jsonify(response.json()), 200
    else:
        return jsonify({"erro": response.text}), 400
