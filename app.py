"""Flask application for Wine Collection Manager."""

import os
import uuid
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_from_directory

import database
from wine_analyzer import analyze_wine_image, validate_wine_data

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload

UPLOAD_FOLDER = Path(__file__).parent / "static" / "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def allowed_file(filename):
    """Check if file extension is allowed."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_file(file):
    """Save uploaded file with unique name and return path."""
    if not file or not file.filename:
        return None

    if not allowed_file(file.filename):
        return None

    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = UPLOAD_FOLDER / filename
    file.save(filepath)
    return f"uploads/{filename}"


# Routes


@app.route("/")
def index():
    """Serve the main page."""
    return render_template("index.html")


@app.route("/static/uploads/<path:filename>")
def serve_upload(filename):
    """Serve uploaded files."""
    return send_from_directory(UPLOAD_FOLDER, filename)


# API Endpoints


@app.route("/api/wines", methods=["GET"])
def get_wines():
    """Get all wines with optional filtering."""
    filters = {
        "country": request.args.get("country"),
        "region": request.args.get("region"),
        "style": request.args.get("style"),
        "vintage_min": request.args.get("vintage_min", type=int),
        "vintage_max": request.args.get("vintage_max", type=int),
        "drinking_now": request.args.get("drinking_now") == "true",
        "search": request.args.get("search"),
        "sort_by": request.args.get("sort_by", "name"),
        "sort_order": request.args.get("sort_order", "asc")
    }
    # Remove None values
    filters = {k: v for k, v in filters.items() if v is not None and v != ""}

    wines = database.get_all_wines(filters if filters else None)
    return jsonify(wines)


@app.route("/api/wines", methods=["POST"])
def create_wine():
    """Create a new wine entry."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    if not data.get("name"):
        return jsonify({"error": "Wine name is required"}), 400

    wine_id = database.create_wine(data)
    wine = database.get_wine(wine_id)
    return jsonify(wine), 201


@app.route("/api/wines/<int:wine_id>", methods=["GET"])
def get_wine(wine_id):
    """Get a single wine by ID."""
    wine = database.get_wine(wine_id)
    if not wine:
        return jsonify({"error": "Wine not found"}), 404
    return jsonify(wine)


@app.route("/api/wines/<int:wine_id>", methods=["PUT"])
def update_wine(wine_id):
    """Update a wine entry."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    success = database.update_wine(wine_id, data)
    if not success:
        return jsonify({"error": "Wine not found or no changes made"}), 404

    wine = database.get_wine(wine_id)
    return jsonify(wine)


@app.route("/api/wines/<int:wine_id>", methods=["DELETE"])
def delete_wine(wine_id):
    """Delete a wine entry."""
    # Get wine to check for image
    wine = database.get_wine(wine_id)
    if not wine:
        return jsonify({"error": "Wine not found"}), 404

    # Delete the image file if it exists
    if wine.get("image_path"):
        image_file = Path(__file__).parent / "static" / wine["image_path"]
        if image_file.exists():
            try:
                image_file.unlink()
            except OSError:
                pass  # Ignore deletion errors

    success = database.delete_wine(wine_id)
    if not success:
        return jsonify({"error": "Failed to delete wine"}), 500

    return jsonify({"message": "Wine deleted successfully"})


@app.route("/api/analyze", methods=["POST"])
def analyze_image():
    """Upload and analyze a wine bottle image."""
    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type. Allowed: png, jpg, jpeg, gif, webp"}), 400

    # Save the file
    image_path = save_uploaded_file(file)
    if not image_path:
        return jsonify({"error": "Failed to save image"}), 500

    # Analyze with Claude
    full_path = Path(__file__).parent / "static" / image_path
    result = analyze_wine_image(image_path=str(full_path))

    # Validate and clean the data
    cleaned = validate_wine_data(result)

    # Add the image path to the result
    cleaned["image_path"] = image_path

    return jsonify(cleaned)


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Get collection statistics."""
    stats = database.get_stats()
    return jsonify(stats)


# Ensure upload directory exists on startup
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# Initialize database on startup
database.init_db()

if __name__ == "__main__":
    # Local development
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5001)))
