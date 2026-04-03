import random
import sys
from datetime import datetime, timedelta

import pandas as pd


def create_synthetic_row(last_row, date_str):
    """Creates a mostly identical synthetic row but with a new date and modified balance."""
    new_row = last_row.copy()
    new_row.iloc[0] = date_str
    # Generate a random debit
    debit = round(random.uniform(10.0, 500.0), 2)
    # Clear credit
    new_row.iloc[4] = pd.NA
    new_row.iloc[3] = debit

    # Calculate new balance
    prev_balance = float(last_row.iloc[5]) if pd.notna(last_row.iloc[5]) else 0.0
    new_balance = round(prev_balance - debit, 2)
    new_row.iloc[5] = new_balance

    # Modify Details slightly
    details = ["POS ATM PURCH ZOMATO", "UPI PAYMENT REMARK", "AMAZON PAY", "SWIGGY DINE"]
    new_row.iloc[1] = random.choice(details)
    return new_row


def main():
    file_path = "/Users/mohammedhassanmohiddin/Downloads/statement_updated.xlsx"
    print(f"Reading {file_path}...")

    try:
        df = pd.read_excel(file_path, header=None)
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    # Find the header row
    header_idx = -1
    for i in range(len(df)):
        row_vals = df.iloc[i].astype(str).str.lower().tolist()
        if any("date" in str(v).lower() for v in row_vals) and any("details" in str(v).lower() for v in row_vals):
            header_idx = i
            break

    if header_idx == -1:
        print("Could not find transactions table header")
        return

    print(f"Found headers at row {header_idx}")

    # Identify transaction rows
    transactions_start = header_idx + 1
    # Sometimes there are footer rows. We stop when Date is NaN
    transactions_end = transactions_start
    while (
        transactions_end < len(df)
        and pd.notna(df.iloc[transactions_end, 0])
        and str(df.iloc[transactions_end, 0]).strip() != ""
    ):
        transactions_end += 1

    print(f"Found {transactions_end - transactions_start} transactions.")

    # Parse dates
    # Date is at column 0
    # Let's find the max date
    max_date = None
    dates = []

    for i in range(transactions_start, transactions_end):
        date_val = str(df.iloc[i, 0]).strip()
        try:
            # Assuming DD/MM/YYYY format based on preview
            dt = datetime.strptime(date_val, "%d/%m/%Y")
            dates.append((i, dt))
            if max_date is None or dt > max_date:
                max_date = dt
        except ValueError:
            pass  # Keep track of parsing failures but don't crash

    if not dates:
        print("Could not parse any dates")
        return

    print(f"Max date found: {max_date.strftime('%Y-%m-%d')}")

    # Calculate delta to today
    today = datetime.now()
    delta = today.date() - max_date.date()
    # If max_date is already today, we can just optionally add some days...
    # The requirement: "update the dates so the last transactions are of today and all the days before it"
    delta_days = delta.days
    print(f"Shifting dates by {delta_days} days to make max date today.")

    for idx, dt in dates:
        new_dt = dt + timedelta(days=delta_days)
        df.iloc[idx, 0] = new_dt.strftime("%d/%m/%Y")

    # Add synthetic data for "today"
    print("Adding synthetic data for today...")
    new_rows = []
    last_idx = transactions_end - 1
    last_row = df.iloc[last_idx]

    for _ in range(5):
        # Generate some records for today or yesterday
        synth_date = today.strftime("%d/%m/%Y")
        synth_row = create_synthetic_row(last_row, synth_date)
        new_rows.append(synth_row)
        last_row = synth_row  # Update last_row for balance calculation

    # Append new rows
    synth_df = pd.DataFrame(new_rows)

    # Split df into before footer and footer
    head_df = df.iloc[:transactions_end]
    tail_df = df.iloc[transactions_end:]

    final_df = pd.concat([head_df, synth_df, tail_df], ignore_index=True)

    # Save back
    output_path = file_path
    print(f"Saving updated file to {output_path}...")
    final_df.to_excel(output_path, index=False, header=False)
    print("Done!")


if __name__ == "__main__":
    main()
