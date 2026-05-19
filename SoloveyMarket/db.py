import os
import sqlite3

from config import DB_PATH, FREE_CATEGORY_LIMIT


def ensure_db_dir():
    db_dir = os.path.dirname(DB_PATH)

    if db_dir:
        os.makedirs(db_dir, exist_ok=True)


def db():
    ensure_db_dir()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    return conn


def safe_alter(cur, sql):
    try:
        cur.execute(sql)
    except sqlite3.OperationalError:
        pass


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        subcategory TEXT,
        description TEXT,
        public_location TEXT,
        private_address TEXT,
        phone TEXT,
        status TEXT DEFAULT 'new',
        executor_id INTEGER,
        dispatcher_comment TEXT,
        assignment_reason TEXT,
        executor_done_at DATETIME,
        completed_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS executors (
        tg_id INTEGER PRIMARY KEY,
        name TEXT,
        category TEXT,
        location_name TEXT,
        is_active INTEGER DEFAULT 1,
        rating REAL DEFAULT 5.0,
        completed_count INTEGER DEFAULT 0,
        cancel_count INTEGER DEFAULT 0,
        complaint_count INTEGER DEFAULT 0,
        response_count INTEGER DEFAULT 0,
        trust_score INTEGER DEFAULT 50,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS executor_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        executor_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        is_paid INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(executor_id, category)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS clients (
        phone TEXT PRIMARY KEY,
        total_requests INTEGER DEFAULT 0,
        completed_requests INTEGER DEFAULT 0,
        canceled_requests INTEGER DEFAULT 0,
        complaint_count INTEGER DEFAULT 0,
        trust_score INTEGER DEFAULT 50,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER NOT NULL,
        executor_id INTEGER NOT NULL,
        status TEXT DEFAULT 'new',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(request_id, executor_id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER,
        action TEXT,
        details TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER,
        from_type TEXT,
        from_id TEXT,
        to_type TEXT,
        to_id TEXT,
        rating INTEGER,
        text TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS disputes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER,
        initiator_type TEXT,
        initiator_id TEXT,
        reason TEXT,
        status TEXT DEFAULT 'open',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        district TEXT,
        region TEXT,
        status TEXT DEFAULT 'active',
        is_active INTEGER DEFAULT 1,
        executor_count INTEGER DEFAULT 0,
        request_count INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS location_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        location_name TEXT,
        district TEXT,
        region TEXT,
        description TEXT,
        executor_name TEXT,
        executor_tg_id INTEGER,
        status TEXT DEFAULT 'pending',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS service_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            description TEXT,
            phone TEXT,
            public_location TEXT,
            status TEXT DEFAULT 'new',
            admin_comment TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS executor_locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        executor_id INTEGER NOT NULL,
        location_name TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(executor_id, location_name)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        text TEXT,
        image_url TEXT,
        link_url TEXT,
        button_text TEXT DEFAULT 'Подробнее',
        placement TEXT DEFAULT 'home_top',
        is_active INTEGER DEFAULT 1,
        sort_order INTEGER DEFAULT 100,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    migrations = [
        "ALTER TABLE requests ADD COLUMN subcategory TEXT",
        "ALTER TABLE requests ADD COLUMN public_location TEXT",
        "ALTER TABLE requests ADD COLUMN private_address TEXT",
        "ALTER TABLE requests ADD COLUMN executor_id INTEGER",
        "ALTER TABLE requests ADD COLUMN dispatcher_comment TEXT",
        "ALTER TABLE requests ADD COLUMN assignment_reason TEXT",
        "ALTER TABLE requests ADD COLUMN executor_done_at DATETIME",
        "ALTER TABLE requests ADD COLUMN completed_at DATETIME",

        "ALTER TABLE executors ADD COLUMN location_name TEXT",
        "ALTER TABLE executors ADD COLUMN is_active INTEGER DEFAULT 1",
        "ALTER TABLE executors ADD COLUMN rating REAL DEFAULT 5.0",
        "ALTER TABLE executors ADD COLUMN completed_count INTEGER DEFAULT 0",
        "ALTER TABLE executors ADD COLUMN cancel_count INTEGER DEFAULT 0",
        "ALTER TABLE executors ADD COLUMN complaint_count INTEGER DEFAULT 0",
        "ALTER TABLE executors ADD COLUMN response_count INTEGER DEFAULT 0",
        "ALTER TABLE executors ADD COLUMN trust_score INTEGER DEFAULT 50",

        "ALTER TABLE executor_categories ADD COLUMN is_paid INTEGER DEFAULT 0",
        "ALTER TABLE executor_categories ADD COLUMN is_active INTEGER DEFAULT 1",

        "ALTER TABLE locations ADD COLUMN district TEXT",
        "ALTER TABLE locations ADD COLUMN region TEXT",
        "ALTER TABLE locations ADD COLUMN status TEXT DEFAULT 'active'",
        "ALTER TABLE locations ADD COLUMN is_active INTEGER DEFAULT 1",
        "ALTER TABLE locations ADD COLUMN executor_count INTEGER DEFAULT 0",
        "ALTER TABLE locations ADD COLUMN request_count INTEGER DEFAULT 0",
        "ALTER TABLE locations ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP",

        "ALTER TABLE service_suggestions ADD COLUMN title TEXT",
        "ALTER TABLE service_suggestions ADD COLUMN description TEXT",
        "ALTER TABLE service_suggestions ADD COLUMN phone TEXT",
        "ALTER TABLE service_suggestions ADD COLUMN public_location TEXT",
        "ALTER TABLE service_suggestions ADD COLUMN status TEXT DEFAULT 'new'",
        "ALTER TABLE service_suggestions ADD COLUMN admin_comment TEXT",
        "ALTER TABLE service_suggestions ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP",

        "ALTER TABLE ads ADD COLUMN image_url TEXT",
        "ALTER TABLE ads ADD COLUMN link_url TEXT",
        "ALTER TABLE ads ADD COLUMN button_text TEXT DEFAULT 'Подробнее'",
        "ALTER TABLE ads ADD COLUMN placement TEXT DEFAULT 'home_top'",
        "ALTER TABLE ads ADD COLUMN is_active INTEGER DEFAULT 1",
        "ALTER TABLE ads ADD COLUMN sort_order INTEGER DEFAULT 100",
    ]

    for sql in migrations:
        safe_alter(cur, sql)

    try:
        cur.execute("""
            UPDATE requests
            SET private_address = address
            WHERE private_address IS NULL
        """)
    except sqlite3.OperationalError:
        pass

    cur.execute("""
        INSERT OR IGNORE INTO executor_categories(
            executor_id,
            category,
            is_paid,
            is_active
        )
        SELECT
            tg_id,
            category,
            0,
            1
        FROM executors
        WHERE category IS NOT NULL
          AND category != ''
    """)

    conn.commit()
    conn.close()


def seed_default_locations():
    conn = db()

    default_locations = [
        ("Соловей Ключ", "Надеждинский район", "Приморский край"),
        ("Новый", "Надеждинский район", "Приморский край"),
        ("Тавричанка", "Надеждинский район", "Приморский край"),
        ("Раздольное", "Надеждинский район", "Приморский край"),
        ("Вольно-Надеждинское", "Надеждинский район", "Приморский край"),
        ("Прохладное", "Надеждинский район", "Приморский край"),
    ]

    for loc in default_locations:
        conn.execute("""
            INSERT OR IGNORE INTO locations(name, district, region, status, is_active)
            VALUES (?, ?, ?, 'active', 1)
        """, loc)

    conn.commit()
    conn.close()


def trust_label(score):
    if score >= 75:
        return "🟢 Надёжный"
    if score >= 50:
        return "🟡 Обычный"
    if score >= 30:
        return "🟠 Проверять"
    return "🔴 Рискованный"


def ensure_client(phone):
    conn = db()

    conn.execute("""
        INSERT OR IGNORE INTO clients(phone)
        VALUES (?)
    """, (phone,))

    conn.commit()
    conn.close()


def create_request(category, subcategory, description, public_location, private_address, phone):
    ensure_client(phone)

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO requests(
            category,
            subcategory,
            description,
            public_location,
            private_address,
            phone
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        category,
        subcategory,
        description,
        public_location,
        private_address,
        phone
    ))

    request_id = cur.lastrowid

    cur.execute("""
        UPDATE clients
        SET total_requests = total_requests + 1
        WHERE phone = ?
    """, (phone,))

    cur.execute("""
        UPDATE locations
        SET request_count = request_count + 1
        WHERE name = ?
    """, (public_location,))

    cur.execute("""
        INSERT INTO audit_log(request_id, action, details)
        VALUES (?, ?, ?)
    """, (
        request_id,
        "request_created",
        f"Создана заявка. Категория: {category}; населённый пункт: {public_location}"
    ))

    conn.commit()
    conn.close()

    return request_id


def get_request(request_id):
    conn = db()

    row = conn.execute("""
        SELECT *
        FROM requests
        WHERE id = ?
    """, (request_id,)).fetchone()

    conn.close()
    return row


def get_all_requests():
    conn = db()

    rows = conn.execute("""
        SELECT *
        FROM requests
        ORDER BY id DESC
    """).fetchall()

    conn.close()
    return rows


def get_client(phone):
    conn = db()

    row = conn.execute("""
        SELECT *
        FROM clients
        WHERE phone = ?
    """, (phone,)).fetchone()

    conn.close()
    return row


def update_request_status(request_id, status, comment=""):
    conn = db()
    cur = conn.cursor()

    old = cur.execute("""
        SELECT *
        FROM requests
        WHERE id = ?
    """, (request_id,)).fetchone()

    cur.execute("""
        UPDATE requests
        SET status = ?,
            dispatcher_comment = ?
        WHERE id = ?
    """, (status, comment, request_id))

    if old:
        if status in ("canceled", "rejected"):
            cur.execute("""
                UPDATE clients
                SET canceled_requests = canceled_requests + 1,
                    trust_score = MAX(trust_score - 5, 0)
                WHERE phone = ?
            """, (old["phone"],))

        cur.execute("""
            INSERT INTO audit_log(request_id, action, details)
            VALUES (?, ?, ?)
        """, (
            request_id,
            "status_changed",
            f"Статус изменён на {status}. Комментарий: {comment}"
        ))

    conn.commit()
    conn.close()


def add_executor(tg_id, name, category, location_name=None):
    conn = db()

    conn.execute("""
        INSERT OR REPLACE INTO executors(
            tg_id,
            name,
            category,
            location_name,
            is_active,
            rating,
            completed_count,
            cancel_count,
            complaint_count,
            response_count,
            trust_score
        )
        VALUES (
            ?, ?, ?, ?, 1,
            COALESCE((SELECT rating FROM executors WHERE tg_id = ?), 5.0),
            COALESCE((SELECT completed_count FROM executors WHERE tg_id = ?), 0),
            COALESCE((SELECT cancel_count FROM executors WHERE tg_id = ?), 0),
            COALESCE((SELECT complaint_count FROM executors WHERE tg_id = ?), 0),
            COALESCE((SELECT response_count FROM executors WHERE tg_id = ?), 0),
            COALESCE((SELECT trust_score FROM executors WHERE tg_id = ?), 50)
        )
    """, (
        tg_id,
        name,
        category,
        location_name,
        tg_id,
        tg_id,
        tg_id,
        tg_id,
        tg_id,
        tg_id
    ))

    if location_name:
        conn.execute("""
            UPDATE locations
            SET executor_count = executor_count + 1
            WHERE name = ?
        """, (location_name,))

    conn.commit()
    conn.close()


def set_executor_categories(executor_id, categories):
    conn = db()

    conn.execute("""
        UPDATE executor_categories
        SET is_active = 0
        WHERE executor_id = ?
    """, (executor_id,))

    for index, category in enumerate(categories):
        is_paid = 1 if index >= FREE_CATEGORY_LIMIT else 0

        conn.execute("""
            INSERT INTO executor_categories(
                executor_id,
                category,
                is_paid,
                is_active
            )
            VALUES (?, ?, ?, 1)
            ON CONFLICT(executor_id, category)
            DO UPDATE SET
                is_paid = excluded.is_paid,
                is_active = 1
        """, (
            executor_id,
            category,
            is_paid
        ))

    conn.commit()
    conn.close()


def get_executor_categories(executor_id):
    conn = db()

    rows = conn.execute("""
        SELECT *
        FROM executor_categories
        WHERE executor_id = ?
          AND is_active = 1
        ORDER BY is_paid ASC, id ASC
    """, (executor_id,)).fetchall()

    conn.close()
    return rows


def toggle_executor_category(executor_id, category_id):
    conn = db()

    row = conn.execute("""
        SELECT *
        FROM executor_categories
        WHERE id = ?
          AND executor_id = ?
    """, (category_id, executor_id)).fetchone()

    if row:
        new_status = 0 if row["is_active"] else 1

        conn.execute("""
            UPDATE executor_categories
            SET is_active = ?
            WHERE id = ?
        """, (new_status, category_id))

    conn.commit()
    conn.close()


def mark_category_paid(category_id):
    conn = db()

    conn.execute("""
        UPDATE executor_categories
        SET is_paid = 1,
            is_active = 1
        WHERE id = ?
    """, (category_id,))

    conn.commit()
    conn.close()


def mark_category_free(category_id):
    conn = db()

    conn.execute("""
        UPDATE executor_categories
        SET is_paid = 0,
            is_active = 1
        WHERE id = ?
    """, (category_id,))

    conn.commit()
    conn.close()


def get_executor(tg_id):
    conn = db()

    row = conn.execute("""
        SELECT *
        FROM executors
        WHERE tg_id = ?
    """, (tg_id,)).fetchone()

    conn.close()
    return row



def get_executor_profile(executor_id):
    conn = db()

    executor = conn.execute("""
        SELECT *
        FROM executors
        WHERE tg_id = ?
    """, (executor_id,)).fetchone()

    if not executor:
        conn.close()
        return None

    subscriptions = conn.execute("""
        SELECT
            executor_subscriptions.*,
            service_subcategories.name AS subcategory_name,
            service_subcategories.requires_dispatcher,
            service_categories.name AS category_name,
            service_categories.emoji AS category_emoji
        FROM executor_subscriptions
        JOIN service_subcategories
            ON service_subcategories.id = executor_subscriptions.subcategory_id
        JOIN service_categories
            ON service_categories.id = service_subcategories.category_id
        WHERE executor_subscriptions.executor_id = ?
          AND executor_subscriptions.is_active = 1
        ORDER BY
            service_categories.sort_order ASC,
            service_subcategories.sort_order ASC,
            service_subcategories.name ASC
    """, (executor_id,)).fetchall()

    locations = conn.execute("""
        SELECT *
        FROM executor_locations
        WHERE executor_id = ?
        ORDER BY location_name ASC
    """, (executor_id,)).fetchall()

    conn.close()

    return {
        "executor": executor,
        "subscriptions": subscriptions,
        "locations": locations
    }


def set_executor_availability(executor_id, is_available):
    conn = db()

    conn.execute("""
        UPDATE executors
        SET is_available = ?
        WHERE tg_id = ?
    """, (
        1 if is_available else 0,
        executor_id
    ))

    conn.commit()
    conn.close()


def get_executors_with_categories():
    conn = db()

    rows = conn.execute("""
        SELECT *
        FROM executors
        ORDER BY created_at DESC
    """).fetchall()

    result = []

    for ex in rows:
        cats = conn.execute("""
            SELECT *
            FROM executor_categories
            WHERE executor_id = ?
            ORDER BY is_active DESC, is_paid ASC, id ASC
        """, (ex["tg_id"],)).fetchall()

        result.append({
            "executor": ex,
            "categories": cats
        })

    conn.close()
    return result


def get_executors_by_category(category, public_location=None):
    conn = db()

    if public_location:
        rows = conn.execute("""
            SELECT DISTINCT executors.*
            FROM executors
            JOIN executor_categories
                ON executor_categories.executor_id = executors.tg_id
            WHERE executor_categories.category = ?
              AND executor_categories.is_active = 1
              AND executors.is_active = 1
              AND (
                    executors.location_name = ?
                    OR executors.location_name IS NULL
                    OR executors.location_name = ''
                  )
            ORDER BY
              CASE WHEN executors.location_name = ? THEN 1 ELSE 0 END DESC,
              executors.trust_score DESC,
              executors.rating DESC,
              executors.completed_count DESC
        """, (
            category,
            public_location,
            public_location
        )).fetchall()
    else:
        rows = conn.execute("""
            SELECT DISTINCT executors.*
            FROM executors
            JOIN executor_categories
                ON executor_categories.executor_id = executors.tg_id
            WHERE executor_categories.category = ?
              AND executor_categories.is_active = 1
              AND executors.is_active = 1
            ORDER BY
              executors.trust_score DESC,
              executors.rating DESC,
              executors.completed_count DESC
        """, (category,)).fetchall()

    conn.close()
    return rows


def get_all_service_categories_with_subcategories():
    conn = db()

    categories = conn.execute("""
        SELECT *
        FROM service_categories
        ORDER BY sort_order ASC, name ASC
    """).fetchall()

    result = []

    for category in categories:
        subcategories = conn.execute("""
            SELECT *
            FROM service_subcategories
            WHERE category_id = ?
            ORDER BY sort_order ASC, name ASC
        """, (category["id"],)).fetchall()

        result.append({
            "category": category,
            "subcategories": subcategories
        })

    conn.close()
    return result

def get_service_categories_with_subcategories():
    conn = db()

    categories = conn.execute("""
        SELECT *
        FROM service_categories
        WHERE is_active = 1
        ORDER BY sort_order ASC, name ASC
    """).fetchall()

    result = []

    for category in categories:
        subcategories = conn.execute("""
            SELECT *
            FROM service_subcategories
            WHERE category_id = ?
              AND is_active = 1
            ORDER BY sort_order ASC, name ASC
        """, (category["id"],)).fetchall()

        result.append({
            "category": category,
            "subcategories": subcategories
        })

    conn.close()

    return result

def create_service_category(name, emoji="📌", sort_order=100):
    conn = db()

    conn.execute("""
        INSERT INTO service_categories(
            name,
            emoji,
            sort_order
        )
        VALUES (?, ?, ?)
    """, (
        name,
        emoji,
        sort_order
    ))

    conn.commit()
    conn.close()


def create_service_subcategory(category_id, name, sort_order=100):
    conn = db()

    conn.execute("""
        INSERT INTO service_subcategories(
            category_id,
            name,
            sort_order
        )
        VALUES (?, ?, ?)
    """, (
        category_id,
        name,
        sort_order
    ))

    conn.commit()
    conn.close()


def toggle_service_category(category_id):
    conn = db()

    conn.execute("""
        UPDATE service_categories
        SET is_active = CASE
            WHEN is_active = 1 THEN 0
            ELSE 1
        END
        WHERE id = ?
    """, (category_id,))

    conn.commit()
    conn.close()


def toggle_service_subcategory(subcategory_id):
    conn = db()

    conn.execute("""
        UPDATE service_subcategories
        SET is_active = CASE
            WHEN is_active = 1 THEN 0
            ELSE 1
        END
        WHERE id = ?
    """, (subcategory_id,))

    conn.commit()
    conn.close()

def create_response(request_id, executor_id):
    conn = db()

    try:
        conn.execute("""
            INSERT INTO responses(request_id, executor_id)
            VALUES (?, ?)
        """, (request_id, executor_id))

        conn.execute("""
            UPDATE executors
            SET response_count = response_count + 1,
                trust_score = MIN(trust_score + 1, 100)
            WHERE tg_id = ?
        """, (executor_id,))

        conn.execute("""
            INSERT INTO audit_log(request_id, action, details)
            VALUES (?, ?, ?)
        """, (
            request_id,
            "executor_response",
            f"Исполнитель {executor_id} откликнулся"
        ))

        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False

    conn.close()
    return success


def get_responses_for_request(request_id):
    conn = db()

    rows = conn.execute("""
        SELECT
            responses.*,
            executors.name,
            executors.category,
            executors.location_name,
            executors.rating,
            executors.completed_count,
            executors.cancel_count,
            executors.complaint_count,
            executors.response_count,
            executors.trust_score
        FROM responses
        LEFT JOIN executors
            ON executors.tg_id = responses.executor_id
        WHERE responses.request_id = ?
        ORDER BY
            executors.trust_score DESC,
            executors.rating DESC,
            responses.id ASC
    """, (request_id,)).fetchall()

    conn.close()
    return rows


def assign_executor(request_id, executor_id, reason):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE requests
        SET status = 'in_work',
            executor_id = ?,
            assignment_reason = ?
        WHERE id = ?
          AND status IN ('searching_executor', 'accepted', 'new')
    """, (
        executor_id,
        reason,
        request_id
    ))

    success = cur.rowcount

    if success:
        cur.execute("""
            UPDATE responses
            SET status = 'accepted'
            WHERE request_id = ?
              AND executor_id = ?
        """, (
            request_id,
            executor_id
        ))

        cur.execute("""
            UPDATE responses
            SET status = 'rejected'
            WHERE request_id = ?
              AND executor_id != ?
        """, (
            request_id,
            executor_id
        ))

        cur.execute("""
            INSERT INTO audit_log(request_id, action, details)
            VALUES (?, ?, ?)
        """, (
            request_id,
            "assign_executor",
            f"Назначен исполнитель {executor_id}. Причина: {reason}"
        ))

    conn.commit()
    conn.close()
    return success


def executor_mark_done(request_id, executor_id=None):
    conn = db()
    cur = conn.cursor()

    if executor_id:
        cur.execute("""
            UPDATE requests
            SET status = 'executor_done',
                executor_done_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND executor_id = ?
              AND status = 'in_work'
        """, (
            request_id,
            executor_id
        ))
    else:
        cur.execute("""
            UPDATE requests
            SET status = 'executor_done',
                executor_done_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND status = 'in_work'
        """, (request_id,))

    success = cur.rowcount

    if success:
        cur.execute("""
            INSERT INTO audit_log(request_id, action, details)
            VALUES (?, ?, ?)
        """, (
            request_id,
            "executor_done",
            "Исполнитель отметил работу выполненной"
        ))

    conn.commit()
    conn.close()
    return success


def confirm_request_done(request_id):
    conn = db()
    cur = conn.cursor()

    req = cur.execute("""
        SELECT *
        FROM requests
        WHERE id = ?
    """, (request_id,)).fetchone()

    if not req:
        conn.close()
        return False

    cur.execute("""
        UPDATE requests
        SET status = 'done',
            completed_at = CURRENT_TIMESTAMP
        WHERE id = ?
          AND status IN ('executor_done', 'in_work')
    """, (request_id,))

    success = cur.rowcount

    if success:
        if req["executor_id"]:
            cur.execute("""
                UPDATE executors
                SET completed_count = completed_count + 1,
                    trust_score = MIN(trust_score + 5, 100),
                    rating = MIN(rating + 0.05, 5.0)
                WHERE tg_id = ?
            """, (req["executor_id"],))

        cur.execute("""
            UPDATE clients
            SET completed_requests = completed_requests + 1,
                trust_score = MIN(trust_score + 2, 100)
            WHERE phone = ?
        """, (req["phone"],))

        cur.execute("""
            INSERT INTO audit_log(request_id, action, details)
            VALUES (?, ?, ?)
        """, (
            request_id,
            "request_done",
            "Диспетчер подтвердил успешное выполнение заявки"
        ))

    conn.commit()
    conn.close()
    return bool(success)


def create_dispute(request_id, initiator_type, initiator_id, reason):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO disputes(
            request_id,
            initiator_type,
            initiator_id,
            reason
        )
        VALUES (?, ?, ?, ?)
    """, (
        request_id,
        initiator_type,
        initiator_id,
        reason
    ))

    cur.execute("""
        UPDATE requests
        SET status = 'dispute'
        WHERE id = ?
    """, (request_id,))

    cur.execute("""
        INSERT INTO audit_log(request_id, action, details)
        VALUES (?, ?, ?)
    """, (
        request_id,
        "dispute_opened",
        f"Спор открыл: {initiator_type} {initiator_id}. Причина: {reason}"
    ))

    conn.commit()
    conn.close()


def resolve_dispute(request_id, decision, comment=""):
    conn = db()
    cur = conn.cursor()

    req = cur.execute("""
        SELECT *
        FROM requests
        WHERE id = ?
    """, (request_id,)).fetchone()

    if not req:
        conn.close()
        return False

    new_status = "done" if decision in ("executor_right", "compromise_done") else "canceled"

    cur.execute("""
        UPDATE disputes
        SET status = 'closed'
        WHERE request_id = ?
          AND status = 'open'
    """, (request_id,))

    cur.execute("""
        UPDATE requests
        SET status = ?
        WHERE id = ?
    """, (
        new_status,
        request_id
    ))

    if decision == "client_right" and req["executor_id"]:
        cur.execute("""
            UPDATE executors
            SET complaint_count = complaint_count + 1,
                trust_score = MAX(trust_score - 10, 0),
                rating = MAX(rating - 0.2, 1.0)
            WHERE tg_id = ?
        """, (req["executor_id"],))

    if decision == "executor_right":
        cur.execute("""
            UPDATE clients
            SET complaint_count = complaint_count + 1,
                trust_score = MAX(trust_score - 10, 0)
            WHERE phone = ?
        """, (req["phone"],))

    cur.execute("""
        INSERT INTO audit_log(request_id, action, details)
        VALUES (?, ?, ?)
    """, (
        request_id,
        "dispute_resolved",
        f"Решение: {decision}. Комментарий: {comment}"
    ))

    conn.commit()
    conn.close()
    return True


def get_locations():
    conn = db()

    rows = conn.execute("""
        SELECT *
        FROM locations
        WHERE COALESCE(is_active, 1) = 1
          AND COALESCE(status, 'active') = 'active'
        ORDER BY name
    """).fetchall()

    conn.close()
    return rows


def create_location_request(location_name, district, region, description, executor_name, executor_tg_id):
    conn = db()

    conn.execute("""
        INSERT INTO location_requests(
            location_name,
            district,
            region,
            description,
            executor_name,
            executor_tg_id
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        location_name,
        district,
        region,
        description,
        executor_name,
        executor_tg_id
    ))

    conn.commit()
    conn.close()


def get_location_requests():
    conn = db()

    rows = conn.execute("""
        SELECT *
        FROM location_requests
        ORDER BY id DESC
    """).fetchall()

    conn.close()
    return rows


def approve_location_request(request_id):
    conn = db()

    req = conn.execute("""
        SELECT *
        FROM location_requests
        WHERE id = ?
    """, (request_id,)).fetchone()

    if not req:
        conn.close()
        return None

    conn.execute("""
        INSERT OR IGNORE INTO locations(name, district, region, status, is_active)
        VALUES (?, ?, ?, 'active', 1)
    """, (
        req["location_name"],
        req["district"],
        req["region"]
    ))

    conn.execute("""
        UPDATE location_requests
        SET status = 'approved'
        WHERE id = ?
    """, (request_id,))

    conn.commit()
    conn.close()
    return req


def create_ad(title, text, image_url="", link_url="", button_text="Подробнее", placement="home_top", is_active=1, sort_order=100):
    conn = db()

    conn.execute("""
        INSERT INTO ads(
            title,
            text,
            image_url,
            link_url,
            button_text,
            placement,
            is_active,
            sort_order
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        title,
        text,
        image_url,
        link_url,
        button_text,
        placement,
        is_active,
        sort_order
    ))

    conn.commit()
    conn.close()


def get_active_ads(placement=None):
    conn = db()

    if placement:
        rows = conn.execute("""
            SELECT *
            FROM ads
            WHERE COALESCE(is_active, 1) = 1
              AND placement = ?
            ORDER BY sort_order ASC, id DESC
        """, (placement,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT *
            FROM ads
            WHERE COALESCE(is_active, 1) = 1
            ORDER BY sort_order ASC, id DESC
        """).fetchall()

    conn.close()
    return rows


def get_all_ads():
    conn = db()

    rows = conn.execute("""
        SELECT *
        FROM ads
        ORDER BY is_active DESC, sort_order ASC, id DESC
    """).fetchall()

    conn.close()
    return rows


def toggle_ad(ad_id):
    conn = db()

    row = conn.execute("""
        SELECT *
        FROM ads
        WHERE id = ?
    """, (ad_id,)).fetchone()

    if row:
        new_status = 0 if row["is_active"] else 1

        conn.execute("""
            UPDATE ads
            SET is_active = ?
            WHERE id = ?
        """, (new_status, ad_id))

    conn.commit()
    conn.close()


def delete_ad(ad_id):
    conn = db()

    conn.execute("""
        DELETE FROM ads
        WHERE id = ?
    """, (ad_id,))

    conn.commit()
    conn.close()


def get_events_version():
    conn = db()

    row = conn.execute("""
        SELECT
            COALESCE((SELECT MAX(id) FROM audit_log), 0) AS last_audit_id,
            COALESCE((SELECT COUNT(*) FROM requests), 0) AS requests_count,
            COALESCE((SELECT COUNT(*) FROM responses), 0) AS responses_count,
            COALESCE((SELECT COUNT(*) FROM executors), 0) AS executors_count,
            COALESCE((SELECT COUNT(*) FROM executor_categories), 0) AS categories_count,
            COALESCE((SELECT COUNT(*) FROM location_requests), 0) AS location_requests_count,
            COALESCE((SELECT COUNT(*) FROM service_suggestions), 0) AS suggestions_count,
            COALESCE((SELECT COUNT(*) FROM ads), 0) AS ads_count
    """).fetchone()

    conn.close()

    return (
        f"{row['last_audit_id']}-"
        f"{row['requests_count']}-"
        f"{row['responses_count']}-"
        f"{row['executors_count']}-"
        f"{row['categories_count']}-"
        f"{row['location_requests_count']}-"
        f"{row['suggestions_count']}"
        f"{row['ads_count']}"
    )


def get_stats():
    conn = db()

    stats = {
        "requests_total": conn.execute("SELECT COUNT(*) AS c FROM requests").fetchone()["c"],
        "requests_new": conn.execute("SELECT COUNT(*) AS c FROM requests WHERE status='new'").fetchone()["c"],
        "requests_searching": conn.execute("SELECT COUNT(*) AS c FROM requests WHERE status='searching_executor'").fetchone()["c"],
        "requests_in_work": conn.execute("SELECT COUNT(*) AS c FROM requests WHERE status='in_work'").fetchone()["c"],
        "requests_executor_done": conn.execute("SELECT COUNT(*) AS c FROM requests WHERE status='executor_done'").fetchone()["c"],
        "requests_dispute": conn.execute("SELECT COUNT(*) AS c FROM requests WHERE status='dispute'").fetchone()["c"],
        "requests_done": conn.execute("SELECT COUNT(*) AS c FROM requests WHERE status='done'").fetchone()["c"],
        "executors_total": conn.execute("SELECT COUNT(*) AS c FROM executors").fetchone()["c"],
        "locations_total": conn.execute("SELECT COUNT(*) AS c FROM locations WHERE COALESCE(is_active, 1)=1").fetchone()["c"],
        "location_requests_pending": conn.execute("SELECT COUNT(*) AS c FROM location_requests WHERE status='pending'").fetchone()["c"],
        "suggestions_total": conn.execute("SELECT COUNT(*) AS c FROM service_suggestions").fetchone()["c"],
        "suggestions_new": conn.execute("SELECT COUNT(*) AS c FROM service_suggestions WHERE status='new'").fetchone()["c"],
        "ads_total": conn.execute("SELECT COUNT(*) AS c FROM ads").fetchone()["c"],
    }

    conn.close()
    return stats

def get_service_subcategory_by_name(name):
    conn = db()

    row = conn.execute("""
        SELECT
            service_subcategories.*,
            service_categories.name AS category_name,
            service_categories.emoji AS category_emoji
        FROM service_subcategories
        JOIN service_categories
            ON service_categories.id = service_subcategories.category_id
        WHERE service_subcategories.name = ?
        LIMIT 1
    """, (name,)).fetchone()

    conn.close()
    return row


def set_service_subcategory_requires_dispatcher(subcategory_id, requires_dispatcher):
    conn = db()

    conn.execute("""
        UPDATE service_subcategories
        SET requires_dispatcher = ?
        WHERE id = ?
    """, (
        1 if requires_dispatcher else 0,
        subcategory_id
    ))

    conn.commit()
    conn.close()


def get_service_subcategories_flat():
    conn = db()

    rows = conn.execute("""
        SELECT
            service_subcategories.*,
            service_categories.name AS category_name,
            service_categories.emoji AS category_emoji
        FROM service_subcategories
        JOIN service_categories
            ON service_categories.id = service_subcategories.category_id
        WHERE service_categories.is_active = 1
          AND service_subcategories.is_active = 1
        ORDER BY
            service_categories.sort_order ASC,
            service_subcategories.sort_order ASC,
            service_subcategories.name ASC
    """).fetchall()

    conn.close()
    return rows


def set_executor_subcategories(executor_id, subcategory_ids):
    conn = db()

    conn.execute("""
        UPDATE executor_subscriptions
        SET is_active = 0
        WHERE executor_id = ?
    """, (executor_id,))

    for subcategory_id in subcategory_ids:
        conn.execute("""
            INSERT INTO executor_subscriptions(
                executor_id,
                subcategory_id,
                is_active,
                is_paid
            )
            VALUES (?, ?, 1, 0)
            ON CONFLICT(executor_id, subcategory_id)
            DO UPDATE SET
                is_active = 1,
                is_paid = 0
        """, (
            executor_id,
            subcategory_id
        ))

    conn.commit()
    conn.close()


def set_executor_locations(executor_id, location_names):
    conn = db()

    conn.execute("""
        DELETE FROM executor_locations
        WHERE executor_id = ?
    """, (executor_id,))

    clean_locations = []

    for location_name in location_names:
        if not location_name:
            continue

        name = str(location_name).strip()

        if not name or name in clean_locations:
            continue

        clean_locations.append(name)

        conn.execute("""
            INSERT OR IGNORE INTO executor_locations(
                executor_id,
                location_name
            )
            VALUES (?, ?)
        """, (
            executor_id,
            name
        ))

    if clean_locations:
        conn.execute("""
            UPDATE executors
            SET location_name = ?
            WHERE tg_id = ?
        """, (
            ", ".join(clean_locations),
            executor_id
        ))

    conn.commit()
    conn.close()


def get_executor_locations(executor_id):
    conn = db()

    rows = conn.execute("""
        SELECT *
        FROM executor_locations
        WHERE executor_id = ?
        ORDER BY location_name ASC
    """, (executor_id,)).fetchall()

    conn.close()
    return rows


def get_executors_by_subcategory(subcategory_name, public_location=None):
    conn = db()

    if public_location:
        rows = conn.execute("""
            SELECT DISTINCT executors.*
            FROM executors
            JOIN executor_subscriptions
                ON executor_subscriptions.executor_id = executors.tg_id
            JOIN service_subcategories
                ON service_subcategories.id = executor_subscriptions.subcategory_id
            LEFT JOIN executor_locations
                ON executor_locations.executor_id = executors.tg_id
            WHERE service_subcategories.name = ?
              AND executor_subscriptions.is_active = 1
              AND executors.is_active = 1
              AND COALESCE(executors.is_available, 1) = 1
              AND (
                    executor_locations.location_name = ?
                    OR executors.location_name = ?
                    OR executors.location_name IS NULL
                    OR executors.location_name = ''
                  )
            ORDER BY
              executors.trust_score DESC,
              executors.rating DESC,
              executors.completed_count DESC
        """, (
            subcategory_name,
            public_location,
            public_location
        )).fetchall()
    else:
        rows = conn.execute("""
            SELECT DISTINCT executors.*
            FROM executors
            JOIN executor_subscriptions
                ON executor_subscriptions.executor_id = executors.tg_id
            JOIN service_subcategories
                ON service_subcategories.id = executor_subscriptions.subcategory_id
            WHERE service_subcategories.name = ?
              AND executor_subscriptions.is_active = 1
              AND executors.is_active = 1
              AND COALESCE(executors.is_available, 1) = 1
            ORDER BY
              executors.trust_score DESC,
              executors.rating DESC,
              executors.completed_count DESC
        """, (subcategory_name,)).fetchall()

    conn.close()
    return rows


def create_service_suggestion(title, description, phone, public_location):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO service_suggestions(
            title,
            description,
            phone,
            public_location,
            status
        )
        VALUES (?, ?, ?, ?, 'new')
    """, (
        title,
        description,
        phone,
        public_location
    ))

    suggestion_id = cur.lastrowid

    cur.execute("""
        INSERT INTO audit_log(request_id, action, details)
        VALUES (?, ?, ?)
    """, (
        None,
        "service_suggestion_created",
        f"Предложена услуга: {title}; населённый пункт: {public_location}"
    ))

    conn.commit()
    conn.close()

    return suggestion_id


def get_service_suggestions(status=None):
    conn = db()

    if status:
        rows = conn.execute("""
            SELECT *
            FROM service_suggestions
            WHERE status = ?
            ORDER BY id DESC
        """, (status,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT *
            FROM service_suggestions
            ORDER BY
                CASE status
                    WHEN 'new' THEN 1
                    WHEN 'accepted' THEN 2
                    WHEN 'rejected' THEN 3
                    ELSE 4
                END,
                id DESC
        """).fetchall()

    conn.close()
    return rows


def update_service_suggestion_status(suggestion_id, status, admin_comment=""):
    conn = db()

    conn.execute("""
        UPDATE service_suggestions
        SET status = ?,
            admin_comment = ?
        WHERE id = ?
    """, (
        status,
        admin_comment,
        suggestion_id
    ))

    conn.execute("""
        INSERT INTO audit_log(request_id, action, details)
        VALUES (?, ?, ?)
    """, (
        None,
        "service_suggestion_status_changed",
        f"Предложение #{suggestion_id} изменено на {status}. Комментарий: {admin_comment}"
    ))

    conn.commit()
    conn.close()
