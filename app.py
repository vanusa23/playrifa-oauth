from flask import Flask, request, jsonify
import requests
import os
import base64
import json # Para logs de erro mais detalhados

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
DEFAULT_SUCCESS_URL = "https://playrifa.com/sucesso" # Ajuste se necessário

@app.route("/criar-pedido", methods=["POST"])
def criar_pedido():
    if not PAGARME_API_KEY or not PLATFORM_RECIPIENT_ID:
        return jsonify({"error": "Erro interno no servidor: Chaves não configuradas."}), 500

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Requisição inválida: Corpo JSON ausente."}), 400

        # Validações básicas dos dados recebidos (campos comuns)
        required_fields_common = [
            "valor", "customerName", "customerEmail", "customerDocument",
            "customerAddressStreet", "customerAddressNumber", "customerAddressNeighborhood",
            "customerAddressCity", "customerAddressState", "customerAddressZipCode",
            "title"
        ]
        missing_fields = [field for field in required_fields_common if field not in data or not data[field]]
        if missing_fields:
            error_message = "Campos obrigatórios ausentes: " + ", ".join(missing_fields)
            return jsonify({"error": error_message}), 400

        valor = data["valor"]
        # Verifica se é um pedido com split (presença de vendedorRecipientId)
        vendedor_recipient_id = data.get("vendedorRecipientId")
        is_split_order = bool(vendedor_recipient_id)

        if is_split_order and not vendedor_recipient_id:
             return jsonify({"error": "Campo obrigatório ausente para split: vendedorRecipientId"}), 400

        # --- Construção do Payload Base ---
        payload = {
            "items": [
                {
                    "amount": int(valor * 100), # Valor em centavos
                    "description": data["title"],
                    "quantity": 1
                }
            ],
            "customer": {
                "name": data["customerName"],
                "email": data["customerEmail"],
                "document": "".join(filter(str.isdigit, data["customerDocument"])), # Apenas números
                "type": data.get("customerType", "individual"),
                "address": {
                    "country": data.get("customerAddressCountry", "BR"),
                    "state": data["customerAddressState"],
                    "city": data["customerAddressCity"],
                    "neighborhood": data["customerAddressNeighborhood"],
                    "street": data["customerAddressStreet"],
                    "number": data["customerAddressNumber"],
                    "zip_code": "".join(filter(str.isdigit, data["customerAddressZipCode"])) # Apenas números
                }
            },
            "payments": [
                {
                    "payment_method": "checkout",
                    "checkout": {
                        "expires_in": 3600, # 1 hora para pagar
                        "accepted_payment_methods": ["credit_card", "pix"],
                        "success_url": data.get("successUrl", DEFAULT_SUCCESS_URL),
                        "customer_editable": False,
                        "billing_address_editable": False,
                        "skip_checkout_success_page": True,
                        "pix": { 
                            "expires_in": 3600
                        }
                    }
                }
            ],
            "closed": False # Manter False para permitir captura posterior via webhook
        }

        # --- Adiciona o Bloco Split APENAS se vendedorRecipientId foi fornecido ---
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
            # Se não for split, o pedido pode ser fechado imediatamente?
            # Depende se você precisa de alguma ação via webhook para pedidos simples.
            # Vamos manter "closed": False por consistência, mas poderia ser True.
            # payload["closed"] = True 
            print("[INFO] Configurando pedido SIMPLES (sem split).")

        # --- Autenticação Basic Auth ---
        auth_string = f"{PAGARME_API_KEY}:"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        print(f"[INFO] Enviando requisição para criar pedido Pagar.me...")
        # print(f"[DEBUG] Payload: {json.dumps(payload)}") # Descomentar para depuração

        response = requests.post(
            f"{PAGARME_API_BASE_URL}/orders",
            json=payload,
            headers=headers
        )

        print(f"[INFO] Resposta Pagar.me - Status: {response.status_code}")
        # print(f"[DEBUG] Resposta Body: {response.text}") # Descomentar para depuração

        # --- Processamento da Resposta --- 
        try:
            result = response.json()
        except json.JSONDecodeError:
            print(f"[ERRO] Falha ao decodificar JSON da resposta Pagar.me. Status: {response.status_code}, Body: {response.text}")
            return jsonify({"error": "Erro de comunicação com o gateway de pagamento."}), 502

        if response.status_code >= 200 and response.status_code < 300:
            checkout_url = None
            charge_id = None
            order_id = result.get("id")

            if result.get("checkouts") and isinstance(result["checkouts"], list) and len(result["checkouts"]) > 0:
                checkout_url = result["checkouts"][0].get("payment_url")
            
            if result.get("charges") and isinstance(result["charges"], list) and len(result["charges"]) > 0:
                charge_id = result["charges"][0].get("id")

            if not checkout_url:
                 print(f"[ALERTA] Pedido {order_id} criado, mas checkout_url não encontrado na resposta.")

            print(f"[INFO] Pedido {order_id} criado. Charge ID: {charge_id}. Checkout URL: {checkout_url}")
            return jsonify({
                "checkoutUrl": checkout_url,
                "orderId": order_id,
                "chargeId": charge_id
            }), response.status_code
        else:
            error_message = result.get("message", "Erro desconhecido do Pagar.me")
            error_details = result.get("errors", {})
            print(f"[ERRO] Pagar.me retornou erro {response.status_code}: {error_message} - Detalhes: {json.dumps(error_details)}")
            return jsonify({
                "error": f"Gateway de pagamento recusou o pedido: {error_message}",
                "details": error_details
            }), response.status_code

    except KeyError as e:
        print(f"[ERRO] Campo obrigatório ausente na requisição: {e}")
        return jsonify({"error": f"Dado ausente na requisição: {e}"}), 400
    except Exception as e:
        print(f"[ERRO] Exceção não tratada no endpoint /criar-pedido: {e}")
        return jsonify({"error": "Erro interno no servidor ao processar o pedido."}), 500

# Endpoint de Webhook (mantido do exemplo anterior, ajuste conforme necessário)
@app.route("/pagarme", methods=["POST"])
def pagarme_webhook():
    # TODO: Implementar validação de assinatura do webhook aqui!
    # ... (código do webhook)
    pass

@app.route("/")
def index():
    return "Servidor PlayRifa Checkout/Webhook ativo."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
