"""Check FTN 1.1 business diagrams, accounting projections and example records."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schema.json").read_text())


def balance_changes(model):
    """Natural-balance changes in minor units, grouped by business event/account."""
    accounts = {a["id"]: a for a in model["accounts"]}
    changes = defaultdict(lambda: defaultdict(int))
    for journal in model["journals"]:
        for row in journal["rows"]:
            nature = accounts[row["account_ref"]]["nature"]
            debit_positive = nature in {"asset", "expense"}
            sign = 1 if (row["side"] == "DR") == debit_positive else -1
            changes[journal["event_ref"]][row["account_ref"]] += (
                sign * row["money"]["minor"]
            )
    return changes


def validate(model):
    """Return violations without changing the model or consulting external records."""
    structural = sorted(
        Draft202012Validator(SCHEMA).iter_errors(model),
        key=lambda err: str(list(err.path)),
    )
    if structural:
        return [f"SCHEMA {list(err.path)}: {err.message}" for err in structural]
    errors = []

    def require(condition, rule, detail):
        if not condition:
            errors.append(f"{rule}: {detail}")

    def check_numbers(value):
        if isinstance(value, dict):
            if "minor" in value and "currency" in value:
                require(
                    type(value["minor"]) is int
                    and value["currency"] in model["currency_scale"],
                    "R02",
                    "money requires declared currency and integer JSON syntax",
                )
            if "prior_minor" in value:
                require(type(value["prior_minor"]) is int, "R02", "integer prior_minor")
            for child in value.values():
                check_numbers(child)
        elif isinstance(value, list):
            for child in value:
                check_numbers(child)

    check_numbers(model)
    for scale in model["currency_scale"].values():
        require(type(scale) is int, "R02", "integer currency scale")
    groups = (
        "parties",
        "accounts",
        "orders",
        "events",
        "flows",
        "information",
        "journals",
        "records")
    objects = [model["scenario"]] + [v for g in groups for v in model[g]]
    counts = Counter(v["id"] for v in objects)
    require(all(n == 1 for n in counts.values()), "R01", "duplicate object id")
    if errors:
        return errors
    parties = {v["id"]: v for v in model["parties"]}
    accounts = {v["id"]: v for v in model["accounts"]}
    orders = {v["id"]: v for v in model["orders"]}
    events = {v["id"]: v for v in model["events"]}
    flows = {v["id"]: v for v in model["flows"]}
    entity = model["scenario"]["entity"]
    require(entity in parties, "R01", "scenario entity")
    require(model["scenario"]["currency"] in model["currency_scale"], "R02", "scenario currency")
    codes = []
    for account in accounts.values():
        aid = account["id"]
        require(account["party"] in parties, "R01", aid + " party")
        require(account["bank"] is None or account["bank"] in parties, "R01", aid + " bank")
        require(account["currency"] in model["currency_scale"], "R02", aid + " currency")
        external = account["kind"] == "external"
        require(
            (account["nature"] == "external" and account["code"] is None)
            if external
            else (account["nature"] != "external" and account["code"] is not None and account["party"] == entity),
            "R03", aid + " account scope/nature/code",
        )
        if account["kind"] == "bank":
            require(account["nature"] == "asset" and account["bank"]
                    is not None, "R03", aid + " bank account")
        if not external:
            codes.append((account["party"], account["code"], account["currency"]))
    require(len(codes) == len(set(codes)), "R03", "duplicate account code in entity/currency")
    for order in orders.values():
        original = order["original_ref"]
        require(original is None or original in orders, "R01", order["id"] + " original order")
        require(
            (original is not None and original != order["id"] and orders.get(original, {}).get("type") == "payment")
            if order["type"] == "refund" else original is None,
            "R10", order["id"] + " refund origin",
        )
    for event in events.values():
        require(event["order_ref"] in orders, "R01", event["id"] + " order")
        require(all(e in events for e in event["after"]), "R08", event["id"] + " prerequisite")
    for flow in flows.values():
        require(flow["from"] in accounts and flow["to"]
                in accounts, "R01", flow["id"] + " endpoints")
        require(flow["event_ref"] in events, "R01", flow["id"] + " event")
    for info in model["information"]:
        require(info["from_party"] in parties and info["to_party"]
                in parties, "R01", info["id"] + " parties")
        require(info["event_ref"] in events, "R01", info["id"] + " event")
    for journal in model["journals"]:
        require(journal["event_ref"] in events, "R01", journal["id"] + " event")
        for row in journal["rows"]:
            require(row["account_ref"] in accounts, "R01", journal["id"] + " account")
    for record in model["records"]:
        require(record["order_ref"] in orders, "R01", record["id"] + " order")
        require(all(e in events for e in record["event_refs"]), "R01", record["id"] + " events")
    if any(e.startswith(("R01:", "R08:")) for e in errors):
        return errors

    visiting, visited = set(), set()

    def visit(eid):
        if eid in visiting:
            require(False, "R08", eid + " cyclic prerequisites")
            return
        if eid in visited:
            return
        visiting.add(eid)
        for parent in events[eid]["after"]:
            visit(parent)
        visiting.remove(eid)
        visited.add(eid)

    for eid in events:
        visit(eid)
    projections = {kind: defaultdict(lambda: defaultdict(int)) for kind in ("F", "L")}
    touched = {kind: defaultdict(set) for kind in ("F", "L")}
    for flow in flows.values():
        source, target = accounts[flow["from"]], accounts[flow["to"]]
        kind, eid, value = flow["kind"], flow["event_ref"], flow["money"]["minor"]
        require(source["id"] != target["id"], "R03", flow["id"] + " self flow")
        require(source["currency"] == target["currency"] == flow["money"]
                ["currency"], "R03", flow["id"] + " currency")
        if kind == "F":
            require(all(a["kind"] in {"bank", "external"} for a in (
                source, target)), "R03", flow["id"] + " funding endpoints")
        else:
            require(all(a["party"] == entity and a["kind"] != "external" for a in (
                source, target)), "R03", flow["id"] + " ledger endpoints")
        for a, sign in ((source, -1), (target, 1)):
            if kind == "L" or a["kind"] == "bank":
                projections[kind][eid][a["id"]] += sign * value
                touched[kind][eid].add(a["id"])
    for journal in model["journals"]:
        totals = defaultdict(int)
        for row in journal["rows"]:
            account = accounts[row["account_ref"]]
            require(account["party"] == entity and account["kind"]
                    != "external", "R04", journal["id"] + " entity")
            require(
                row["money"]["currency"] == account["currency"],
                "R04",
                journal["id"] +
                " currency")
            totals[row["money"]["currency"]] += row["money"]["minor"] * \
                (1 if row["side"] == "DR" else -1)
        require(len(totals) == 1, "R04", journal["id"] + " single-currency journal")
        require(all(t == 0 for t in totals.values()), "R05", journal["id"] + " unbalanced")
    changes = balance_changes(model)
    for kind, rule in (("L", "R06"), ("F", "R07")):
        for eid, account_ids in touched[kind].items():
            for aid in account_ids:
                require(projections[kind][eid][aid] == changes[eid][aid],
                        rule, f"{eid}/{aid} diagram and journal differ")
    for record in model["records"]:
        require(all(events[e]["order_ref"] == record["order_ref"]
                for e in record["event_refs"]), "R09", record["id"] + " order/event mapping")
    refund = model["refund"]
    refund_orders = {o["id"] for o in orders.values() if o["type"] == "refund"}
    require(bool(refund) == bool(refund_orders), "R10", "refund analysis requires origin and caps")
    if refund:
        order = orders.get(refund["order_ref"], {})
        require(refund_orders == {refund["order_ref"]} and order.get(
            "original_ref") == refund["original_order_ref"], "R10", "refund order/origin")
        require(refund["original_scenario_ref"] != model["scenario"]
                ["id"], "R10", "refund scenario cannot be its own origin")
        cap_names = [c["component"] for c in refund["caps"]]
        require(
            len(cap_names) == len(
                set(cap_names)) and set(cap_names) == set(
                model["components"]),
            "R10",
            "unique cap per declared refund component")
        all_refs = [f for c in refund["caps"] for f in c["flow_refs"]]
        require(len(all_refs) == len(set(all_refs)), "R10",
                "refund component flows must not overlap")
        for cap in refund["caps"]:
            refs = cap["flow_refs"]
            component = model["components"].get(cap["component"])
            valid = all(f in flows for f in refs) and component is not None
            require(valid, "R10", cap["component"] + " component/flow references")
            if not valid:
                continue
            value = sum(flows[f]["money"]["minor"] for f in refs)
            currency = cap["original_money"]["currency"]
            require(all(flows[f]["money"]["currency"] == currency and events[flows[f]["event_ref"]]["order_ref"] == refund["order_ref"]
                    for f in refs) and component["currency"] == currency, "R10", cap["component"] + " currency/order")
            require(
                value == component["minor"] and cap["prior_minor"] +
                value <= cap["original_money"]["minor"],
                "R10",
                cap["component"] +
                " refund amount/cap")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    failed = False
    for path in args.paths:
        try:
            errors = validate(json.loads(path.read_text()))
        except (OSError, json.JSONDecodeError) as exc:
            errors = [str(exc)]
        print(f"{path.name}: " + ("\n  " + "\n  ".join(errors) if errors else "OK"))
        failed |= bool(errors)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
