"""Business consistency checks and regression cases for FTN 1.1 examples."""

import copy
import importlib.util
import json
import re
import subprocess
import sys
import unittest
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ftn_validate", ROOT / "tools" / "validate.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def load(stem="payout"):
    return json.loads((ROOT / "examples" / f"{stem}.json").read_text())


def net_changes(model):
    net = defaultdict(int)
    for changes in validator.balance_changes(model).values():
        for aid, value in changes.items():
            net[aid] += value
    return net


class BusinessNotationTests(unittest.TestCase):
    def assert_invalid(self, model, rule):
        errors = validator.validate(model)
        self.assertTrue(any(e.startswith(rule) for e in errors), errors)

    def test_complete_business_examples_and_cli(self):
        examples = sorted((ROOT / "examples").glob("*.json"))
        self.assertEqual({"payout.json", "refund.json"}, {p.name for p in examples})
        for path in examples:
            self.assertEqual([], validator.validate(json.loads(path.read_text())))
        result = subprocess.run([sys.executable, str(ROOT / "tools" / "validate.py"),
                                *map(str, examples)], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(2, result.stdout.count("OK"))

    def test_customer_and_psp_cost_are_separate(self):
        model = load()
        customer = [r for r in model["records"] if r["perspective"] == "客户"]
        self.assertEqual(101500, sum(r["money"]["minor"] for r in customer))
        self.assertEqual(1000, model["components"]["channel_fee"]["minor"])
        net = net_changes(model)
        self.assertEqual(-101500, net["A_AVAIL"])
        self.assertEqual(-100000, net["A_BANK_C"])
        self.assertEqual(-1000, net["A_BANK_O"])
        self.assertEqual(1500, net["A_REVENUE"])
        self.assertEqual(1000, net["A_COST"])
        self.assertEqual(0, net["A_FROZEN"])
        self.assertEqual(0, net["A_CHANNEL"])

    def test_full_refund_restores_all_shown_accounts(self):
        combined = net_changes(load())
        for aid, value in net_changes(load("refund")).items():
            combined[aid] += value
        self.assertTrue(all(v == 0 for v in combined.values()), combined)

    def test_channel_refund_is_independent_of_customer_refund(self):
        model = load("refund")
        events = {e["id"]: e for e in model["events"]}
        self.assertEqual(["R1"], events["R3"]["after"])
        self.assertEqual(["R3"], events["R4"]["after"])
        customer = [r for r in model["records"] if r["perspective"] == "客户"]
        self.assertEqual(101500, sum(r["money"]["minor"] for r in customer))

    def test_wrong_graph_amount_fails_even_if_journal_balances(self):
        model = load()
        model["flows"][2]["money"]["minor"] -= 100
        self.assert_invalid(model, "R06")

    def test_wrong_bank_funding_account_is_detected(self):
        model = load()
        model["flows"][-1]["from"] = "A_BANK_C"
        self.assert_invalid(model, "R07")

    def test_channel_ledger_is_not_a_cash_destination(self):
        model = load()
        model["flows"][1]["to"] = "A_CHANNEL"
        self.assert_invalid(model, "R03")

    def test_actual_funding_is_not_a_local_balance_allocation(self):
        model = load()
        model["flows"][1].update(kind="L", to="A_CHANNEL")
        self.assert_invalid(model, "R06")

    def test_unbalanced_refund_original_typo_is_rejected(self):
        model = load("refund")
        model["journals"][0]["rows"][1]["money"]["minor"] = 101000
        self.assert_invalid(model, "R05")

    def test_double_bank_receipt_is_rejected(self):
        model = load("refund")
        model["journals"][2]["rows"][0]["account_ref"] = "A_BANK_C"
        self.assert_invalid(model, "R06")

    def test_broken_references_and_duplicate_ids(self):
        model = load()
        model["accounts"][1]["id"] = model["accounts"][0]["id"]
        self.assert_invalid(model, "R01")
        model = load()
        model["flows"][0]["event_ref"] = "missing"
        self.assert_invalid(model, "R01")

    def test_business_prerequisites_cannot_cycle(self):
        model = load()
        model["events"][0]["after"] = ["E3"]
        self.assert_invalid(model, "R08")
        model = load()
        model["events"][0]["after"] = ["missing"]
        self.assert_invalid(model, "R08")

    def test_money_is_positive_integer_minor_units(self):
        for value in (0, -100, 0.5, 100.0, True):
            model = load()
            model["flows"][0]["money"]["minor"] = value
            with self.subTest(value=value):
                self.assertTrue(validator.validate(model))
        model = load()
        model["flows"][0]["money"]["currency"] = "EUR"
        self.assert_invalid(model, "R02")

    def test_currency_and_entity_boundaries(self):
        model = load()
        model["journals"][0]["rows"][0]["money"]["currency"] = "EUR"
        model["currency_scale"]["EUR"] = 2
        self.assert_invalid(model, "R04")
        model = load()
        model["journals"][0]["rows"][0]["account_ref"] = "X_IBC"
        self.assert_invalid(model, "R04")

    def test_records_must_map_to_same_order(self):
        model = load("refund")
        model["records"][0]["order_ref"] = "P00001"
        self.assert_invalid(model, "R09")

    def test_refund_requires_origin_and_component_limits(self):
        model = load("refund")
        model["refund"] = None
        self.assert_invalid(model, "R10")
        model = load("refund")
        model["refund"]["caps"][0]["prior_minor"] = 1
        self.assert_invalid(model, "R10")
        model = load("refund")
        model["refund"]["caps"].pop()
        self.assert_invalid(model, "R10")

    def test_refund_cannot_reuse_one_flow_for_two_components(self):
        model = load("refund")
        model["refund"]["caps"][1]["flow_refs"] = ["L_R1"]
        self.assert_invalid(model, "R10")

    def test_partial_refund_cap_is_checked_without_assuming_history(self):
        model = load("refund")
        cap = model["refund"]["caps"][0]
        model["components"]["principal"]["minor"] = 40000
        model["flows"][2]["money"]["minor"] = 40000
        cap["prior_minor"] = 60000
        errors = validator.validate(model)
        self.assertFalse(any(e.startswith("R10") for e in errors), errors)
        cap["prior_minor"] += 1
        self.assert_invalid(model, "R10")

    def test_natural_balance_uses_account_nature(self):
        model = load()
        changes = validator.balance_changes(model)
        self.assertEqual(-100000, changes["E2"]["A_BANK_C"])
        self.assertEqual(-100000, changes["E2"]["A_CHANNEL"])
        self.assertEqual(100000, changes["E3"]["A_CHANNEL"])
        self.assertEqual(1500, changes["E3"]["A_REVENUE"])
        refund = validator.balance_changes(load("refund"))
        self.assertEqual(-1000, refund["R2"]["A_COST"])
        self.assertEqual(-1500, refund["R3"]["A_REVENUE"])

    def test_document_journal_amounts_and_event_mapping_match_models(self):
        text = (ROOT / "规范.md").read_text()
        tables = {}
        for line in text.splitlines():
            if re.match(r"\| (JE|JR)\d+ /", line):
                cells = [c.strip() for c in line.strip("|").split("|")]
                tables[cells[0]] = cells[1:]
        for stem in ("payout", "refund"):
            for journal in load(stem)["journals"]:
                key = journal["id"] + " / " + journal["event_ref"]
                self.assertIn(key, tables)
                for index, side in enumerate(("DR", "CR")):
                    amounts = [int(v.replace(",", "")) *
                               100 for v in re.findall(r" ([\d,]+)(?=；|$)", tables[key][index])]
                    expected = [r["money"]["minor"] for r in journal["rows"] if r["side"] == side]
                    self.assertEqual(expected, amounts, key + " " + side)

    def test_generated_diagrams_html_and_current_material_are_consistent(self):
        for stem, figure in (("payout", "03-payout"), ("refund", "04-refund")):
            model = load(stem)
            svg = ElementTree.parse(ROOT / "figures" / f"{figure}.svg")
            text = " ".join(svg.getroot().itertext())
            page = (ROOT / "examples" / f"{stem}.html").read_text()
            for j in model["journals"]:
                self.assertIn(j["id"] + " / " + j["event_ref"], text)
                self.assertIn(j["id"] + " / " + j["event_ref"], page)
            for flow in model["flows"]:
                self.assertIn(flow["id"] + " / " + flow["event_ref"], text)
            self.assertIn("viewBox=", page)
            self.assertIn('href="' + ("refund" if stem == "payout" else "payout") + '.html"', page)
        self.assertEqual(5, len(list((ROOT / "figures").glob("*.svg"))))
        self.assertNotIn('"attempt_id"', (ROOT / "schema.json").read_text())

    def test_single_journal_cannot_mix_currencies(self):
        model = load()
        model["currency_scale"]["EUR"] = 2
        for source, aid in ((model["accounts"][3], "A_EUR_BANK"),
                            (model["accounts"][5], "A_EUR_CHANNEL")):
            account = copy.deepcopy(source)
            account.update(id=aid, currency="EUR")
            model["accounts"].append(account)
        model["journals"][1]["rows"].extend([
            {"account_ref": "A_EUR_CHANNEL", "side": "DR", "money": {"currency": "EUR", "minor": 100}},
            {"account_ref": "A_EUR_BANK", "side": "CR", "money": {"currency": "EUR", "minor": 100}},
        ])
        self.assert_invalid(model, "R04")

    def test_document_balance_summary_matches_business_data(self):
        section = (ROOT / "规范.md").read_text().split("## 6.", 1)[1].split("## 7.", 1)[0]
        names = {
            "客户可用": "A_AVAIL",
            "客户冻结": "A_FROZEN",
            "客户资金户": "A_BANK_C",
            "渠道往来": "A_CHANNEL",
            "服务费收入": "A_REVENUE",
            "渠道成本": "A_COST",
            "自有资金户": "A_BANK_O"}
        net = net_changes(load())
        seen = set()
        for line in section.splitlines():
            if not line.startswith("|"):
                continue
            cells = [v.strip() for v in line.strip("|").split("|")]
            if cells[0] in names:
                self.assertEqual(net[names[cells[0]]], int(cells[1].replace(",", "")) * 100)
                seen.add(cells[0])
        self.assertEqual(set(names), seen)

    def test_document_builder_compiles(self):
        for path in (ROOT / "tools").glob("*.py"):
            compile(path.read_text(), str(path), "exec")

    def test_validation_does_not_mutate_example(self):
        model = load()
        original = copy.deepcopy(model)
        validator.validate(model)
        self.assertEqual(original, model)


if __name__ == "__main__":
    unittest.main()
