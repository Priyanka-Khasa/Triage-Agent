import os
import argparse
import pandas as pd
from dotenv import load_dotenv

from agent import TriageAgent
from llm_agent import LLMTriageAgent
from corpus_analyzer import generate_corpus_report
from eval import run_evaluation


def main():
    parser = argparse.ArgumentParser(description="Support Triage Agent CLI")
    parser.add_argument("--judge-mode", action="store_true", help="Run in judge validation mode")
    parser.add_argument("--no-llm", action="store_true", help="Disable LLM and use rule-based agent only")
    args = parser.parse_args()

    # Load .env file for API keys
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    sample_csv = os.path.join(base_dir, "support_tickets", "sample_support_tickets.csv")
    input_csv = os.path.join(base_dir, "support_tickets", "support_tickets.csv")
    output_csv = os.path.join(base_dir, "support_tickets", "output.csv")
    execution_log_path = os.path.join(base_dir, "log.txt")
    corpus_report_path = os.path.join(base_dir, "corpus_report.txt")
    audit_trace_path = os.path.join(base_dir, "audit_trace.csv")
    sample_eval_report_path = os.path.join(base_dir, "sample_eval_report.txt")

    if args.judge_mode:
        print("=" * 60)
        print("JUDGE MODE ACTIVATED")
        print("=" * 60)

    # 1. Validate corpus exists
    print("Step 1/8: Validating corpus and analyzing coverage...")
    if not os.path.exists(data_dir) or not os.listdir(data_dir):
        print("Error: Corpus directory is empty or missing.")
        return

    # 7. Generate corpus_report.txt
    corpus_analyzer = generate_corpus_report(data_dir, corpus_report_path)
    print(f"Corpus report written to {corpus_report_path}")

    # 2. Run sample evaluation
    eval_metrics = None
    if args.judge_mode:
        print("\nStep 2/8: Running sample evaluation...")
        eval_metrics = run_evaluation(data_dir, sample_csv, sample_eval_report_path)

    use_llm = not args.no_llm and bool(os.environ.get('GROQ_API_KEY') or os.environ.get('GROQ_API_KEY_2'))

    if use_llm:
        print("\nStep 3/8: Initializing LLM-powered triage pipeline (Groq/Llama 3.3 70B)...")
        agent = LLMTriageAgent(data_dir=data_dir, corpus_analyzer=corpus_analyzer)
    else:
        print("\nStep 3/8: Initializing rule-based triage pipeline...")
        agent = TriageAgent(data_dir=data_dir, retrieval_threshold=0.15, corpus_analyzer=corpus_analyzer)

    # 3. Run final support_tickets.csv
    print(f"\nStep 4/8: Processing {os.path.basename(input_csv)}...")
    df = pd.read_csv(input_csv)
    output_rows = []
    audit_rows = []

    with open(execution_log_path, "w", encoding="utf-8") as log_file:
        for idx, row in df.iterrows():
            issue = str(row.get('Issue', '') or '')
            subject = str(row.get('Subject', '') or '')
            company = str(row.get('Company', 'None') or 'None')

            row_num = idx + 1
            if row_num % 5 == 0 or row_num == len(df):
                print(f"  Processed {row_num}/{len(df)} tickets...")

            ticket_result = agent.process_ticket(issue, subject, company)
            retrieved_files = ", ".join(ticket_result['retrieved_sources']) if ticket_result['retrieved_sources'] else 'None'

            # 5. Generate log.txt
            log_entry = [
                f"Row: {row_num}",
                f"Company: {company}",
                f"Inferred Domain: {ticket_result['domain']}",
                f"Corpus Coverage: {'Yes' if corpus_analyzer.get_coverage_status(ticket_result['domain']) else 'No'}",
                f"Subject: {subject}",
                f"Request Type: {ticket_result['request_type']}",
                f"Product Area: {ticket_result['product_area']}",
                f"Sub-requests: {', '.join(ticket_result['sub_requests']) if ticket_result.get('sub_requests') else 'none'}",
                f"Risk Level: {ticket_result['risk_level']}",
                f"Risk Flags: {', '.join(ticket_result['risk_flags']) if ticket_result['risk_flags'] else 'none'}",
                f"Retrieved Source Files: {retrieved_files}",
                f"Retrieval Confidence: {ticket_result['retrieval_confidence']:.4f}",
                f"Classification Confidence: {ticket_result['classification_confidence']:.4f}",
                f"Risk Penalty: {ticket_result['risk_penalty']:.2f}",
                f"Final Confidence: {ticket_result['final_confidence']:.4f}",
                f"Status: {ticket_result['status']}",
            ]
            if ticket_result['status'] == 'escalated':
                escalation_route = ticket_result.get('escalation_route', 'general human support')
                escalation_reason = ticket_result.get('escalation_reason', 'No specific reason')
                log_entry.append(f"Escalation Route: {escalation_route}")
                log_entry.append(f"Escalation Reason: {escalation_reason}")
            log_entry.extend([
                f"Final Justification: {ticket_result['justification']}",
                "-" * 40,
            ])
            log_file.write("\n".join(log_entry) + "\n")

            # 4. Generate output.csv
            output_rows.append({
                "issue": issue,
                "subject": subject,
                "company": company,
                "response": ticket_result['response'],
                "product_area": ticket_result['product_area'],
                "status": ticket_result['status'],
                "request_type": ticket_result['request_type'],
                "justification": ticket_result['justification']
            })

            # 6. Generate audit_trace.csv
            audit_rows.append({
                "row_id": row_num,
                "inferred_domain": ticket_result['domain'],
                "request_type": ticket_result['request_type'],
                "product_area": ticket_result['product_area'],
                "risk_level": ticket_result['risk_level'],
                "risk_flags": "|".join(ticket_result['risk_flags']) if ticket_result['risk_flags'] else 'none',
                "retrieval_confidence": f"{ticket_result['retrieval_confidence']:.4f}",
                "final_confidence": f"{ticket_result['final_confidence']:.4f}",
                "top_sources": "|".join(ticket_result['retrieved_sources']) if ticket_result['retrieved_sources'] else 'none',
                "escalation_route": ticket_result.get('escalation_route') or 'none',
                "decision": ticket_result['status'],
                "justification": ticket_result['justification']
            })

    print(f"\nStep 5/8: Writing final outputs...")
    out_df = pd.DataFrame(output_rows)
    cols = ['issue', 'subject', 'company', 'response', 'product_area', 'status', 'request_type']
    out_df = out_df[cols]
    out_df.to_csv(output_csv, index=False)
    print(f"  [OK] {output_csv}")

    print(f"Step 6/8: Writing audit trace...")
    audit_df = pd.DataFrame(audit_rows)
    audit_df.to_csv(audit_trace_path, index=False)
    print(f"  [OK] {audit_trace_path}")

    print("Step 7/8: Finalizing execution log...")
    print(f"  [OK] {execution_log_path}")

    # 9. Update Dashboard
    print("\nStep 8/9: Synchronizing Dashboard...")
    try:
        from update_dashboard import update_dashboard
        update_dashboard()
    except Exception as e:
        print(f"  [Warning] Could not update dashboard: {e}")

    # 8. Print final summary
    print("\nStep 9/9: Final Summary")
    print("=" * 60)
    print(f"Tickets Processed: {len(df)}")
    print(f"Escalation Rate:   {sum(1 for r in output_rows if r['status'] == 'escalated') / len(df) * 100:.1f}%")
    if eval_metrics:
        print(f"Eval Accuracy:     {eval_metrics['status_acc']*100:.1f}% (Status)")
    print(f"Corpus Coverage:   {corpus_analyzer.total_docs} documents analyzed")
    print("=" * 60)
    print("ALL ARTIFACTS GENERATED SUCCESSFULLY.")


if __name__ == '__main__':
    main()
