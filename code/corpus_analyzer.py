import os
from collections import defaultdict


class CorpusAnalyzer:
    """Analyzes corpus coverage by domain to detect gaps and provide pre-processing insights."""

    SUPPORTED_DOMAINS = ['HackerRank', 'Claude', 'Visa']

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.domain_docs = defaultdict(int)
        self.domain_chunks = defaultdict(int)
        self.domain_coverage = {}
        self.total_docs = 0
        self.total_chunks = 0

    def _infer_company(self, filepath: str) -> str:
        # Use relative path to avoid matching parent directories (like 'Hackerrank' in the user's download folder)
        rel_path = os.path.relpath(filepath, self.data_dir).lower()
        if 'hackerrank' in rel_path:
            return 'HackerRank'
        if 'claude' in rel_path:
            return 'Claude'
        if 'visa' in rel_path:
            return 'Visa'
        return 'None'

    def _chunk_text(self, text: str) -> int:
        """Count the number of chunks that would be created from this text."""
        paragraphs = text.split('\n\n')
        chunks = 0
        current_chunk = ""
        max_chunk_size = 1000

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue

            if len(current_chunk) + len(paragraph) > max_chunk_size:
                if current_chunk:
                    chunks += 1
                current_chunk = paragraph
            else:
                current_chunk = f"{current_chunk}\n\n{paragraph}" if current_chunk else paragraph

        if current_chunk.strip():
            chunks += 1

        return chunks

    def analyze(self):
        """Scan the corpus and count documents and chunks by domain."""
        for root, _, files in os.walk(self.data_dir):
            for file in files:
                if file.endswith('.md'):
                    filepath = os.path.join(root, file)
                    company = self._infer_company(filepath)
                    self.domain_docs[company] += 1
                    self.total_docs += 1

                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            text = f.read()
                            chunks = self._chunk_text(text)
                            self.domain_chunks[company] += chunks
                            self.total_chunks += chunks
                    except Exception as e:
                        print(f"Warning: Error reading {filepath}: {e}")

        # Calculate coverage
        for domain in self.SUPPORTED_DOMAINS:
            docs = self.domain_docs.get(domain, 0)
            chunks = self.domain_chunks.get(domain, 0)
            self.domain_coverage[domain] = {
                'documents': docs,
                'chunks': chunks,
                'has_coverage': docs > 0,
                'coverage_percent': (docs / self.total_docs * 100) if self.total_docs > 0 else 0
            }

    def get_coverage_status(self, domain: str) -> bool:
        """Returns True if domain has corpus coverage, False otherwise."""
        if domain not in self.domain_coverage:
            return False
        return self.domain_coverage[domain]['has_coverage']

    def generate_report(self, output_path: str):
        """Generate and write corpus coverage report."""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("CORPUS COVERAGE ANALYSIS REPORT\n")
            f.write("=" * 70 + "\n\n")

            f.write("1. OVERALL CORPUS STATISTICS\n")
            f.write("-" * 70 + "\n")
            f.write(f"Total Documents: {self.total_docs}\n")
            f.write(f"Total Chunks: {self.total_chunks}\n")
            f.write(f"Average Chunks per Document: {self.total_chunks / self.total_docs if self.total_docs > 0 else 0:.1f}\n\n")

            f.write("2. COVERAGE BY DOMAIN\n")
            f.write("-" * 70 + "\n")

            for domain in self.SUPPORTED_DOMAINS:
                coverage = self.domain_coverage.get(domain, {})
                docs = coverage.get('documents', 0)
                chunks = coverage.get('chunks', 0)
                pct = coverage.get('coverage_percent', 0)
                has_coverage = coverage.get('has_coverage', False)

                status = "✓ COVERED" if has_coverage else "✗ NO COVERAGE"
                f.write(f"\n{domain:15s} {status:15s}\n")
                f.write(f"  Documents: {docs:4d}  ({pct:5.1f}% of total)\n")
                f.write(f"  Chunks:    {chunks:4d}\n")

            f.write("\n")
            f.write("3. COVERAGE ISSUES AND WARNINGS\n")
            f.write("-" * 70 + "\n")

            uncovered_domains = [d for d in self.SUPPORTED_DOMAINS if not self.domain_coverage.get(d, {}).get('has_coverage', False)]
            weak_coverage_domains = []

            for domain in self.SUPPORTED_DOMAINS:
                coverage = self.domain_coverage.get(domain, {})
                pct = coverage.get('coverage_percent', 0)
                if 0 < pct < 20:
                    weak_coverage_domains.append((domain, pct))

            if uncovered_domains:
                f.write(f"\n⚠ NO CORPUS COVERAGE:\n")
                for domain in uncovered_domains:
                    f.write(f"  • {domain}: Zero documents available\n")
                f.write(f"    Action: Tickets for these domains WILL BE ESCALATED.\n")
            else:
                f.write(f"\n✓ All supported domains have corpus coverage.\n")

            if weak_coverage_domains:
                f.write(f"\n⚠ WEAK COVERAGE WARNING:\n")
                for domain, pct in weak_coverage_domains:
                    f.write(f"  • {domain}: Only {pct:.1f}% of corpus documents\n")
                f.write(f"    Action: Escalation rates may be higher for these domains.\n")
            else:
                f.write(f"\n✓ All domains have reasonable coverage (>= 20% or zero).\n")

            f.write("\n")
            f.write("4. ESCALATION POLICY\n")
            f.write("-" * 70 + "\n")
            f.write("During ticket processing:\n")
            f.write("  • If ticket domain has NO corpus coverage, ticket is ESCALATED.\n")
            f.write("  • If ticket domain has WEAK coverage, escalation rate may increase.\n")
            f.write("  • If ticket domain has adequate coverage, normal triage rules apply.\n\n")

            f.write("5. RECOMMENDATIONS\n")
            f.write("-" * 70 + "\n")

            if uncovered_domains:
                f.write(f"  1. Add support documentation for: {', '.join(uncovered_domains)}\n")
                f.write(f"  2. Until documentation is added, all tickets for these domains\n")
                f.write(f"     will be routed to human support.\n")
            else:
                f.write(f"  • Corpus coverage is complete for all supported domains.\n")

            if weak_coverage_domains:
                for domain, pct in weak_coverage_domains:
                    f.write(f"  • Consider expanding {domain} documentation ({pct:.1f}% coverage).\n")

            f.write("\n")
            f.write("=" * 70 + "\n")
            f.write("END OF REPORT\n")
            f.write("=" * 70 + "\n")


def generate_corpus_report(data_dir: str, output_path: str) -> CorpusAnalyzer:
    """Convenience function to analyze corpus and generate report."""
    analyzer = CorpusAnalyzer(data_dir)
    analyzer.analyze()
    analyzer.generate_report(output_path)
    return analyzer
