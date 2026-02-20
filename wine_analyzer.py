"""Claude API integration for wine label analysis."""

import os
import base64
import json
from anthropic import Anthropic

_client = None


def get_client():
    """Get or create the Anthropic client."""
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
        _client = Anthropic(api_key=api_key)
    return _client

ANALYSIS_PROMPT = """Analyze this wine bottle label image and extract as much information as possible.

Return a JSON object with the following fields (use null for any fields you cannot determine):

{
    "name": "Full wine name",
    "producer": "Winery/Producer name",
    "vintage": 2020,  // Year as integer, or null if non-vintage
    "country": "Country of origin",
    "region": "Wine region (e.g., Napa Valley, Burgundy)",
    "appellation": "Specific appellation/AOC/DOC if visible",
    "style": "Red|White|Rosé|Sparkling|Dessert|Fortified",
    "grape_varieties": ["Grape1", "Grape2"],  // Array of grape varieties
    "alcohol_percentage": 13.5,  // As decimal number
    "drinking_window_start": 2024,  // Estimated year to start drinking
    "drinking_window_end": 2030,  // Estimated year by which to drink
    "score": 88,  // Estimated score 0-100 based on producer reputation and vintage
    "description": "Brief description of the wine and producer",
    "tasting_notes": {
        "aromas": ["aroma1", "aroma2"],
        "flavors": ["flavor1", "flavor2"],
        "body": "Light|Medium|Full",
        "tannins": "Low|Medium|High",  // For reds
        "acidity": "Low|Medium|High",
        "finish": "Short|Medium|Long"
    },
    "needs_clarification": false,  // Set to true if you're uncertain about key details
    "clarification_questions": []  // Array of questions if uncertain, e.g. ["Is this wine red or white?"]
}

Important guidelines:
- Only include information you can see or reasonably infer from the label
- For drinking windows, consider the wine style, region, and vintage quality
- For scores, be conservative and base it on typical quality for the producer/region
- If the image is not a wine bottle or label, return {"error": "Not a wine label image"}

CRITICAL - Wine style clarification:
- Many Burgundy appellations (Santenay, Meursault, Pommard, Gevrey-Chambertin, Bourgogne, etc.) can be BOTH red and white
- Many producers make both red AND white versions with nearly identical labels
- If you CANNOT see the actual wine color through the bottle, AND the appellation/region produces both styles, you MUST:
  1. Set "needs_clarification": true
  2. Add "Is this wine red or white?" to clarification_questions
  3. Set "style": null (do not guess!)
- Only set the style confidently if you can see the wine color, or if the label explicitly states "Blanc", "Rouge", "White", "Red", or lists a grape that's clearly one color (e.g., Chardonnay = white, Pinot Noir = typically red)
- When in doubt, ASK. It's better to ask than to guess wrong.

Return ONLY the JSON object, no additional text."""


IDENTIFY_PROMPT = """Look at this wine bottle image and identify the wine.

Return a JSON object with just the key identifying information:

{
    "name": "Full wine name",
    "producer": "Winery/Producer name",
    "vintage": 2020  // Year as integer, or null if non-vintage
}

If you cannot identify the wine, return {"error": "Cannot identify wine"}

Return ONLY the JSON object, no additional text."""


def analyze_wine_image(image_path=None, image_base64=None, media_type="image/jpeg"):
    """
    Analyze a wine bottle image using Claude's vision capabilities.

    Args:
        image_path: Path to the image file (optional if image_base64 provided)
        image_base64: Base64-encoded image data (optional if image_path provided)
        media_type: MIME type of the image (default: image/jpeg)

    Returns:
        dict: Extracted wine information or error
    """
    if not image_path and not image_base64:
        return {"error": "No image provided"}

    # Read and encode image if path provided
    if image_path and not image_base64:
        try:
            with open(image_path, "rb") as f:
                image_base64 = base64.standard_b64encode(f.read()).decode("utf-8")

            # Determine media type from extension
            ext = os.path.splitext(image_path)[1].lower()
            media_types = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp"
            }
            media_type = media_types.get(ext, "image/jpeg")
        except FileNotFoundError:
            return {"error": f"Image file not found: {image_path}"}
        except Exception as e:
            return {"error": f"Error reading image: {str(e)}"}

    try:
        client = get_client()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": ANALYSIS_PROMPT
                        }
                    ]
                }
            ]
        )

        # Parse the response
        response_text = response.content[0].text.strip()

        # Try to extract JSON from the response
        # Sometimes the model might wrap it in markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.startswith("```") and not in_json:
                    in_json = True
                    continue
                elif line.startswith("```") and in_json:
                    break
                elif in_json:
                    json_lines.append(line)
            response_text = "\n".join(json_lines)

        result = json.loads(response_text)
        return result

    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse AI response: {str(e)}", "raw_response": response_text}
    except Exception as e:
        return {"error": f"API error: {str(e)}"}


