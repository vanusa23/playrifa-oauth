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

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=3000)
