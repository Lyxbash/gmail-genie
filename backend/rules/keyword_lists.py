"""
Comprehensive keyword ontology for Gmail Genie rule classification.

Keywords are grouped by intent and category. Rule modules import only the
lists they need to keep matching fast and maintainable.
"""

# ---------------------------------------------------------------------------
# Security & account alerts
# ---------------------------------------------------------------------------

SECURITY_KEYWORDS = [
    "otp",
    "one-time password",
    "one time password",
    "verification code",
    "verify your code",
    "security alert",
    "security notification",
    "login attempt",
    "sign-in attempt",
    "sign in attempt",
    "new sign-in",
    "new sign in",
    "suspicious login",
    "suspicious sign-in",
    "password reset",
    "reset your password",
    "change your password",
    "2fa",
    "two-factor",
    "two factor",
    "multi-factor",
    "authentication code",
    "verify your identity",
    "account recovery",
    "recover your account",
    "unusual activity",
    "unrecognized device",
    "device verification",
    "authorize this login",
    "confirm it was you",
    "account locked",
    "account suspended",
    "verify your email",
    "email verification",
    "magic link",
    "passcode",
    "pin code",
    "authenticator app",
]

SECURITY_SUBJECT_KEYWORDS = [
    "security alert",
    "verification code",
    "password reset",
    "otp",
    "new sign-in",
    "suspicious login",
    "login alert",
    "account alert",
]

SECURITY_DOMAIN_SUBJECT_KEYWORDS = [
    "alert",
    "security",
    "verification",
    "password",
    "login",
    "sign-in",
    "sign in",
    "otp",
    "verify",
]

# ---------------------------------------------------------------------------
# Spam & phishing
# ---------------------------------------------------------------------------

SPAM_KEYWORDS = [
    "win cash",
    "claim reward",
    "lottery winner",
    "lottery",
    "free iphone",
    "congratulations you won",
    "you have been selected",
    "urgent response required",
    "urgent action required",
    "crypto doubling",
    "double your bitcoin",
    "investment guaranteed",
    "guaranteed returns",
    "click here immediately",
    "act now or lose",
    "limited time only",
    "nigerian prince",
    "inheritance fund",
    "wire transfer fee",
    "western union",
    "moneygram",
    "bank details required",
    "verify your account now",
    "account will be closed",
    "suspended account",
    "paypal limited",
    "irs refund",
    "tax refund pending",
    "free gift card",
    "amazon refund",
    "microsoft support",
    "apple id locked",
    "netflix payment failed",
    "weight loss miracle",
    "work from home",
    "earn $5000",
    "make money fast",
    "viagra",
    "cialis",
    "enlarge",
    "hot singles",
    "dating verification",
    "keto pills",
    "cbd oil",
    "forex signals",
    "binary options",
    "penny stocks alert",
]

SPAM_COMBO_PATTERNS = [
    ("bitcoin giveaway",),
    ("claim now", "offer"),
    ("urgent action required",),
    ("inheritance",),
    ("nigerian prince",),
    ("verify your wallet",),
    ("seed phrase",),
    ("metamask", "urgent"),
]

# ---------------------------------------------------------------------------
# Job applications & hiring pipeline
# ---------------------------------------------------------------------------

JOB_APPLICATION_KEYWORDS = [
    "referral",
    "referred by",
    "application received",
    "application submitted",
    "application status",
    "interview",
    "online assessment",
    "oa link",
    "coding challenge",
    "hackerrank",
    "codesignal",
    "codility",
    "hacker rank",
    "next round",
    "recruiter update",
    "technical interview",
    "hr round",
    "panel interview",
    "offer letter",
    "job offer",
    "background check",
    "take-home assignment",
    "take home assignment",
    "screening call",
    "phone screen",
    "onsite interview",
    "virtual onsite",
    "next interview round",
    "assessment link",
    "skills assessment",
]

JOB_ALERT_KEYWORDS = [
    "jobs near you",
    "recommended jobs",
    "job alert",
    "job alerts",
    "new openings",
    "hiring now",
    "top jobs",
    "jobs you may like",
    "jobs for you",
    "position available",
    "open roles",
    "matching jobs",
    "career opportunities",
    "apply now on linkedin",
    "new jobs posted",
    "job recommendations",
    "similar jobs",
    "jobs based on your profile",
]

RECRUITER_KEYWORDS = [
    "consultancy",
    "staffing",
    "talent acquisition",
    "recruiter",
    "recruitment",
    "hiring manager",
    "hr team",
    "headhunter",
    "placement agency",
    "contract role",
    "bench resource",
    "immediate joiner",
    "client requirement",
    "bulk hiring",
]

