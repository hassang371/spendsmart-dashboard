"""Category constants for transaction classification.

This module defines the standard categories used throughout the SCALE application
for transaction classification. Using constants instead of hardcoded strings
ensures consistency and makes it easier to add new categories.
"""

from enum import Enum


class Category(str, Enum):
    """Standard transaction categories for classification."""

    FOOD = "Food"
    TRANSPORT = "Transport"
    UTILITIES = "Utilities"
    SALARY = "Salary"
    SHOPPING = "Shopping"
    ENTERTAINMENT = "Entertainment"
    HEALTH = "Health"
    EDUCATION = "Education"
    FINANCE = "Finance"
    PEOPLE = "People"
    MISC = "Misc"
    UNCATEGORIZED = "Uncategorized"


# Default category keywords for HypCD classifier
DEFAULT_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    Category.FOOD.value: [
        "swiggy order",
        "zomato payment",
        "restaurant bill",
        "blinkit grocery delivery",
        "zepto quick delivery",
        "bigbasket grocery order",
        "dunzo delivery payment",
        "eatfit healthy meal",
        "dominos pizza order",
        "cafe coffee purchase",
        "food delivery payment",
    ],
    Category.TRANSPORT.value: [
        "uber ride payment",
        "ola cab trip",
        "rapido bike taxi",
        "metro card recharge",
        "irctc train ticket",
        "indigo flight booking",
        "makemytrip travel",
        "fastag toll payment",
        "petrol pump payment",
        "redbus bus ticket booking",
    ],
    Category.UTILITIES.value: [
        "electricity bill payment",
        "water bill bescom",
        "airtel mobile recharge",
        "jio prepaid recharge",
        "act fibernet broadband bill",
        "tata power electricity",
        "bwssb water bill payment",
        "vodafone postpaid bill",
        "gas cylinder booking",
        "broadband monthly bill",
    ],
    Category.SALARY.value: [
        "salary credited",
        "monthly payroll credit",
        "salary transfer neft",
        "payroll deposit",
        "salary for month of",
        "stipend payment",
        "wages credited account",
        "monthly income transfer",
    ],
    Category.SHOPPING.value: [
        "amazon purchase order",
        "flipkart product order",
        "myntra fashion purchase",
        "nykaa beauty order",
        "meesho clothing order",
        "croma electronics purchase",
        "decathlon sports equipment",
        "ajio fashion sale",
        "retail shopping payment",
        "online shopping order",
    ],
    Category.ENTERTAINMENT.value: [
        "netflix monthly subscription",
        "spotify premium payment",
        "jiocinema subscription",
        "sonyliv monthly plan",
        "hotstar disney subscription",
        "youtube premium individual",
        "bookmyshow movie ticket",
        "pvr cinema ticket",
        "play pass monthly google",
        "music premium subscription",
    ],
    Category.HEALTH.value: [
        "pharmacy medicine purchase",
        "hospital bill payment",
        "clinic doctor consultation",
        "1mg medicine order",
        "netmeds pharmacy delivery",
        "cult.fit gym membership",
        "healthifyme subscription",
        "apollo pharmacy order",
        "lab test payment diagnostics",
        "pharmeasy medicine",
    ],
    Category.EDUCATION.value: [
        "udemy course payment",
        "unacademy subscription",
        "byju learning app",
        "coursera online course",
        "tuition fee school",
        "college exam fee payment",
        "physics wallah subscription",
        "upgrad course enrollment",
        "simplilearn certification",
        "book purchase education",
    ],
    Category.FINANCE.value: [
        "loan emi payment",
        "insurance premium payment",
        "mutual fund sip investment",
        "zerodha brokerage",
        "groww investment transfer",
        "cred credit card payment",
        "bajaj finance emi debit",
        "fd interest deposit bank",
        "tax payment government",
        "upstox trading account",
    ],
    Category.PEOPLE.value: [
        "transfer to friend upi",
        "sent money family member",
        "gift payment personal",
        "reimbursement from colleague",
        "upi transfer person",
        "money sent contact",
        "personal transfer neft",
        "family expense payment",
    ],
    Category.MISC.value: [
        "miscellaneous payment service",
        "general charge fee",
        "other payment unknown",
        "service fee charge",
        "processing fee payment",
        "convenience fee transaction",
        "bank charge fee debit",
        "penalty fine payment",
    ],
}
