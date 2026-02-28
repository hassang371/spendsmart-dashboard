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
        "Food",
        "Restaurant",
        "Dining",
        "Groceries",
        "Swiggy",
        "Zomato",
        "Blinkit",
        "Zepto",
        "Delivery",
        "Cafe",
        "Coffee",
        "Tea",
        "Snacks",
        "Lunch",
        "Dinner",
        "Breakfast",
        "Burger",
        "Pizza",
    ],
    Category.TRANSPORT.value: [
        "Transport",
        "Taxi",
        "Uber",
        "Ola",
        "Rapido",
        "Bus",
        "Train",
        "Flight",
        "Fuel",
        "Petrol",
        "Diesel",
        "Metro",
        "Travel",
        "Fare",
        "Ticket",
    ],
    Category.UTILITIES.value: [
        "Utilities",
        "Bill",
        "Electricity",
        "Water",
        "Gas",
        "Broadband",
        "Wifi",
        "Recharge",
        "Mobile",
        "Phone",
        "Airtel",
        "Jio",
        "Vodafone",
        "Bescom",
    ],
    Category.SALARY.value: [
        "Salary",
        "Income",
        "Paycheck",
        "Credit",
        "Deposit",
        "Earnings",
        "Wage",
        "Bonus",
        "Stipend",
    ],
    Category.SHOPPING.value: [
        "Shopping",
        "Amazon",
        "Flipkart",
        "Myntra",
        "Clothing",
        "Electronics",
        "Retail",
        "Store",
        "Fashion",
        "Purchase",
        "Mall",
        "Mart",
        "Decathlon",
    ],
    Category.ENTERTAINMENT.value: [
        "Entertainment",
        "Movie",
        "Cinema",
        "Netflix",
        "Spotify",
        "Youtube",
        "Hotstar",
        "Prime",
        "Game",
        "Steam",
        "Subscription",
        "Event",
        "Show",
    ],
    Category.HEALTH.value: [
        "Health",
        "Medical",
        "Doctor",
        "Pharmacy",
        "Medicine",
        "Hospital",
        "Clinic",
        "Fitness",
        "Gym",
        "Healthcare",
        "Lab",
        "Test",
        "Diagnostics",
        "Apollo",
        "Pharmeasy",
    ],
    Category.EDUCATION.value: [
        "Education",
        "Course",
        "Tuition",
        "School",
        "College",
        "University",
        "Book",
        "Udemy",
        "Coursera",
        "Learning",
        "Fee",
        "Exam",
    ],
    Category.FINANCE.value: [
        "Finance",
        "Investment",
        "Loan",
        "Insurance",
        "Bank",
        "Transfer",
        "Withdrawal",
        "ATM",
        "EMI",
        "Mutual Fund",
        "SIP",
        "Stocks",
        "Zerodha",
        "Groww",
        "Tax",
    ],
    Category.PEOPLE.value: [
        "Transfer",
        "Sent",
        "Received",
        "Friend",
        "Family",
        "Person",
        "Relative",
        "Gift",
        "Refund",
        "Reimbursement",
    ],
    Category.MISC.value: [
        "Misc",
        "General",
        "Other",
        "Unknown",
        "Payment",
        "Service",
        "Charge",
    ],
}
