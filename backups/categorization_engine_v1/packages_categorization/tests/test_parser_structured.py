from packages.categorization.data_loader import BankStatementParser

# Examples provided by user
UPI_OUTGOING = "WDL TFR UPI/DR/931523643407/SHAIK YA/SBIN/skya smeen1/Paym"
UPI_INCOMING = "DEP TFR UPI/CR/320278741671/SHAIK YA/SBIN/skya smeen1/Paym"
POS_PURCHASE = "POS ATM PURCH OTHPG 3155010693 17Pho*PHONEPE RECHARGE BANGALORE"
ATM_WDL = "ATM WDL ATM CASH 1957 SP OFFICE DARGAMITTA, NELLORE"
INB_AMAZON = "WDL TFR INB Amazon Seller Services Pv"
INB_GIFT = "WDL TFR INB Gift to relatives / Friends"
CASH_DEP = "CASH DEPOSIT SELF AT 04413 PBB NELLORE"
CDM_DEP = "CEMTEX DEP 00000004413 0 40623"
# Bank transfer examples (user-reported: should extract "MEERA MOHIDDIN" as entity)
BANK_TRANSFER_IN = (
    "DEP TFR SBIY2260332207597607O6924 M Transfer to Family or OF Mr MEERA MOHIDDIN MO"
)
BANK_TRANSFER_OUT = "WDL TFR 0010604296427 OF Mr HASSAN MOHIDDIN AT 04413 PBB NELLORE"
NEFT_TRANSFER = "NEFT/N123456789/MEERA MOHIDDIN/SBI/HDFC"


class TestStructuredParsing:
    def test_extract_upi_outgoing(self):
        # We need to test the extraction logic directly, regardless of file input
        # We can simulate the `apply` call
        parser = BankStatementParser("dummy.xlsx")

        info = parser.extract_details(UPI_OUTGOING)
        assert info["method"] == "UPI"
        assert info["type"] == "DEBIT"  # derived from WDL or /DR
        assert info["ref"] == "931523643407"
        assert info["entity"] == "SHAIK YA"
        assert info["meta"] == {"upi_id": "skya smeen1", "bank": "SBIN", "app": "Paym"}

    def test_extract_upi_incoming(self):
        parser = BankStatementParser("dummy.xlsx")
        info = parser.extract_details(UPI_INCOMING)
        assert info["method"] == "UPI"
        assert info["type"] == "CREDIT"
        assert info["ref"] == "320278741671"
        assert info["entity"] == "SHAIK YA"

    def test_extract_pos_purchase(self):
        parser = BankStatementParser("dummy.xlsx")
        info = parser.extract_details(POS_PURCHASE)
        assert info["method"] == "POS"
        assert info["ref"] == "3155010693"
        assert info["entity"] == "PHONEPE RECHARGE"  # Extracted from 17Pho*...
        assert info["location"] == "BANGALORE"

    def test_extract_atm_wdl(self):
        parser = BankStatementParser("dummy.xlsx")
        info = parser.extract_details(ATM_WDL)
        assert info["method"] == "ATM"
        assert info["location"] == "OFFICE DARGAMITTA, NELLORE"
        assert info["ref"] == "1957 SP"

    def test_extract_inb(self):
        parser = BankStatementParser("dummy.xlsx")
        info = parser.extract_details(INB_AMAZON)
        assert info["method"] == "INB"
        assert info["entity"] == "Amazon Seller Services Pv"

    def test_extract_cash_deposit(self):
        parser = BankStatementParser("dummy.xlsx")
        info = parser.extract_details(CASH_DEP)
        assert info["method"] == "CASH"
        assert info["type"] == "DEPOSIT"  # derived from DEP/CASH DEPOSIT
        assert info["location"] == "04413 PBB NELLORE"

    def test_extract_bank_transfer_incoming(self):
        """DEP TFR with 'OF Mr NAME' should extract method=TRANSFER and entity=NAME."""
        parser = BankStatementParser("dummy.xlsx")
        info = parser.extract_details(BANK_TRANSFER_IN)
        assert info["method"] == "TRANSFER", f"Expected TRANSFER, got {info['method']}"
        assert (
            info["entity"] == "MEERA MOHIDDIN"
        ), f"Expected 'MEERA MOHIDDIN', got '{info['entity']}'"
        assert info["type"] == "CREDIT"  # DEP = incoming

    def test_extract_bank_transfer_outgoing(self):
        """WDL TFR with 'OF Mr NAME' should extract method=TRANSFER and entity=NAME."""
        parser = BankStatementParser("dummy.xlsx")
        info = parser.extract_details(BANK_TRANSFER_OUT)
        assert info["method"] == "TRANSFER", f"Expected TRANSFER, got {info['method']}"
        assert (
            info["entity"] == "HASSAN MOHIDDIN"
        ), f"Expected 'HASSAN MOHIDDIN', got '{info['entity']}'"
        assert info["type"] == "DEBIT"  # WDL = outgoing

    def test_extract_neft_transfer(self):
        """NEFT/ref/name/bank pattern should extract method=NEFT and entity=NAME."""
        parser = BankStatementParser("dummy.xlsx")
        info = parser.extract_details(NEFT_TRANSFER)
        assert info["method"] == "NEFT", f"Expected NEFT, got {info['method']}"
        assert (
            info["entity"] == "MEERA MOHIDDIN"
        ), f"Expected 'MEERA MOHIDDIN', got '{info['entity']}'"
