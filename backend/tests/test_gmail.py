from backend.infrastructure.gmail.gmail_client import GmailClient
from backend.config import load_config, resolve_gmail_query

config = load_config()

gmail = GmailClient()

emails = gmail.fetch_emails(
    query=resolve_gmail_query(config=config),
    max_results=5,
)

for email in emails:

    print("\n===================")

    print("FROM:", email["sender"])

    print("SUBJECT:", email["subject"])

    print("SNIPPET:", email["snippet"][:100])