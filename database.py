import sqlite3
import datetime 
import json

def create_tables():
    conn = sqlite3.connect('evaluation.db')
    conn.execute("""
                CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                build_system,
                metrics TEXT,
                evaluation TEXT,
                overall_rating TEXT,
                errors TEXT
                )
                 """)
    conn.commit()
    conn.close()

def insert(filename, build_system, metrics, evaluation, overall_rating, errors):
    conn = sqlite3.connect('evaluation.db')
    cursor = conn.cursor()
    cursor.execute("""INSERT OR IGNORE INTO evaluations (filename, submitted_at, build_system, metrics, evaluation, overall_rating, errors)
                 VALUES (?, ?, ?, ?, ?, ?, ?)
                 """, (filename, datetime.datetime.now(), build_system, json.dumps(metrics), json.dumps(evaluation), evaluation.get(overall_rating) if evaluation else None, json.dumps(errors)))
    conn.commit()
    evaluation_id = cursor.lastrowid
    conn.close()
    return evaluation_id
    
def get_all():
    conn = sqlite3.connect('evaluation.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''SELECT * FROM evaluations 
                   ORDER BY submitted_at DESC
                   ''')
   
    result = conn.fetchall()
    rows = [dict(row) for row in result]
    conn.close()
    return rows

def get_by_id(evaluation_id):
    conn = sqlite3.connect('evaluation.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''SELECT * FROM evaluations
                   WHERE id = ?
                   ''', (evaluation_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None
    
    result = dict(row)
    result['metrics'] = json.loads(result['metrics'])
    result['evaluation'] = json.loads(result['evaluation'])
    result['errors'] = json.loads(result['errors'])

    return result

