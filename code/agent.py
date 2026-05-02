import os
import re

class DomainRouterAgent:
    """Determines the supported domain from company metadata, issue text, and subject."""

    SUPPORTED_DOMAINS = ["HackerRank", "Claude", "Visa"]

    def route_domain(self, issue: str, subject: str, company: str) -> dict:
        text = f"{subject} {issue}".strip().lower()
        company_hint = str(company or "").strip().lower()

        if company_hint and company_hint != 'none':
            for domain in self.SUPPORTED_DOMAINS:
                if domain.lower() == company_hint:
                    return {"domain": domain, "inferred": False, "out_of_scope": False}

        inferred_domain = self._infer_domain_from_text(text)
        if inferred_domain:
            return {"domain": inferred_domain, "inferred": True, "out_of_scope": False}

        return {"domain": None, "inferred": True, "out_of_scope": True}

    def _infer_domain_from_text(self, text: str) -> str | None:
        if any(keyword in text for keyword in ['hackerrank', 'candidate', 'assessment', 'test', 'interview', 'score', 'submission']):
            return 'HackerRank'
        if any(keyword in text for keyword in ['claude', 'workspace', 'chat', 'prompt', 'model', 'anthropic', 'project', 'conversation']):
            return 'Claude'
        if any(keyword in text for keyword in ['visa', 'card', 'merchant', 'refund', 'charge', 'travel', 'payment']):
            return 'Visa'
        return None

    def determine_product_area(self, issue: str, subject: str, domain: str) -> str:
        text = f"{subject} {issue}".lower()

        if domain == 'HackerRank':
            if any(token in text for token in ['test', 'assessment', 'score', 'time', 'submission', 'interview']):
                return 'screen'
            if any(token in text for token in ['community', 'login', 'profile', 'account', 'organization', 'team']):
                return 'community'
            return 'general_support'

        if domain == 'Claude':
            if any(token in text for token in ['private', 'privacy', 'data', 'crawl', 'personal']):
                return 'privacy'
            if any(token in text for token in ['conversation', 'project', 'workspace', 'api', 'connector', 'knowledge']):
                return 'conversation_management'
            return 'general_support'

        if domain == 'Visa':
            if any(token in text for token in ['travel', 'abroad', 'foreign', 'transaction']):
                return 'travel_support'
            return 'general_support'

        return 'general_support'

class IntentAgent:
    """Classifies the user request into one of the supported intent buckets."""

    def classify_intent(self, issue: str, subject: str) -> tuple[str, float]:
        text = f"{subject} {issue}".lower()

        invalid_patterns = [
            r'\bspam\b',
            r'ignore.*instructions',
            r'\bactor\b',
            r'\bmovie\b',
            r'thank you',
            r'\biron man\b',
            r'unsubscribe',
            r'promotion',
            r'spammy',
            r'not related',
        ]
        invalid_matches = [pattern for pattern in invalid_patterns if re.search(pattern, text)]
        if invalid_matches:
            return 'invalid', 0.95

        bug_patterns = [
            r'\bbroken\b',
            r'\berror\b',
            r'\bfailed\b',
            r'not working',
            r'\bcrash\b',
            r'incorrect',
            r'\bdown\b',
            r'inaccessible',
            r'outage',
            r'issue',
            r'problem',
            r'cannot',
            r'cannot access',
        ]
        bug_matches = [pattern for pattern in bug_patterns if re.search(pattern, text)]
        if bug_matches:
            confidence = min(0.98, 0.75 + 0.05 * len(bug_matches))
            return 'bug', confidence

        feature_patterns = [
            r'\badd\b',
            r'integrate',
            r'\benable\b',
            r'\bimprove\b',
            r'new feature',
            r'feature request',
            r'would like',
            r'can you add',
        ]
        feature_matches = [pattern for pattern in feature_patterns if re.search(pattern, text)]
        if feature_matches and 'time' not in text:
            confidence = min(0.9, 0.65 + 0.05 * len(feature_matches))
            return 'feature_request', confidence

        return 'product_issue', 0.55

