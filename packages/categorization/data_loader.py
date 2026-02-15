import pandas as pd
import msoffcrypto
import io
import re


class BankStatementParser:
    def __init__(self, file_path_or_obj, password=None):
        """
        :param file_path_or_obj: str path to file OR bytes/file-like object
        :param password: str password for encrypted Excel
        """
        self.file_source = file_path_or_obj
        self.file_path = file_path_or_obj
        self.password = password
        self.df = None  # Initialize to None

    def parse(self):
        """
        Parses the bank statement Excel file.
        1. Decrypts if password provided.
        2. Reads file to find header row.
        3. Extracts and cleans data.
        """
        # 1. Decrypt / Load
        # Handle file source types
        if isinstance(self.file_source, str):
            # It's a path
            if self.password:
                decrypted = io.BytesIO()
                with open(self.file_source, "rb") as f:
                    office_file = msoffcrypto.OfficeFile(f)
                    office_file.load_key(password=self.password)
                    office_file.decrypt(decrypted)
                decrypted.seek(0)
                file_obj = decrypted
            else:
                file_obj = self.file_source
        else:
            # It's bytes or file-like
            # If bytes, wrap in BytesIO
            if isinstance(self.file_source, bytes):
                f_stream = io.BytesIO(self.file_source)
            else:
                f_stream = self.file_source

            if self.password:
                decrypted = io.BytesIO()
                # Ensure at start
                if hasattr(f_stream, "seek"):
                    f_stream.seek(0)
                office_file = msoffcrypto.OfficeFile(f_stream)
                office_file.load_key(password=self.password)
                office_file.decrypt(decrypted)
                decrypted.seek(0)
                file_obj = decrypted
            else:
                if hasattr(f_stream, "seek"):
                    f_stream.seek(0)
                file_obj = f_stream

        # 2. Read with header detection logic
        # Based on inspection, header is likely around row 16.
        # We can try to read with header=None first, find "Details" row, then reload.
        # Or just use the known logic if we want to be fast.
        # Let's be robust: Search for "Details" in first 30 rows.

        # Read first 30 rows as raw
        raw_df = pd.read_excel(file_obj, header=None, nrows=30, engine="openpyxl")
        header_row_idx = None

        for idx, row in raw_df.iterrows():
            # Check if this row looks like a header
            row_str = row.astype(str).str.lower().tolist()
            if any("details" in s for s in row_str):
                header_row_idx = idx
                break

        if header_row_idx is None:
            raise ValueError("Could not find header row containing 'Details'")

        # Reload with correct header
        if hasattr(file_obj, "seek"):
            file_obj.seek(0)

        df = pd.read_excel(file_obj, header=header_row_idx, engine="openpyxl")

        # 3. Clean and Extract
        # Standardize column names
        # Map actual columns to standard: Date, Details, Debit, Credit
        # We expect columns like "Txn Date", "Description", "Debit", "Credit" etc.
        # Let's build a mapper based on our inspection or fuzzy match.

        col_map = {}
        for col in df.columns:
            c = str(col).lower()
            if "date" in c and "txn" in c or "date" in c:
                col_map[col] = "Date"
            elif "detail" in c or "narration" in c or "desc" in c:
                col_map[col] = "Details"
            elif "debit" in c or "dr" in c:
                col_map[col] = "Debit"
            elif ("credit" in c or "cr" in c) and "balance" not in c:
                col_map[col] = "Credit"

        df = df.rename(columns=col_map)

        # Validate required columns
        required = ["Date", "Details"]
        missing = [r for r in required if r not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}. Found: {list(df.columns)}")

        # Calculate Amount
        # Credit is positive, Debit is negative
        # Ensure numeric
        if "Credit" in df.columns:
            df["Credit"] = pd.to_numeric(df["Credit"], errors="coerce").fillna(0)
        else:
            df["Credit"] = 0

        if "Debit" in df.columns:
            df["Debit"] = pd.to_numeric(df["Debit"], errors="coerce").fillna(0)
        else:
            df["Debit"] = 0

        df["Amount"] = df["Credit"] - df["Debit"]

        # Extract Dictionary of Details
        details_struct = df["Details"].astype(str).apply(self.extract_details)

        # Expand into columns
        df_struct = pd.DataFrame(details_struct.tolist())
        df = pd.concat([df, df_struct], axis=1)

        # Use Entity as Cleaned_Details if available, else fallback to regex cleaning
        # This addresses the user's issue about "wdl tfr upi" being the name
        def get_best_name(row):
            if row["entity"] and len(row["entity"]) > 2:
                return row["entity"]
            return self.clean_details(row["Details"])

        df["Cleaned_Details"] = df.apply(get_best_name, axis=1)

        self.df = df  # Store for inspection
        return df

    def clean_details(self, text):
        """
        Cleans transaction description string.
        Removes:
        - Common banking prefixes (POS, ATM, PURCH)
        - Dates and timestamps
        - Long numeric IDs
        - Special characters
        """
        if not isinstance(text, str):
            text = str(text)

        # 1. Remove prefixes
        prefixes = [
            "POS",
            "ATM",
            "PURCH",
            "PURCHASE",
            "OTHPG",
            "UPI",
            "WDL",
            "TFR",
            "ME",
            "MB",
            "IB",
            "DEP",
            "CR",
            "DR",
            "SBIPG",
            "Paym",
            "NEFT",
            "SBIN",
            "IMPS",
        ]
        for p in prefixes:
            text = re.sub(r"\b" + p + r"\b", "", text, flags=re.IGNORECASE)

        # Remove IFSC-like codes (SBIN followed by digits/chars)
        text = re.sub(r"\bSBIN[A-Z0-9]+\b", "", text, flags=re.IGNORECASE)

        # 2. Remove "AT <Branch Code> <Branch Name>"
        # Pattern: AT 04413 PBB NELLORE
        text = re.sub(r"\bAT \d{4,}\b.*", "", text)

        # 3. Remove "XXRAZ*" pattern (Razorpay?)
        # Pattern: 30RAZ*FamPay -> FamPay
        text = re.sub(r"\b\d{2}RAZ\*", "", text)

        # 4. Remove dates (DD/MM/YYYY or DD-MM-YYYY or DDMMYY)
        # simplistic regex for now
        text = re.sub(r"\d{2}[/-]\d{2}[/-]\d{2,4}", "", text)

        # 5. Remove long distinct numbers (IDs) e.g. > 6 digits
        text = re.sub(r"\b\d{6,}\b", "", text)

        # 6. Separate stuck numbers (e.g. 79SWIGGY -> 79 SWIGGY)
        # Then we can remove the number if it's just 2 digits
        text = re.sub(r"(\d+)([A-Za-z]+)", r"\1 \2", text)

        # Remove standalone numbers (any length)
        # We assume standalone numbers in bank statements are usually not useful (amounts, IDs, dates parts)
        text = re.sub(r"\b\d+\b", "", text)

        # 7. Remove special characters and newlines
        text = re.sub(r"[\n\r\t]", " ", text)
        text = re.sub(r"[^\w\s]", " ", text)

        text = re.sub(r"\s+", " ", text).strip()

        return text

    def extract_details(self, text):
        """
        Extracts structured information from transaction details.
        Returns dict: {method, entity, ref, location, type, meta}
        """
        text = str(text).strip()
        info = {
            "method": "OTHERS",
            "entity": "",
            "ref": "",
            "location": "",
            "type": "DEBIT",  # Default, can be overridden
            "meta": {},
        }

        # 1. UPI Transactions
        # Pattern: [WDL/DEP] TFR UPI/[DR/CR]/[UTR]/[NAME]/[BANK]/[ID]
        # Example: WDL TFR UPI/DR/931523643407/SHAIK YA/SBIN/skya smeen1/Paym
        upi_match = re.search(r"UPI/([A-Z]+)/(\d+)/([^/]+)/([^/]+)/([^/]+)", text)
        if upi_match:
            info["method"] = "UPI"
            dr_cr = upi_match.group(1)
            info["type"] = "CREDIT" if dr_cr == "CR" else "DEBIT"
            info["ref"] = upi_match.group(2)
            info["entity"] = upi_match.group(3).strip()
            info["meta"] = {
                "bank": upi_match.group(4).strip(),
                "upi_id": upi_match.group(5).strip(),
            }
            # Check for App at the end (e.g. /Paym)
            parts = text.split("/")
            if len(parts) > 6:
                info["meta"]["app"] = parts[-1].split()[
                    0
                ]  # Take first word if extra junk
            return info

        # 2. POS / Card Transactions
        # Pattern: POS ATM PURCH [Gateway] [Ref] [Merchant]
        # Example: POS ATM PURCH OTHPG 3155010693 17Pho*PHONEPE RECHARGE BANGALORE
        if "POS" in text and "PURCH" in text:
            info["method"] = "POS"
            # Try to extract Ref (usually 10+ digits)
            ref_match = re.search(r"\b(\d{10,})\b", text)
            if ref_match:
                info["ref"] = ref_match.group(1)

            # Extract Merchant & Location (Everything after Ref)
            # Or if Ref not found, everything after prefix

            # Remove standard prefixes to isolate merchant
            clean = text
            for p in ["POS", "ATM", "PURCH", "OTHPG", "SBIPG", "DBTPG"]:
                clean = re.sub(r"\b" + p + r"\b", "", clean, flags=re.IGNORECASE)

            # Remove Ref if found
            if info["ref"]:
                clean = clean.replace(info["ref"], "")

            # Heuristic: Last word is often location
            words = clean.split()
            if words:
                info["location"] = words[-1]
                # Merchant is the rest, but remove location if it looks like a city
                # For now, just take the rest as merchant
                merchant_parts = words[:-1]

                # Cleanup merchant (remove 17Pho* or 36Swiggy junk)
                merchant_str = " ".join(merchant_parts)
                # Rule 1: Remove "17Pho*" style (digits...*)
                merchant_str = re.sub(r"^\d+[^*]*\*", "", merchant_str)
                # Rule 2: Remove leading digits (e.g. 36Swiggy -> Swiggy)
                merchant_str = re.sub(r"^\d+", "", merchant_str)
                # Rule 3: Remove prefixes ending in * (e.g. Pho* -> PhonePe)
                merchant_str = re.sub(r"^[A-Za-z0-9]+\*", "", merchant_str)
                # Rule 4: Remove prefixes ending in _ (e.g. Paytm_ -> Paytm)
                # But wait, Paytm_ONE97... -> ONE97... maybe better?
                # or just replace _ with space?
                merchant_str = re.sub(r"^[A-Za-z0-9]+_", "", merchant_str)

                info["entity"] = merchant_str.strip()

                # Special case: If entity is empty, maybe location was actually the merchant?
                if not info["entity"]:
                    info["entity"] = info["location"]
                    info["location"] = ""
            return info

        # 3. ATM Withdrawals
        # Pattern: ATM WDL ATM CASH [ID] [Location]
        # Example: ATM WDL ATM CASH 1957 SP OFFICE DARGAMITTA, NELLORE
        if "ATM WDL" in text:
            info["method"] = "ATM"
            # Remove prefixes
            clean = re.sub(r"ATM WDL|ATM CASH", "", text).strip()
            # First part usually ID, rest location
            # Example: 1957 SP OFFICE... -> ID: 1957 SP, Loc: OFFICE...
            # Hard to split exactly without more examples.
            # Let's assume ID is first 2 words if they are distinct?
            # Or just Regex for ID?

            # Let's try to find the ID (usually digits or alphanumeric)
            # Maybe just take strict "everything is location" except first token?
            match = re.match(r"^([A-Za-z0-9]+)\s+(.*)", clean)
            if match:
                # Naive split
                # User example: 1957 SP OFFICE...
                # 1957 is likely ID-part. SP is likely ID-part.
                # Let's just put everything in location for now, or try to be smart.
                pass

            # Improved logic based on example "1957 SP OFFICE DARGAMITTA"
            # ID seems to be "1957 SP"
            # Let's extract generic "Location" as the tail.
            info["location"] = clean  # Fallback

            # Try to identify ID pattern?
            # Let's just say everything after "ATM CASH" is useful details.
            # User said: "[ATM ID] [Location]"
            # We'll map "1957 SP" to Ref?

            # Let's try to capture digits at start as Ref
            ref_match = re.match(r"^(\d+\s*[A-Z]*)", clean)
            if ref_match:
                info["ref"] = ref_match.group(1).strip()
                info["location"] = clean.replace(info["ref"], "").strip()

            return info

        # 4. Internet Banking (INB)
        # Pattern: WDL TFR INB [Merchant/Purpose] [Ref] AT [Branch]
        # Example: WDL TFR INB Amazon Seller Services Pv...
        if "INB" in text:
            info["method"] = "INB"
            # Remove WDL TFR INB
            clean = re.sub(r"WDL|TFR|INB", "", text).strip()
            # Remove AT ... at end
            clean = re.sub(r"\bAT \d+.*", "", clean).strip()

            info["entity"] = clean.strip()
            return info

        # 5. Cash Deposits
        # Pattern 1: CASH DEPOSIT SELF AT ...
        # Pattern 2: CEMTEX DEP ...
        if "CASH DEPOSIT" in text or "CEMTEX" in text:
            info["method"] = "CASH"
            info["type"] = "DEPOSIT"

            if "CASH DEPOSIT" in text:
                # Extract Location (AT ...)
                loc_match = re.search(r"AT (.*)", text)
                if loc_match:
                    info["location"] = loc_match.group(1).strip()

            return info

        # 6. NEFT / RTGS Transfers
        # Pattern: NEFT/ref/name/bank/... or RTGS/ref/name/bank/...
        neft_match = re.search(r"(?:NEFT|RTGS)/([^/]+)/([^/]+)/([^/]+)", text)
        if neft_match:
            info["method"] = "NEFT" if "NEFT" in text else "RTGS"
            info["ref"] = neft_match.group(1).strip()
            info["entity"] = neft_match.group(2).strip()
            info["meta"] = {"bank": neft_match.group(3).strip()}
            info["type"] = "CREDIT" if "DEP" in text or "CR" in text else "DEBIT"
            return info

        # 7. Generic Bank Transfers (DEP TFR / WDL TFR without UPI or INB)
        # Example: DEP TFR SBIY2260332207597607O6924 M Transfer to Family or OF Mr MEERA MOHIDDIN MO
        # Example: WDL TFR 0010604296427 OF Mr HASSAN MOHIDDIN AT 04413 PBB NELLORE
        if "TFR" in text and "UPI" not in text and "INB" not in text:
            info["method"] = "TRANSFER"
            # Extract person name from "OF Mr/Mrs/Ms/Miss NAME" pattern
            name_match = re.search(
                r"(?:OF|of)\s+(?:Mr|Mrs|Ms|Miss|MR|MRS|MS)?\s*\.?\s*([A-Z][A-Z\s]+)",
                text,
            )
            if name_match:
                raw_name = name_match.group(1).strip()
                # Clean trailing noise (e.g. "MO", "AT", single letters)
                raw_name = re.sub(r"\s+(?:MO|AT|M)\s*$", "", raw_name).strip()
                info["entity"] = raw_name
            # Extract location from "AT XXXXX PLACE" pattern
            loc_match = re.search(r"\bAT\s+(\d{4,}\s+.*)", text)
            if loc_match:
                info["location"] = loc_match.group(1).strip()
            info["type"] = "CREDIT" if "DEP" in text else "DEBIT"
            return info

        return info

    def get_cleaning_diff(self):
        """Returns list of (Raw, Cleaned) tuples for inspection."""
        if self.df is None or "Cleaned_Details" not in self.df.columns:
            return []
        return list(zip(self.df["Details"], self.df["Cleaned_Details"]))


