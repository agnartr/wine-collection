# Agnar's Cellar - Self-Hosting Roadmap

Future implementation plan for self-hosting with multi-user support and wine pairing features.

---

## Phase 1: Self-Hosting Setup

- [ ] **1.1** Get VPS at 1984.is (or similar)
  - Linux server (Ubuntu/Debian recommended)
  - Install: Python 3.8+, PostgreSQL, Nginx, Certbot (SSL)

- [ ] **1.2** Clone and configure the app
  ```bash
  git clone https://github.com/agnartr/wine-collection.git
  cd wine-collection
  pip install -r requirements.txt
  ```

- [ ] **1.3** Set up PostgreSQL database
  ```bash
  sudo -u postgres createdb wine_collection
  sudo -u postgres createuser wineapp --pwprompt
  sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE wine_collection TO wineapp;"
  ```

- [ ] **1.4** Set up systemd service (`/etc/systemd/system/wine-app.service`)
  ```ini
  [Unit]
  Description=Wine Collection App
  After=network.target

  [Service]
  User=www-data
  WorkingDirectory=/path/to/wine-collection
  Environment="ANTHROPIC_API_KEY=your-key"
  Environment="DATABASE_URL=postgresql://wineapp:password@localhost/wine_collection"
  ExecStart=/usr/bin/gunicorn --bind 127.0.0.1:5001 --timeout 120 app:app
  Restart=always

  [Install]
  WantedBy=multi-user.target
  ```

- [ ] **1.5** Set up Nginx reverse proxy (`/etc/nginx/sites-available/wine`)
  ```nginx
  server {
      listen 80;
      server_name yourdomain.com;
      return 301 https://$server_name$request_uri;
  }

  server {
      listen 443 ssl;
      server_name yourdomain.com;

      ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
      ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

      client_max_body_size 16M;

      location / {
          proxy_pass http://127.0.0.1:5001;
          proxy_set_header Host $host;
          proxy_set_header X-Real-IP $remote_addr;
      }

      location /static {
          alias /path/to/wine-collection/static;
      }
  }
  ```

- [ ] **1.6** Get SSL certificate
  ```bash
  sudo certbot --nginx -d yourdomain.com
  ```

- [ ] **1.7** Enable and start services
  ```bash
  sudo systemctl enable wine-app
  sudo systemctl start wine-app
  sudo systemctl reload nginx
  ```

---

## Phase 2: Multi-Instance Setup (Subdomains for Friends)

- [ ] **2.1** Create instance folder structure
  ```
  instances/
  ├── agnar/
  │   ├── wines.db
  │   └── uploads/
  ├── friend1/
  │   ├── wines.db
  │   └── uploads/
  └── friend2/
      ├── wines.db
      └── uploads/
  ```

- [ ] **2.2** Modify `database.py` to support instance-based paths
  ```python
  def get_instance_name():
      """Get instance from subdomain or request."""
      # Extract from request host or key parameter
      pass

  def get_instance_db_path(instance):
      return Path(__file__).parent / "instances" / instance / "wines.db"
  ```

- [ ] **2.3** Modify `app.py` for instance-based uploads
  ```python
  def get_upload_folder(instance):
      return Path(__file__).parent / "instances" / instance / "uploads"
  ```

- [ ] **2.4** Add hidden access key middleware
  ```python
  INSTANCE_KEYS = {
      "agnar": "secret-key-1",
      "friend1": "secret-key-2",
  }

  @app.before_request
  def check_access():
      instance = get_instance_name()
      key = request.args.get('key') or session.get('key')
      if INSTANCE_KEYS.get(instance) != key:
          abort(403)
      session['key'] = key  # Remember for session
  ```

- [ ] **2.5** Configure Nginx for wildcard subdomains
  ```nginx
  server {
      listen 443 ssl;
      server_name *.wine.yourdomain.com;
      # ... rest of config
  }
  ```

- [ ] **2.6** Wildcard SSL certificate
  ```bash
  sudo certbot certonly --manual --preferred-challenges=dns -d "*.wine.yourdomain.com"
  ```

---

## Phase 3: Add Price Field

- [ ] **3.1** Database migration
  ```sql
  ALTER TABLE wines ADD COLUMN price DECIMAL(10,2);
  ALTER TABLE wines ADD COLUMN price_currency TEXT DEFAULT 'USD';
  ```

- [ ] **3.2** Update `database.py`
  - Add `price` and `price_currency` to create/update functions
  - Add to `updatable_fields` list

