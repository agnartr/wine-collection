"""SQLite/PostgreSQL database helpers for wine collection management."""

import os
import sqlite3
import json
from datetime import datetime
from pathlib import Path
# Check for PostgreSQL connection
DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor

# SQLite fallback path
SQLITE_PATH = Path(__file__).parent / "wines.db"


def get_connection():
    """Get a database connection."""
    if USE_POSTGRES:
        # Use DATABASE_URL directly
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def get_cursor(conn):
    """Get a cursor with appropriate row factory."""
    if USE_POSTGRES:
        return conn.cursor(cursor_factory=RealDictCursor)
    else:
        return conn.cursor()


def get_placeholder():
    """Get the parameter placeholder for the database."""
    return "%s" if USE_POSTGRES else "?"


def init_db():
    """Initialize the database with the wines table."""
    conn = get_connection()
    cursor = get_cursor(conn)

    if USE_POSTGRES:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wines (
                id SERIAL PRIMARY KEY,
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
                cloudinary_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Add cloudinary_id column if it doesn't exist (for existing tables)
        cursor.execute("""
            DO $$
            BEGIN
                ALTER TABLE wines ADD COLUMN cloudinary_id TEXT;
            EXCEPTION
                WHEN duplicate_column THEN NULL;
            END $$;
        """)
    else:
        cursor.execute("""
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
                cloudinary_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    conn.commit()
    cursor.close()
    conn.close()


def row_to_dict(row):
    """Convert a database row to a dictionary, parsing JSON fields."""
    if row is None:
        return None

    # Handle both dict (PostgreSQL) and sqlite3.Row
    if isinstance(row, dict):
        d = dict(row)
    else:
        d = dict(row)

    # Parse JSON fields
    if d.get("grape_varieties"):
        try:
            d["grape_varieties"] = json.loads(d["grape_varieties"])
        except (json.JSONDecodeError, TypeError):
            d["grape_varieties"] = []
    else:
        d["grape_varieties"] = []

    if d.get("tasting_notes"):
        try:
            d["tasting_notes"] = json.loads(d["tasting_notes"])
        except (json.JSONDecodeError, TypeError):
            d["tasting_notes"] = {}
    else:
        d["tasting_notes"] = {}

    return d


def create_wine(data):
    """Create a new wine entry."""
    conn = get_connection()
    cursor = get_cursor(conn)
    p = get_placeholder()

    # Serialize JSON fields
    grape_varieties = json.dumps(data.get("grape_varieties", []))
    tasting_notes = json.dumps(data.get("tasting_notes", {}))

    if USE_POSTGRES:
        cursor.execute(f"""
            INSERT INTO wines (
                name, producer, vintage, country, region, appellation,
                style, grape_varieties, alcohol_percentage, quantity,
                drinking_window_start, drinking_window_end, score,
                description, tasting_notes, image_path, cloudinary_id
            ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
            RETURNING id
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
            data.get("image_path"),
            data.get("cloudinary_id")
        ))
        wine_id = cursor.fetchone()["id"]
    else:
        cursor.execute(f"""
            INSERT INTO wines (
                name, producer, vintage, country, region, appellation,
                style, grape_varieties, alcohol_percentage, quantity,
                drinking_window_start, drinking_window_end, score,
                description, tasting_notes, image_path, cloudinary_id
            ) VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p})
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
            data.get("image_path"),
            data.get("cloudinary_id")
        ))
        wine_id = cursor.lastrowid

    conn.commit()
    cursor.close()
    conn.close()
    return wine_id


def get_wine(wine_id):
    """Get a single wine by ID."""
    conn = get_connection()
    cursor = get_cursor(conn)
    p = get_placeholder()

    cursor.execute(f"SELECT * FROM wines WHERE id = {p}", (wine_id,))
    row = cursor.fetchone()

    cursor.close()
    conn.close()
    return row_to_dict(row)


def get_all_wines(filters=None):
    """Get all wines with optional filtering."""
    conn = get_connection()
    cursor = get_cursor(conn)
    p = get_placeholder()

    query = "SELECT * FROM wines WHERE 1=1"
    params = []

    if filters:
        if filters.get("country"):
            query += f" AND country = {p}"
            params.append(filters["country"])
        if filters.get("region"):
            query += f" AND region = {p}"
            params.append(filters["region"])
        if filters.get("style"):
            query += f" AND style = {p}"
            params.append(filters["style"])
        if filters.get("vintage_min"):
            query += f" AND vintage >= {p}"
            params.append(filters["vintage_min"])
        if filters.get("vintage_max"):
            query += f" AND vintage <= {p}"
            params.append(filters["vintage_max"])
        if filters.get("drinking_now"):
            current_year = datetime.now().year
            query += f" AND drinking_window_start <= {p} AND drinking_window_end >= {p}"
            params.extend([current_year, current_year])
        if filters.get("search"):
            search_term = f"%{filters['search']}%"
            if USE_POSTGRES:
                query += f" AND (name ILIKE {p} OR producer ILIKE {p} OR grape_varieties ILIKE {p})"
            else:
                query += f" AND (name LIKE {p} OR producer LIKE {p} OR grape_varieties LIKE {p})"
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

    cursor.close()
    conn.close()
    return [row_to_dict(row) for row in rows]


def update_wine(wine_id, data):
    """Update a wine entry."""
    conn = get_connection()
    cursor = get_cursor(conn)
    p = get_placeholder()

    # Build dynamic update query
    fields = []
    params = []

    updatable_fields = [
        "name", "producer", "vintage", "country", "region", "appellation",
        "style", "alcohol_percentage", "quantity", "drinking_window_start",
        "drinking_window_end", "score", "description", "image_path", "cloudinary_id"
    ]

    for field in updatable_fields:
        if field in data:
            fields.append(f"{field} = {p}")
            params.append(data[field])

    # Handle JSON fields specially
    if "grape_varieties" in data:
        fields.append(f"grape_varieties = {p}")
        params.append(json.dumps(data["grape_varieties"]))

    if "tasting_notes" in data:
        fields.append(f"tasting_notes = {p}")
        params.append(json.dumps(data["tasting_notes"]))

    if not fields:
        cursor.close()
        conn.close()
        return False

    fields.append("updated_at = CURRENT_TIMESTAMP")
    params.append(wine_id)

    query = f"UPDATE wines SET {', '.join(fields)} WHERE id = {p}"
    cursor.execute(query, params)

    success = cursor.rowcount > 0
    conn.commit()
    cursor.close()
    conn.close()
    return success


def delete_wine(wine_id):
    """Delete a wine entry."""
    conn = get_connection()
    cursor = get_cursor(conn)
    p = get_placeholder()

    cursor.execute(f"DELETE FROM wines WHERE id = {p}", (wine_id,))
    success = cursor.rowcount > 0

    conn.commit()
    cursor.close()
    conn.close()
    return success


def get_stats():
    """Get collection statistics."""
    conn = get_connection()
    cursor = get_cursor(conn)
    p = get_placeholder()
    current_year = datetime.now().year

    stats = {}

    # Total bottles
    cursor.execute("SELECT COALESCE(SUM(quantity), 0) as total FROM wines")
    row = cursor.fetchone()
    stats["total_bottles"] = row["total"] if isinstance(row, dict) else row[0]

    # Total unique wines
    cursor.execute("SELECT COUNT(*) as count FROM wines")
    row = cursor.fetchone()
    stats["total_wines"] = row["count"] if isinstance(row, dict) else row[0]

    # By country
    cursor.execute("""
        SELECT country, SUM(quantity) as count
        FROM wines
        WHERE country IS NOT NULL
        GROUP BY country
        ORDER BY count DESC
    """)
    stats["by_country"] = [dict(row) if isinstance(row, dict) else {"country": row[0], "count": row[1]} for row in cursor.fetchall()]

    # By style
    cursor.execute("""
        SELECT style, SUM(quantity) as count
        FROM wines
        WHERE style IS NOT NULL
        GROUP BY style
        ORDER BY count DESC
    """)
    stats["by_style"] = [dict(row) if isinstance(row, dict) else {"style": row[0], "count": row[1]} for row in cursor.fetchall()]

    # Ready to drink
    cursor.execute(f"""
        SELECT COUNT(*) as count
        FROM wines
        WHERE drinking_window_start <= {p} AND drinking_window_end >= {p}
    """, (current_year, current_year))
    row = cursor.fetchone()
    stats["ready_to_drink"] = row["count"] if isinstance(row, dict) else row[0]

    # Needs cellaring
    cursor.execute(f"""
        SELECT COUNT(*) as count
        FROM wines
        WHERE drinking_window_start > {p}
    """, (current_year,))
    row = cursor.fetchone()
    stats["needs_cellaring"] = row["count"] if isinstance(row, dict) else row[0]

    cursor.close()
    conn.close()
    return stats


def find_matching_wine(name, producer=None, vintage=None):
    """
    Find a wine that matches the given criteria.
    Returns the wine if found, None otherwise.
    """
    conn = get_connection()
    cursor = get_cursor(conn)
    p = get_placeholder()

    # Try exact match first
    if producer and vintage:
        if USE_POSTGRES:
            cursor.execute(f"""
                SELECT * FROM wines
                WHERE LOWER(name) = LOWER({p})
                AND LOWER(producer) = LOWER({p})
                AND vintage = {p}
            """, (name, producer, vintage))
        else:
            cursor.execute(f"""
                SELECT * FROM wines
                WHERE LOWER(name) = LOWER({p})
                AND LOWER(producer) = LOWER({p})
                AND vintage = {p}
            """, (name, producer, vintage))
        row = cursor.fetchone()
        if row:
            cursor.close()
            conn.close()
            return row_to_dict(row)

    # Try name + vintage
    if vintage:
        cursor.execute(f"""
            SELECT * FROM wines
            WHERE LOWER(name) = LOWER({p})
            AND vintage = {p}
        """, (name, vintage))
        row = cursor.fetchone()
        if row:
            cursor.close()
            conn.close()
            return row_to_dict(row)

    # Try name + producer
    if producer:
        cursor.execute(f"""
            SELECT * FROM wines
            WHERE LOWER(name) = LOWER({p})
            AND LOWER(producer) = LOWER({p})
        """, (name, producer))
        row = cursor.fetchone()
        if row:
            cursor.close()
            conn.close()
            return row_to_dict(row)

    # Try fuzzy match on name containing the search term
    search_pattern = f"%{name}%"
    if USE_POSTGRES:
        cursor.execute(f"""
            SELECT * FROM wines
            WHERE LOWER(name) LIKE LOWER({p})
            ORDER BY
                CASE WHEN vintage = {p} THEN 0 ELSE 1 END,
                created_at DESC
            LIMIT 1
        """, (search_pattern, vintage or 0))
    else:
        cursor.execute(f"""
            SELECT * FROM wines
            WHERE LOWER(name) LIKE LOWER({p})
            ORDER BY
                CASE WHEN vintage = {p} THEN 0 ELSE 1 END,
                created_at DESC
            LIMIT 1
        """, (search_pattern, vintage or 0))
    row = cursor.fetchone()

    cursor.close()
    conn.close()

    if row:
        return row_to_dict(row)
    return None


def increment_wine_quantity(wine_id, amount=1):
    """Increment the quantity of a wine by the given amount."""
    conn = get_connection()
    cursor = get_cursor(conn)
    p = get_placeholder()

    cursor.execute(f"""
        UPDATE wines
        SET quantity = quantity + {p}, updated_at = CURRENT_TIMESTAMP
        WHERE id = {p}
    """, (amount, wine_id))
    success = cursor.rowcount > 0

    conn.commit()
    cursor.close()
    conn.close()
    return success


# Initialize database on module import
init_db()
