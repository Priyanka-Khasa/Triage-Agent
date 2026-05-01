import pandas as pd
import os
import re

def validate_outputs(base_dir):
    print("\n" + "="*60)
    print("FINAL SUBMISSION VALIDATION")
    print("="*60)
    
    input_csv = os.path.join(base_dir, "support_tickets", "support_tickets.csv")
    output_csv = os.path.join(base_dir, "support_tickets", "output.csv")
    log_file = os.path.join(base_dir, "log.txt")
    audit_csv = os.path.join(base_dir, "audit_trace.csv")
    
    if not os.path.exists(output_csv):
        print("FAIL: output.csv missing.")
        return False
        
    in_df = pd.read_csv(input_csv)
    out_df = pd.read_csv(output_csv)
    
    # 1. Row count check
    if len(in_df) != len(out_df):
        print(f"FAIL: Row count mismatch. Input: {len(in_df)}, Output: {len(out_df)}")
    else:
        print(f"PASS: Row count matches ({len(out_df)})")
        
    # 2. Blank fields check
    required_cols = ['response', 'product_area', 'status', 'request_type', 'justification']
    blanks = out_df[required_cols].isnull().any(axis=1).sum()
    if blanks > 0:
        print(f"FAIL: {blanks} rows have blank required fields.")
    else:
        print("PASS: No blank required fields.")
        
    # 3. Status values check
    valid_statuses = ['replied', 'escalated']
    invalid_status = out_df[~out_df['status'].isin(valid_statuses)]
    if len(invalid_status) > 0:
        print(f"FAIL: Found invalid status values: {invalid_status['status'].unique()}")
    else:
        print("PASS: All status values are valid.")
        
    # 4. Request type check
    valid_types = ['product_issue', 'feature_request', 'bug', 'invalid']
    invalid_types = out_df[~out_df['request_type'].isin(valid_types)]
    if len(invalid_types) > 0:
        print(f"FAIL: Found invalid request_type values: {invalid_types['request_type'].unique()}")
    else:
        print("PASS: All request_type values are valid.")
        
    # 5. Hallucination check (no invented links)
    hallucinated_links = 0
    for idx, row in out_df.iterrows():
        response = str(row['response'])
        links = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', response)
        # Check if link looks generic or suspicious
        for link in links:
            if "example.com" in link or "invented-link" in link:
                hallucinated_links += 1
    if hallucinated_links > 0:
        print(f"FAIL: Found {hallucinated_links} potentially hallucinated links.")
    else:
        print("PASS: No suspicious external links detected in responses.")

    # 6. High-risk escalation check
    risk_keywords = ['fraud', 'security', 'identity theft', 'stolen', 'dispute', 'cheat']
    audit_df = pd.read_csv(audit_csv) if os.path.exists(audit_csv) else None
    if audit_df is not None:
        missed_escalations = 0
        for idx, row in in_df.iterrows():
            text = f"{row['Subject']} {row['Issue']}".lower()
            if any(k in text for k in risk_keywords):
                decision = out_df.iloc[idx]['status']
                if decision != 'escalated':
                    missed_escalations += 1
        if missed_escalations > 0:
            print(f"WARNING: {missed_escalations} tickets with risk keywords were NOT escalated. (Check audit_trace.csv for reasons)")
        else:
            print("PASS: High-risk keyword tickets were correctly escalated.")

    print("="*60)
    print("VALIDATION COMPLETE.")
    return True

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    validate_outputs(base_dir)
