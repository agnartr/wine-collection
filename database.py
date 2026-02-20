"""SQLite database helpers for wine collection management."""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DATABASE_PATH = Path(__file__).parent / "wines.db"


def get_connection():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database with the wines table."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            producer TEXT,
            vintage INTEGER,
            country TEXT,
            region TEXT,
            appellation TEXT,
            style TEXT,
            grape_varieties TEXT,
            alcohol_percentage REAL,
            quantity INTEGER DEFAULT 1,
            drinking_window_start INTEGER,
            drinking_window_end INTEGER,
            score INTEGER,
            description TEXT,
            tasting_notes TEXT,
            image_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def row_to_dict(row):
    """Convert a sqlite3.Row to a dictionary, parsing JSON fields."""
    if row is None:
        return None
    d = dict(row)
    # Parse JSON fields
    if d.get("grape_varieties"):
        try:
            d["grape_varieties"] = json.loads(d["grape_varieties"])
        except json.JSONDecodeError:
            d["grape_varieties"] = []
    else:
        d["grape_varieties"] = []

    if d.get("tasting_notes"):
        try:
            d["tasting_notes"] = json.loads(d["tasting_notes"])
        except json.JSONDecodeError:
            d["tasting_notes"] = {}
    else:
        d["tasting_notes"] = {}

    return d


