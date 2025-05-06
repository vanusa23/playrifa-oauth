from flask import Flask, request, jsonify
import requests
import os
import base64
import json  # Para logs de erro mais detalhados

app = Flask(__name__)

# Carrega as variáveis de ambiente
PAGARME_API_KEY = os.environ.get("PAGARME_API_KEY")
PLATFORM_RECIPIENT_ID = os.environ.get("PLATFORM_RECIPIENT_ID")

# Validações iniciais das variáveis de ambiente
if not PAGARME_API_KEY:
    print("ERRO CRÍTICO: Variável de ambiente PAGARME_API_KEY não definida!")
if not PLATFORM_RECIPIENT_ID:
    print("ERRO CRÍTICO: Variável de ambiente PLATFORM_RECIPIENT_ID não definida!")

# Constantes
PAGARME_API_BASE_URL = "https://api.pagar.me/core/v5"
DEFAULT_SUCCESS_URL = "https://playrifa.com/sucesso"

@app.route("/criar-pedido", methods=["POST"])
def criar_pedido():
    if not PAGARME_API_KEY or not PLATFORM_RECIPIENT_ID:
        return jsonify({"error": "Erro interno no servidor: Chaves não configuradas."}), 500

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Requisição inválida: Corpo JSON ausente."}), 400

        required_fields_common = [
            "valor", "customerName", "customerEmail", "customerDocument",
            "customerAddressStreet", "customerAddressNumber", "customerAddressNeighborhood",
            "customerAddressCity", "customerAddressState", "customerAddressZipCode",
            "title"
        ]
        missing_fields = [field for field in required_fields_common if field not in data or not data[field]]
        if missing_fields:
            return jsonify({"error": "Campos obrigatórios ausentes: " + ", ".join(missing_fields)}), 400

        valor = data["valor"]
        vendedor_recipient_id = data.get("vendedorRecipientId")
        is_split_order = bool(vendedor_recipient_id)

        payload = {
            "items": [{
                "amount": int(valor * 100),
                "description": data["title"],
                "quantity": 1
            }],
            "customer": {
                "name": data["customerName"],
                "email": data["customerEmail"],
                "document": "".join(filter(str.isdigit, data["customerDocument"])),
                "type": data.get("customerType", "individual"),
                "address": {
                    "country": data.get("customerAddressCountry", "BR"),
                    "state": data["customerAddressState"],
                    "city": data["customerAddressCity"],
                    "neighborhood": data["customerAddressNeighborhood"],
                    "street": data["customerAddressStreet"],
                    "number": data["customerAddressNumber"],
                    "zip_code": "".join(filter(str.isdigit, data["customerAddressZipCode"]))
                }
            },
            "payments": [{
                "payment_method": "checkout",
                "checkout": {
                    "expires_in": 3600,
                    "accepted_payment_methods": ["credit_card", "pix"],
                    "success_url": data.get("successUrl", DEFAULT_SUCCESS_URL),
                    "customer_editable": False,
                    "billing_address_editable": False,
                    "skip_checkout_success_page": True,
                    "pix": {
                        "expires_in": 3600
                    }
                }
            }],
            "closed": False
        }

        if is_split_order:
            payload["split"] = [
                {
                    "recipient_id": vendedor_recipient_id,
                    "type": "percentage",
                    "percentage": 95,
                    "options": {
                        "charge_processing_fee": True,
                        "charge_remainder_fee": True,
                        "liable": True
                    }
                },
                {
                    "recipient_id": PLATFORM_RECIPIENT_ID,
                    "type": "percentage",
                    "percentage": 5,
                    "options": {
                        "charge_processing_fee": True,
                        "charge_remainder_fee": True,
                        "liable": True
                    }
                }
            ]
            print("[INFO] Configurando pedido com SPLIT.")
        else:
            print("[INFO] Configurando pedido SIMPLES (sem split).")

        auth_string = f"{PAGARME_API_KEY}:"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        response = requests.post(
            f"{PAGARME_API_BASE_URL}/orders",
            json=payload,
            headers=headers
        )

        try:
            result = response.json()
        except json.JSONDecodeError:
            return jsonify({"error": "Erro de comunicação com o gateway de pagamento."}), 502

        if response.status_code >= 200 and response.status_code < 300:
            checkout_url = None
            charge_id = None
            order_id = result.get("id")

            if result.get("checkouts"):
                checkout_url = result["checkouts"][0].get("payment_url")
            if result.get("charges"):
                charge_id = result["charges"][0].get("id")

            return jsonify({
                "checkoutUrl": checkout_url,
                "orderId": order_id,
                "chargeId": charge_id
            }), response.status_code
        else:
            return jsonify({
                "error": result.get("message", "Erro desconhecido do Pagar.me"),
                "details": result.get("errors", {})
            }), response.status_code

    except KeyError as e:
        return jsonify({"error": f"Dado ausente na requisição: {e}"}), 400
    except Exception as e:
        print(f"[ERRO] Exceção não tratada no endpoint /criar-pedido: {e}")
        return jsonify({"error": "Erro interno no servidor ao processar o pedido."}), 500

# ✅ Webhook com captura de cobrança
@app.route("/pagarme", methods=["POST"])
def pagarme_webhook():
    try:
        payload = request.get_json()
        print("[WEBHOOK] Payload recebido:", json.dumps(payload))

        if payload.get("type") == "charge.paid":
            charge_id = payload.get("data", {}).get("id")
            amount = payload.get("data", {}).get("amount")

            if not charge_id or not amount:
                return jsonify({"error": "charge_id ou amount ausente"}), 400

            print(f"[WEBHOOK] Iniciando captura da cobrança {charge_id} com valor {amount} centavos.")

            auth_string = f"{PAGARME_API_KEY}:"
            encoded_auth = base64.b64encode(auth_string.encode()).decode()
            headers = {
                "Authorization": f"Basic {encoded_auth}",
                "Content-Type": "application/json"
            }

            response = requests.post(
                f"{PAGARME_API_BASE_URL}/charges/{charge_id}/capture",
                json={"amount": amount},
                headers=headers
            )

            print(f"[WEBHOOK] Resposta da captura - Status: {response.status_code}")
            print("[WEBHOOK] Corpo da resposta:", response.text)

            if response.status_code in [200, 201]:
                return jsonify({"message": "Cobrança capturada com sucesso!"}), 200
            else:
                return jsonify({"error": "Falha ao capturar cobrança", "details": response.text}), 502

        return jsonify({"message": "Evento ignorado."}), 200

    except Exception as e:
        print(f"[WEBHOOK] Erro ao processar webhook: {e}")
        return jsonify({"error": "Erro interno no servidor"}), 500

@app.route("/")
def index():
    return "Servidor PlayRifa Checkout/Webhook ativo."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
