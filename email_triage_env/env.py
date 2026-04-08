"""Email Triage Environment Core implementing step/reset/state."""

import hashlib
import random
from datetime import datetime
from typing import Optional, Tuple

from email_triage_env.models import Email, Observation, Reward, State, TriageAction


class EmailTriageEnv:
    """
    Email Triage OpenEnv Environment.

    Task: Classify incoming emails into categories (spam, urgent, follow_up, informational).
    State: Managed per-session to prevent leakage across episodes.
    """

    # Synthetic email dataset - task-specific
    EASY_EMAILS = [
        {
            "subject": "URGENT: Meeting at 2pm Today",
            "body": "Important meeting scheduled for today at 2pm in conference room A. Please confirm attendance.",
            "sender": "boss@company.com",
            "category": "urgent",
            "has_attachment": False,
            "is_flagged": True,
        },
        {
            "subject": "Congratulations! You've won a FREE iPhone",
            "body": "Claim your prize now! Click here to collect your FREE iPhone. Limited time offer!!!",
            "sender": "noreply@spam-service.com",
            "category": "spam",
            "has_attachment": False,
            "is_flagged": False,
        },
        {
            "subject": "Weekly Report - March 30",
            "body": "Here is the weekly status report. Q1 metrics are attached. Please review.",
            "sender": "reports@company.com",
            "category": "informational",
            "has_attachment": True,
            "is_flagged": False,
        },
        {
            "subject": "Extend your car warranty - Final Notice",
            "body": "Your vehicle warranty is about to expire. Act now to extend coverage and avoid expensive repairs.",
            "sender": "offers@warranty-now.biz",
            "category": "spam",
            "has_attachment": False,
            "is_flagged": False,
        },
        {
            "subject": "Server down - production outage",
            "body": "Production API is returning 500 errors across regions. Join the incident bridge immediately.",
            "sender": "oncall@company.com",
            "category": "urgent",
            "has_attachment": False,
            "is_flagged": True,
        },
        {
            "subject": "Company holiday schedule",
            "body": "Please find the approved company holiday calendar for this year. No immediate action required.",
            "sender": "hr@company.com",
            "category": "informational",
            "has_attachment": True,
            "is_flagged": False,
        },
        {
            "subject": "Re: Your expense report submission",
            "body": "Thanks for submitting your expense report. Please confirm one missing receipt when convenient.",
            "sender": "expenses@company.com",
            "category": "follow_up",
            "has_attachment": False,
            "is_flagged": False,
        },
        {
            "subject": "Monthly product updates",
            "body": "Highlights from this month: new dashboard, faster exports, and mobile improvements.",
            "sender": "product-updates@company.com",
            "category": "informational",
            "has_attachment": False,
            "is_flagged": False,
        },
        {
            "subject": "Your ticket has been resolved",
            "body": "Support ticket #84321 is now marked resolved. Reply if the issue persists.",
            "sender": "support@company.com",
            "category": "follow_up",
            "has_attachment": False,
            "is_flagged": False,
        },
        {
            "subject": "Team sync - Thursday 10am",
            "body": "Calendar invite for weekly team sync. Agenda includes sprint progress and blockers.",
            "sender": "calendar@company.com",
            "category": "informational",
            "has_attachment": True,
            "is_flagged": False,
        },
    ]

    MEDIUM_EMAILS = [
        {
            "subject": "Project Budget Review - Action Needed",
            "body": "Need your input on Q2 budget allocation. Previously discussed in our meeting. Can you provide updated numbers?",
            "sender": "finance@company.com",
            "category": "follow_up",
            "has_attachment": True,
            "is_flagged": False,
        },
        {
            "subject": "Awesome opportunities await! Make $5000/week",
            "body": "Work from home. Send bitcoin to activate account. No experience needed! Amazing income potential.",
            "sender": "opportunity@sketchy-site.com",
            "category": "spam",
            "has_attachment": False,
            "is_flagged": False,
        },
        {
            "subject": "System Alert: Unusual Login Detected",
            "body": "Your account detected login from unknown location. Verify immediately or your account will be locked.",
            "sender": "security@company.com",
            "category": "urgent",
            "has_attachment": False,
            "is_flagged": True,
        },
        {
            "subject": "Follow up: Proposal Feedback?",
            "body": "Hi, just checking in on the proposal we discussed last week. Would love to hear your thoughts when you get a chance.",
            "sender": "partner@external.com",
            "category": "follow_up",
            "has_attachment": False,
            "is_flagged": False,
        },
        {
            "subject": "Monthly Newsletter - Industry Trends",
            "body": "Latest insights on AI adoption. Read about emerging trends in enterprise automation.",
            "sender": "newsletter@industry.com",
            "category": "informational",
            "has_attachment": False,
            "is_flagged": False,
        },
        {
            "subject": "Urgent: Mailbox quota exceeded - verify now",
            "body": "Your mailbox will stop receiving emails today unless you confirm account details at the link below.",
            "sender": "it-helpdesk@company-mail.net",
            "category": "spam",
            "has_attachment": False,
            "is_flagged": True,
        },
        {
            "subject": "Urgent request: FYI only before 5 PM",
            "body": "Need a quick read of the deck before leadership review; no response needed unless you spot major risks.",
            "sender": "pm@company.com",
            "category": "informational",
            "has_attachment": True,
            "is_flagged": False,
        },
        {
            "subject": "Re: Notes from yesterday's client call",
            "body": "Sharing follow-up notes from the call. Main decisions are captured below for your reference.",
            "sender": "account-manager@company.com",
            "category": "follow_up",
            "has_attachment": False,
            "is_flagged": False,
        },
        {
            "subject": "Monthly Newsletter: Action required for preferences",
            "body": "Please update your regional notification settings by Friday to continue receiving relevant content.",
            "sender": "newsletter@vendor.com",
            "category": "follow_up",
            "has_attachment": False,
            "is_flagged": False,
        },
        {
            "subject": "Support escalation: intermittent login failures",
            "body": "Customer impact is growing. Please advise if engineering can prioritize a fix in the next sprint.",
            "sender": "support-escalations@company.com",
            "category": "urgent",
            "has_attachment": False,
            "is_flagged": True,
        },
        {
            "subject": "Quick favor before board meeting",
            "body": "Are you available to send me the latest account summary today? Keep this between us for now.",
            "sender": "ceo-office@companny.com",
            "category": "spam",
            "has_attachment": False,
            "is_flagged": False,
        },
        {
            "subject": "Invoice 8841 for April services",
            "body": "Attached is this month's invoice for managed services. Please process through standard AP workflow.",
            "sender": "billing@trustedvendor.com",
            "category": "follow_up",
            "has_attachment": True,
            "is_flagged": False,
        },
        {
            "subject": "Password reset requested",
            "body": "We received a request to reset your password. If this was you, use the secure portal to continue.",
            "sender": "no-reply@identity-provider.com",
            "category": "urgent",
            "has_attachment": False,
            "is_flagged": True,
        },
        {
            "subject": "Meeting moved to 4:30 PM today",
            "body": "Rescheduling due to conflict. Please confirm if the new time works for your team.",
            "sender": "coordinator@partner.com",
            "category": "follow_up",
            "has_attachment": False,
            "is_flagged": False,
        },
        {
            "subject": "Senior Remote Role - Immediate Interview Slot",
            "body": "Your profile fits a confidential leadership role. Share your resume to reserve priority interview timing.",
            "sender": "talent-team@career-network.pro",
            "category": "spam",
            "has_attachment": False,
            "is_flagged": False,
        },
        {
            "subject": "Invitation: Cloud Security Summit 2025",
            "body": "You are invited to attend our annual summit. Registration is complimentary for enterprise attendees.",
            "sender": "events@cloudsummit.org",
            "category": "informational",
            "has_attachment": False,
            "is_flagged": False,
        },
        {
            "subject": "Software update available for endpoint agent",
            "body": "Version 4.9 includes stability fixes. Schedule upgrade during your next maintenance window.",
            "sender": "updates@it-ops.company.com",
            "category": "informational",
            "has_attachment": False,
            "is_flagged": False,
        },
        {
            "subject": "Team announcement: submit OKRs by Monday",
            "body": "Department OKRs are due by end of day Monday. Please add yours in the planning sheet.",
            "sender": "operations@company.com",
            "category": "urgent",
            "has_attachment": True,
            "is_flagged": False,
        },
        {
            "subject": "Expense approval needed for travel reimbursement",
            "body": "A pending expense report requires your approval to meet this payroll cycle cutoff.",
            "sender": "expenses@company.com",
            "category": "follow_up",
            "has_attachment": False,
            "is_flagged": False,
        },
        {
            "subject": "Contract review request - Vendor MSA",
            "body": "Please review the redlines in sections 4 and 7 before tomorrow's legal sync.",
            "sender": "legal@company.com",
            "category": "follow_up",
            "has_attachment": True,
            "is_flagged": False,
        },
    ]

    HARD_EMAILS = [
        # Deceptive spam with professional appearance
        {
            "subject": "Invoice #2024-031: Payment Due",
            "body": "Please process payment of $2,450 to the attached account. Wire transfer required immediately.",
            "sender": "invoicing@legit-looking-fraud.com",
            "category": "spam",
            "has_attachment": True,
            "is_flagged": False,
        },
        # Nuanced follow-up vs informational
        {
            "subject": "Insights from Our Last Discussion",
            "body": "Wanted to share some thoughts following our conversation yesterday. These approaches align with what you mentioned.",
            "sender": "colleague@company.com",
            "category": "follow_up",
            "has_attachment": False,
            "is_flagged": False,
        },
        # Time-sensitive but not marked urgent
        {
            "subject": "Conference Registration - 2 Days Left",
            "body": "Early bird registration closes March 31st. Secure your spot for the annual tech summit. Link below.",
            "sender": "events@conference.com",
            "category": "informational",
            "has_attachment": False,
            "is_flagged": False,
        },
        # Mixed signals - looks urgent but is spam
        {
            "subject": "CRITICAL: Verify Your Identity NOW",
            "body": "Security alert: Click here to verify your banking credentials. Failure to act may result in account suspension!",
            "sender": "phishing@bank-imposter.com",
            "category": "spam",
            "has_attachment": False,
            "is_flagged": False,
        },
        # Context-dependent: could be follow-up
        {
            "subject": "RE: Budget Discussion",
            "body": "Thanks for the detailed breakdown. One clarification - can you detail the infrastructure costs separately?",
            "sender": "manager@company.com",
            "category": "follow_up",
            "has_attachment": False,
            "is_flagged": False,
        },
        {
            "subject": "Confidential request before earnings call",
            "body": "Need you to urgently purchase gift cards for client incentives and send codes privately.",
            "sender": "ceo@company-co.com",
            "category": "spam",
            "has_attachment": False,
            "is_flagged": True,
        },
        {
            "subject": "Wire transfer required - Acquisition escrow",
            "body": "Please process same-day transfer to updated beneficiary. Legal documents are attached and board approved.",
            "sender": "finance-director@business-consulting.com",
            "category": "spam",
            "has_attachment": True,
            "is_flagged": True,
        },
        {
            "subject": "Following up on your recent promotion",
            "body": "Congrats on your new role from LinkedIn. Please review attached leadership onboarding policy update.",
            "sender": "peopleops@company-benefits.co",
            "category": "spam",
            "has_attachment": True,
            "is_flagged": False,
        },
        {
            "subject": "M365 security notice: re-authentication needed",
            "body": "Your enterprise mailbox needs immediate token refresh. Visit portal: https://micr0soft-login.com/security.",
            "sender": "alerts@micr0soft.com",
            "category": "spam",
            "has_attachment": False,
            "is_flagged": True,
        },
        {
            "subject": "PayPal limitation warning",
            "body": "Your account access is limited. Verify ownership now to restore payment receiving capability.",
            "sender": "service@раypal.com",
            "category": "spam",
            "has_attachment": False,
            "is_flagged": True,
        },
        {
            "subject": "Your account will be closed in 24 hours",
            "body": "Final warning from your bank: confirm identity immediately or all transactions will be blocked.",
            "sender": "notice@secure-bank-alerts.net",
            "category": "spam",
            "has_attachment": False,
            "is_flagged": True,
        },
        {
            "subject": "HR Compliance: W-2 verification needed today",
            "body": "Send scanned W-2 copies for all team members before 3 PM for annual tax reconciliation.",
            "sender": "hr-compliance@company-payroll.co",
            "category": "spam",
            "has_attachment": False,
            "is_flagged": True,
        },
        {
            "subject": "Updated remittance details for outstanding invoice",
            "body": "Please use the new bank account listed in this message for all pending payments effective immediately.",
            "sender": "ap@trustedvendor.com",
            "category": "spam",
            "has_attachment": True,
            "is_flagged": False,
        },
        {
            "subject": "Re: Q3 planning deck (updated link)",
            "body": "Great discussion earlier. Use this revised shared link to view the final deck before tomorrow.",
            "sender": "colleague@company.com",
            "category": "spam",
            "has_attachment": False,
            "is_flagged": False,
        },
        {
            "subject": "Delivery failed - reschedule your package",
            "body": "We attempted delivery today. Confirm address and pay redelivery fee using the secure form.",
            "sender": "support@parcel-track-help.com",
            "category": "spam",
            "has_attachment": False,
            "is_flagged": False,
        },
        {
            "subject": "Invoice correction - same PO, new bank coordinates",
            "body": "Only the beneficiary account has changed due to audit migration. Kindly settle before end of day.",
            "sender": "accounts@longtime-vendor.com",
            "category": "spam",
            "has_attachment": True,
            "is_flagged": False,
        },
        {
            "subject": "Team sync invite - strategy review",
            "body": "Please join via attached calendar file to preview meeting objectives and supporting notes.",
            "sender": "calendar-invite@corp-events.net",
            "category": "spam",
            "has_attachment": True,
            "is_flagged": False,
        },
        {
            "subject": "Security alert: Approve new sign-in",
            "body": "A login was blocked. Confirm your two-factor code immediately to prevent account lockout.",
            "sender": "security-center@identity-checker.io",
            "category": "spam",
            "has_attachment": False,
            "is_flagged": True,
        },
        {
            "subject": "Critical patch available for build pipeline",
            "body": "Install attached updater from your CI vendor to fix high severity package execution vulnerability.",
            "sender": "release@trusted-ci-tools.com",
            "category": "spam",
            "has_attachment": True,
            "is_flagged": True,
        },
        {
            "subject": "Privileged legal hold request - immediate action",
            "body": "As discussed with CFO, send all pending litigation files to external counsel before market open.",
            "sender": "legal.ops@executive-advisory.co",
            "category": "spam",
            "has_attachment": False,
            "is_flagged": True,
        },
    ]

    def __init__(self):
        """Initialize environment with clean state."""
        self._state: Optional[State] = None
        self.episode_id: Optional[str] = None

    def reset(self, task="easy", seed=None) -> Observation:
        """
        Reset environment for a new episode.

        Args:
            task: "easy", "medium", or "hard"
            seed: Random seed for reproducibility

        Returns:
            Initial observation
        """
        if seed is not None:
            random.seed(seed)

        if task not in ["easy", "medium", "hard"]:
            raise ValueError(
                f"Invalid task: {task}. Must be 'easy', 'medium', or 'hard'"
            )

        # Generate unique episode ID
        self.episode_id = hashlib.md5(
            f"{datetime.now().isoformat()}{random.random()}".encode()
        ).hexdigest()[:8]

        # Select emails based on task difficulty
        if task == "easy":
            email_list = self.EASY_EMAILS
        elif task == "medium":
            email_list = self.MEDIUM_EMAILS
        else:  # hard
            email_list = self.HARD_EMAILS

        # Shuffle emails
        email_list = random.sample(email_list, len(email_list))

        # Create Email objects with IDs
        emails = []
        ground_truth = {}
        base_timestamp = int(datetime.now().timestamp())

        for idx, email_data in enumerate(email_list):
            email_id = f"email_{self.episode_id}_{idx}"
            email = Email(
                email_id=email_id,
                sender=email_data["sender"],
                subject=email_data["subject"],
                body=email_data["body"][:500],  # Truncate to 500 chars
                timestamp=base_timestamp
                - (len(email_list) - idx) * 3600,  # Spread over hours
                has_attachment=email_data["has_attachment"],
                is_flagged=email_data["is_flagged"],
            )
            emails.append(email)
            ground_truth[email_id] = email_data["category"]

        # Initialize state
        self._state = State(
            episode_id=self.episode_id,
            task_type=task,
            emails_in_inbox=emails,
            current_email_idx=0,
            classifications={},
            ground_truth=ground_truth,
            episode_done=False,
            cumulative_reward=0.0,
            correctly_classified=0,
            total_processed=0,
            last_action_signature="",
            repeated_invalid_actions=0,
        )

        return self._get_observation()

    def step(self, action: TriageAction) -> Tuple[Observation, Reward, bool, dict]:
        """
        Process an email classification action.

        Args:
            action: TriageAction with email_id, category, and confidence

        Returns:
            (observation, reward, done, info)
        """
        if self._state is None:
            raise RuntimeError("Environment not initialized. Call reset() first.")

        reward_value = 0.0
        reward_breakdown = {}
        is_invalid = False

        # Penalize repeated invalid or repeated identical classifications on the same email.
        action_signature = (
            f"{action.email_id}:{action.category.value}:{action.confidence:.3f}"
        )
        if self._state.last_action_signature == action_signature:
            reward_breakdown["repeat_action_penalty"] = -0.2
            reward_value += reward_breakdown["repeat_action_penalty"]

        # Validate action
        if action.email_id not in self._state.ground_truth:
            # Invalid email ID
            reward_value = -1.0
            reward_breakdown["error"] = "Invalid email ID"
            is_invalid = True
        else:
            if action.email_id in self._state.classifications:
                reward_breakdown["reclassify_penalty"] = -0.35
                reward_value += reward_breakdown["reclassify_penalty"]

            # Check correctness
            correct_category = self._state.ground_truth[action.email_id]
            is_correct = action.category.value == correct_category

            # Base correctness reward
            correctness_bonus = 1.0 if is_correct else 0.0
            reward_breakdown["correctness"] = correctness_bonus

            # Confidence penalty: penalize overconfidence on wrong answers
            if not is_correct and action.confidence > 0.8:
                confidence_penalty = -0.5 * action.confidence
                reward_breakdown["confidence_penalty"] = confidence_penalty
            elif is_correct:
                # Bonus for justified confidence
                confidence_bonus = (
                    0.2 * action.confidence if action.confidence > 0.5 else 0.0
                )
                reward_breakdown["confidence_bonus"] = confidence_bonus

            reward_value += correctness_bonus
            reward_value += reward_breakdown.get("confidence_penalty", 0.0)
            reward_value += reward_breakdown.get("confidence_bonus", 0.0)

        # Record classification
        self._state.classifications[action.email_id] = {
            "category": action.category.value,
            "confidence": action.confidence,
        }
        self._state.last_action_signature = action_signature
        if is_invalid:
            self._state.repeated_invalid_actions += 1

        # Update metrics
        if action.category.value == self._state.ground_truth.get(action.email_id):
            self._state.correctly_classified += 1

        self._state.total_processed += 1
        self._state.cumulative_reward += reward_value

        # Move to next email
        self._state.current_email_idx += 1

        # Check if episode is done
        done = self._state.current_email_idx >= len(self._state.emails_in_inbox)
        self._state.episode_done = done

        reward = Reward(value=reward_value, breakdown=reward_breakdown)

        observation = self._get_observation()

        info = {
            "episode_id": self.episode_id,
            "task": self._state.task_type,
            "emails_processed": self._state.total_processed,
            "accuracy_so_far": self._state.correctly_classified
            / max(1, self._state.total_processed),
            "cumulative_reward": self._state.cumulative_reward,
            "repeated_invalid_actions": self._state.repeated_invalid_actions,
        }

        return observation, reward, done, info

    def state(self) -> State:
        """
        Return current internal state (for debugging/evaluation).
        """
        if self._state is None:
            raise RuntimeError("Environment not initialized. Call reset() first.")
        return self._state

    def _get_observation(self) -> Observation:
        """
        Generate observation for the agent.
        """
        if self._state is None:
            raise RuntimeError("Environment not initialized.")

        current_idx = self._state.current_email_idx
        if current_idx >= len(self._state.emails_in_inbox):
            # Return final observation
            current_email = self._state.emails_in_inbox[-1]
        else:
            current_email = self._state.emails_in_inbox[current_idx]

        return Observation(
            current_email=current_email,
            inbox_remaining=len(self._state.emails_in_inbox) - current_idx - 1,
            correctly_classified=self._state.correctly_classified,
            total_processed=self._state.total_processed,
            task_difficulty=self._state.task_type,
        )
