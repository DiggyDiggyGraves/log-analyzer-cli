import argparse
import re
import sqlite3

def init_db(db_name="logs.db"):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS access_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, method TEXT, endpoint TEXT, status INTEGER, response_time REAL)")
    conn.commit()
    return conn

def parse_logs(file_path, conn):
    pattern = re.compile(r"\[(.*?)\]\s+(\w+)\s+(.*?)\s+(\d+)\s+([\d\.]+)")
    cursor = conn.cursor()
    count = 0
    with open(file_path, "r") as f:
        for line in f:
            match = pattern.search(line)
            if match:
                ts, method, endpoint, status, resp_time = match.groups()
                cursor.execute("INSERT INTO access_logs (timestamp, method, endpoint, status, response_time) VALUES (?, ?, ?, ?, ?)", (ts, method, endpoint, int(status), float(resp_time)))
                count += 1
    conn.commit()
    print(f"Successfully ingested {count} log entries.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--db", default="logs.db")
    args = parser.parse_args()
    conn = init_db(args.db)
    parse_logs(args.file, conn)
    conn.close()
