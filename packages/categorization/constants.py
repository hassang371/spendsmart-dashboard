"""Category constants for transaction classification (v2).

Expanded taxonomy with ~25 categories for better user visibility.
Categories are stored as a flat enum — the model uses semantic embeddings
so adding a new category requires zero retraining.
"""

from enum import Enum


class Category(str, Enum):
    """Standard transaction categories for classification."""

    # ── Food & Dining ────────────────────────────────────────────────────
    FOOD = "Food"
    GROCERIES = "Groceries"
    COFFEE_SNACKS = "Coffee & Snacks"

    # ── Transport ────────────────────────────────────────────────────────
    TAXI_RIDESHARE = "Taxi & Rideshare"
    PUBLIC_TRANSIT = "Public Transit"
    FLIGHTS = "Flights"
    FUEL = "Fuel"

    # ── Housing & Utilities ──────────────────────────────────────────────
    RENT_MORTGAGE = "Rent & Mortgage"
    ELECTRICITY_WATER = "Electricity & Water"
    INTERNET_PHONE = "Internet & Phone"
    HOME_MAINTENANCE = "Home Maintenance"

    # ── Shopping ─────────────────────────────────────────────────────────
    CLOTHING_FASHION = "Clothing & Fashion"
    ELECTRONICS = "Electronics"
    GENERAL_RETAIL = "General Retail"

    # ── Entertainment ────────────────────────────────────────────────────
    SUBSCRIPTIONS = "Subscriptions"
    MOVIES_EVENTS = "Movies & Events"
    GAMING = "Gaming"

    # ── Health ───────────────────────────────────────────────────────────
    MEDICAL = "Medical"
    PHARMACY = "Pharmacy"
    FITNESS = "Fitness"

    # ── Finance ──────────────────────────────────────────────────────────
    INVESTMENTS = "Investments"
    INSURANCE = "Insurance"
    LOAN_EMI = "Loan EMI"
    TAXES = "Taxes"
    BANK_FEES = "Bank Fees"

    # ── Travel & Lodging ─────────────────────────────────────────────────
    HOTELS_STAYS = "Hotels & Stays"
    TRAVEL_BOOKING = "Travel Booking"

    # ── People ───────────────────────────────────────────────────────────
    TRANSFERS_TO_PEOPLE = "Transfers to People"
    RECEIVED_FROM_PEOPLE = "Received from People"

    # ── Income ───────────────────────────────────────────────────────────
    SALARY = "Salary"
    REFUNDS = "Refunds"
    INTEREST = "Interest"

    # ── Misc ─────────────────────────────────────────────────────────────
    UNCATEGORIZED = "Uncategorized"


