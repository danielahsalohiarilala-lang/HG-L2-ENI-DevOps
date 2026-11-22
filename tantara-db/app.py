import os
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def home():
    return '<h1>Tantara SaaS - API Running(Docker)</h1><a href="/docs">/docs</a> - <a href="/health">Health</a>'

@app.route("/health")
def health():
    return jsonify({"status":"healthy"})

@app.route("/docs")
def docs_route():
    try:
        base = "/app/docs/ARCHITECTURE.md"
        if os.path.exists(base):
            with open(base, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return f"<html><meta charset='utf-8'><body><h1>ARCHITECTURE.md</h1><pre>{content}</pre></body></html>", 200
        else:
            files = os.listdir("/app")
            docs_files = []
            if os.path.exists("/app/docs"):
                docs_files = os.listdir("/app/docs")
            return f"File not found at {base}. /app contains {files}, /app/docs contains {docs_files}", 404
    except Exception as e:
        import traceback
        return f"ERROR: {str(e)}<br><pre>{traceback.format_exec()}</pre>", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
