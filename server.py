import base64
import json
import os
import tempfile

import psycopg2
from flask import Flask, jsonify, request, send_from_directory
from google.cloud import aiplatform
from google.cloud.aiplatform.gapic.schema import predict

# Render only supports plain env vars, not mounted secret files, so the GCP
# credentials JSON travels as a string in GOOGLE_APPLICATION_CREDENTIALS_JSON
# and gets written out to a temp file here, where the google-cloud libraries
# expect to find it (via GOOGLE_APPLICATION_CREDENTIALS).
_creds_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
if _creds_json:
    _creds_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    _creds_file.write(_creds_json)
    _creds_file.close()
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _creds_file.name

app = Flask(__name__, static_folder=".", static_url_path="")

DATABASE_URL = os.environ["DATABASE_URL"]

# Vertex AI endpoint serving the trained ripening-stage classifier.
GCP_PROJECT = "861128124880"
GCP_ENDPOINT_ID = "8881934643767541760"
GCP_LOCATION = "us-central1"

STAGE_COPY = {
    1: {"status": "ripening", "days": 4},
    2: {"status": "ripening", "days": 3},
    3: {"status": "ripening", "days": 1},
    4: {"status": "ready", "days": 0},
    5: {"status": "ready", "days": 0},
}

_prediction_client = None


def _get_prediction_client():
    global _prediction_client
    if _prediction_client is None:
        client_options = {"api_endpoint": f"{GCP_LOCATION}-aiplatform.googleapis.com"}
        _prediction_client = aiplatform.gapic.PredictionServiceClient(client_options=client_options)
    return _prediction_client


def classify_avocado_image(image_bytes: bytes) -> dict:
    """Send a photo to the Vertex AI endpoint and return the top ripening-stage prediction."""
    client = _get_prediction_client()

    encoded_content = base64.b64encode(image_bytes).decode("utf-8")
    instance = predict.instance.ImageClassificationPredictionInstance(
        content=encoded_content,
    ).to_value()
    parameters = predict.params.ImageClassificationPredictionParams(
        confidence_threshold=0.5,
        max_predictions=5,
    ).to_value()

    endpoint = client.endpoint_path(
        project=GCP_PROJECT, location=GCP_LOCATION, endpoint=GCP_ENDPOINT_ID
    )
    response = client.predict(endpoint=endpoint, instances=[instance], parameters=parameters)

    prediction = response.predictions[0]
    display_names = prediction["displayNames"]
    confidences = prediction["confidences"]

    # The model's labels are the ripening stage numbers ("1".."5") as strings;
    # take whichever label came back with the highest confidence.
    best_idx = max(range(len(confidences)), key=lambda i: confidences[i])
    stage = int(display_names[best_idx])
    confidence = round(confidences[best_idx] * 100)

    return {
        "stage": stage,
        "confidence": confidence,
        **STAGE_COPY[stage],
    }


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/login", methods=["POST"])
def login():
    email = (request.get_json(silent=True) or {}).get("email", "").strip().lower()
    if not email:
        return jsonify({"error": "email is required"}), 400

    conn = psycopg2.connect(DATABASE_URL)
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM users WHERE lower(email) = %s", (email,))
        row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        return jsonify({"error": "no account with that email"}), 404
    return jsonify({"email": email, "name": row[0]})


@app.route("/api/classify", methods=["POST"])
def classify():
    if "image" not in request.files:
        return jsonify({"error": "image file is required"}), 400

    image_bytes = request.files["image"].read()
    try:
        result = classify_avocado_image(image_bytes)
    except Exception as e:
        return jsonify({"error": str(e)}), 502
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
