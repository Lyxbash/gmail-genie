"""
Regression tests for deterministic rules (no LLM).

Run from project root:
  python backend/tests/test_rules_regression.py -v
  python -m backend.tests.test_rules_regression -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Allow ``python backend/tests/test_rules_regression.py`` without setting PYTHONPATH.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.rules.rule_engine import classify_by_rules


class RulesRegressionTests(unittest.TestCase):
    def _classify(self, sender: str, subject: str, snippet: str = "") -> dict:
        return classify_by_rules(sender, subject, snippet)

    def _cat(self, sender: str, subject: str, snippet: str = "") -> str:
        return self._classify(sender, subject, snippet)["category"]

    def test_google_play_refund(self) -> None:
        c = self._cat(
            "Google Play <googleplay-noreply@google.com>",
            "Your Google Play refund has been approved",
        )
        self.assertIn(c, ("Receipts", "Finance"))

    def test_google_one_subscription(self) -> None:
        c = self._cat(
            "Google One <googleone-noreply@google.com>",
            "You've activated a new Google AI Pro plan",
        )
        self.assertEqual(c, "Finance")

    def test_google_setup_not_job(self) -> None:
        c = self._cat(
            "Google <no-reply@google.com>",
            "Finish setting up your iPhone with Google",
        )
        self.assertNotEqual(c, "Job Alerts")
        self.assertIn(c, ("Security Alerts", "General"))

    def test_linkedin_newsletter(self) -> None:
        c = self._cat(
            "LinkedIn <newsletters-noreply@linkedin.com>",
            "Kunal Kushwaha via LinkedIn — Weekly digest",
        )
        self.assertEqual(c, "Newsletters")

    def test_linkedin_jobs(self) -> None:
        c = self._cat(
            "LinkedIn <jobs-noreply@linkedin.com>",
            "Your job recommendations for this week",
        )
        self.assertEqual(c, "Job Alerts")

    def test_linkedin_invitation(self) -> None:
        c = self._cat(
            "LinkedIn <invitations@linkedin.com>",
            "You have a new invitation",
        )
        self.assertEqual(c, "Social")

    def test_leetcode_weekly_digest(self) -> None:
        c = self._cat(
            "LeetCode <no-reply@leetcode.com>",
            "LeetCode Weekly Digest",
        )
        self.assertEqual(c, "Newsletters")

    def test_deeplearning_the_batch(self) -> None:
        c = self._cat(
            "DeepLearning.AI <newsletter@deeplearning.ai>",
            "The Batch @ DeepLearning.AI — Issue 42",
        )
        self.assertEqual(c, "Newsletters")

    def test_stripe_receipt(self) -> None:
        c = self._cat(
            "Stripe <receipts@stripe.com>",
            "Your receipt from Acme #1234",
        )
        self.assertIn(c, ("Receipts", "Finance"))

    def test_github_security(self) -> None:
        c = self._cat(
            "GitHub <security@github.com>",
            "Security alert: vulnerable dependency",
        )
        self.assertEqual(c, "Security Alerts")

    def test_tldr_newsletter(self) -> None:
        c = self._cat(
            "TLDR <hello@tldrnewsletter.com>",
            "TLDR Daily — tech roundup",
        )
        self.assertEqual(c, "Newsletters")

    def test_domain_only_not_job_alerts(self) -> None:
        """Generic google.com noreply without job intent must not be Job Alerts."""
        c = self._cat(
            "Google <no-reply@google.com>",
            "Your account summary is ready",
        )
        self.assertNotEqual(c, "Job Alerts")

    def test_domain_only_linkedin_not_job_alerts(self) -> None:
        c = self._cat(
            "LinkedIn <noreply@linkedin.com>",
            "Your weekly account summary",
        )
        self.assertNotEqual(c, "Job Alerts")

    def test_domain_only_leetcode_not_job_applications(self) -> None:
        c = self._cat(
            "LeetCode <no-reply@leetcode.com>",
            "Explore new problems on LeetCode",
        )
        self.assertNotEqual(c, "Job Applications/Referrals")

    def test_linkedin_profile_view_social(self) -> None:
        c = self._cat(
            "LinkedIn <noreply@linkedin.com>",
            "Someone viewed your profile",
        )
        self.assertEqual(c, "Social")

    def test_leetcode_application_status(self) -> None:
        c = self._cat(
            "LeetCode <no-reply@leetcode.com>",
            "Your application status update",
        )
        self.assertEqual(c, "Job Applications/Referrals")

    def test_google_play_refund_with_snippet(self) -> None:
        c = self._cat(
            "Google Play <googleplay-noreply@google.com>",
            "Your Google Play refund has been approved",
            "Transaction ID 123. Payment method Visa. Refund processed.",
        )
        self.assertIn(c, ("Receipts", "Finance"))
        self.assertNotEqual(c, "Job Alerts")

    def test_google_one_with_snippet(self) -> None:
        c = self._cat(
            "Google One <googleone-noreply@google.com>",
            "You've activated a new Google AI Pro 5 TB plan",
            "Subscription activated. Billing starts today.",
        )
        self.assertEqual(c, "Finance")
        self.assertNotEqual(c, "Job Alerts")

    def test_paypal_payment(self) -> None:
        c = self._cat(
            "PayPal <service@paypal.com>",
            "You sent a payment",
            "Transaction receipt payment debited",
        )
        self.assertIn(c, ("Receipts", "Finance"))

    def test_amazon_receipt(self) -> None:
        c = self._cat(
            "Amazon <order-update@amazon.com>",
            "Your Amazon.com order of item",
            "Order receipt invoice shipped",
        )
        self.assertIn(c, ("Receipts", "Shopping", "Finance"))

    def test_deeplearning_batch_not_finance(self) -> None:
        c = self._cat(
            "DeepLearning.AI <newsletter@deeplearning.ai>",
            "The Batch @ DeepLearning.AI — Issue 42",
        )
        self.assertEqual(c, "Newsletters")
        self.assertNotEqual(c, "Finance")

    def test_leetcode_weekly_not_job_application(self) -> None:
        c = self._cat(
            "LeetCode <no-reply@leetcode.com>",
            "LeetCode Weekly Digest",
        )
        self.assertEqual(c, "Newsletters")
        self.assertNotEqual(c, "Job Applications/Referrals")

    def test_zoom_reminder_not_promotions(self) -> None:
        c = self._cat(
            "Zoom <no-reply@zoom.us>",
            "Reminder: Team standup meeting starts in 15 minutes",
            "Join Zoom Meeting",
        )
        self.assertNotEqual(c, "Promotions")
        self.assertIn(c, ("Work", "General"))

    def test_codepen_digest_newsletter(self) -> None:
        c = self._cat(
            "CodePen <newsletter@codepen.io>",
            "The Code — your weekly front-end digest",
        )
        self.assertEqual(c, "Newsletters")
        self.assertNotEqual(c, "Promotions")


if __name__ == "__main__":
    unittest.main()
