# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import _, api, models
from odoo.exceptions import ValidationError
from odoo.tools import str2bool

from odoo.addons.base_iban.models.res_partner_bank import validate_iban

_logger = logging.getLogger(__name__)


class ResPartnerBank(models.Model):
    """
    Extend res.partner.bank to add configurable IBAN validation.

    Adds country-specific IBAN validation enforcement based on system parameters.
    """

    _inherit = "res.partner.bank"

    def _get_validation_config(self):
        """
        Load validation configuration once to avoid repeated lookups.

        Returns:
            dict: Configuration dictionary with keys:
                - enforce (bool): Whether to enforce validation
                - bank_country_ids (list): List of bank country IDs to enforce
                - partner_country_ids (list): List of partner country IDs to enforce
        """
        ICP = self.env["ir.config_parameter"].sudo()
        Settings = self.env["res.config.settings"]

        return {
            "enforce": str2bool(
                ICP.get_param(
                    "partner_enforce_iban_validation.raise_exception", "false"
                )
            ),
            "bank_country_ids": Settings._load_iban_check_country_ids(
                self.env, "bank_country_ids"
            ),
            "partner_country_ids": Settings._load_iban_check_country_ids(
                self.env, "partner_country_ids"
            ),
        }

    @api.constrains("acc_number", "partner_id", "bank_id")
    def _check_iban(self):
        """
        Validate IBAN with configurable enforcement.

        Applies IBAN validation based on system configuration:
        - Skips validation if skip_iban_validation context is set
        - Validates only records matching country filters
        - Delegates to parent validation for non-enforced records

        Raises:
            ValidationError: If IBAN is invalid and enforcement is enabled
        """
        if self.env.context.get("skip_iban_validation"):
            return

        config = self._get_validation_config()

        records_to_enforce = self.env["res.partner.bank"]
        records_to_delegate = self.env["res.partner.bank"]

        for record in self:
            if not record.acc_number:
                continue
            if record._should_validate(config):
                records_to_enforce |= record
            else:
                records_to_delegate |= record

        # Validate enforced records
        for record in records_to_enforce:
            try:
                validate_iban(record.acc_number)
            except ValidationError as err:
                raise ValidationError(
                    _(
                        "The IBAN %(iban)s is invalid. Please correct it "
                        "or disable validation in Settings.",
                        iban=record.acc_number,
                    )
                ) from err

        # Delegate remaining records
        if records_to_delegate:
            super(ResPartnerBank, records_to_delegate)._check_iban()

        return

    def _should_validate(self, config):
        """
        Check if validation should apply to this record (no config loading).

        Args:
            config (dict): Validation configuration from _get_validation_config()

        Returns:
            bool: True if validation should be enforced for this record
        """
        self.ensure_one()

        if not config["enforce"]:
            return False

        bank_country_ids = config["bank_country_ids"]
        partner_country_ids = config["partner_country_ids"]

        # No filters → enforce for all
        if not bank_country_ids and not partner_country_ids:
            return True

        # Enforce by bank country
        if (
            bank_country_ids
            and self.bank_id
            and self.bank_id.country
            and self.bank_id.country.id in bank_country_ids
        ):
            return True

        # Enforce by partner country
        if (
            partner_country_ids
            and self.partner_id
            and self.partner_id.country_id
            and self.partner_id.country_id.id in partner_country_ids
        ):
            return True

        return False
