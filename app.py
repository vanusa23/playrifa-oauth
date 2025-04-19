from flask import Flask, request, redirect

app = Flask(__name__)

@app.route("/oauth")
def oauth_redirect():
    code = request.args.get("code")
    state = request.args.get("state")
    return redirect(f"playrifa://oauth?code={code}&state={state}")