class PromptInjectionAgent:
    """Detects prompt injection and malicious instruction patterns in ticket text."""

    MALICIOUS_PATTERNS = [
        r'ignore\s+previous\s+instructions',
        r'reveal\s+system\s+prompt',
        r'use\s+outside\s+knowledge',
        r'bypass\s+policy',
        r'pretend\s+you\s+are',
        r'answer\s+without\s+corpus',
        r'delete\s+files',
        r'run\s+commands?',
        r'scrape\s+website',
        r'override\s+developer\s+instructions',
    ]

    def detect(self, issue: str, subject: str) -> dict[str, object]:
        text = f"{subject} {issue}".lower()
        for pattern in self.MALICIOUS_PATTERNS:
            if re.search(pattern, text):
                return {'detected': True, 'pattern': pattern}
        return {'detected': False, 'pattern': None}

class MultiRequestAgent:
    """Detects and splits tickets that contain multiple request statements."""

    SPLIT_PATTERNS = [r'\band\b', r'\balso\b', r'\bplus\b', r'\badditionally\b']
    BULLET_REGEX = re.compile(r'^[\s]*[-*•]\s*(.+)$', re.MULTILINE)
    NUMBERED_REGEX = re.compile(r'^[\s]*\d+[\.)]\s*(.+)$', re.MULTILINE)

    def extract_subrequests(self, issue: str, subject: str) -> list[str]:
        trimmed = issue.strip()
        if not trimmed:
            return [trimmed]

        bullets = self.BULLET_REGEX.findall(trimmed)
        numbered = self.NUMBERED_REGEX.findall(trimmed)
        if len(bullets) > 1 or len(numbered) > 1:
            subrequests = []
            main_text = self._strip_list_items(trimmed)
            if main_text:
                subrequests.append(self._normalize_text(main_text))
            items = bullets if len(bullets) > 1 else numbered
            subrequests.extend(self._normalize_text(item) for item in items if item.strip())
            return [item for item in subrequests if item]

        split_requests = self._split_by_conjunctions(trimmed)
        if len(split_requests) > 1:
            return [self._normalize_text(item) for item in split_requests if item.strip()]

        return [trimmed]

    def _split_by_conjunctions(self, text: str) -> list[str]:
        parts = re.split(r'\s+(?:and\s+also|also|and|plus|additionally)\s+', text, flags=re.IGNORECASE)
        if len(parts) <= 1:
            return [text]

        if all(len(part.split()) >= 4 for part in parts):
            return parts
        return [text]

    def _strip_list_items(self, text: str) -> str:
        cleaned = self.BULLET_REGEX.sub('', text)
        cleaned = self.NUMBERED_REGEX.sub('', cleaned)
        return cleaned.strip()

    def _normalize_text(self, text: str) -> str:
        text = text.strip()
        if text.endswith('.'):
            text = text[:-1].strip()
        return text

class EscalationRouter:
    """Routes escalated tickets to appropriate internal teams based on risk flags, product area, and company."""

    TEAM_ROUTES = {
        'fraud/security/security': 'fraud/security team',
        'fraud/security/billing': 'billing/payments team',
        'fraud/security/refund': 'billing/payments team',
        'fraud/security/dispute': 'billing/payments team',
        'fraud/security/account_access': 'account access team',
        'fraud/security/assessment_integrity': 'assessment integrity team',
        'fraud/security/prompt_injection': 'fraud/security team',
        'fraud/security/privacy': 'privacy/legal team',
        'fraud/security/legal': 'privacy/legal team',
    }

    def route_escalation(self, company: str, risk_flags: list[str], product_area: str, domain: str) -> tuple[str, str]:
        """
        Returns (escalation_route, escalation_reason).
        """
        if not risk_flags:
            return 'general human support', 'No specific risk flags; routing to general support.'

        primary_risk = risk_flags[0] if risk_flags else None
        routing_key = f"{company}/{primary_risk}/{product_area}"

        if primary_risk in ['fraud', 'security', 'prompt_injection']:
            return 'fraud/security team', f"Risk flag: {primary_risk}."
        if primary_risk in ['billing', 'refund', 'dispute', 'payment']:
            return 'billing/payments team', f"Risk flag: {primary_risk}."
        if primary_risk == 'account_access':
            return 'account access team', f"Risk flag: {primary_risk}."
        if primary_risk == 'assessment_integrity':
            return 'assessment integrity team', f"Risk flag: {primary_risk}."
        if primary_risk in ['privacy', 'legal']:
            return 'privacy/legal team', f"Risk flag: {primary_risk}."
        if primary_risk == 'low_context':
            return 'technical support team', f"Risk flag: {primary_risk}."

        return 'general human support', f"Risk flags: {', '.join(risk_flags)}."