def identify_wine_image(image_path=None, image_base64=None, media_type="image/jpeg"):
    """
    Identify a wine from a bottle image (for drink/find operations).
    Returns just name, producer, vintage for matching.
    """
    if not image_path and not image_base64:
        return {"error": "No image provided"}

    if image_path and not image_base64:
        try:
            with open(image_path, "rb") as f:
                image_base64 = base64.standard_b64encode(f.read()).decode("utf-8")
            ext = os.path.splitext(image_path)[1].lower()
            media_types = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp"
            }
            media_type = media_types.get(ext, "image/jpeg")
        except FileNotFoundError:
            return {"error": f"Image file not found: {image_path}"}
        except Exception as e:
            return {"error": f"Error reading image: {str(e)}"}

    try:
        client = get_client()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": IDENTIFY_PROMPT
                        }
                    ]
                }
            ]
        )

        response_text = response.content[0].text.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.startswith("```") and not in_json:
                    in_json = True
                    continue
                elif line.startswith("```") and in_json:
                    break
                elif in_json:
                    json_lines.append(line)
            response_text = "\n".join(json_lines)

        return json.loads(response_text)

    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse AI response: {str(e)}"}
    except Exception as e:
        return {"error": f"API error: {str(e)}"}


def validate_wine_data(data):
    """
    Validate and clean wine data from AI analysis.

    Args:
        data: Dictionary of wine data

    Returns:
        dict: Cleaned and validated wine data
    """
    if "error" in data:
        return data

    cleaned = {}

    # Required field
    cleaned["name"] = data.get("name") or "Unknown Wine"

    # String fields
    string_fields = ["producer", "country", "region", "appellation", "description"]
    for field in string_fields:
        value = data.get(field)
        cleaned[field] = value if value else None

    # Style validation
    valid_styles = ["Red", "White", "Rosé", "Sparkling", "Dessert", "Fortified"]
    style = data.get("style")
    cleaned["style"] = style if style in valid_styles else None

    # Integer fields
    vintage = data.get("vintage")
    if vintage is not None:
        try:
            vintage = int(vintage)
            if 1800 <= vintage <= 2100:
                cleaned["vintage"] = vintage
            else:
                cleaned["vintage"] = None
        except (ValueError, TypeError):
            cleaned["vintage"] = None
    else:
        cleaned["vintage"] = None

    # Drinking window
    for field in ["drinking_window_start", "drinking_window_end"]:
        value = data.get(field)
        if value is not None:
            try:
                value = int(value)
                if 1900 <= value <= 2200:
                    cleaned[field] = value
                else:
                    cleaned[field] = None
            except (ValueError, TypeError):
                cleaned[field] = None
        else:
            cleaned[field] = None

    # Score (0-100)
    score = data.get("score")
    if score is not None:
        try:
            score = int(score)
            if 0 <= score <= 100:
                cleaned["score"] = score
            else:
                cleaned["score"] = None
        except (ValueError, TypeError):
            cleaned["score"] = None
    else:
        cleaned["score"] = None

    # Alcohol percentage
    alcohol = data.get("alcohol_percentage")
    if alcohol is not None:
        try:
            alcohol = float(alcohol)
            if 0 <= alcohol <= 100:
                cleaned["alcohol_percentage"] = alcohol
            else:
                cleaned["alcohol_percentage"] = None
        except (ValueError, TypeError):
            cleaned["alcohol_percentage"] = None
    else:
        cleaned["alcohol_percentage"] = None

    # Grape varieties (array)
    grapes = data.get("grape_varieties")
    if isinstance(grapes, list):
        cleaned["grape_varieties"] = [str(g) for g in grapes if g]
    else:
        cleaned["grape_varieties"] = []

    # Tasting notes (object)
    notes = data.get("tasting_notes")
    if isinstance(notes, dict):
        cleaned["tasting_notes"] = notes
    else:
        cleaned["tasting_notes"] = {}

    # Clarification fields
    cleaned["needs_clarification"] = bool(data.get("needs_clarification", False))
    questions = data.get("clarification_questions", [])
    if isinstance(questions, list):
        cleaned["clarification_questions"] = [str(q) for q in questions if q]
    else:
        cleaned["clarification_questions"] = []

    return cleaned
