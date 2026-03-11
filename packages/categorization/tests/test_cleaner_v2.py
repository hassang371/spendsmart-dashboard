"""Tests for the v2 text preprocessing pipeline.

Tests the multi-stage process_description() function that produces:
- raw: Original bank string (audit)
- informative: Human-readable sentence (model input)
- merchant_name: Clean name (UI display)
- transaction_type: Structural type tag
"""

from packages.categorization.cleaner import ProcessedText, process_description

# ── UPI Transfer Tests ──────────────────────────────────────────────────


class TestUPITransfers:
    """Test UPI debit and credit transaction parsing."""

    def test_upi_debit_extracts_person_name(self):
        raw = "WDL TFR   UPI/DR/459686795992/MUJITHABA/YESB/paytmqr6ar/Pay" "   0097696162090 AT 04413 PBB NELLORE"
        result = process_description(raw)
        assert isinstance(result, ProcessedText)
        assert result.merchant_name == "Mujithaba"
        assert "Transfer" in result.informative
        assert "Mujithaba" in result.informative
        assert result.transaction_type == "upi_transfer"

    def test_upi_credit_extracts_person_name(self):
        raw = "DEP TFR   UPI/CR/102094690998/LAKSHMI /KKBK/lak" "shmi.44/PAY   0097735162098 AT 04413 PBB NELLORE"
        result = process_description(raw)
        assert result.merchant_name == "Lakshmi"
        assert "Received" in result.informative
        assert "Lakshmi" in result.informative
        assert result.transaction_type == "upi_transfer"

    def test_upi_known_merchant_swiggy(self):
        raw = "WDL TFR   UPI/DR/123456789012/SWIGGY/HDFC/swiggy@hdfcbank/Pay" "   0097696162090 AT 04413 PBB NELLORE"
        result = process_description(raw)
        assert result.merchant_name == "Swiggy"
        assert "Transfer" in result.informative
        assert result.transaction_type == "upi_transfer"

    def test_upi_debit_with_truncated_name(self):
        raw = "WDL TFR   UPI/DR/195855869839/ADITYA F/YESB/BHA" "RATPE07/Pay   0097691162095 AT 04413 PBB NELLORE"
        result = process_description(raw)
        assert result.merchant_name == "Aditya F"
        assert result.transaction_type == "upi_transfer"


# ── POS Transaction Tests ───────────────────────────────────────────────


class TestPOSTransactions:
    """Test POS / Point of Sale transaction parsing."""

    def test_pos_purchase_extracts_merchant(self):
        raw = "POS ATM PURCH OTHPG 3155010693 17Pho*PHONEPE RECHARGE BANGALORE"
        result = process_description(raw)
        assert "PhonePe" in result.merchant_name or "PHONEPE" in result.merchant_name
        assert result.transaction_type == "pos_purchase"
        assert "Purchase" in result.informative


# ── ATM Withdrawal Tests ────────────────────────────────────────────────


class TestATMWithdrawals:
    """Test ATM withdrawal parsing."""

    def test_atm_withdrawal(self):
        raw = "ATM WDL  ATM CASH  S1CW0012 NELLORE"
        result = process_description(raw)
        assert result.merchant_name == "ATM Withdrawal"
        assert result.transaction_type == "atm_withdrawal"
        assert "ATM" in result.informative


# ── Internet Banking Tests ──────────────────────────────────────────────


class TestInternetBanking:
    """Test internet banking transfer parsing."""

    def test_inb_transfer(self):
        raw = "WDL TFR  INB  Gift Card Purchase... AT 04413 PBB NELLORE"
        result = process_description(raw)
        assert result.transaction_type == "internet_banking"
        assert "Transfer" in result.informative or "Banking" in result.informative


# ── Cash Deposit Tests ──────────────────────────────────────────────────


class TestCashDeposits:
    """Test cash deposit parsing."""

    def test_cash_deposit_self(self):
        raw = "CASH DEPOSIT SELF AT PBB NELLORE"
        result = process_description(raw)
        assert result.merchant_name == "Self Deposit"
        assert result.transaction_type == "cash_deposit"

    def test_cdm_deposit(self):
        raw = "CEMTEX DEP 1234567890 SELF DEPOSIT"
        result = process_description(raw)
        assert result.transaction_type == "cash_deposit"


# ── Interest / Bank Credit Tests ────────────────────────────────────────


class TestBankCredits:
    """Test interest and bank credit parsing."""

    def test_interest_credit(self):
        raw = " INTERES\n T CREDIT"
        result = process_description(raw)
        assert result.merchant_name == "Interest Credit"
        assert result.transaction_type == "bank_credit"


# ── Backward Compatibility ──────────────────────────────────────────────


class TestBackwardCompatibility:
    """Ensure clean_description() still works as a wrapper."""

    def test_clean_description_returns_string(self):
        from packages.categorization.cleaner import clean_description

        result = clean_description("WDL TFR   UPI/DR/123/TEST/SBIN/test@sbi/Pay AT BRANCH")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_empty_input(self):
        result = process_description("")
        assert result.raw == ""
        assert result.informative == ""
        assert result.merchant_name == ""

    def test_none_like_input(self):
        result = process_description("   ")
        assert result.informative == ""
