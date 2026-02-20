"""Flask application for Agnar's Cellar."""

import os
import uuid
import base64
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_from_directory

import database
from wine_analyzer import analyze_wine_image, identify_wine_image, validate_wine_data

# Cloudinary configuration
CLOUDINARY_URL = os.environ.get("CLOUDINARY_URL")
USE_CLOUDINARY = CLOUDINARY_URL is not None

if USE_CLOUDINARY:
    import cloudinary
    import cloudinary.uploader
    cloudinary.config(cloudinary_url=CLOUDINARY_URL)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload

UPLOAD_FOLDER = Path(__file__).parent / "static" / "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def allowed_file(filename):
    """Check if file extension is allowed."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_file(file_content, filename):
    """Save uploaded file and return path/URL."""
    if not file_content or not filename:
        return None, None

    if not allowed_file(filename):
        return None, None

    # Determine media type
    ext = filename.rsplit(".", 1)[1].lower() if "." in filename else "jpg"
    media_types = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp"
    }
    media_type = media_types.get(ext, "image/jpeg")

    if USE_CLOUDINARY:
        # Upload to Cloudinary using base64 data URI
        try:
            b64_data = base64.standard_b64encode(file_content).decode("utf-8")
            data_uri = f"data:{media_type};base64,{b64_data}"
            result = cloudinary.uploader.upload(
                data_uri,
                folder="wine-collection",
                resource_type="image"
            )
            # Return (cloudinary_url, public_id)
            return result["secure_url"], result["public_id"]
        except Exception as e:
            print(f"Cloudinary upload error: {e}", flush=True)
            return None, None
    else:
        # Save locally
        new_filename = f"{uuid.uuid4()}.{ext}"
        filepath = UPLOAD_FOLDER / new_filename
        with open(filepath, "wb") as f:
            f.write(file_content)
        return f"uploads/{new_filename}", None


def get_image_for_analysis(file):
    """Get image data for AI analysis. Returns (base64_data, media_type, file_content, filename)."""
    if not file:
        return None, None, None, None

    # Read file content
    content = file.read()

    # Determine media type
    filename = file.filename if file.filename else "image.jpg"
    ext = filename.rsplit(".", 1)[1].lower() if "." in filename else "jpg"
    media_types = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp"
    }
    media_type = media_types.get(ext, "image/jpeg")

    # Encode to base64
    b64_data = base64.standard_b64encode(content).decode("utf-8")

    return b64_data, media_type, content, filename


def delete_cloudinary_image(public_id):
    """Delete an image from Cloudinary."""
    if USE_CLOUDINARY and public_id:
        try:
            cloudinary.uploader.destroy(public_id)
        except Exception as e:
            print(f"Cloudinary delete error: {e}")


# Routes


@app.route("/")
def index():
    """Serve the main page."""
    return render_template("index.html")


@app.route("/static/uploads/<path:filename>")
def serve_upload(filename):
    """Serve uploaded files (only used when not using Cloudinary)."""
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

    # Delete the image
    if wine.get("image_path"):
        if USE_CLOUDINARY and wine.get("cloudinary_id"):
            delete_cloudinary_image(wine["cloudinary_id"])
        elif not USE_CLOUDINARY:
            image_file = Path(__file__).parent / "static" / wine["image_path"]
            if image_file.exists():
                try:
                    image_file.unlink()
                except OSError:
                    pass

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

    # Get image data for analysis
    b64_data, media_type, file_content, filename = get_image_for_analysis(file)
    if not b64_data:
        return jsonify({"error": "Failed to process image"}), 500

    # Analyze with Claude
    result = analyze_wine_image(image_base64=b64_data, media_type=media_type)

    # Validate and clean the data
    cleaned = validate_wine_data(result)

    # Save the file (after analysis succeeds)
    image_url, cloudinary_id = save_uploaded_file(file_content, filename)

    if image_url:
        cleaned["image_path"] = image_url
        if cloudinary_id:
            cleaned["cloudinary_id"] = cloudinary_id

    # Check if this wine already exists in the database
    if not cleaned.get("error") and not cleaned.get("needs_clarification"):
        existing = database.find_matching_wine(
            name=cleaned.get("name"),
            producer=cleaned.get("producer"),
            vintage=cleaned.get("vintage")
        )
        if existing:
            cleaned["existing_wine"] = existing
            cleaned["is_duplicate"] = True

    return jsonify(cleaned)


@app.route("/api/drink", methods=["POST"])
def drink_wine():
    """Identify a wine from photo and reduce quantity by 1."""
    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type. Allowed: png, jpg, jpeg, gif, webp"}), 400

    # Get image data for analysis (don't save, just analyze)
    b64_data, media_type, _, _ = get_image_for_analysis(file)
    if not b64_data:
        return jsonify({"error": "Failed to process image"}), 500

    # Identify the wine
    result = identify_wine_image(image_base64=b64_data, media_type=media_type)

    if result.get("error"):
        return jsonify(result), 400

    # Find matching wine in database
    existing = database.find_matching_wine(
        name=result.get("name"),
        producer=result.get("producer"),
        vintage=result.get("vintage")
    )

    if not existing:
        return jsonify({
            "error": "Wine not found in collection",
            "identified": result
        }), 404

    # Check if there's any quantity left
    if existing.get("quantity", 0) <= 0:
        return jsonify({
            "error": "No bottles left of this wine",
            "wine": existing
        }), 400

    # Reduce quantity by 1
    database.increment_wine_quantity(existing["id"], -1)
    updated_wine = database.get_wine(existing["id"])

    return jsonify({
        "message": f"Enjoyed a bottle of {existing['name']}!",
        "wine": updated_wine,
        "previous_quantity": existing["quantity"],
        "new_quantity": updated_wine["quantity"]
    })


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Get collection statistics."""
    stats = database.get_stats()
    return jsonify(stats)


@app.route("/api/debug", methods=["GET"])
def debug_env():
    """Debug endpoint to check environment."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    return jsonify({
        "api_key_set": bool(api_key),
        "cloudinary_configured": USE_CLOUDINARY,
        "database_type": "postgresql" if os.environ.get("DATABASE_URL") else "sqlite"
    })


# Ensure upload directory exists on startup (for local dev)
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# Initialize database on startup
database.init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug, host="0.0.0.0", port=port)