# ---------------------------------------------------------------------------
# Receipts & transactional
# ---------------------------------------------------------------------------

RECEIPT_KEYWORDS = [
    "invoice",
    "receipt",
    "payment successful",
    "payment received",
    "payment confirmation",
    "order receipt",
    "tax invoice",
    "billing statement",
    "your payment of",
    "amount paid",
    "transaction id",
    "transaction reference",
    "paid successfully",
    "payment completed",
    "e-receipt",
    "digital receipt",
]

# ---------------------------------------------------------------------------
# Shopping & e-commerce
# ---------------------------------------------------------------------------

SHOPPING_KEYWORDS = [
    "order confirmed",
    "order confirmation",
    "your order",
    "order placed",
    "shipped",
    "out for delivery",
    "delivered",
    "refund initiated",
    "return initiated",
    "package tracking",
    "track your order",
    "delivery update",
    "dispatch confirmation",
    "order cancelled",
    "order canceled",
    "back in stock",
    "cart reminder",
    "items in your cart",
    "wishlist",
    "price drop",
]

FOOD_DELIVERY_KEYWORDS = [
    "your order is being prepared",
    "food delivery",
    "order picked up",
    "delivery partner",
    "restaurant order",
    "meal delivered",
    "rider is on the way",
    "delivery executive",
]

# ---------------------------------------------------------------------------
# Finance & banking
# ---------------------------------------------------------------------------

FINANCE_KEYWORDS = [
    "transaction alert",
    "account statement",
    "bank statement",
    "monthly statement",
    "credited",
    "debited",
    "bank account",
    "upi",
    "imps",
    "neft",
    "rtgs",
    "mutual fund",
    "sip",
    "credit card",
    "debit card",
    "emi",
    "loan disbursement",
    "fd maturity",
    "portfolio",
    "trading statement",
    "brokerage",
    "demat",
    "payment due",
    "minimum due",
    "autopay",
    "nach",
    "standing instruction",
]

BILL_UTILITY_KEYWORDS = [
    "electricity bill",
    "internet bill",
    "mobile recharge",
    "broadband bill",
    "gas bill",
    "water bill",
    "utility bill",
    "postpaid bill",
    "prepaid recharge",
    "due date reminder",
]

# ---------------------------------------------------------------------------
# Travel & transport
# ---------------------------------------------------------------------------

TRAVEL_KEYWORDS = [
    "pnr",
    "boarding pass",
    "flight",
    "hotel booking",
    "trip confirmed",
    "itinerary",
    "check-in",
    "check in",
    "e-ticket",
    "eticket",
    "reservation confirmed",
    "cab booking",
    "ride receipt",
    "train ticket",
    "bus ticket",
    "visa appointment",
    "travel insurance",
    "baggage allowance",
    "gate change",
    "flight delayed",
    "hotel reservation",
    "airbnb",
    "rental car",
]

# ---------------------------------------------------------------------------
# Promotions & marketing
# ---------------------------------------------------------------------------

PROMOTION_KEYWORDS = [
    "sale",
    "discount",
    "limited offer",
    "limited time offer",
    "buy now",
    "shop now",
    "exclusive deal",
    "flat off",
    "mega sale",
    "special offer",
    "flash sale",
    "clearance",
    "end of season",
    "black friday",
    "cyber monday",
    "big billion days",
    "great indian festival",
    "upto 70%",
    "up to 70%",
    "coupon code",
    "promo code",
    "use code",
    "free shipping",
    "last chance",
    "don't miss out",
    "unlock offer",
    "member exclusive",
]

PROMOTION_SECONDARY_KEYWORDS = [
    "unsubscribe",
    "marketing",
    "contest",
    "coupon",
    "giveaway",
    "sweepstakes",
    "advertisement",
    "promotional",
]

# ---------------------------------------------------------------------------
# Newsletters & digests
# ---------------------------------------------------------------------------

NEWSLETTER_KEYWORDS = [
    "newsletter",
    "weekly digest",
    "daily digest",
    "weekly",
    "daily",
    "digest",
    "round-up",
    "latest news",
    "top stories",
    "editorial",
    "morning brief",
    "evening brief",
    "this week in",
    "roundup",
    "issue #",
    "edition",
    "weekly roundup",
    "daily roundup",
    "weekly round-up",
    "daily round-up",
    "the batch",
    "product hunt daily",
    "product hunt weekly",
    "subscriber update",
    "read online",
    "view in browser",
]

