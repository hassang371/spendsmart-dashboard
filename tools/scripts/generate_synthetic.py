import pandas as pd
import random
from datetime import datetime, timedelta
import string

def generate_transaction_id():
    prefixes = ["GPY", "YPC", "GPA", "SOP"]
    prefix = random.choice(prefixes)
    parts = [
        "".join(random.choices(string.digits, k=4)),
        "".join(random.choices(string.digits, k=4)),
        "".join(random.choices(string.digits, k=4)),
        "".join(random.choices(string.digits, k=5))
    ]
    base = f"{prefix}.{parts[0]}-{parts[1]}-{parts[2]}-{parts[3]}"
    if random.random() < 0.1:
        base += f"..{random.randint(0,2)}"
    return base

products = [
    ("YouTube", ["Music Premium", "YouTube Premium Individual", "Samay Raina membership"]),
    ("Google One", ["Cloud Storage Monthly", "Google One 200 GB"]),
    ("Google Play Apps", ["Play Pass Monthly", "AI Pro Subscription", "Productivity Suite"]),
    ("Google Play Movies", ["Movie Rental HD"])
]

payment_methods = [
    "Visa **** 3534", "Visa **** 5315", "UPI: QR code", 
    "Axis Bank UPI", "HDFC Bank UPI", "SBI UPI", "ICICI Bank"
]

statuses = ["Complete", "Refunded", "Cancelled"]
status_weights = [0.8, 0.1, 0.1]

amounts = [59.00, 79.00, 99.00, 129.00, 149.00, 199.00, 210.00, 249.00, 299.00, 399.00, 499.00]

# Date range: today to 1 month ago
end_date = datetime.now() # "2026-02-25 19:27:00" roughly
start_date = end_date - timedelta(days=30)

num_transactions = 150
data = []

for _ in range(num_transactions):
    # Random date within range
    random_seconds = random.randint(0, int((end_date - start_date).total_seconds()))
    tx_time = start_date + timedelta(seconds=random_seconds)
    
    # Format time: "7 Feb 2026, 17:13"
    # Using %-d doesn't work on all platforms, so string manipulation is safer
    day = str(tx_time.day)
    time_str = f"{day} {tx_time.strftime('%b %Y, %H:%M')}"
    
    tx_id = generate_transaction_id()
    
    # Random product & description
    product_tuple = random.choice(products)
    product = product_tuple[0]
    description = random.choice(product_tuple[1])
    
    payment_method = random.choice(payment_methods)
    status = random.choices(statuses, weights=status_weights, k=1)[0]
    amount_val = random.choice(amounts)
    amount_str = f"INR {amount_val:.2f}"
    
    data.append([time_str, tx_id, description, product, payment_method, status, amount_str])

df = pd.DataFrame(data, columns=["Time", "Transaction ID", "Description", "Product", "Payment method", "Status", "Amount"])

# Sort by Time descending
df['ParsedTime'] = pd.to_datetime(df['Time'])
df = df.sort_values(by='ParsedTime', ascending=False)
df = df.drop(columns=['ParsedTime'])

output_path = './tools/synthetic_transactions.csv'
df.to_csv(output_path, index=False)
print(f"Generated {num_transactions} synthetic transactions at {output_path}")