- [ ] **3.3** Update `wine_analyzer.py` prompt
  ```
  "price_estimate": 25.00,  // Estimated retail price if visible or inferable
  ```

- [ ] **3.4** Update `index.html` form
  ```html
  <label for="wine-price">Price</label>
  <input type="number" id="wine-price" step="0.01" placeholder="29.99">
  <select id="wine-currency">
      <option value="USD">USD</option>
      <option value="EUR">EUR</option>
      <option value="ISK">ISK</option>
  </select>
  ```

- [ ] **3.5** Update `app.js`
  - Add price to form handling
  - Display price on wine cards and detail view

---

## Phase 4: Wine Pairing Feature

- [ ] **4.1** Create pairing prompt in `wine_analyzer.py`
  ```python
  PAIRING_PROMPT = """You are a sommelier. The user has this wine collection:

  {wines_json}

  They are having: {food_description}
  Occasion context: {occasion}
  Maximum price: {max_price}

  Suggest 3 wines from their collection that would pair well.
  Consider:
  - Food and wine pairing principles
  - The occasion (casual = cheaper wines, special = allow premium)
  - Drinking windows (prefer wines ready to drink now)
  - Available quantity (avoid suggesting last bottles for casual meals)

  Return JSON:
  {
      "suggestions": [
          {
              "wine_id": 1,
              "wine_name": "...",
              "why": "Brief pairing explanation",
              "confidence": "perfect|good|acceptable"
          }
      ],
      "general_advice": "Any tips for this pairing"
  }
  """
  ```

- [ ] **4.2** Add pairing function in `wine_analyzer.py`
  ```python
  def get_wine_pairing(wines, food_description, occasion="casual", max_price=None):
      # Format wines as context
      # Call Claude with pairing prompt
      # Return suggestions
      pass
  ```

- [ ] **4.3** Add API endpoint in `app.py`
  ```python
  @app.route("/api/pair", methods=["POST"])
  def pair_wine():
      data = request.get_json()
      food = data.get("food")
      occasion = data.get("occasion", "casual")
      max_price = data.get("max_price")

      wines = database.get_all_wines()
      suggestions = get_wine_pairing(wines, food, occasion, max_price)
      return jsonify(suggestions)
  ```

- [ ] **4.4** Add pairing UI in `index.html`
  ```html
  <div id="pairing-section">
      <h3>Wine Pairing</h3>
      <input type="text" id="food-input" placeholder="What are you eating?">
      <select id="occasion-select">
          <option value="casual">Casual (Tuesday dinner)</option>
          <option value="nice">Nice evening</option>
          <option value="special">Special occasion</option>
      </select>
      <button id="get-pairing-btn">Suggest Wines</button>
      <div id="pairing-results"></div>
  </div>
  ```

- [ ] **4.5** Add pairing JavaScript in `app.js`
  ```javascript
  async function getPairing() {
      const food = document.getElementById('food-input').value;
      const occasion = document.getElementById('occasion-select').value;

      const response = await fetch(`${API_BASE}/pair`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ food, occasion })
      });

      const suggestions = await response.json();
      displayPairingSuggestions(suggestions);
  }
  ```

- [ ] **4.6** Smart occasion-based price filtering
  ```python
  OCCASION_PRICE_LIMITS = {
      "casual": 30,      # Max $30 for casual
      "nice": 75,        # Max $75 for nice dinner
      "special": None,   # No limit for special occasions
  }
  ```

---

## Summary

| Phase | Description | Depends On |
|-------|-------------|------------|
| 1 | Self-hosting on VPS | Hosting account |
| 2 | Multi-user subdomains | Phase 1 |
| 3 | Price tracking | Phase 1 |
| 4 | Wine pairing AI | Phase 1 + Phase 3 |

---

## Quick Reference: Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=your-anthropic-api-key

# For PostgreSQL (optional, defaults to SQLite)
DATABASE_URL=postgresql://user:password@localhost/dbname

# For Cloudinary (optional, defaults to local storage)
CLOUDINARY_URL=cloudinary://key:secret@cloudname
```

---

## Useful Commands

```bash
# Start app
sudo systemctl start wine-app

# View logs
sudo journalctl -u wine-app -f

# Restart after code changes
sudo systemctl restart wine-app

# Pull latest code and restart
cd /path/to/wine-collection && git pull && sudo systemctl restart wine-app
```
