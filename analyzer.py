import argparse
import json
import re
import sqlite3
import time
import requests

KOFI_URL = "https://ko-fi.com/andrewhall99564"

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

def tail_log_file(file_path, conn, webhook_url=None):
    pattern = re.compile(r"\[(.*?)\]\s+(\w+)\s+(.*?)\s+(\d+)\s+([\d\.]+)")
    cursor = conn.cursor()
    print(f"Tailing log file: {file_path} (Press Ctrl+C to stop)...")
    try:
        with open(file_path, "r") as f:
            f.seek(0, 2)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                line_str = line.strip()
                match = pattern.search(line_str)
                if match:
                    ts, method, endpoint, status, resp_time = match.groups()
                    status_code = int(status)
                    cursor.execute("""
                        INSERT INTO access_logs (timestamp, method, endpoint, status, response_time)
                        VALUES (?, ?, ?, ?, ?)
                    """, (ts, method, endpoint, status_code, float(resp_time)))
                    conn.commit()
                    print(f"[LIVE] {ts} | {method} {endpoint} | Status: {status} | {resp_time}ms")
                    
                    if status_code >= 500 and webhook_url:
                        send_webhook(webhook_url, f"Critical 5xx Error detected on live tail: {method} {endpoint} - Status {status}")
    except KeyboardInterrupt:
        print("\nStopped live tail mode.")

def query_logs(conn, status=None, endpoint=None):
    cursor = conn.cursor()
    query = "SELECT timestamp, method, endpoint, status, response_time FROM access_logs WHERE 1=1"
    params = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if endpoint:
        query += " AND endpoint LIKE ?"
        params.append(f"%{endpoint}%")
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    print(f"\n--- Filtered Query Results ({len(results)} matches) ---")
    for row in results:
        print(f"  [{row[0]}] {row[1]} {row[2]} - Status: {row[3]} - {row[4]}ms")

def run_stats_and_anomaly_detection(conn, webhook_url=None):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM access_logs WHERE status >= 500")
    server_errors = cursor.fetchone()[0]

    print("\n--- Statistical Summary & Anomaly Check ---")
    print(f"Total Server Errors (5xx): {server_errors}")

    if server_errors > 10 and webhook_url:
        msg = f"Anomaly Alert: High count of 5xx server errors detected ({server_errors} total)."
        print(f"🚨 {msg}")
        send_webhook(webhook_url, msg)

def send_webhook(webhook_url, message):
    try:
        payload = {"content": f"🚨 Log Analyzer Alert: {message}"}
        requests.post(webhook_url, json=payload, timeout=5)
    except Exception as e:
        print(f"Failed to dispatch webhook: {e}")

def generate_report(conn, export_path=None):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM access_logs")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT status, COUNT(*) FROM access_logs GROUP BY status")
    status_breakdown = {f"HTTP {status}": count for status, count in cursor.fetchall()}

    cursor.execute("SELECT endpoint, AVG(response_time) as avg_rt FROM access_logs GROUP BY endpoint ORDER BY avg_rt DESC LIMIT 5")
    slowest_endpoints = [{"endpoint": ep, "avg_response_time_ms": round(rt, 2)} for ep, rt in cursor.fetchall()]

    support_footer = f"\n\n--- \n*Enjoying this tool? Support open-source development: [{KOFI_URL}]({KOFI_URL})*"

    if export_path:
        if export_path.endswith(".json"):
            data = {
                "total_requests": total,
                "status_breakdown": status_breakdown,
                "slowest_endpoints": slowest_endpoints,
                "support": KOFI_URL
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
                md_content += f"- `{item['endpoint']}`: {item['avg_response_time_ms']}ms\n"
            md_content += support_footer
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
            print(f"  {item['endpoint']}: {item['avg_response_time_ms']}ms")
        print(f"\n💡 Support open-source development: {KOFI_URL}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SQLite Log Analyzer CLI with Tailing, Filtering, and Webhook Alerts")
    parser.add_argument("--file", help="Path to the log file to analyze")
    parser.add_argument("--db", default="logs.db", help="SQLite database file name")
    parser.add_argument("--export", help="Path to export report (.json or .md)")
    parser.add_argument("--tail", action="store_true", help="Real-time tail mode for incoming log streams")
    parser.add_argument("--filter-status", type=int, help="Filter database logs by specific HTTP status code")
    parser.add_argument("--filter-endpoint", help="Filter database logs by endpoint substring")
    parser.add_argument("--stats", action="store_true", help="Run statistical analysis and anomaly detection")
    parser.add_argument("--webhook", help="Webhook URL for anomaly alerts")
    args = parser.parse_args()

    conn = init_db(args.db)

    if args.file and not args.tail:
        parse_logs(args.file, conn)

    if args.tail:
        if not args.file:
            print("Error: --file is required when using --tail")
        else:
            tail_log_file(args.file, conn, args.webhook)

    if args.filter_status is not None or args.filter_endpoint:
        query_logs(conn, args.filter_status, args.filter_endpoint)

    if args.stats:
        run_stats_and_anomaly_detection(conn, args.webhook)

    if not args.tail and args.file:
        generate_report(conn, args.export)

    conn.close()
