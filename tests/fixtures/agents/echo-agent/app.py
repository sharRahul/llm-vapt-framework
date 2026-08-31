from flask import Flask, request

app = Flask(__name__)


@app.get("/health")
def health():
    return "ok"


@app.get("/get")
def get_response():
    return request.args.get("msg", "")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
