from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

PAGARME_API_KEY = os.environ.get('PAGARME_API_KEY')
PLATFORM_RECIPIENT_ID = os.environ.get('PLATFORM_RECIPIENT_ID')

@app.route("/criar-pedido", methods=["POST"])
def criar_pedido():
    try:
        data = request.get_json()

        payload = {
            "amount": int(data["valor"] * 100),
            "customer": {
                "name": data["customerName"],
                "email": data["customerEmail"],
                "document": data["customerDocument"],
                "type": data.get("customerType", "individual"),
                "address": {
                    "street": data["customerAddressStreet"],
                    "number": data["customerAddressNumber"],
                    "neighborhood": data["customerAddressNeighborhood"],
                    "city": data["customerAddressCity"],
                    "state": data["customerAddressState"],
                    "zip_code": data["customerAddressZipCode"],
                    "country": data.get("customerAddressCountry", "BR"),
                    "line_1": f"{data['customerAddressNumber']}, {data['customerAddressStreet']}, {data['customerAddressNeighborhood']}"
                }
            },
            "items": [
                {
                    "amount": int(data["valor"] * 100),
                    "description": data["title"],
                    "quantity": 1
                }
            ],
            "split": [
                {
                    "amount": int(data["valor"] * 95),  # 95%
                    "recipient_id": data["vendedorRecipientId"],
                    "type": "percentage",
                    "options": {
                        "charge_processing_fee": True
                    }
                },
                {
                    "amount": int(data["valor"] * 5),  # 5%
                    "recipient_id": PLATFORM_RECIPIENT_ID,
                    "type": "percentage",
                    "options": {
                        "charge_processing_fee": False
                    }
                }
            ],
            "charges": [
                {
                    "payment_method": "pix",
                    "payment_method_options": {
                        "pix": {
                            "expires_in": 3600
                        }
                    }
                }
            ]
        }

        headers = {
            "Authorization": f"Basic {PAGARME_API_KEY}",
            "Content-Type": "application/json"
        }

        response = requests.post(
            "https://api.pagar.me/core/v5/orders",
            json=payload,
            headers=headers
        )

        result = response.json()

        checkout_url = None
        charge_id = None
        order_id = result.get("id")

        if "charges" in result and len(result["charges"]) > 0:
            charge = result["charges"][0]
            charge_id = charge.get("id")
            checkout_url = charge.get("checkout_url")

        return jsonify({
            "checkoutUrl": checkout_url,
            "orderId": order_id,
            "chargeId": charge_id,
            "fullResponse": result
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/")
def index():
    return "Servidor PlayRifa Checkout ativo."


if __name__ == "__main__":
    app.run(debug=True)
