# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestPartnerEnforceIban(TransactionCase):
    """Test enforcing IBAN validation for partner bank accounts."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Bank = cls.env["res.partner.bank"]
        cls.Config = cls.env["ir.config_parameter"].sudo()
        cls.Country = cls.env["res.country"]

        # Test data
        cls.partner = cls.env["res.partner"].create({"name": "Test Partner"})
        cls.partner_us = cls.env["res.partner"].create(
            {"name": "US Partner", "country_id": cls.env.ref("base.us").id}
        )
        cls.partner_de = cls.env["res.partner"].create(
            {"name": "German Partner", "country_id": cls.env.ref("base.de").id}
        )

        # Test bank with country
        cls.bank_de = cls.env["res.bank"].create(
            {
                "name": "German Bank",
                "bic": "DEUTDEFF",
                "country": cls.env.ref("base.de").id,
            }
        )

        # Test IBANs
        cls.valid_iban = "GB82WEST12345698765432"  # UK IBAN
        cls.valid_iban_de = "DE89370400440532013000"  # German IBAN
        cls.invalid_iban = "INVALID123"

    def _set_enforcement(self, value):
        """Enable or disable strict IBAN validation."""
        self.Config.set_param(
            "partner_enforce_iban_validation.raise_exception", str(value).lower()
        )

    def _set_country_restrictions(
        self, bank_country_ids=None, partner_country_ids=None
    ):
        """Set country restrictions for validation."""
        if bank_country_ids is not None:
            country_str = ",".join(str(x) for x in bank_country_ids)
            self.Config.set_param(
                "partner_enforce_iban_validation.bank_country_ids",
                country_str,
            )
        if partner_country_ids is not None:
            country_str = ",".join(str(x) for x in partner_country_ids)
            self.Config.set_param(
                "partner_enforce_iban_validation.partner_country_ids",
                country_str,
            )

    def test_01_create_valid_iban_with_enforcement(self):
        """Should create record successfully if IBAN is valid and enforcement is ON."""
        self._set_enforcement(True)
        self._set_country_restrictions(bank_country_ids=[], partner_country_ids=[])
        bank = self.Bank.create(
            {
                "acc_number": self.valid_iban,
                "partner_id": self.partner.id,
            }
        )
        self.assertEqual(bank.acc_number.replace(" ", ""), self.valid_iban)

    def test_02_create_invalid_iban_with_enforcement(self):
        """Should raise ValidationError if IBAN is invalid and enforcement is ON."""
        self._set_enforcement(True)
        self._set_country_restrictions(bank_country_ids=[], partner_country_ids=[])
        with self.assertRaises(ValidationError):
            self.Bank.create(
                {
                    "acc_number": self.invalid_iban,
                    "partner_id": self.partner.id,
                }
            )

    def test_03_create_invalid_iban_without_enforcement(self):
        """Should NOT raise error if enforcement is OFF."""
        self._set_enforcement(False)
        self._set_country_restrictions(bank_country_ids=[], partner_country_ids=[])
        bank = self.Bank.create(
            {
                "acc_number": self.invalid_iban,
                "partner_id": self.partner.id,
            }
        )
        self.assertTrue(bank)

    def test_04_skip_validation_via_context(self):
        """Should skip validation if skip_iban_validation=True in context."""
        self._set_enforcement(True)
        self._set_country_restrictions(bank_country_ids=[], partner_country_ids=[])
        bank = self.Bank.with_context(skip_iban_validation=True).create(
            {
                "acc_number": self.invalid_iban,
                "partner_id": self.partner.id,
            }
        )
        self.assertTrue(bank)

    def test_05_country_filter_bank_country(self):
        """Should validate only when bank country matches."""
        self._set_enforcement(True)
        de_country_id = self.env.ref("base.de").id
        self._set_country_restrictions(bank_country_ids=[de_country_id])

        bank = self.Bank.create(
            {
                "acc_number": self.valid_iban_de,
                "bank_id": self.bank_de.id,
                "partner_id": self.partner.id,
            }
        )
        self.assertTrue(bank)

        bank2 = self.Bank.create(
            {
                "acc_number": self.invalid_iban,
                "partner_id": self.partner.id,
            }
        )
        self.assertTrue(bank2)

    def test_06_country_filter_partner_country(self):
        """Should validate only when partner country matches."""
        self._set_enforcement(True)
        de_country_id = self.env.ref("base.de").id
        self._set_country_restrictions(partner_country_ids=[de_country_id])

        with self.assertRaises(ValidationError):
            self.Bank.create(
                {
                    "acc_number": self.invalid_iban,
                    "partner_id": self.partner_de.id,
                }
            )

        bank = self.Bank.create(
            {
                "acc_number": self.invalid_iban,
                "partner_id": self.partner_us.id,
            }
        )
        self.assertTrue(bank)

    def test_07_country_filter_both_countries(self):
        """Should validate when either bank OR partner country matches."""
        self._set_enforcement(True)
        de_country_id = self.env.ref("base.de").id
        self._set_country_restrictions(
            bank_country_ids=[de_country_id], partner_country_ids=[de_country_id]
        )

        bank1 = self.Bank.create(
            {
                "acc_number": self.valid_iban_de,
                "bank_id": self.bank_de.id,
                "partner_id": self.partner_us.id,
            }
        )
        self.assertTrue(bank1)

        bank2 = self.Bank.create(
            {
                "acc_number": self.valid_iban_de,
                "partner_id": self.partner_de.id,
            }
        )
        self.assertTrue(bank2)

    def test_08_no_country_restrictions(self):
        """Should validate all when no country restrictions."""
        self._set_enforcement(True)
        self._set_country_restrictions(bank_country_ids=[], partner_country_ids=[])

        with self.assertRaises(ValidationError):
            self.Bank.create(
                {
                    "acc_number": self.invalid_iban,
                    "partner_id": self.partner.id,
                }
            )

    def test_09_empty_country_restrictions(self):
        """Should validate all when country restrictions are empty strings."""
        self._set_enforcement(True)
        self.Config.set_param("partner_enforce_iban_validation.bank_country_ids", "")
        self.Config.set_param("partner_enforce_iban_validation.partner_country_ids", "")

        with self.assertRaises(ValidationError):
            self.Bank.create(
                {
                    "acc_number": self.invalid_iban,
                    "partner_id": self.partner.id,
                }
            )

    def test_10_write_invalid_iban_with_enforcement(self):
        """Should raise ValidationError when updating to invalid IBAN."""
        self._set_enforcement(True)
        self._set_country_restrictions(bank_country_ids=[], partner_country_ids=[])

        bank = self.Bank.create(
            {
                "acc_number": self.valid_iban,
                "partner_id": self.partner.id,
            }
        )

        with self.assertRaises(ValidationError):
            bank.write({"acc_number": self.invalid_iban})

    def test_11_write_valid_iban_with_enforcement(self):
        """Should successfully update to valid IBAN."""
        self._set_enforcement(True)
        bank = self.Bank.create(
            {
                "acc_number": self.valid_iban,
                "partner_id": self.partner.id,
            }
        )

        bank.write({"acc_number": self.valid_iban_de})
        self.assertEqual(bank.acc_number.replace(" ", ""), self.valid_iban_de)

    def test_12_write_with_country_filter(self):
        """Should validate on write when country filters match."""
        self._set_enforcement(True)
        de_country_id = self.env.ref("base.de").id
        self._set_country_restrictions(partner_country_ids=[de_country_id])

        bank = self.Bank.create(
            {
                "acc_number": self.valid_iban,
                "partner_id": self.partner_de.id,
            }
        )

        with self.assertRaises(ValidationError):
            bank.write({"acc_number": self.invalid_iban})