class InverseFrequencyMasking:
    def __init__(self, texts, min_drop_prob=0.1, max_drop_prob=0.9):
        from collections import Counter

        self.min_drop_prob = min_drop_prob
        self.max_drop_prob = max_drop_prob

        # Calculate word counts
        all_words = []
        for text in texts:
            # Simple tokenization by splitting on space
            words = str(text).split()
            all_words.extend(words)

        self.word_counts = Counter(all_words)
        total_words = sum(self.word_counts.values())

        # Calculate drop probabilities
        # High frequency -> High drop prob
        self.drop_probs = {}
        if total_words > 0:
            max_count = max(self.word_counts.values())
            for word, count in self.word_counts.items():
                if max_count == 1:
                    prob = min_drop_prob
                else:
                    # Scale count to [0, 1]
                    norm_freq = count / max_count
                    # Map to [min_prob, max_prob]
                    prob = min_drop_prob + (max_drop_prob - min_drop_prob) * norm_freq
                self.drop_probs[word] = prob

    def augment(self, text):
        import numpy as np

        words = str(text).split()
        if not words:
            return ""

        new_words = []
        for word in words:
            prob = self.drop_probs.get(word, self.min_drop_prob)
            if np.random.rand() > prob:
                new_words.append(word)

        # If we dropped everything, keep at least one random word to avoid empty string
        if not new_words and words:
            new_words.append(np.random.choice(words))

        return " ".join(new_words)
