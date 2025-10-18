from flask import Flask, request, jsonify, render_template, session, redirect, url_for, Response
import json
import os
from datetime import datetime
import hashlib
import requests
import random

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'  # Change this to a secure secret key

# Configuration
CONFIG_FILE = 'homelab_services.json'
CALENDAR_CONFIG_FILE = 'calendar_config.json'
ADMIN_PASSWORD = 'admin123'  # Change this to a secure password
DEFAULT_SERVICES = []

# We'll load the calendar config from the JSON file, no need for defaults here

def load_services():
    """Load services from JSON file"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Ensure each service has required properties
                services = []
                for service in data.get('services', []):
                    if 'column' not in service:
                        service['column'] = 0
                    if 'type' not in service:
                        service['type'] = 'url'
                    if 'description' not in service:
                        service['description'] = ''
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
            backup_file = f"{CONFIG_FILE}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(CONFIG_FILE, backup_file)
            
            # Keep only last 5 backups
            backup_files = sorted([f for f in os.listdir('.') if f.startswith(f"{CONFIG_FILE}.backup.")])
            for backup in backup_files[:-5]:
                os.remove(backup)
        
        # Save new data
        data = {
            'services': services,
            'last_updated': datetime.now().isoformat()
        }
        
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving services: {e}")
        return False

def load_calendar_config():
    """Load calendar configuration from JSON file"""
    try:
        if os.path.exists(CALENDAR_CONFIG_FILE):
            with open(CALENDAR_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # If no config file exists, create it with the default from our separate config file
            print(f"Calendar config file not found. Please ensure {CALENDAR_CONFIG_FILE} exists.")
            return {"months": {}, "quotes": [], "siteTitle": "BCOS"}
    except Exception as e:
        print(f"Error loading calendar config: {e}")
        return {"months": {}, "quotes": [], "siteTitle": "BCOS"}

def save_calendar_config(config):
    """Save calendar configuration to JSON file"""
    try:
        with open(CALENDAR_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving calendar config: {e}")
        return False

def load_quotes():
    """Load quotes from calendar config"""
    try:
        calendar_config = load_calendar_config()
        return calendar_config.get('quotes', [])
    except Exception as e:
        print(f"Error loading quotes: {e}")
        return []

def check_admin_auth():
    """Check if user is authenticated as admin"""
    return session.get('admin_authenticated', False)

@app.route('/')
def index():
    return render_template("index.html", admin_mode=False)

@app.route('/admin')
def admin():
    if not check_admin_auth():
        return render_template("admin_login.html")
    return render_template("index.html", admin_mode=True)

@app.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json()
    password = data.get('password', '')
    
    if password == ADMIN_PASSWORD:
        session['admin_authenticated'] = True
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Invalid password'}), 401

@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('admin_authenticated', None)
    return jsonify({'success': True})

@app.route('/api/services', methods=['GET'])
def get_services():
    """Get all services"""
    try:
        services = load_services()
        return jsonify({
            'success': True,
            'services': services,
            'count': len(services)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/services', methods=['POST'])
def save_services_endpoint():
    """Save services - admin only"""
    if not check_admin_auth():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        
    try:
        data = request.get_json()
        
        if not data or 'services' not in data:
            return jsonify({
                'success': False,
                'error': 'Invalid request data'
            }), 400
        
        services = data['services']
        
        # Validate services data
        for i, service in enumerate(services):
            required_fields = ['name', 'type']
            for field in required_fields:
                if field not in service or not service[field].strip():
                    return jsonify({
                        'success': False,
                        'error': f'Service {i+1}: {field} is required'
                    }), 400
            
            # Type-specific validation
            if service['type'] == 'url' and not service.get('url', '').strip():
                return jsonify({
                    'success': False,
                    'error': f'Service {i+1}: URL is required for URL type services'
                }), 400
            elif service['type'] == 'search' and not service.get('search_url', '').strip():
                return jsonify({
                    'success': False,
                    'error': f'Service {i+1}: Search URL is required for search type services'
                }), 400
            elif service['type'] == 'iframe' and not service.get('iframe_url', '').strip():
                return jsonify({
                    'success': False,
                    'error': f'Service {i+1}: Iframe URL is required for iframe type services'
                }), 400
            
            # Ensure required properties exist
            if 'column' not in service:
                service['column'] = 0
            else:
                service['column'] = max(0, min(2, int(service['column'])))
            
            if 'description' not in service:
                service['description'] = ''
                
            if 'type' not in service:
                service['type'] = 'url'
        
        success = save_services(services)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Services saved successfully',
                'count': len(services)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save services'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/services/<int:service_id>', methods=['DELETE'])
def delete_service(service_id):
    """Delete a specific service - admin only"""
    if not check_admin_auth():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        
    try:
        services = load_services()
        
        if service_id < 0 or service_id >= len(services):
            return jsonify({
                'success': False,
                'error': 'Service not found'
            }), 404
        
        deleted_service = services.pop(service_id)
        success = save_services(services)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Service "{deleted_service["name"]}" deleted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to delete service'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/quote', methods=['GET'])
def get_quote():
    """Get a random quote"""
    try:
        quotes = load_quotes()
        quote = random.choice(quotes)
        return jsonify({
            'success': True,
            'quote': quote
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/calendar-config', methods=['GET'])
def get_calendar_config():
    """Get calendar configuration"""
    try:
        config = load_calendar_config()
        return jsonify({
            'success': True,
            'config': config
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/calendar-config', methods=['POST'])
def save_calendar_config_endpoint():
    """Save calendar configuration - admin only"""
    if not check_admin_auth():
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
        
    try:
        data = request.get_json()
        
        if not data or 'config' not in data:
            return jsonify({
                'success': False,
                'error': 'Invalid request data'
            }), 400
        
        config = data['config']
        success = save_calendar_config(config)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Calendar configuration saved successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save calendar configuration'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/calendar-phrase', methods=['POST'])
def get_calendar_phrase():
    """Get formatted calendar phrase for specific date"""
    try:
        data = request.get_json()
        day = data.get('day')
        month = data.get('month')
        year = data.get('year')
        phrase = data.get('phrase', '')
        
        if not all([day, month, year]):
            return jsonify({
                'success': False,
                'error': 'Day, month, and year are required'
            }), 400
        
        config = load_calendar_config()
        month_name = config['months'].get(str(month), {}).get('name', str(month))
        
        formatted_phrase = f"{month_name} {day}, {year}"
        if phrase:
            formatted_phrase += f" - {phrase}"
        
        return jsonify({
            'success': True,
            'formatted_phrase': formatted_phrase
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'config_file': CONFIG_FILE,
        'config_exists': os.path.exists(CONFIG_FILE),
        'calendar_config_exists': os.path.exists(CALENDAR_CONFIG_FILE)
    })


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500

# CORS support for development
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# Serve favicon
@app.route('/favicon.svg')
def favicon_svg():
    from flask import send_from_directory
    return send_from_directory('static', 'favicon.svg', mimetype='image/svg+xml')

@app.route('/favicon.ico')
def favicon_ico():
    from flask import send_from_directory
    return send_from_directory('static', 'favicon.svg', mimetype='image/svg+xml')

if __name__ == '__main__':
    # Ensure the services config file exists with default structure
    if not os.path.exists(CONFIG_FILE):
        save_services(DEFAULT_SERVICES)
    
    # Check if calendar config exists - if not, user needs to create it or copy the provided one
    if not os.path.exists(CALENDAR_CONFIG_FILE):
        print(f"Warning: Calendar configuration file '{CALENDAR_CONFIG_FILE}' not found!")
        print(f"Please create this file or copy from the provided calendar_config.json template.")
        print("The application will still work, but calendar and quote features will be limited.")

    app.run(host='0.0.0.0', port=80, debug=True)
