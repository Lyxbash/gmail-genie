from backend.infrastructure.gmail.gmail_client import GmailClient
from backend.services.classifier_service import EmailClassifier
from backend.config import load_config


config = load_config()

gmail = GmailClient()

classifier = EmailClassifier()

emails = gmail.fetch_emails(
    query=config["app"]["gmail_query"],
    max_results=5
)

for email in emails:

    result = classifier.classify_email(
        email
    )

    print("\n======================")

    print("FROM:", email["sender"])

    print("SUBJECT:", email["subject"])

    print("CATEGORY:", result["category"])

    print("CONFIDENCE:", result["confidence"])

    print("SOURCE:", result.get("source"))