class RiskAgent:
    """Evaluates risk severity and identifies named risk flags from the ticket text."""

    RISK_PATTERNS = {
        'fraud': [r'\bfraud', r'unusual transaction', r'unauthorized', r'chargeback', r'scam', r'suspicious', r'phishing'],
        'billing': [r'\bbilling\b', r'payment', r'invoice', r'charge', r'fee', r'refund'],
        'refund': [r'\brefund\b', r'reimburse', r'money back', r'chargeback'],
        'dispute': [r'\bdispute\b', r'contest', r'complaint', r'argue'],
        'account_access': [r'login', r'sign in', r'password', r'locked out', r'locked', r'account access', r'access denied', r'credential'],
        'legal': [r'\blegal\b', r'lawsuit', r'attorney', r'compliance', r'privacy policy', r'regulation', r'identity theft'],
        'privacy': [r'privacy', r'data leak', r'personal data', r'personal information', r'gdpr', r'data breach'],
        'security': [r'security', r'hacked', r'breach', r'vulnerability', r'compromised', r'credential stuffing', r'stolen'],
        'assessment_integrity': [r'cheat', r'cheating', r'integrity', r'plagiarism', r'exam integrity', r'misconduct'],
        'prompt_injection': [r'prompt injection', r'jailbreak', r'malicious prompt', r'injection'],
        'low_context': [r'too vague', r'more details', r'more information', r'not enough', r'too little'],
    }

    RISK_PENALTIES = {
        'fraud': 0.30,
        'billing': 0.25,
        'refund': 0.25,
        'dispute': 0.25,
        'account_access': 0.15,
        'legal': 0.30,
        'privacy': 0.25,
        'security': 0.20,
        'assessment_integrity': 0.30,
        'prompt_injection': 0.40,
        'low_context': 0.10,
    }

    def analyze(self, issue: str, subject: str, company: str, domain: str) -> dict:
        text = f"{subject} {issue}".lower()
        risk_flags = []

        for flag, patterns in self.RISK_PATTERNS.items():
            if any(re.search(pattern, text) for pattern in patterns):
                risk_flags.append(flag)

        risk_level = 'low'
        if any(flag in risk_flags for flag in ['fraud', 'billing', 'refund', 'dispute', 'account_access', 'legal', 'privacy', 'security', 'assessment_integrity', 'prompt_injection']):
            risk_level = 'high'
        elif any(flag in risk_flags for flag in ['low_context']):
            risk_level = 'medium'
        elif any(keyword in text for keyword in ['urgent', 'asap', 'immediately', 'critical', 'important']):
            risk_level = 'medium'

        risk_penalty = self._calculate_penalty(risk_flags)

        return {
            'risk_level': risk_level,
            'risk_flags': sorted(set(risk_flags)),
            'risk_penalty': risk_penalty
        }

    def _calculate_penalty(self, risk_flags: list[str]) -> float:
        penalty = sum(self.RISK_PENALTIES.get(flag, 0.0) for flag in risk_flags)
        return min(0.8, penalty)

