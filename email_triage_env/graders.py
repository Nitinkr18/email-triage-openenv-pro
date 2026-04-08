"""
Task Graders for Email Triage Environment
Deterministic, reproducible graders for each difficulty level.
"""

import re
import unicodedata
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from email_triage_env.models import Email, State


class EmailTriageGrader:
    """Deterministic grader for email triage tasks."""

    # --- Reputation and phishing heuristics (deterministic) ---
    KNOWN_BUSINESS_DOMAINS: Set[str] = {
        "company.com",
        "company.co",
        "trustedvendor.com",
        "longtime-vendor.com",
        "identity-provider.com",
        "paypal.com",
        "microsoft.com",
        "bank.com",
        "cloudsummit.org",
    }

    FREE_EMAIL_DOMAINS: Set[str] = {
        "gmail.com",
        "yahoo.com",
        "outlook.com",
        "hotmail.com",
        "proton.me",
        "protonmail.com",
        "icloud.com",
    }

    SUSPICIOUS_TLDS: Set[str] = {
        "xyz",
        "top",
        "click",
        "work",
        "buzz",
        "info",
        "biz",
        "live",
        "rest",
    }

    DOMAIN_BRAND_MAP: Dict[str, Set[str]] = {
        "paypal.com": {"paypal"},
        "microsoft.com": {"microsoft", "m365", "office365"},
        "company.com": {"company", "corp", "internal", "hr", "finance"},
        "bank.com": {"bank", "secure", "account"},
    }

    PHISHING_KEYWORDS: Set[str] = {
        "verify now",
        "account will be closed",
        "wire transfer",
        "gift card",
        "w-2",
        "password reset",
        "approve login",
        "urgent action",
        "suspend",
        "beneficiary changed",
        "new bank account",
        "security alert",
        "re-authentication",
    }

    @staticmethod
    def _extract_domain(sender: str) -> str:
        sender = (sender or "").strip().lower()
        if "@" not in sender:
            return ""
        return sender.split("@", 1)[1].strip()

    @staticmethod
    def _normalize_ascii(text: str) -> str:
        if not text:
            return ""
        # Keep deterministic normalization for homograph checks
        return (
            unicodedata.normalize("NFKD", text)
            .encode("ascii", "ignore")
            .decode("ascii")
            .lower()
        )

    @staticmethod
    def _contains_non_ascii(text: str) -> bool:
        return any(ord(ch) > 127 for ch in (text or ""))

    @staticmethod
    def _extract_urls(text: str) -> List[str]:
        # Practical URL regex for deterministic grading
        return re.findall(r"(https?://[^\s)>\]]+)", text or "", flags=re.IGNORECASE)

    @staticmethod
    def _looks_like_typosquatting(domain: str) -> bool:
        d = domain.lower()
        # Common visual substitutions
        substitutions = [
            ("0", "o"),
            ("1", "l"),
            ("3", "e"),
            ("5", "s"),
            ("7", "t"),
            ("rn", "m"),
        ]

        # Check against common brands/domains
        targets = ["microsoft.com", "paypal.com", "company.com", "bank.com"]
        for target in targets:
            base_target = target.split(".")[0]
            base_d = d.split(".")[0]
            candidate = base_d
            for a, b in substitutions:
                candidate = candidate.replace(a, b)
            if candidate == base_target and d != target:
                return True
        return False

    @staticmethod
    def check_url_legitimacy(
        email_body: str, email_sender: str
    ) -> Tuple[float, Dict[str, bool]]:
        """
        Return URL legitimacy risk score in [0, 1] and evidence flags.
        Checks:
        - Typosquatting
        - Homograph/non-ASCII domains
        - Link domain mismatch with sender domain
        """
        urls = EmailTriageGrader._extract_urls(email_body)
        sender_domain = EmailTriageGrader._extract_domain(email_sender)

        evidence = {
            "has_urls": bool(urls),
            "typosquatting": False,
            "homograph": False,
            "domain_mismatch": False,
        }

        if not urls:
            return 0.0, evidence

        risk = 0.0
        for u in urls:
            try:
                parsed = urlparse(u)
                link_domain = (parsed.netloc or "").lower()
            except Exception:
                link_domain = ""

            if not link_domain:
                continue

            if EmailTriageGrader._looks_like_typosquatting(link_domain):
                evidence["typosquatting"] = True
                risk += 0.45

            if EmailTriageGrader._contains_non_ascii(link_domain):
                evidence["homograph"] = True
                risk += 0.45

            # Sender/link mismatch for business contexts
            if (
                sender_domain
                and link_domain
                and sender_domain not in link_domain
                and link_domain not in sender_domain
            ):
                evidence["domain_mismatch"] = True
                risk += 0.25

        return min(1.0, risk), evidence

    @staticmethod
    def check_sender_reputation(
        sender: str, subject: str = "", body: str = ""
    ) -> Tuple[float, Dict[str, bool]]:
        """
        Sender reputation risk in [0, 1]:
        - suspicious TLD
        - free-mail sender making business/financial asks
        - unknown business domain
        """
        domain = EmailTriageGrader._extract_domain(sender)
        evidence = {
            "suspicious_tld": False,
            "free_mail_business_request": False,
            "unknown_domain": False,
        }

        if not domain:
            return 0.8, evidence  # malformed sender

        risk = 0.0
        tld = domain.rsplit(".", 1)[-1] if "." in domain else ""

        if tld in EmailTriageGrader.SUSPICIOUS_TLDS:
            evidence["suspicious_tld"] = True
            risk += 0.35

        text = f"{subject} {body}".lower()
        business_request = any(
            kw in text
            for kw in [
                "wire",
                "invoice",
                "payment",
                "bank account",
                "beneficiary",
                "gift card",
                "w-2",
                "tax",
                "transfer",
                "legal hold",
            ]
        )

        if domain in EmailTriageGrader.FREE_EMAIL_DOMAINS and business_request:
            evidence["free_mail_business_request"] = True
            risk += 0.45

        if (
            domain not in EmailTriageGrader.KNOWN_BUSINESS_DOMAINS
            and domain not in EmailTriageGrader.FREE_EMAIL_DOMAINS
        ):
            evidence["unknown_domain"] = True
            risk += 0.2

        return min(1.0, risk), evidence

    @staticmethod
    def check_email_consistency(
        subject: str, body: str, sender: str
    ) -> Tuple[float, Dict[str, bool]]:
        """
        Content consistency risk in [0, 1]:
        - Subject/body mismatch
        - Tone inconsistency
        - Grammar signals for purportedly professional senders
        """
        s = (subject or "").lower()
        b = (body or "").lower()
        sender_domain = EmailTriageGrader._extract_domain(sender)

        evidence = {
            "subject_body_mismatch": False,
            "tone_inconsistency": False,
            "grammar_signal": False,
        }

        risk = 0.0

        # Subject-body mismatch: urgent/security subject but generic/non-matching body
        urgent_subject = any(
            k in s
            for k in ["urgent", "critical", "security alert", "verify", "account"]
        )
        generic_body = any(
            k in b
            for k in ["hello dear", "kindly do the needful", "act now", "limited offer"]
        )
        if urgent_subject and generic_body:
            evidence["subject_body_mismatch"] = True
            risk += 0.3

        # Tone inconsistency: highly formal subject with casual body
        formal_subject = any(
            k in s for k in ["invoice", "legal", "compliance", "escalation", "security"]
        )
        casual_body = any(
            k in b for k in ["hey buddy", "quick favor", "pls", "u there"]
        )
        if formal_subject and casual_body:
            evidence["tone_inconsistency"] = True
            risk += 0.2

        # Grammar/spelling signal for professional domains
        pro_sender = (
            sender_domain.endswith("company.com")
            or sender_domain in EmailTriageGrader.KNOWN_BUSINESS_DOMAINS
        )
        grammar_hits = 0
        for bad in [
            "kindly revert back",
            "do the needful",
            "dear user",
            "immediatly",
            "verfy",
            "recieve",
        ]:
            if bad in b:
                grammar_hits += 1
        if pro_sender and grammar_hits >= 1:
            evidence["grammar_signal"] = True
            risk += min(0.3, 0.12 * grammar_hits)

        return min(1.0, risk), evidence

    @staticmethod
    def _is_phishing_pattern(email_obj: Optional[Email]) -> bool:
        """Classify an email as phishing-like using multi-factor deterministic heuristics."""
        if email_obj is None:
            return False

        subject = email_obj.subject or ""
        body = email_obj.body or ""
        sender = email_obj.sender or ""
        lower_text = f"{subject} {body}".lower()

        keyword_hit = any(k in lower_text for k in EmailTriageGrader.PHISHING_KEYWORDS)
        url_risk, url_evidence = EmailTriageGrader.check_url_legitimacy(body, sender)
        sender_risk, _ = EmailTriageGrader.check_sender_reputation(
            sender, subject, body
        )
        consistency_risk, _ = EmailTriageGrader.check_email_consistency(
            subject, body, sender
        )

        # Deterministic thresholding
        composite = (0.45 * url_risk) + (0.3 * sender_risk) + (0.25 * consistency_risk)
        if keyword_hit:
            composite += 0.2

        high_signal = (
            url_evidence.get("typosquatting", False)
            or url_evidence.get("homograph", False)
            or "gift card" in lower_text
            or "wire transfer" in lower_text
            or "w-2" in lower_text
        )

        return high_signal or composite >= 0.45

    @staticmethod
    def _confidence_calibration_score(state: State) -> float:
        """
        Confidence calibration score in [0,1]:
        - Rewards high confidence on correct decisions
        - Penalizes overconfidence on wrong decisions
        """
        total = len(state.ground_truth)
        if total == 0:
            return 0.0

        score = 0.0
        for email_id, true_category in state.ground_truth.items():
            pred = state.classifications.get(email_id)
            if not pred:
                continue

            conf = float(pred.get("confidence", 0.5))
            conf = max(0.0, min(1.0, conf))
            is_correct = pred.get("category") == true_category

            if is_correct:
                # Base reward, slightly better when confidence aligns
                score += 0.6 + (0.4 * conf)
            else:
                # Strong penalty for overconfidence
                score += max(0.0, 0.4 - (0.7 * conf))

        # Normalize by theoretical max per item (=1.0)
        return max(0.0, min(1.0, score / total))

    @staticmethod
    def grade_easy(state: State) -> float:
        """
        Grade easy task: simple email classification.
        Returns score between 0.0 and 1.0
        """
        if len(state.classifications) == 0:
            return 0.0

        correct = 0
        total = len(state.ground_truth)

        for email_id, true_category in state.ground_truth.items():
            if email_id in state.classifications:
                classified_category = state.classifications[email_id]["category"]
                if classified_category == true_category:
                    correct += 1

        accuracy = correct / total if total > 0 else 0.0
        return round(accuracy, 3)

    @staticmethod
    def grade_medium(state: State) -> float:
        """
        Grade medium task: classification accuracy with confidence weighting.
        Returns score between 0.0 and 1.0
        """
        if len(state.classifications) == 0:
            return 0.0

        total = len(state.ground_truth)
        if total == 0:
            return 0.0

        correct = 0
        confidence_component = 0.0

        for email_id, true_category in state.ground_truth.items():
            pred = state.classifications.get(email_id)
            if not pred:
                continue

            is_correct = pred["category"] == true_category
            confidence = max(0.0, min(1.0, float(pred.get("confidence", 0.5))))

            if is_correct:
                correct += 1
                confidence_component += 0.2 * confidence
            elif confidence > 0.7:
                confidence_component -= 0.15

        accuracy_component = correct / total
        confidence_component = max(0.0, min(1.0, confidence_component / total))

        final_score = (0.7 * accuracy_component) + (0.3 * confidence_component)
        return round(max(0.0, min(1.0, final_score)), 3)

    @staticmethod
    def grade_hard(state: State) -> float:
        """
        Grade hard task with multi-factor scoring:
        1) Overall accuracy (40%)
        2) Phishing detection accuracy (40%)
        3) Confidence calibration (20%)

        Returns:
            Score between 0.0 and 1.0
        """
        if len(state.classifications) == 0:
            return 0.0

        total = len(state.ground_truth)
        if total == 0:
            return 0.0

        overall_correct = 0
        phishing_total = 0
        phishing_correct = 0

        # Build email lookup once
        inbox_map: Dict[str, Email] = {e.email_id: e for e in state.emails_in_inbox}

        for email_id, true_category in state.ground_truth.items():
            pred = state.classifications.get(email_id)
            if not pred:
                continue

            predicted_category = pred.get("category")
            is_correct = predicted_category == true_category
            if is_correct:
                overall_correct += 1

            email_obj = inbox_map.get(email_id)
            is_phishing = EmailTriageGrader._is_phishing_pattern(email_obj)

            if is_phishing:
                phishing_total += 1
                # For phishing-like patterns, "spam" is expected true positive behavior.
                true_is_spam = true_category == "spam"
                pred_is_spam = predicted_category == "spam"
                if pred_is_spam == true_is_spam:
                    phishing_correct += 1

        overall_accuracy = overall_correct / total
        phishing_accuracy = (
            (phishing_correct / phishing_total) if phishing_total > 0 else 0.5
        )
        confidence_score = EmailTriageGrader._confidence_calibration_score(state)

        final_score = (
            (0.4 * overall_accuracy)
            + (0.4 * phishing_accuracy)
            + (0.2 * confidence_score)
        )
        return round(max(0.0, min(1.0, final_score)), 3)

    @staticmethod
    def grade_task(state: State) -> float:
        """Grade by task type using deterministic rubric."""
        if state.task_type == "easy":
            return EmailTriageGrader.grade_easy(state)
        if state.task_type == "medium":
            return EmailTriageGrader.grade_medium(state)
        if state.task_type == "hard":
            return EmailTriageGrader.grade_hard(state)
        raise ValueError(f"Unsupported task type for grading: {state.task_type}")
