import argparse
import json
import re
import sqlite3

def init_db(db_name="logs.db"):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            method TEXT,
            endpoint TEXT,
            status INTEGER,
            response_time REAL
        )
    """)
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
                cursor.execute("""
                    INSERT INTO access_logs (timestamp, method, endpoint, status, response_time)
                    VALUES (?, ?, ?, ?, ?)
                """, (ts, method, endpoint, int(status), float(resp_time)))
                count += 1
    conn.commit()
    print(f"Successfully ingested {count} log entries.")

def generate_report(conn, export_path=None):
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM access_logs")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT status, COUNT(*) FROM access_logs GROUP BY status")
    status_breakdown = {f"HTTP {status}": count for status, count in cursor.fetchall()}

    cursor.execute("SELECT endpoint, AVG(response_time) as avg_rt FROM access_logs GROUP BY endpoint ORDER BY avg_rt DESC LIMIT 5")
    slowest_endpoints = [{"endpoint": ep, "avg_response_time_ms": round(rt, 2)} for ep, rt in cursor.fetchall()]

    if export_path:
        if export_path.endswith(".json"):
            data = {
                "total_requests": total,
                "status_breakdown": status_breakdown,
                "slowest_endpoints": slowest_endpoints
            }
            with open(export_path, "w") as f:
                json.dump(data, f, indent=4)
            print(f"Report exported successfully to {export_path}")
        elif export_path.endswith(".md"):
            md_content = f"# Log Analysis Report\n\n- **Total Requests**: {total}\n\n## Status Code Breakdown\n"
            for k, v in status_breakdown.items():
                md_content += f"- {k}: {v}\n"
            md_content += "\n## Top 5 Slowest Endpoints\n"
            for item in slowest_endpoints:
                md_content += f"- `{item["endpoint"]}`: {item["avg_response_time_ms"]}ms\n"
            with open(export_path, "w") as f:
                f.write(md_content)
            print(f"Report exported successfully to {export_path}")
        else:
            print("Error: Export file must end with .json or .md")
    else:
        print("\n--- Log Analysis Report ---")
        print(f"Total Requests: {total}")
        print("\nStatus Code Breakdown:")
        for k, v in status_breakdown.items():
            print(f"  {k}: {v} requests")
        print("\nTop 5 Slowest Endpoints (Avg Response Time):")
        for item in slowest_endpoints:
            print(f"  {item["endpoint"]}: {item["avg_response_time_ms"]}ms")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SQLite Log Analyzer CLI")
    parser.add_argument("--file", required=True, help="Path to the log file to analyze")
    parser.add_argument("--db", default="logs.db", help="SQLite database file name")
    parser.add_argument("--export", help="Path to export report (.json or .md)")
    args = parser.parse_args()

    conn = init_db(args.db)
    parse_logs(args.file, conn)
    generate_report(conn, args.export)
    conn.close()
