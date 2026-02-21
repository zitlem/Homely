from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    session,
    redirect,
    url_for,
    Response,
    make_response,
)
import json
import os
from datetime import datetime
import hashlib
import requests
import random
import argparse

app = Flask(__name__)
app.secret_key = "your-secret-key-change-this"  # Change this to a secure secret key

# Configuration
CONFIG_FILE = "homelab_services.json"
CALENDAR_CONFIG_FILE = "calendar_config.json"
SUGGESTIONS_FILE = "suggestions.json"
DEFAULT_VISIBILITY_FILE = "default_visibility.json"
ADMIN_PASSWORD = "admin123"  # Change this to a secure password
DEFAULT_SERVICES = []

# We'll load the calendar config from the JSON file, no need for defaults here


def load_services():
    """Load services from JSON file"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Ensure each service has required properties
                services = []
                for service in data.get("services", []):
                    if "column" not in service:
                        service["column"] = 0
                    if "type" not in service:
                        service["type"] = "url"
                    if "description" not in service:
                        service["description"] = ""
                    services.append(service)
                return services
        else:
            return DEFAULT_SERVICES
    except Exception as e:
        print(f"Error loading services: {e}")
        return DEFAULT_SERVICES


def save_services(services):
    """Save services to JSON file"""
    try:
        # Create backup
        if os.path.exists(CONFIG_FILE):
            backup_file = (
                f"{CONFIG_FILE}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            os.rename(CONFIG_FILE, backup_file)

            # Keep only last 5 backups
            backup_files = sorted(
                [f for f in os.listdir(".") if f.startswith(f"{CONFIG_FILE}.backup.")]
            )
            for backup in backup_files[:-5]:
                os.remove(backup)

        # Save new data
        data = {"services": services, "last_updated": datetime.now().isoformat()}

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving services: {e}")
        return False


def load_calendar_config():
    """Load calendar configuration from JSON file"""
    try:
        if os.path.exists(CALENDAR_CONFIG_FILE):
            with open(CALENDAR_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            # If no config file exists, create it with the default from our separate config file
            print(
                f"Calendar config file not found. Please ensure {CALENDAR_CONFIG_FILE} exists."
            )
            return {"months": {}, "quotes": [], "siteTitle": "BCOS"}
    except Exception as e:
        print(f"Error loading calendar config: {e}")
        return {"months": {}, "quotes": [], "siteTitle": "BCOS"}


def save_calendar_config(config):
    """Save calendar configuration to JSON file"""
    try:
        with open(CALENDAR_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving calendar config: {e}")
        return False


def load_quotes():
    """Load quotes from calendar config"""
    try:
        calendar_config = load_calendar_config()
        return calendar_config.get("quotes", [])
    except Exception as e:
        print(f"Error loading quotes: {e}")
        return []


def load_suggestions():
    """Load suggestions from JSON file"""
    try:
        if os.path.exists(SUGGESTIONS_FILE):
            with open(SUGGESTIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            return []
    except Exception as e:
        print(f"Error loading suggestions: {e}")
        return []


def save_suggestions(suggestions):
    """Save suggestions to JSON file"""
    try:
        with open(SUGGESTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(suggestions, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving suggestions: {e}")
        return False


def check_admin_auth():
    """Check if user is authenticated as admin"""
    return session.get("admin_authenticated", False)


@app.route("/")
def index():
    return render_template("index.html", admin_mode=False)


@app.route("/admin")
def admin():
    if not check_admin_auth():
        return render_template("admin_login.html")
    return render_template("index.html", admin_mode=True)


@app.route("/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json()
    password = data.get("password", "")

    if password == ADMIN_PASSWORD:
        session["admin_authenticated"] = True
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": "Invalid password"}), 401


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("admin_authenticated", None)
    return jsonify({"success": True})


@app.route("/api/services", methods=["GET"])
def get_services():
    """Get all services"""
    try:
        services = load_services()
        return jsonify({"success": True, "services": services, "count": len(services)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/services", methods=["POST"])
def save_services_endpoint():
    """Save services - admin only"""
    if not check_admin_auth():
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    try:
        data = request.get_json()

        if not data or "services" not in data:
            return jsonify({"success": False, "error": "Invalid request data"}), 400

        services = data["services"]

        # Validate services data
        for i, service in enumerate(services):
            required_fields = ["type"]
            if service.get("type") != "url-group":
                required_fields.append("name")

            for field in required_fields:
                if field not in service or not service[field].strip():
                    return jsonify(
                        {
                            "success": False,
                            "error": f"Service {i + 1}: {field} is required",
                        }
                    ), 400

            # Type-specific validation
            if service["type"] == "url" and not service.get("url", "").strip():
                return jsonify(
                    {
                        "success": False,
                        "error": f"Service {i + 1}: URL is required for URL type services",
                    }
                ), 400
            elif (
                service["type"] == "search"
                and not service.get("search_url", "").strip()
            ):
                return jsonify(
                    {
                        "success": False,
                        "error": f"Service {i + 1}: Search URL is required for search type services",
                    }
                ), 400
            elif (
                service["type"] == "iframe"
                and not service.get("iframe_url", "").strip()
            ):
                return jsonify(
                    {
                        "success": False,
                        "error": f"Service {i + 1}: Iframe URL is required for iframe type services",
                    }
                ), 400

            # Ensure required properties exist
            if "column" not in service:
                service["column"] = 0
            else:
                service["column"] = max(0, min(2, int(service["column"])))

            if "description" not in service:
                service["description"] = ""

            if "type" not in service:
                service["type"] = "url"

        success = save_services(services)

        if success:
            return jsonify(
                {
                    "success": True,
                    "message": "Services saved successfully",
                    "count": len(services),
                }
            )
        else:
            return jsonify({"success": False, "error": "Failed to save services"}), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/services/<int:service_id>", methods=["DELETE"])
def delete_service(service_id):
    """Delete a specific service - admin only"""
    if not check_admin_auth():
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    try:
        services = load_services()

        if service_id < 0 or service_id >= len(services):
            return jsonify({"success": False, "error": "Service not found"}), 404

        deleted_service = services.pop(service_id)
        success = save_services(services)

        if success:
            return jsonify(
                {
                    "success": True,
                    "message": f'Service "{deleted_service["name"]}" deleted successfully',
                }
            )
        else:
            return jsonify({"success": False, "error": "Failed to delete service"}), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/quote", methods=["GET"])
def get_quote():
    """Get quote of the day (same quote for the whole day)"""
    try:
        quotes = load_quotes()
        if not quotes:
            return jsonify({"success": False, "error": "No quotes available"}), 404

        # Use today's date as seed for consistent daily quote
        today = datetime.now().date()
        seed = int(today.strftime("%Y%m%d"))
        random.seed(seed)
        quote = random.choice(quotes)
        random.seed()  # Reset seed to default behavior

        return jsonify({"success": True, "quote": quote})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/calendar-config", methods=["GET"])
def get_calendar_config():
    """Get calendar configuration"""
    try:
        config = load_calendar_config()
        return jsonify({"success": True, "config": config})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/calendar-config", methods=["POST"])
def save_calendar_config_endpoint():
    """Save calendar configuration - admin only"""
    if not check_admin_auth():
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    try:
        data = request.get_json()

        if not data or "config" not in data:
            return jsonify({"success": False, "error": "Invalid request data"}), 400

        config = data["config"]
        success = save_calendar_config(config)

        if success:
            return jsonify(
                {
                    "success": True,
                    "message": "Calendar configuration saved successfully",
                }
            )
        else:
            return jsonify(
                {"success": False, "error": "Failed to save calendar configuration"}
            ), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/calendar-phrase", methods=["POST"])
def get_calendar_phrase():
    """Get formatted calendar phrase for specific date"""
    try:
        data = request.get_json()
        day = data.get("day")
        month = data.get("month")
        year = data.get("year")
        phrase = data.get("phrase", "")

        if not all([day, month, year]):
            return jsonify(
                {"success": False, "error": "Day, month, and year are required"}
            ), 400

        config = load_calendar_config()
        month_name = config["months"].get(str(month), {}).get("name", str(month))

        formatted_phrase = f"{month_name} {day}, {year}"
        if phrase:
            formatted_phrase += f" - {phrase}"

        return jsonify({"success": True, "formatted_phrase": formatted_phrase})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/suggestions", methods=["GET"])
def get_suggestions():
    """Get all suggestions"""
    try:
        suggestions = load_suggestions()
        # Calculate score for each suggestion (for backward compatibility)
        for s in suggestions:
            if "score" not in s:
                s["score"] = s.get("upvotes", s.get("votes", 0)) - s.get("downvotes", 0)
        # Sort by score (descending) then by creation date
        suggestions.sort(key=lambda x: (-x.get("score", 0), x.get("created_at", "")))

        return jsonify({"success": True, "suggestions": suggestions})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/suggestions", methods=["POST"])
def submit_suggestion():
    """Submit a new suggestion - anonymous"""
    try:
        data = request.get_json()
        suggestion_text = data.get("suggestion", "").strip()

        if not suggestion_text:
            return jsonify(
                {"success": False, "error": "Suggestion text is required"}
            ), 400

        if len(suggestion_text) > 500:
            return jsonify(
                {"success": False, "error": "Suggestion must be 500 characters or less"}
            ), 400

        suggestions = load_suggestions()

        # Create new suggestion
        new_suggestion = {
            "id": len(suggestions) + 1,
            "text": suggestion_text,
            "votes": 0,
            "created_at": datetime.now().isoformat(),
            "voted_by": [],  # Track IPs to prevent duplicate votes
        }

        suggestions.append(new_suggestion)

        if save_suggestions(suggestions):
            return jsonify(
                {
                    "success": True,
                    "message": "Suggestion submitted successfully",
                    "suggestion": new_suggestion,
                }
            )
        else:
            return jsonify(
                {"success": False, "error": "Failed to save suggestion"}
            ), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/suggestions/<int:suggestion_id>/vote", methods=["POST"])
def vote_suggestion(suggestion_id):
    """Vote for a suggestion - 1 minute cooldown to prevent spam"""
    try:
        data = request.get_json()
        vote_type = data.get("type", "up")  # 'up' or 'down'

        # Initialize cooldown tracking in session
        if "vote_cooldowns" not in session:
            session["vote_cooldowns"] = {}

        current_time = datetime.now().timestamp()
        cooldown_key = f"{suggestion_id}_{vote_type}"
        last_vote_time = session["vote_cooldowns"].get(cooldown_key, 0)

        # Prevent spam: minimum 60 seconds (1 minute) between votes
        time_diff = current_time - last_vote_time
        if time_diff < 60:
            wait_time = int(60 - time_diff)
            return jsonify(
                {
                    "success": False,
                    "error": f"Please wait {wait_time} seconds before voting again",
                }
            ), 429

        suggestions = load_suggestions()

        # Find the suggestion
        suggestion = next(
            (s for s in suggestions if s.get("id") == suggestion_id), None
        )

        if not suggestion:
            return jsonify({"success": False, "error": "Suggestion not found"}), 404

        # Initialize vote tracking fields
        if "upvotes" not in suggestion:
            suggestion["upvotes"] = 0
        if "downvotes" not in suggestion:
            suggestion["downvotes"] = 0

        # Add vote (no checking for duplicates, anyone can vote anytime after cooldown)
        if vote_type == "up":
            suggestion["upvotes"] += 1
        elif vote_type == "down":
            suggestion["downvotes"] += 1

        # Calculate net score for sorting
        suggestion["score"] = suggestion["upvotes"] - suggestion["downvotes"]

        # Update cooldown
        session["vote_cooldowns"][cooldown_key] = current_time
        session.modified = True

        if save_suggestions(suggestions):
            return jsonify(
                {
                    "success": True,
                    "message": "Vote recorded successfully",
                    "upvotes": suggestion["upvotes"],
                    "downvotes": suggestion["downvotes"],
                    "score": suggestion["score"],
                }
            )
        else:
            return jsonify({"success": False, "error": "Failed to save vote"}), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/suggestions/<int:suggestion_id>", methods=["PUT"])
def edit_suggestion(suggestion_id):
    """Edit a suggestion - admin only"""
    if not check_admin_auth():
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    try:
        data = request.get_json()
        new_text = data.get("text", "").strip()

        if not new_text:
            return jsonify(
                {"success": False, "error": "Suggestion text is required"}
            ), 400

        if len(new_text) > 500:
            return jsonify(
                {"success": False, "error": "Suggestion must be 500 characters or less"}
            ), 400

        suggestions = load_suggestions()

        # Find the suggestion
        suggestion = next(
            (s for s in suggestions if s.get("id") == suggestion_id), None
        )

        if not suggestion:
            return jsonify({"success": False, "error": "Suggestion not found"}), 404

        # Update the text
        suggestion["text"] = new_text

        if save_suggestions(suggestions):
            return jsonify(
                {
                    "success": True,
                    "message": "Suggestion updated successfully",
                    "suggestion": suggestion,
                }
            )
        else:
            return jsonify(
                {"success": False, "error": "Failed to update suggestion"}
            ), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/suggestions/<int:suggestion_id>", methods=["DELETE"])
def delete_suggestion(suggestion_id):
    """Delete a suggestion - admin only"""
    if not check_admin_auth():
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    try:
        suggestions = load_suggestions()

        # Find and remove the suggestion
        suggestion = next(
            (s for s in suggestions if s.get("id") == suggestion_id), None
        )

        if not suggestion:
            return jsonify({"success": False, "error": "Suggestion not found"}), 404

        suggestions.remove(suggestion)

        if save_suggestions(suggestions):
            return jsonify(
                {"success": True, "message": "Suggestion deleted successfully"}
            )
        else:
            return jsonify(
                {"success": False, "error": "Failed to delete suggestion"}
            ), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def load_default_visibility():
    """Load default visibility configuration"""
    try:
        if os.path.exists(DEFAULT_VISIBILITY_FILE):
            with open(DEFAULT_VISIBILITY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading default visibility: {e}")
        return {}


def save_default_visibility(visibility):
    """Save default visibility configuration"""
    try:
        with open(DEFAULT_VISIBILITY_FILE, "w", encoding="utf-8") as f:
            json.dump(visibility, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving default visibility: {e}")
        return False


@app.route("/api/default-visibility", methods=["GET"])
def get_default_visibility():
    """Get default card visibility configuration for new users"""
    try:
        visibility = load_default_visibility()
        return jsonify({"success": True, "visibility": visibility})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/default-visibility", methods=["POST"])
def set_default_visibility():
    """Set default card visibility configuration (admin only)"""
    if not check_admin_auth():
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    try:
        data = request.get_json()
        visibility = data.get("visibility", {})

        if save_default_visibility(visibility):
            return jsonify(
                {
                    "success": True,
                    "message": "Default visibility settings saved successfully",
                }
            )
        else:
            return jsonify(
                {
                    "success": False,
                    "error": "Failed to save default visibility settings",
                }
            ), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/nuke-cookies", methods=["POST"])
def nuke_cookies():
    """Admin endpoint to trigger cookie/localStorage clearing for all users"""
    if not check_admin_auth():
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    try:
        # Create a timestamp for this nuke event
        timestamp = datetime.now().isoformat()

        # Save timestamp to a file that all clients will check
        with open("nuke_timestamp.txt", "w") as f:
            f.write(timestamp)

        return jsonify(
            {
                "success": True,
                "message": "Nuke timestamp set successfully",
                "timestamp": timestamp,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/nuke-visibility", methods=["POST"])
def nuke_visibility():
    """Admin endpoint to trigger visibility settings clearing for all users"""
    if not check_admin_auth():
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    try:
        # Create a timestamp for this visibility nuke event
        timestamp = datetime.now().isoformat()

        # Save timestamp to a file that all clients will check
        with open("nuke_visibility_timestamp.txt", "w") as f:
            f.write(timestamp)

        return jsonify(
            {
                "success": True,
                "message": "Visibility nuke timestamp set successfully",
                "timestamp": timestamp,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/nuke-timestamp", methods=["GET"])
def get_nuke_timestamp():
    """Get the current nuke timestamps"""
    try:
        result = {"success": True}

        # Check for full nuke timestamp
        if os.path.exists("nuke_timestamp.txt"):
            with open("nuke_timestamp.txt", "r") as f:
                result["timestamp"] = f.read().strip()
        else:
            result["timestamp"] = None

        # Check for visibility-only nuke timestamp
        if os.path.exists("nuke_visibility_timestamp.txt"):
            with open("nuke_visibility_timestamp.txt", "r") as f:
                result["visibility_timestamp"] = f.read().strip()
        else:
            result["visibility_timestamp"] = None

        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "config_file": CONFIG_FILE,
            "config_exists": os.path.exists(CONFIG_FILE),
            "calendar_config_exists": os.path.exists(CALENDAR_CONFIG_FILE),
            "suggestions_file_exists": os.path.exists(SUGGESTIONS_FILE),
            "default_visibility_exists": os.path.exists(DEFAULT_VISIBILITY_FILE),
        }
    )


@app.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"success": False, "error": "Internal server error"}), 500


# CORS support for development
@app.after_request
def after_request(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")
    return response


# Serve favicon
@app.route("/favicon.svg")
def favicon_svg():
    from flask import send_from_directory

    return send_from_directory("static", "favicon.svg", mimetype="image/svg+xml")


@app.route("/favicon.ico")
def favicon_ico():
    from flask import send_from_directory

    return send_from_directory("static", "favicon.svg", mimetype="image/svg+xml")


if __name__ == "__main__":
    # Ensure the services config file exists with default structure
    if not os.path.exists(CONFIG_FILE):
        save_services(DEFAULT_SERVICES)

    # Check if calendar config exists - if not, user needs to create it or copy the provided one
    if not os.path.exists(CALENDAR_CONFIG_FILE):
        print(
            f"Warning: Calendar configuration file '{CALENDAR_CONFIG_FILE}' not found!"
        )
        print(
            f"Please create this file or copy from the provided calendar_config.json template."
        )
        print(
            "The application will still work, but calendar and quote features will be limited."
        )

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Homepage Service Dashboard")
    parser.add_argument(
        "--port", type=int, default=80, help="Port to run the server on (default: 80)"
    )
    parser.add_argument(
        "--host", type=str, default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)"
    )
    args = parser.parse_args()

    app.run(host=args.host, port=args.port, debug=True)
