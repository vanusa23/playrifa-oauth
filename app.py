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
            "pix": {
                "expires_in": 3600
            }
        },
        "customer": {
            "name": data["nome"],
            "email": data["email"],
            "document": data["documento"],
            "type": "individual",
            "address": {
                "street": data["endereco_rua"],
                "number": data["endereco_numero"],
                "neighborhood": data["endereco_bairro"],
                "city": data["endereco_cidade"],
                "state": data["endereco_estado"],
                "zip_code": data["endereco_cep"],
                "country": data.get("endereco_pais", "BR")
            }
        },
        "items": [
            {
                "description": data["descricao"],
                "quantity": 1,
                "amount": int(data["valor"] * 100)
            }
        ],
        "split": [
            {
                "amount": int(data["valor"] * 95),  # 95%
                "recipient_id": data["recebedor_id"]
            },
            {
                "amount": int(data["valor"] * 5),  # 5%
                "recipient_id": os.environ['PLATAFORMA_RECIPIENT_ID']
            }
        ]
    }

    response = requests.post(
        "https://api.pagar.me/core/v5/orders",
        headers=headers,
        json=payload
    )

    if response.status_code != 200:
        return jsonify({"erro": "Erro ao criar pedido", "detalhes": response.text}), response.status_code

    response_json = response.json()

    order_id = response_json.get("id")
    charge_id = response_json.get("charges", [{}])[0].get("id")
    checkout_url = response_json.get("charges", [{}])[0].get("checkout", {}).get("url")

    return jsonify({
        "order_id": order_id,
        "charge_id": charge_id,
        "checkout_url": checkout_url
    })
