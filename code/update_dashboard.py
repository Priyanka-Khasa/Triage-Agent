import json
import os
import pandas as pd
import re

def update_dashboard():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_csv = os.path.join(base_dir, "support_tickets", "output.csv")
    audit_csv = os.path.join(base_dir, "audit_trace.csv")
    html_path = os.path.join(base_dir, "triage_dashboard.html")
    
    if not os.path.exists(output_csv) or not os.path.exists(audit_csv):
        print("Missing data files for dashboard generation.")
        return

    # Load data
    df_out = pd.read_csv(output_csv)
    df_audit = pd.read_csv(audit_csv)
    
    # Merge data
    tickets = []
    for idx, row in df_out.iterrows():
        audit_match = df_audit[df_audit['row_id'] == (idx + 1)]
        if audit_match.empty:
            continue
        audit_row = audit_match.iloc[0]
        tickets.append({
            "row_id": int(idx + 1),
            "issue": str(row['issue']),
            "subject": str(row['subject']),
            "company": str(row['company']),
            "response": str(row['response']),
            "product_area": str(row['product_area']),
            "status": str(row['status']),
            "request_type": str(row['request_type']),
            "justification": str(audit_row['justification']),
            "final_confidence": float(audit_row['final_confidence']),
            "escalation_route": str(audit_row['escalation_route']) if audit_row['escalation_route'] != 'none' else None,
            "escalation_reason": "Sensitive handling required" if row['status'] == 'escalated' else None
        })

    # Get corpus stats
    corpus_stats = {"HackerRank": 0, "Claude": 0, "Visa": 0}
    report_path = os.path.join(base_dir, "corpus_report.txt")
    if os.path.exists(report_path):
        with open(report_path, 'r') as f:
            content = f.read()
            for domain in corpus_stats.keys():
                # Use raw string for regex
                match = re.search(f"{domain}" + r".*?(\d+) documents", content)
                if match:
                    corpus_stats[domain] = int(match.group(1))

    # Update HTML
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # Inject JSON using direct string replacement instead of regex to avoid escape issues
    # We look for the markers we put in the HTML
    tickets_marker = "const allTickets = [];"
    coverage_marker = "const corpusCoverage = {};"
    
    if tickets_marker in html_content:
        html_content = html_content.replace(tickets_marker, f"const allTickets = {json.dumps(tickets)};")
    else:
        # Use a lambda to avoid backslash escaping issues in re.sub
        pattern = r'const allTickets = \[.*?\];'
        replacement = f"const allTickets = {json.dumps(tickets)};"
        html_content = re.sub(pattern, lambda m: replacement, html_content, flags=re.DOTALL)

    if coverage_marker in html_content:
        html_content = html_content.replace(coverage_marker, f"const corpusCoverage = {json.dumps(corpus_stats)};")
    else:
        pattern = r'const corpusCoverage = \{.*?\};'
        replacement = f"const corpusCoverage = {json.dumps(corpus_stats)};"
        html_content = re.sub(pattern, lambda m: replacement, html_content, flags=re.DOTALL)

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Dashboard updated successfully at {html_path}")

if __name__ == "__main__":
    update_dashboard()