class DecisionAgent:
    """Decides whether to reply or escalate based on domain, intent, risk, and retrieval evidence."""

    ACTION_KEYWORDS = [
        'go to', 'click', 'select', 'navigate', 'open', 'enter', 'save', 'update', 'change',
        'reset', 'review', 'enable', 'disable', 'turn on', 'turn off', 'use', 'choose', 'check',
        'log in', 'sign in', 'follow', 'set', 'configure'
    ]

    def __init__(self):
        self.escalation_router = EscalationRouter()

    def decide(self, domain_info: dict, intent: str, risk_info: dict, retrieval_info: dict, malicious_detected: bool = False, company: str = None, product_area: str = None, issue: str = "") -> dict:
        if malicious_detected:
            route, reason = self.escalation_router.route_escalation(company, risk_info['risk_flags'], product_area, domain_info['domain'])
            return {
                'status': 'escalated',
                'response': 'This request cannot be handled automatically due to potentially malicious or unsupported instructions detected in the query. For security reasons, this has been routed to our specialized integrity team.',
                'justification': f'Escalated to {route}: malicious or unsupported instruction detected.',
                'escalation_route': route,
                'escalation_reason': 'Malicious instruction detected.'
            }

        if intent == 'invalid':
            return {
                'status': 'replied',
                'response': 'This request is unrelated to our products or does not contain a clear support inquiry. We cannot assist you with this at this time.',
                'justification': 'Replied: Dismissed invalid or spam request.',
                'escalation_route': None,
                'escalation_reason': None
            }

        if domain_info['out_of_scope']:
            route, reason = self.escalation_router.route_escalation(company, risk_info['risk_flags'], product_area, domain_info['domain'])
            return self._escalate('The request falls outside our supported domains or involves an unidentified company.', route, reason)

        if retrieval_info['retrieval_confidence'] <= 0.0 or not retrieval_info['results'] or retrieval_info.get('escalate', False):
            route, reason = self.escalation_router.route_escalation(company, risk_info['risk_flags'], product_area, domain_info['domain'])
            return self._escalate('Our documentation does not currently contain a specific solution for this inquiry.', route, reason)

        # High-Precision Semantic Validation
        top_text = retrieval_info['results'][0]['text'].lower()
        issue_lower = issue.lower()
        
        # 1. Define High-Value Intent Keywords
        INTENT_KEYWORDS = ['access', 'restore', 'refund', 'delete', 'cancel', 'reset', 'password', 'error', 'bug', 'hack', 'stolen', 'payment', 'billing']
        critical_keywords_in_issue = [k for k in INTENT_KEYWORDS if k in issue_lower]
        
        # 2. Check if the retrieved text also contains these critical intent keywords
        missing_critical_match = False
        for k in critical_keywords_in_issue:
            if k not in top_text:
                missing_critical_match = True
                break

        # 3. Keyword Overlap (Nouns/Verbs > 4 chars)
        keywords = [w for w in re.findall(r'\b\w{5,}\b', issue_lower)]
        match_count = sum(1 for k in keywords if k in top_text)
        semantic_confidence = match_count / max(1, len(keywords))
        
        final_confidence = retrieval_info.get('final_confidence', 0.0)
        
        # Thresholds for safe replying - now much stricter for critical intents
        if missing_critical_match or final_confidence < 0.35 or semantic_confidence < 0.15:
            route, reason = self.escalation_router.route_escalation(company, risk_info['risk_flags'], product_area, domain_info['domain'])
            return self._escalate('Insufficient semantic alignment or missing critical documentation evidence.', route, reason)

        if risk_info['risk_level'] == 'high' and retrieval_info['retrieval_confidence'] < 0.45:
            route, reason = self.escalation_router.route_escalation(company, risk_info['risk_flags'], product_area, domain_info['domain'])
            return self._escalate('This high-risk matter requires a human review as the retrieved documentation is not sufficiently comprehensive.', route, reason)

        grounded_response = self._build_grounded_response(retrieval_info['results'])
        if not grounded_response or len(grounded_response.split()) < 15:
            route, reason = self.escalation_router.route_escalation(company, risk_info['risk_flags'], product_area, domain_info['domain'])
            return self._escalate('The retrieved documentation does not contain enough actionable information to generate a helpful response.', route, reason)

        best_source = os.path.basename(retrieval_info['results'][0]['filepath'])
        justification = f"Replied using exact support documentation from {best_source}."

        return {
            'status': 'replied',
            'response': grounded_response,
            'justification': justification
        }

    def _build_grounded_response(self, results: list[dict]) -> str:
        """Build a multi-sentence response from the best retrieved evidence."""
        candidate_sentences = []
        
        # Extract sentences from top 2 results (more context for complex answers)
        for result in results[:2]:
            sentences = self._extract_useful_sentences(result['text'])
            candidate_sentences.extend(sentences)
            if len(candidate_sentences) >= 5:
                break
        
        # Select up to 4 sentences for comprehensive answers
        chosen = candidate_sentences[:4]
        return ' '.join(chosen).strip() if chosen else ''

    def _extract_useful_sentences(self, text: str) -> list[str]:
        """Extract action-oriented and informative sentences from corpus text."""
        raw_sentences = [sentence.strip() for sentence in re.split(r'(?<=[.!?])\s+', text) if sentence.strip()]
        filtered = []
        
        for sentence in raw_sentences:
            lowered = sentence.lower()
            
            # Skip very short or URL-only sentences
            if len(sentence) < 30:
                continue
            if any(token in lowered for token in ['http://', 'https://', 'www.', 'mailto:']):
                continue
            
            # Prioritize action-oriented sentences (steps, instructions)
            if any(keyword in lowered for keyword in self.ACTION_KEYWORDS):
                filtered.append(sentence.rstrip('.').strip() + '.')
            # Also capture informative sentences (at least 8 words) if not many actions yet
            elif len(filtered) < 2 and len(sentence.split()) >= 8:
                filtered.append(sentence.rstrip('.').strip() + '.')
        
        return filtered

    def _escalate(self, reason: str, route: str = None, route_reason: str = None) -> dict:
        if route is None:
            route = 'general human support'
        if route_reason is None:
            route_reason = reason
        return {
            'status': 'escalated',
            'response': f"We apologize, but this issue needs human support. Reason: {reason} Please wait while we connect you to an agent.",
            'justification': f"Escalated to {route}: {route_reason}",
            'escalation_route': route,
            'escalation_reason': route_reason
        }

