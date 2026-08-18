import os
import json
import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='static')

# Render injects DATABASE_URL automatically when you link the database.
# Locally (pgAdmin) set it yourself, e.g.:
#   postgresql://postgres:YOURPASSWORD@localhost:5432/maturity
DATABASE_URL = os.environ.get('DATABASE_URL')


def get_conn():
    # 'require' on Render (cloud enforces SSL), 'disable' for local pgAdmin.
    sslmode = os.environ.get('PGSSLMODE', 'require')
    return psycopg2.connect(DATABASE_URL, sslmode=sslmode)


def init_db():
    with get_conn() as con, con.cursor() as cur:
        cur.execute('''
            CREATE TABLE IF NOT EXISTS assessments (
                id       SERIAL PRIMARY KEY,
                name     TEXT,
                owner    TEXT,
                repo     TEXT,
                scope    TEXT,
                answers  JSONB,
                result   TEXT,
                created  TIMESTAMP DEFAULT NOW(),
                updated  TIMESTAMP DEFAULT NOW()
            );
        ''')
        # Safe upgrade for existing databases that pre-date the repo column.
        cur.execute("ALTER TABLE assessments ADD COLUMN IF NOT EXISTS repo TEXT;")
        con.commit()


# ---------- serve the front-end ----------
@app.route('/')
def home():
    return send_from_directory('static', 'index.html')


# ---------- API ----------
@app.route('/list')
def list_all():
    with get_conn() as con, con.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute('''
            SELECT id, name, owner, repo, scope, answers, result, created, updated
            FROM assessments
            ORDER BY created DESC;
        ''')
        rows = cur.fetchall()
    return jsonify(rows)


@app.route('/get/<int:rec_id>')
def get_one(rec_id):
    with get_conn() as con, con.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute('''
            SELECT id, name, owner, repo, scope, answers, result
            FROM assessments WHERE id = %s;
        ''', (rec_id,))
        row = cur.fetchone()
    if not row:
        return jsonify(None), 404
    return jsonify(row)


@app.route('/save', methods=['POST'])
def save():
    """Insert a new record, or update an existing one when an id is supplied."""
    d = request.get_json(silent=True) or {}
    rec_id = d.get('id')
    name = d.get('name', '')
    owner = d.get('owner', '')
    repo = d.get('repo', '')
    scope = d.get('scope', '')
    answers = json.dumps(d.get('ans', {}))

    with get_conn() as con, con.cursor() as cur:
        if rec_id:
            cur.execute('''
                UPDATE assessments
                   SET name = %s, owner = %s, repo = %s, scope = %s,
                       answers = %s, updated = NOW()
                 WHERE id = %s
             RETURNING id;
            ''', (name, owner, repo, scope, answers, rec_id))
            row = cur.fetchone()
            new_id = row[0] if row else rec_id
        else:
            cur.execute('''
                INSERT INTO assessments (name, owner, repo, scope, answers, result)
                VALUES (%s, %s, %s, %s, %s, '')
             RETURNING id;
            ''', (name, owner, repo, scope, answers))
            new_id = cur.fetchone()[0]
        con.commit()
    return jsonify(ok=True, id=new_id)


@app.route('/result/<int:rec_id>', methods=['POST'])
def set_result(rec_id):
    """Persist the classification result for a record."""
    d = request.get_json(silent=True) or {}
    result = d.get('result', '')
    with get_conn() as con, con.cursor() as cur:
        cur.execute('''
            UPDATE assessments SET result = %s, updated = NOW()
             WHERE id = %s;
        ''', (result, rec_id))
        con.commit()
    return jsonify(ok=True)


@app.route('/delete/<int:rec_id>', methods=['POST'])
def delete(rec_id):
    with get_conn() as con, con.cursor() as cur:
        cur.execute('DELETE FROM assessments WHERE id = %s;', (rec_id,))
        con.commit()
    return jsonify(ok=True)


init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