def create_wine(data):
    """Create a new wine entry."""
    conn = get_connection()
    cursor = conn.cursor()

    # Serialize JSON fields
    grape_varieties = json.dumps(data.get("grape_varieties", []))
    tasting_notes = json.dumps(data.get("tasting_notes", {}))

    cursor.execute("""
        INSERT INTO wines (
            name, producer, vintage, country, region, appellation,
            style, grape_varieties, alcohol_percentage, quantity,
            drinking_window_start, drinking_window_end, score,
            description, tasting_notes, image_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("name"),
        data.get("producer"),
        data.get("vintage"),
        data.get("country"),
        data.get("region"),
        data.get("appellation"),
        data.get("style"),
        grape_varieties,
        data.get("alcohol_percentage"),
        data.get("quantity", 1),
        data.get("drinking_window_start"),
        data.get("drinking_window_end"),
        data.get("score"),
        data.get("description"),
        tasting_notes,
        data.get("image_path")
    ))

    wine_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return wine_id


def get_wine(wine_id):
    """Get a single wine by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM wines WHERE id = ?", (wine_id,))
    row = cursor.fetchone()
    conn.close()
    return row_to_dict(row)


def get_all_wines(filters=None):
    """Get all wines with optional filtering."""
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM wines WHERE 1=1"
    params = []

    if filters:
        if filters.get("country"):
            query += " AND country = ?"
            params.append(filters["country"])
        if filters.get("region"):
            query += " AND region = ?"
            params.append(filters["region"])
        if filters.get("style"):
            query += " AND style = ?"
            params.append(filters["style"])
        if filters.get("vintage_min"):
            query += " AND vintage >= ?"
            params.append(filters["vintage_min"])
        if filters.get("vintage_max"):
            query += " AND vintage <= ?"
            params.append(filters["vintage_max"])
        if filters.get("drinking_now"):
            current_year = datetime.now().year
            query += " AND drinking_window_start <= ? AND drinking_window_end >= ?"
            params.extend([current_year, current_year])
        if filters.get("search"):
            search_term = f"%{filters['search']}%"
            query += " AND (name LIKE ? OR producer LIKE ? OR grape_varieties LIKE ?)"
            params.extend([search_term, search_term, search_term])

    # Sorting
    sort_by = filters.get("sort_by", "name") if filters else "name"
    sort_order = filters.get("sort_order", "asc") if filters else "asc"
    valid_sort_fields = ["name", "vintage", "score", "quantity", "drinking_window_start", "created_at"]
    if sort_by not in valid_sort_fields:
        sort_by = "name"
    sort_order = "DESC" if sort_order.lower() == "desc" else "ASC"
    query += f" ORDER BY {sort_by} {sort_order}"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [row_to_dict(row) for row in rows]


def update_wine(wine_id, data):
    """Update a wine entry."""
    conn = get_connection()
    cursor = conn.cursor()

    # Build dynamic update query
    fields = []
    params = []

    updatable_fields = [
        "name", "producer", "vintage", "country", "region", "appellation",
        "style", "alcohol_percentage", "quantity", "drinking_window_start",
        "drinking_window_end", "score", "description", "image_path"
    ]

    for field in updatable_fields:
        if field in data:
            fields.append(f"{field} = ?")
            params.append(data[field])

    # Handle JSON fields specially
    if "grape_varieties" in data:
        fields.append("grape_varieties = ?")
        params.append(json.dumps(data["grape_varieties"]))

    if "tasting_notes" in data:
        fields.append("tasting_notes = ?")
        params.append(json.dumps(data["tasting_notes"]))

    if not fields:
        conn.close()
        return False

    fields.append("updated_at = CURRENT_TIMESTAMP")
    params.append(wine_id)

    query = f"UPDATE wines SET {', '.join(fields)} WHERE id = ?"
    cursor.execute(query, params)

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


def delete_wine(wine_id):
    """Delete a wine entry."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM wines WHERE id = ?", (wine_id,))
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


def get_stats():
    """Get collection statistics."""
    conn = get_connection()
    cursor = conn.cursor()
    current_year = datetime.now().year

    stats = {}

    # Total bottles
    cursor.execute("SELECT COALESCE(SUM(quantity), 0) as total FROM wines")
    stats["total_bottles"] = cursor.fetchone()["total"]

    # Total unique wines
    cursor.execute("SELECT COUNT(*) as count FROM wines")
    stats["total_wines"] = cursor.fetchone()["count"]

    # By country
    cursor.execute("""
        SELECT country, SUM(quantity) as count
        FROM wines
        WHERE country IS NOT NULL
        GROUP BY country
        ORDER BY count DESC
    """)
    stats["by_country"] = [dict(row) for row in cursor.fetchall()]

    # By style
    cursor.execute("""
        SELECT style, SUM(quantity) as count
        FROM wines
        WHERE style IS NOT NULL
        GROUP BY style
        ORDER BY count DESC
    """)
    stats["by_style"] = [dict(row) for row in cursor.fetchall()]

    # Ready to drink
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM wines
        WHERE drinking_window_start <= ? AND drinking_window_end >= ?
    """, (current_year, current_year))
    stats["ready_to_drink"] = cursor.fetchone()["count"]

    # Needs cellaring
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM wines
        WHERE drinking_window_start > ?
    """, (current_year,))
    stats["needs_cellaring"] = cursor.fetchone()["count"]

    conn.close()
    return stats


def find_matching_wine(name, producer=None, vintage=None):
    """
    Find a wine that matches the given criteria.
    Returns the wine if found, None otherwise.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Try exact match first
    if producer and vintage:
        cursor.execute("""
            SELECT * FROM wines
            WHERE LOWER(name) = LOWER(?)
            AND LOWER(producer) = LOWER(?)
            AND vintage = ?
        """, (name, producer, vintage))
        row = cursor.fetchone()
        if row:
            conn.close()
            return row_to_dict(row)

    # Try name + vintage
    if vintage:
        cursor.execute("""
            SELECT * FROM wines
            WHERE LOWER(name) = LOWER(?)
            AND vintage = ?
        """, (name, vintage))
        row = cursor.fetchone()
        if row:
            conn.close()
            return row_to_dict(row)

    # Try name + producer
    if producer:
        cursor.execute("""
            SELECT * FROM wines
            WHERE LOWER(name) = LOWER(?)
            AND LOWER(producer) = LOWER(?)
        """, (name, producer))
        row = cursor.fetchone()
        if row:
            conn.close()
            return row_to_dict(row)

    # Try fuzzy match on name containing the search term
    cursor.execute("""
        SELECT * FROM wines
        WHERE LOWER(name) LIKE LOWER(?)
        ORDER BY
            CASE WHEN vintage = ? THEN 0 ELSE 1 END,
            created_at DESC
        LIMIT 1
    """, (f"%{name}%", vintage or 0))
    row = cursor.fetchone()
    conn.close()

    if row:
        return row_to_dict(row)
    return None


def increment_wine_quantity(wine_id, amount=1):
    """Increment the quantity of a wine by the given amount."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE wines
        SET quantity = quantity + ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (amount, wine_id))
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


# Initialize database on module import
init_db()