# ---------------------------------------------------------------------------
# Work & productivity
# ---------------------------------------------------------------------------

WORK_KEYWORDS = [
    "meeting",
    "calendar invite",
    "calendar invitation",
    "sprint",
    "standup",
    "stand-up",
    "retrospective",
    "jira",
    "asana",
    "notion",
    "linear",
    "clickup",
    "trello",
    "slack",
    "teams meeting",
    "zoom meeting",
    "project update",
    "action items",
    "deadline",
    "roadmap",
    "okr",
    "quarterly review",
    "1:1",
    "one on one",
]

# ---------------------------------------------------------------------------
# Social
# ---------------------------------------------------------------------------

SOCIAL_KEYWORDS = [
    "someone mentioned you",
    "new follower",
    "connection request",
    "friend request",
    "liked your post",
    "commented on your",
    "tagged you",
    "shared a post",
    "birthday today",
    "memory with",
    "invited you to connect",
    "accepted your invitation",
    "profile view",
    "message request",
    "dm you",
    "direct message",
]

# ---------------------------------------------------------------------------
# Entertainment & streaming
# ---------------------------------------------------------------------------

ENTERTAINMENT_KEYWORDS = [
    "your subscription",
    "subscription renewed",
    "new episode",
    "new season",
    "now streaming",
    "watch now",
    "continue watching",
    "playlist",
    "premium plan",
    "free trial ending",
    "trial expires",
    "membership",
    "streaming",
    "binge",
]

# ---------------------------------------------------------------------------
# Developer & cloud
# ---------------------------------------------------------------------------

DEVELOPER_KEYWORDS = [
    "pull request",
    "merge request",
    "deployment",
    "deployed",
    "ci/cd",
    "ci cd",
    "pipeline failed",
    "build failed",
    "repository",
    "commit",
    "workflow run",
    "github actions",
    "gitlab ci",
    "vercel",
    "netlify",
    "docker",
    "kubernetes",
    "aws alert",
    "gcp alert",
    "azure alert",
    "sentry",
    "datadog",
    "incident",
    "on-call",
    "pagerduty",
    "dependabot",
    "security advisory",
    "npm audit",
    "pypi",
    "artifact",
]

# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------

EDUCATION_KEYWORDS = [
    "course",
    "assignment",
    "certificate",
    "enrollment",
    "enrolment",
    "lesson",
    "module",
    "quiz",
    "exam",
    "grades",
    "syllabus",
    "lecture",
    "webinar recording",
    "learning path",
    "cohort",
    "bootcamp",
    "degree program",
]

# ---------------------------------------------------------------------------
# Health & wellness
# ---------------------------------------------------------------------------

HEALTH_KEYWORDS = [
    "appointment confirmed",
    "lab report",
    "prescription",
    "doctor appointment",
    "teleconsultation",
    "health checkup",
    "diagnostic",
    "pharmacy order",
    "medicine delivery",
    "vaccination",
    "medical records",
    "test results",
]

# ---------------------------------------------------------------------------
# Government & civic
# ---------------------------------------------------------------------------

GOVERNMENT_KEYWORDS = [
    "income tax",
    "aadhaar",
    "aadhar",
    "pan card",
    "passport",
    "voter id",
    "driving licence",
    "driving license",
    "gst",
    "itr",
    "efiling",
    "e-filing",
    "government of",
    "ministry of",
    "municipal",
    "property tax",
    "ration card",
    "digilocker",
    "umang",
]

# ---------------------------------------------------------------------------
# Personal
# ---------------------------------------------------------------------------

PERSONAL_KEYWORDS = [
    "happy birthday",
    "wedding invitation",
    "family",
    "dinner plans",
    "see you soon",
    "party invitation",
    "catch up",
    "thinking of you",
    "anniversary",
    "baby shower",
    "reunion",
]

# ---------------------------------------------------------------------------
# Intent signals (cross-category)
# ---------------------------------------------------------------------------

INTENT_TRANSACTIONAL = [
    "confirmation",
    "confirmed",
    "receipt",
    "invoice",
    "payment",
    "order",
    "booking",
    "reservation",
    "ticket",
]

INTENT_PROMOTIONAL = [
    "sale",
    "discount",
    "offer",
    "deal",
    "unsubscribe",
    "promo",
]

INTENT_SECURITY = [
    "otp",
    "verify",
    "security",
    "login",
    "password",
]