# Seed phrases for category embedding anchors (used by zero-shot classifier)
DEFAULT_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    Category.FOOD.value: [
        "swiggy food order",
        "zomato restaurant payment",
        "dining out",
        "food delivery",
        "restaurant bill",
        "eatfit meal",
        "dunzo food",
        "dominos pizza",
        "kfc chicken",
        "burger king",
        "mcdonald meal",
    ],
    Category.GROCERIES.value: [
        "blinkit grocery delivery",
        "zepto quick delivery",
        "bigbasket order",
        "supermarket purchase",
        "grocery store shopping",
        "vegetables fruits",
        "swiggy instamart",
        "dunzo grocery delivery",
        "jiomart order",
    ],
    Category.COFFEE_SNACKS.value: [
        "starbucks coffee",
        "cafe coffee day",
        "third wave coffee",
        "tea snack purchase",
        "bakery pastry order",
        "juice smoothie",
    ],
    Category.TAXI_RIDESHARE.value: [
        "uber ride payment",
        "ola cab trip",
        "rapido bike taxi",
        "uber auto ride",
        "ola share cab",
        "rideshare payment",
    ],
    Category.PUBLIC_TRANSIT.value: [
        "metro card recharge",
        "bus ticket booking",
        "local train pass",
        "redbus bus ticket",
        "irctc train ticket",
        "railway pass renewal",
    ],
    Category.FLIGHTS.value: [
        "indigo flight booking",
        "spicejet airline ticket",
        "air india flight",
        "vistara airline",
        "goair booking",
        "flight ticket purchase",
        "airline booking payment",
    ],
    Category.FUEL.value: [
        "petrol pump payment",
        "diesel fuel purchase",
        "hp petrol",
        "indian oil fuel",
        "bharat petroleum",
        "fastag toll payment",
        "fuel station refueling",
    ],
    Category.RENT_MORTGAGE.value: [
        "rent payment monthly",
        "house rent transfer",
        "landlord rental payment",
        "mortgage emi debit",
        "property maintenance fee",
        "housing society charges",
    ],
    Category.ELECTRICITY_WATER.value: [
        "electricity bill payment",
        "bescom power bill",
        "tata power electricity",
        "bwssb water bill",
        "gas cylinder booking",
        "lpg refill delivery",
    ],
    Category.INTERNET_PHONE.value: [
        "airtel mobile recharge",
        "jio prepaid recharge",
        "act fibernet broadband bill",
        "vodafone postpaid bill",
        "bsnl broadband payment",
        "vi recharge plan",
    ],
    Category.HOME_MAINTENANCE.value: [
        "plumber service payment",
        "electrician home repair",
        "carpenter furniture fix",
        "home cleaning service",
        "painting renovation charge",
        "pest control service",
    ],
    Category.CLOTHING_FASHION.value: [
        "myntra fashion purchase",
        "ajio clothing order",
        "meesho fashion sale",
        "nykaa beauty order",
        "h&m clothing purchase",
        "zara fashion store",
    ],
    Category.ELECTRONICS.value: [
        "croma electronics purchase",
        "reliance digital store",
        "laptop computer purchase",
        "mobile phone accessory",
        "electronic gadget order",
        "smartwatch purchase",
    ],
    Category.GENERAL_RETAIL.value: [
        "amazon purchase order",
        "flipkart product order",
        "online shopping payment",
        "retail store purchase",
        "decathlon sports equipment",
        "dmart shopping bill",
    ],
    Category.SUBSCRIPTIONS.value: [
        "netflix monthly subscription",
        "spotify premium payment",
        "jiocinema subscription",
        "sonyliv monthly plan",
        "hotstar disney subscription",
        "youtube premium individual",
        "apple one subscription",
        "play pass monthly google",
    ],
    Category.MOVIES_EVENTS.value: [
        "bookmyshow movie ticket",
        "pvr cinema ticket",
        "event concert booking",
        "inox movie hall",
        "comedy show ticket",
        "theater performance booking",
    ],
    Category.GAMING.value: [
        "google play games purchase",
        "steam gaming purchase",
        "playstation store",
        "xbox game pass",
        "dream11 contest",
        "mobile game purchase",
        "in-app gaming payment",
    ],
    Category.MEDICAL.value: [
        "hospital bill payment",
        "clinic doctor consultation",
        "medical test diagnostics",
        "health checkup package",
        "surgery operation charges",
        "dental treatment payment",
    ],
    Category.PHARMACY.value: [
        "1mg medicine order",
        "netmeds pharmacy delivery",
        "apollo pharmacy order",
        "pharmeasy medicine purchase",
        "medical store prescription",
        "pharmacy health products",
    ],
    Category.FITNESS.value: [
        "cultfit gym membership",
        "gold gym monthly plan",
        "yoga class subscription",
        "fitness studio payment",
        "healthifyme premium",
        "sports club membership",
    ],
    Category.INVESTMENTS.value: [
        "mutual fund sip investment",
        "zerodha brokerage",
        "groww investment transfer",
        "upstox trading account",
        "stock market purchase",
        "fixed deposit investment",
    ],
    Category.INSURANCE.value: [
        "insurance premium payment",
        "life insurance policy",
        "health insurance renewal",
        "vehicle insurance premium",
        "term plan premium",
        "bajaj allianz insurance",
    ],
    Category.LOAN_EMI.value: [
        "loan emi payment",
        "bajaj finance emi debit",
        "home loan emi monthly",
        "personal loan installment",
        "credit card emi payment",
        "education loan emi",
    ],
    Category.TAXES.value: [
        "income tax payment",
        "gst payment government",
        "property tax municipal",
        "advance tax challan",
        "tds tax deducted source",
        "professional tax debit",
    ],
    Category.BANK_FEES.value: [
        "bank charge fee debit",
        "processing fee payment",
        "convenience fee transaction",
        "annual maintenance charge",
        "sms alert charges",
        "atm usage surcharge",
    ],
    Category.HOTELS_STAYS.value: [
        "airbnb accommodation booking",
        "oyo hotel room",
        "hotel stay reservation",
        "resort booking payment",
        "makemytrip hotel",
        "goibibo hotel booking",
        "booking.com accommodation",
        "treebo hotel stay",
    ],
    Category.TRAVEL_BOOKING.value: [
        "makemytrip travel booking",
        "ixigo trip planning",
        "cleartrip holiday package",
        "yatra travel booking",
        "goibibo flight hotel",
        "travel agency package",
    ],
    Category.TRANSFERS_TO_PEOPLE.value: [
        "upi transfer to friend",
        "sent money family member",
        "personal payment transfer",
        "money sent contact person",
        "neft imps transfer individual",
        "upi debit transfer person",
    ],
    Category.RECEIVED_FROM_PEOPLE.value: [
        "upi received from friend",
        "money received family",
        "reimbursement from colleague",
        "personal credit transfer",
        "neft credit individual",
        "upi credit from person",
    ],
    Category.SALARY.value: [
        "salary credited monthly",
        "payroll credit transfer",
        "salary neft deposit",
        "wages credited account",
        "monthly income payment",
        "stipend credit",
    ],
    Category.REFUNDS.value: [
        "refund credited account",
        "return order refund",
        "cashback credit received",
        "payment reversal credit",
        "order cancellation refund",
        "reimbursement received",
    ],
    Category.INTEREST.value: [
        "interest credit savings",
        "fd maturity interest",
        "bank interest deposit",
        "interest earned account",
        "savings account interest",
        "recurring deposit interest",
    ],
    Category.UNCATEGORIZED.value: [
        "miscellaneous payment service",
        "general charge fee",
        "other payment unknown",
        "service fee charge",
    ],
}


# ── Legacy Mapping ──────────────────────────────────────────────────────
# Maps old 11-class category names to new expanded equivalents.
# Used when migrating existing data or handling old API requests.

LEGACY_CATEGORY_MAP: dict[str, str] = {
    "Food": Category.FOOD.value,
    "Transport": Category.TAXI_RIDESHARE.value,
    "Utilities": Category.ELECTRICITY_WATER.value,
    "Salary": Category.SALARY.value,
    "Shopping": Category.GENERAL_RETAIL.value,
    "Entertainment": Category.SUBSCRIPTIONS.value,
    "Health": Category.MEDICAL.value,
    "Education": Category.UNCATEGORIZED.value,  # Removed — reclassify
    "Finance": Category.INVESTMENTS.value,
    "People": Category.TRANSFERS_TO_PEOPLE.value,
    "Misc": Category.UNCATEGORIZED.value,
    "Uncategorized": Category.UNCATEGORIZED.value,
}
