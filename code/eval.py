import os
import pandas as pd
from agent import TriageAgent


def run_evaluation(data_dir: str, sample_csv: str, report_path: str = None):
    print(f"Running sample evaluation against {os.path.basename(sample_csv)}...")
    agent = TriageAgent(data_dir=data_dir, retrieval_threshold=0.15)

    df = pd.read_csv(sample_csv)
    total = len(df)

    status_correct = 0
    type_correct = 0
    area_correct = 0
    differences = []

    for idx, row in df.iterrows():
        issue = str(row.get('Issue', '') or '')
        subject = str(row.get('Subject', '') or '')
        company = str(row.get('Company', 'None') or 'None')

        exp_status = str(row.get('Status', '')).strip().lower()
        exp_type = str(row.get('Request Type', '')).strip().lower()
        exp_area = str(row.get('Product Area', '')).strip().lower()

        ticket_result = agent.process_ticket(issue, subject, company)
        status = ticket_result['status']
        request_type = ticket_result['request_type']
        product_area = ticket_result['product_area']

        stat_match = (status == exp_status) if exp_status and exp_status != 'nan' else True
        type_match = (request_type == exp_type) if exp_type and exp_type != 'nan' else True
        area_match = (product_area.lower() in exp_area or exp_area in product_area.lower()) if exp_area and exp_area != 'nan' else True

        if stat_match:
            status_correct += 1
        if type_match:
            type_correct += 1
        if area_match:
            area_correct += 1

        if not (stat_match and type_match and area_match):
            diff = {
                "row": idx + 1,
                "subject": subject,
                "status": {"exp": exp_status, "pred": status, "match": stat_match},
                "type": {"exp": exp_type, "pred": request_type, "match": type_match},
                "area": {"exp": exp_area, "pred": product_area, "match": area_match}
            }
            differences.append(diff)

    metrics = {
        "total": total,
        "status_acc": status_correct / total if total > 0 else 0,
        "type_acc": type_correct / total if total > 0 else 0,
        "area_acc": area_correct / total if total > 0 else 0,
    }
    
    report_lines = [
        "=" * 60,
        "SAMPLE EVALUATION REPORT",
        "=" * 60,
        f"Sample Source: {os.path.basename(sample_csv)}",
        f"Total Tickets: {total}",
        "",
        "METRICS:",
        f"  Status Accuracy:       {metrics['status_acc']*100:.1f}%",
        f"  Request Type Accuracy: {metrics['type_acc']*100:.1f}%",
        f"  Product Area Match:    {metrics['area_acc']*100:.1f}%",
        "",
        "DETAILED DISCREPANCIES:",
        "-" * 60
    ]

    for d in differences:
        report_lines.append(f"Row {d['row']}: {d['subject']}")
        if not d['status']['match']:
            report_lines.append(f"  [Status] Expected: '{d['status']['exp']}', Predicted: '{d['status']['pred']}'")
        if not d['type']['match']:
            report_lines.append(f"  [Type]   Expected: '{d['type']['exp']}', Predicted: '{d['type']['pred']}'")
        if not d['area']['match']:
            report_lines.append(f"  [Area]   Expected: '{d['area']['exp']}', Predicted: '{d['area']['pred']}'")
        report_lines.append("")

    report_text = "\n".join(report_lines)
    print(report_text)

    if report_path:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"Report saved to {report_path}\n")
    
    return metrics


if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    sample_csv = os.path.join(base_dir, "support_tickets", "sample_support_tickets.csv")
    report_path = os.path.join(base_dir, "sample_eval_report.txt")
    run_evaluation(data_dir, sample_csv, report_path)
