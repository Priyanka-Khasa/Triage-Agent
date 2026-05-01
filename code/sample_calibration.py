import os
import pandas as pd
from collections import defaultdict
from agent import TriageAgent


def categorize_failure(expected, predicted, field_name):
    """Categorize the type of prediction failure."""
    if field_name == 'status':
        if expected == 'replied' and predicted == 'escalated':
            return 'over_escalation'
        elif expected == 'escalated' and predicted == 'replied':
            return 'under_escalation'
        else:
            return 'status_mismatch'
    elif field_name == 'request_type':
        if expected == predicted:
            return 'correct'
        elif expected == 'invalid' or predicted == 'invalid':
            return 'invalid_classification'
        else:
            return 'type_confusion'
    elif field_name == 'product_area':
        return 'area_mismatch'
    return 'unknown'


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "..", "data")
    sample_csv = os.path.join(base_dir, "..", "support_tickets", "sample_support_tickets.csv")
    report_path = os.path.join(base_dir, "..", "sample_eval_report.txt")

    print("Initializing calibration pipeline...")
    agent = TriageAgent(data_dir=data_dir, retrieval_threshold=0.15)

    df = pd.read_csv(sample_csv)
    total = len(df)

    # Metrics
    status_correct = 0
    type_correct = 0
    area_correct = 0

    # Failure analysis
    status_failures = defaultdict(int)
    type_failures = defaultdict(int)
    area_failures = []
    risk_flag_patterns = defaultdict(int)
    request_type_patterns = defaultdict(int)
    status_by_risk = defaultdict(lambda: {'replied': 0, 'escalated': 0})

    predictions = []

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
        risk_flags = ticket_result['risk_flags']
        final_confidence = ticket_result['final_confidence']

        # Store prediction for pattern analysis
        predictions.append({
            'expected_status': exp_status,
            'predicted_status': status,
            'expected_type': exp_type,
            'predicted_type': request_type,
            'expected_area': exp_area,
            'predicted_area': product_area,
            'risk_flags': risk_flags,
            'final_confidence': final_confidence,
            'request_type': request_type,
        })

        # Status accuracy
        stat_match = (status == exp_status) if exp_status and exp_status != 'nan' else True
        if stat_match:
            status_correct += 1
        else:
            failure_type = categorize_failure(exp_status, status, 'status')
            status_failures[failure_type] += 1

        # Type accuracy
        type_match = (request_type == exp_type) if exp_type and exp_type != 'nan' else True
        if type_match:
            type_correct += 1
        else:
            failure_type = categorize_failure(exp_type, request_type, 'request_type')
            type_failures[failure_type] += 1

        # Area accuracy
        area_match = (product_area.lower() in exp_area or exp_area in product_area.lower()) if exp_area and exp_area != 'nan' else True
        if area_match:
            area_correct += 1
        else:
            area_failures.append({
                'expected': exp_area,
                'predicted': product_area.lower(),
                'risk_flags': risk_flags,
            })

        # Pattern tracking
        for flag in risk_flags:
            risk_flag_patterns[flag] += 1
        request_type_patterns[request_type] += 1
        primary_risk = risk_flags[0] if risk_flags else 'none'
        status_by_risk[primary_risk][status] += 1

    # Analyze confidence distribution
    replied_confidences = [p['final_confidence'] for p in predictions if p['predicted_status'] == 'replied']
    escalated_confidences = [p['final_confidence'] for p in predictions if p['predicted_status'] == 'escalated']

    avg_replied_conf = sum(replied_confidences) / len(replied_confidences) if replied_confidences else 0.0
    avg_escalated_conf = sum(escalated_confidences) / len(escalated_confidences) if escalated_confidences else 0.0
    min_replied_conf = min(replied_confidences) if replied_confidences else 0.0
    max_escalated_conf = max(escalated_confidences) if escalated_confidences else 0.0

    # Generate report
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("SAMPLE-BASED CALIBRATION REPORT\n")
        f.write("=" * 70 + "\n\n")

        f.write("1. ACCURACY METRICS\n")
        f.write("-" * 70 + "\n")
        f.write(f"Total Samples Evaluated: {total}\n\n")

        status_acc = status_correct / total * 100
        type_acc = type_correct / total * 100
        area_acc = area_correct / total * 100

        f.write(f"Status Accuracy:       {status_correct:3d}/{total} ({status_acc:6.1f}%)\n")
        f.write(f"Request Type Accuracy: {type_correct:3d}/{total} ({type_acc:6.1f}%)\n")
        f.write(f"Product Area Accuracy: {area_correct:3d}/{total} ({area_acc:6.1f}%)\n\n")

        f.write("2. FAILURE CATEGORIES\n")
        f.write("-" * 70 + "\n")

        if status_failures:
            f.write("Status Prediction Failures:\n")
            for failure_type, count in sorted(status_failures.items(), key=lambda x: -x[1]):
                pct = count / (total - status_correct) * 100 if (total - status_correct) > 0 else 0
                f.write(f"  {failure_type:20s}: {count:2d} ({pct:5.1f}%)\n")
        else:
            f.write("Status Prediction Failures: None\n")

        f.write("\n")

        if type_failures:
            f.write("Request Type Prediction Failures:\n")
            for failure_type, count in sorted(type_failures.items(), key=lambda x: -x[1]):
                pct = count / (total - type_correct) * 100 if (total - type_correct) > 0 else 0
                f.write(f"  {failure_type:20s}: {count:2d} ({pct:5.1f}%)\n")
        else:
            f.write("Request Type Prediction Failures: None\n")

        f.write("\n")

        if area_failures:
            f.write(f"Product Area Mismatches: {len(area_failures)}\n")
            common_area_errors = defaultdict(int)
            for failure in area_failures:
                key = f"{failure['expected']} -> {failure['predicted']}"
                common_area_errors[key] += 1
            for error_pair, count in sorted(common_area_errors.items(), key=lambda x: -x[1])[:5]:
                f.write(f"  {error_pair:40s}: {count}\n")
        else:
            f.write("Product Area Mismatches: None\n")

        f.write("\n")
        f.write("3. RISK FLAG DISTRIBUTION\n")
        f.write("-" * 70 + "\n")

        for flag, count in sorted(risk_flag_patterns.items(), key=lambda x: -x[1]):
            pct = count / sum(len(p['risk_flags']) for p in predictions) * 100
            f.write(f"  {flag:20s}: {count:3d} occurrences ({pct:5.1f}%)\n")

        f.write("\n")
        f.write("4. STATUS DISTRIBUTION BY PRIMARY RISK FLAG\n")
        f.write("-" * 70 + "\n")

        for risk, statuses in sorted(status_by_risk.items()):
            replied = statuses['replied']
            escalated = statuses['escalated']
            total_risk = replied + escalated
            if total_risk > 0:
                replied_pct = replied / total_risk * 100
                f.write(f"  {risk:20s}: Replied {replied:2d} ({replied_pct:5.1f}%), Escalated {escalated:2d}\n")

        f.write("\n")
        f.write("5. CONFIDENCE SCORE ANALYSIS\n")
        f.write("-" * 70 + "\n")
        f.write(f"Replied Tickets:\n")
        f.write(f"  Average Confidence: {avg_replied_conf:.4f}\n")
        f.write(f"  Min Confidence:     {min_replied_conf:.4f}\n\n")

        f.write(f"Escalated Tickets:\n")
        f.write(f"  Average Confidence: {avg_escalated_conf:.4f}\n")
        f.write(f"  Max Confidence:     {max_escalated_conf:.4f}\n\n")

        f.write("Note: Escalated tickets naturally have lower confidence due to risk penalties.\n\n")

        f.write("6. CALIBRATION RECOMMENDATIONS\n")
        f.write("-" * 70 + "\n")

        recommendations = []

        if status_acc < 90:
            recommendations.append(f"  • Status classification accuracy is {status_acc:.1f}%. Consider:")
            if status_failures.get('over_escalation', 0) > status_failures.get('under_escalation', 0):
                recommendations.append("    - Lowering risk penalty thresholds for non-critical issues")
                recommendations.append("    - Adding more nuanced risk flag detection")
            if status_failures.get('under_escalation', 0) > status_failures.get('over_escalation', 0):
                recommendations.append("    - Raising confidence thresholds for replied status")
                recommendations.append("    - Expanding high-risk keyword patterns")

        if type_acc < 85:
            recommendations.append(f"  • Request type accuracy is {type_acc:.1f}%. Consider:")
            recommendations.append("    - Reviewing intent classification patterns")
            recommendations.append("    - Adding more specific regex patterns for underperforming types")

        if area_acc < 90:
            recommendations.append(f"  • Product area accuracy is {area_acc:.1f}%. Consider:")
            recommendations.append("    - Refining product area keyword mappings")
            recommendations.append("    - Cross-validating with risk flag product area correlations")

        if avg_escalated_conf > 0.5:
            recommendations.append(f"  • Escalated tickets have high average confidence ({avg_escalated_conf:.4f}).")
            recommendations.append("    This suggests risk penalties may not be aggressive enough.")

        if not recommendations:
            recommendations.append("  ✓ Pipeline is well-calibrated. No major changes recommended.")

        for rec in recommendations:
            f.write(rec + "\n")

        f.write("\n")
        f.write("7. CHANGES MADE THIS SESSION\n")
        f.write("-" * 70 + "\n")
        f.write("  • Multi-agent triage pipeline with confidence scoring\n")
        f.write("  • Prompt injection and malicious instruction detection\n")
        f.write("  • Multi-request detection and separate sub-request processing\n")
        f.write("  • Escalation routing to appropriate internal teams\n")
        f.write("  • Evidence-grounded response generation from corpus\n")
        f.write("  • Comprehensive logging with risk flags and escalation details\n\n")

        f.write("=" * 70 + "\n")
        f.write("END OF REPORT\n")
        f.write("=" * 70 + "\n")

    print(f"\n✓ Calibration report written to {report_path}")
    print(f"\nQuick Summary:")
    print(f"  Status Accuracy:       {status_acc:.1f}%")
    print(f"  Request Type Accuracy: {type_acc:.1f}%")
    print(f"  Product Area Accuracy: {area_acc:.1f}%")
    print(f"\nRecommendations generated based on pattern analysis.")


if __name__ == '__main__':
    main()