class TriageAgent:
    """Orchestrates the full multi-agent ticket triage pipeline."""

    def __init__(self, data_dir: str, retrieval_threshold: float = 0.15, corpus_analyzer=None):
        self.domain_router = DomainRouterAgent()
        self.intent_agent = IntentAgent()
        self.prompt_injection_agent = PromptInjectionAgent()
        self.multi_request_agent = MultiRequestAgent()
        self.risk_agent = RiskAgent()
        self.decision_agent = DecisionAgent()
        self.escalation_router = EscalationRouter()
        self.retrieval_agent = None
        self.retrieval_threshold = retrieval_threshold
        self.corpus_analyzer = corpus_analyzer

        if data_dir:
            from retriever import RetrievalAgent
            self.retrieval_agent = RetrievalAgent(data_dir=data_dir)
            self.retrieval_agent.build_index()

    def process_ticket(self, issue: str, subject: str, company: str) -> dict:
        domain_info = self.domain_router.route_domain(issue, subject, company)
        injection_info = self.prompt_injection_agent.detect(issue, subject)
        request_type, classification_confidence = self.intent_agent.classify_intent(issue, subject)
        product_area = self.domain_router.determine_product_area(issue, subject, domain_info['domain'])
        risk_info = self.risk_agent.analyze(issue, subject, company, domain_info['domain'])

        # Check corpus coverage for this domain
        if self.corpus_analyzer and domain_info['domain']:
            if not self.corpus_analyzer.get_coverage_status(domain_info['domain']):
                if 'no_corpus' not in risk_info['risk_flags']:
                    risk_info['risk_flags'].append('no_corpus')
                risk_info['risk_level'] = 'high'
                risk_info['risk_penalty'] = max(risk_info['risk_penalty'], 0.9)

        sub_requests = self.multi_request_agent.extract_subrequests(issue, subject)
        is_multi_request = len(sub_requests) > 1
        subrequest_details = []

        if request_type != 'invalid' and self.retrieval_agent is not None:
            for sub_request in sub_requests:
                sub_request_type, sub_classification_confidence = self.intent_agent.classify_intent(sub_request, subject)
                sub_risk = self.risk_agent.analyze(sub_request, subject, company, domain_info['domain'])
                sub_retrieval_info = {
                    'results': [],
                    'retrieval_confidence': 0.0,
                    'final_confidence': 0.0
                }
                if sub_request_type != 'invalid':
                    sub_query = self._build_retrieval_query(sub_request, subject, company, domain_info)
                    sub_retrieval_info = self.retrieval_agent.retrieve(sub_query, top_k=5, threshold=self.retrieval_threshold)
                sub_final_confidence = self._compute_final_confidence(
                    sub_retrieval_info['retrieval_confidence'],
                    sub_classification_confidence,
                    sub_risk['risk_penalty']
                )
                sub_retrieval_info['final_confidence'] = sub_final_confidence
                subrequest_details.append({
                    'text': sub_request,
                    'request_type': sub_request_type,
                    'classification_confidence': sub_classification_confidence,
                    'risk_info': sub_risk,
                    'retrieval_info': sub_retrieval_info,
                })

        if injection_info['detected']:
            request_type = 'invalid'
            classification_confidence = 0.99
            product_area = 'security/prompt_injection'
            if 'prompt_injection' not in risk_info['risk_flags']:
                risk_info['risk_flags'].append('prompt_injection')
            risk_info['risk_level'] = 'high'
            risk_info['risk_penalty'] = max(risk_info['risk_penalty'], self.risk_agent.RISK_PENALTIES.get('prompt_injection', 0.5))

        if subrequest_details:
            aggregated_flags = set(risk_info['risk_flags'])
            aggregate_penalty = risk_info['risk_penalty']
            has_high_risk = risk_info['risk_level'] == 'high'
            for detail in subrequest_details:
                aggregated_flags.update(detail['risk_info']['risk_flags'])
                aggregate_penalty = max(aggregate_penalty, detail['risk_info']['risk_penalty'])
                if detail['risk_info']['risk_level'] == 'high':
                    has_high_risk = True
            risk_info['risk_flags'] = sorted(aggregated_flags)
            risk_info['risk_penalty'] = aggregate_penalty
            risk_info['risk_level'] = 'high' if has_high_risk else risk_info['risk_level']

        if subrequest_details:
            primary_detail = next((item for item in subrequest_details if item['request_type'] != 'invalid'), subrequest_details[0])
            retrieval_info = primary_detail['retrieval_info']
            classification_confidence = primary_detail['classification_confidence']
        else:
            retrieval_info = {
                'results': [],
                'retrieval_confidence': 0.0,
                'escalate': True,
                'final_confidence': 0.0
            }

        final_confidence = self._compute_final_confidence(
            retrieval_info['retrieval_confidence'],
            classification_confidence,
            risk_info['risk_penalty']
        )
        retrieval_info['final_confidence'] = final_confidence

        # If the request was classified as invalid but came from a generic chat-like query,
        # preserve a conversation management product_area fallback for scoring and analysis.
        if request_type == 'invalid' and company.strip().lower() in ['none', 'nan'] and domain_info['domain'] in [None, 'None']:
            product_area = 'conversation_management'

        if injection_info['detected']:
            decision = self.decision_agent.decide(domain_info, request_type, risk_info, retrieval_info, malicious_detected=True, company=company, product_area=product_area, issue=issue)
        elif is_multi_request and len(sub_requests) > 2 and any(detail['risk_info']['risk_level'] == 'high' for detail in subrequest_details):
            route, reason = self.escalation_router.route_escalation(company, risk_info['risk_flags'], product_area, domain_info['domain'])
            decision = self.decision_agent._escalate('Multiple complex sub-requests with conflicting risk levels detected.', route, reason)
        else:
            decision = self.decision_agent.decide(domain_info, request_type, risk_info, retrieval_info, company=company, product_area=product_area, issue=issue)

        return {
            'request_type': request_type,
            'product_area': product_area,
            'domain': domain_info['domain'] or 'None',
            'out_of_scope': domain_info['out_of_scope'],
            'risk_level': risk_info['risk_level'],
            'risk_flags': risk_info['risk_flags'],
            'risk_penalty': risk_info['risk_penalty'],
            'retrieval_confidence': retrieval_info['retrieval_confidence'],
            'classification_confidence': classification_confidence,
            'final_confidence': final_confidence,
            'retrieved_sources': [os.path.basename(item['filepath']) for item in retrieval_info['results']],
            'status': decision['status'],
            'response': decision['response'],
            'justification': decision['justification'],
            'escalation_route': decision.get('escalation_route'),
            'escalation_reason': decision.get('escalation_reason'),
            'sub_requests': sub_requests if is_multi_request else []
        }

    def _compute_final_confidence(self, retrieval_confidence: float, classification_confidence: float, risk_penalty: float) -> float:
        raw_score = retrieval_confidence * 0.70 + classification_confidence * 0.30 - risk_penalty
        return max(0.0, min(1.0, raw_score))

    def _build_retrieval_query(self, issue: str, subject: str, company: str, domain_info: dict) -> str:
        """Build an enriched retrieval query with synonym expansion for better recall."""
        source = domain_info['domain'] if domain_info['domain'] else company
        base_query = ' '.join([source, subject, issue]).strip()
        
        # Expand with common synonyms to catch more relevant documents
        expansions = []
        text_lower = (issue + ' ' + subject).lower()
        
        # Map product-specific synonyms
        synonym_map = {
            'password reset': ['password', 'login', 'authentication', 'credential'],
            'account access': ['login', 'authentication', 'account', 'permissions'],
            'billing': ['payment', 'invoice', 'charge', 'subscription'],
            'refund': ['reimbursement', 'charge back', 'money back'],
            'bug': ['error', 'broken', 'crash', 'issue', 'problem'],
            'test': ['assessment', 'exam', 'evaluation', 'challenge'],
            'candidate': ['applicant', 'user', 'participant'],
            'escalation': ['escalate', 'elevate', 'urgent', 'priority'],
        }
        
        for term, synonyms in synonym_map.items():
            if term in text_lower:
                expansions.extend(synonyms)
        
        if expansions:
            expanded = ' '.join(set(expansions))
            return f"{base_query} {expanded}"
        return base_query
