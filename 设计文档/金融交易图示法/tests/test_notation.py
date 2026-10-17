"""Behavioral checks for unsafe or ambiguous FTN models."""

import copy
import importlib.util
import json
import unittest
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "ftn_validate", ROOT / "tools" / "validate.py"
)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def load(name="payout"):
    return json.loads((ROOT / "examples" / f"{name}.json").read_text())


class NotationTests(unittest.TestCase):
    def assert_invalid(self, model, marker):
        self.assertTrue(
            any(marker in err for err in validator.validate(model)),
            validator.validate(model),
        )

    def test_all_complete_examples_and_unknown_scope(self):
        for path in sorted((ROOT / "examples").glob("*.json")):
            with self.subTest(path=path.name):
                model = json.loads(path.read_text())
                self.assertEqual([], validator.validate(model))
                expected = "partial" if path.stem == "unknown" else "completed"
                self.assertEqual(
                    {model["operations"][0]["id"]: expected}, validator.outcomes(model)
                )

    def test_unknown_is_not_failure_and_cannot_enable_retry(self):
        model = load("retry")
        model["legs"][2].update(state=None, knowledge="unknown")
        self.assert_invalid(model, "R11")
        self.assert_invalid(model, "R10")

    def test_repeated_active_payment_effect_is_rejected(self):
        model = load()
        duplicate = copy.deepcopy(model["legs"][-1])
        duplicate["id"] = "F_DUP"
        model["legs"].append(duplicate)
        self.assert_invalid(model, "R10")

    def test_atomic_batch_cannot_be_partially_posted(self):
        model = load()
        model["legs"][1]["state"] = "planned"
        self.assert_invalid(model, "R06")

    def test_same_time_does_not_replace_same_commit(self):
        model = load()
        model["legs"][1]["commit_ref"] = "different-commit"
        self.assert_invalid(model, "R06")

    def test_currency_and_ledger_types_are_not_inferred(self):
        model = load()
        model["accounts"][1]["currency"] = "AUD"
        model["currencies"]["AUD"] = 2
        self.assert_invalid(model, "R03")
        model = load()
        model["legs"][0]["to"] = "A_PROVIDER_BANK"
        self.assert_invalid(model, "R03")

    def test_confirmation_requires_evidence(self):
        model = load()
        model["legs"][-1]["evidence"] = []
        self.assert_invalid(model, "SCHEMA")

    def test_only_mutating_requests_require_idempotency_keys(self):
        model = load("addon")
        self.assertIsNone(model["messages"][0]["idempotency_key"])
        self.assertEqual([], validator.validate(model))
        model["messages"][1]["idempotency_key"] = None
        self.assert_invalid(model, "SCHEMA")
        model = load()
        model["messages"][0]["attempt_id"] = None
        self.assert_invalid(model, "SCHEMA")

    def test_finality_requires_specific_rule(self):
        model = load()
        model["legs"][-1]["finality"] = "final"
        self.assert_invalid(model, "R09")

    def test_money_must_be_positive_integral_minor_units(self):
        for amount in (-100, 0, 1.5, 100.0):
            with self.subTest(amount=amount):
                model = load()
                model["legs"][0]["money"]["minor"] = amount
                self.assert_invalid(model, "R02" if amount == 100.0 else "SCHEMA")

    def test_duplicate_ids_and_broken_completion_are_rejected(self):
        model = load()
        model["accounts"][1]["id"] = "A_WALLET"
        self.assert_invalid(model, "R01")
        model = load()
        model["operations"][0]["required_legs"] = ["missing"]
        self.assert_invalid(model, "R14")

    def test_returns_are_cumulative_and_successful_history_is_preserved(self):
        model = load()
        for idx in range(2):
            leg = copy.deepcopy(model["legs"][-1] if idx == 0 else model["legs"][-2])
            leg.update(id=f"F_RETURN{idx}", effect_ref=f"E_RETURN{idx}")
            leg["from"], leg["to"] = "A_BENE_BANK", "A_PROVIDER_BANK"
            leg["money"]["minor"] = 6000
            model["legs"].append(leg)
            model["relations"].append(
                {"type": "returns", "from_ref": leg["id"], "to_ref": "F1"}
            )
            if idx == 0:
                self.assertEqual([], validator.validate(model))
        self.assert_invalid(model, "R13")
        self.assertEqual("confirmed", model["legs"][2]["state"])

    def test_retry_cannot_change_amount(self):
        model = load("retry")
        model["legs"][-1]["money"]["minor"] = 9999
        self.assert_invalid(model, "R11")

    def test_fee_and_fx_numbers_in_document(self):
        d = Decimal
        round2 = lambda x: x.quantize(d("0.01"), rounding=ROUND_HALF_UP)
        principal = d("990.10")
        self.assertEqual(d("1000.00"), principal + round2(principal * d("0.01")))
        self.assertEqual(d("99.01"), round2(principal * d("0.1")))
        net = d("99.01")
        self.assertEqual(d("100.00"), net + round2(net * d("0.01")))
        recovered = round2(d("180") * d("0.4722"))
        self.assertEqual(d("85.00"), recovered)
        self.assertEqual(d("5.00"), d("90.00") - recovered)


if __name__ == "__main__":
    unittest.main()
