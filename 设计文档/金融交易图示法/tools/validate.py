"""Validate the FTN Core snapshot; no network calls or payment execution."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schema.json").read_text())


def validate(model):
    """Return all structural or cross-object violations, without modifying input."""
    errors = []

    def require(condition, rule, detail):
        if not condition:
            errors.append(f"{rule}: {detail}")

    structural = sorted(
        Draft202012Validator(SCHEMA, format_checker=FormatChecker()).iter_errors(model),
        key=lambda err: str(list(err.path)),
    )
    if structural:
        return [f"SCHEMA {list(err.path)}: {err.message}" for err in structural]

    groups = (
        "parties",
        "ledgers",
        "accounts",
        "operations",
        "batches",
        "legs",
        "messages",
    )
    objects = [item for group in groups for item in model[group]]
    counts = Counter(item["id"] for item in objects)
    require(all(n == 1 for n in counts.values()), "R01", "duplicate global id")
    if errors:
        return errors
    by_id = {item["id"]: item for item in objects}
    parties = {p["id"] for p in model["parties"]}
    ledgers = {k["id"]: k for k in model["ledgers"]}
    accounts = {a["id"]: a for a in model["accounts"]}
    operations = {o["id"]: o for o in model["operations"]}
    batches = {b["id"]: b for b in model["batches"]}
    legs = {leg["id"]: leg for leg in model["legs"]}
    require(model["observer"] in parties, "R01", "unknown observer")
    for ledger in ledgers.values():
        require(ledger["custodian"] in parties, "R01", ledger["id"] + " custodian")
    for account in accounts.values():
        aid = account["id"]
        require(
            account["owner"] in parties and account["custodian"] in parties,
            "R01",
            aid + " party",
        )
        require(account["currency"] in model["currencies"], "R02", aid + " currency")
        ledger = ledgers.get(account["ledger"])
        require(
            ledger is not None
            or (
                account["purpose"] == "external_boundary" and account["ledger"] is None
            ),
            "R01",
            aid + " ledger",
        )
        if ledger:
            require(
                ledger["custodian"] == account["custodian"],
                "R01",
                aid + " ledger custodian mismatch",
            )
        if account["purpose"] == "bank":
            require(
                ledger is not None and ledger["mode"] == "settlement",
                "R03",
                aid + " bank ledger",
            )

    for message in model["messages"]:
        require(
            message["from_party"] in parties and message["to_party"] in parties,
            "R01",
            message["id"] + " endpoint",
        )
        require(
            message["operation_ref"] in operations, "R01", message["id"] + " operation"
        )
    for leg in legs.values():
        lid = leg["id"]
        require(
            type(leg["money"]["minor"]) is int,
            "R02",
            lid + " amount must use integer JSON syntax",
        )
        require(leg["operation_ref"] in operations, "R01", lid + " operation")
        require(
            leg["money"]["currency"] in model["currencies"], "R02", lid + " currency"
        )
        source, target = accounts.get(leg["from"]), accounts.get(leg["to"])
        require(source is not None and target is not None, "R01", lid + " endpoints")
        require(leg["from"] != leg["to"], "R03", lid + " self transfer")
        if source and target:
            require(
                source["currency"] == target["currency"] == leg["money"]["currency"],
                "R03",
                lid + " currency mismatch",
            )
            if leg["kind"] == "L":
                ledger = ledgers.get(source["ledger"])
                require(
                    source["ledger"] == target["ledger"]
                    and ledger is not None
                    and ledger["mode"] == "normalized",
                    "R03",
                    lid + " local ledger",
                )
                batch = batches.get(leg["batch_ref"])
                require(
                    batch is not None and batch["ledger"] == source["ledger"],
                    "R04",
                    lid + " batch",
                )
            else:
                require(
                    source["purpose"] in {"bank", "external_boundary"}
                    and target["purpose"] in {"bank", "external_boundary"},
                    "R03",
                    lid + " external endpoint type",
                )
        if leg["kind"] == "F":
            known = leg["knowledge"] == "known"
            require(
                (known and leg["state"] is not None)
                or (not known and leg["state"] is None),
                "R08",
                lid + " knowledge/state",
            )
            if leg["state"] in {"confirmed", "failed", "cancelled"}:
                require(
                    known and bool(leg["evidence"]), "R07", lid + " terminal evidence"
                )
            if leg["state"] != "confirmed":
                require(
                    leg["confirmation_basis"] is None,
                    "R07",
                    lid + " premature confirmation basis",
                )
            if leg["finality"] == "final":
                require(
                    known
                    and leg["state"] == "confirmed"
                    and bool(leg["evidence"])
                    and bool(leg["finality_rule_ref"]),
                    "R09",
                    lid + " finality claim",
                )

    for batch in batches.values():
        members = [leg for leg in legs.values() if leg["batch_ref"] == batch["id"]]
        require(batch["ledger"] in ledgers, "R04", batch["id"] + " ledger")
        require(bool(members), "R04", batch["id"] + " empty batch")
        require(
            len({leg["operation_ref"] for leg in members}) == 1,
            "R04",
            batch["id"] + " mixed operations",
        )
        sources, targets = {x["from"] for x in members}, {x["to"] for x in members}
        valid = {
            "transfer": len(members) == 1,
            "split": len(sources) == 1 and len(targets) > 1,
            "gather": len(sources) > 1 and len(targets) == 1,
            "compound": True,
        }
        require(valid[batch["composition"]], "R05", batch["id"] + " composition")
        if batch["atomic"]:
            require(
                len({x["state"] for x in members}) == 1,
                "R06",
                batch["id"] + " partial atomic batch",
            )
            posted = [x for x in members if x["state"] == "posted"]
            if posted:
                require(
                    len({(x["posted_at"], x["commit_ref"]) for x in posted}) == 1,
                    "R06",
                    batch["id"] + " commit mismatch",
                )

    possible = Counter(
        leg["effect_ref"]
        for leg in legs.values()
        if leg["kind"] == "F"
        and (leg["state"] in {"confirmed", "submitted"} or leg["knowledge"] != "known")
    )
    for effect, count in possible.items():
        require(count <= 1, "R10", effect + " possible duplicate execution")
    external_units = defaultdict(list)
    for leg in legs.values():
        if leg["kind"] == "F":
            external_units[leg["effect_ref"]].append(leg)
    for effect, unit in external_units.items():
        reference = unit[0]
        require(
            all(
                all(
                    item[k] == reference[k]
                    for k in ("operation_ref", "from", "to", "money")
                )
                for item in unit
            ),
            "R10",
            effect + " inconsistent payment unit",
        )
    returned = defaultdict(int)
    reversed_count = Counter()
    seen_relations = set()
    for relation in model["relations"]:
        kind = relation["type"]
        key = (kind, relation["from_ref"], relation["to_ref"])
        require(key not in seen_relations, "R01", "duplicate relation")
        seen_relations.add(key)
        new, old = by_id.get(relation["from_ref"]), by_id.get(relation["to_ref"])
        require(
            new is not None and old is not None and new != old,
            "R01",
            "invalid relation endpoint",
        )
        if not new or not old or new == old:
            continue
        if kind == "refunds":
            require(
                new["id"] in operations and old["id"] in operations,
                "R13",
                "refunds endpoints must be operations",
            )
        elif kind == "realizes":
            require(
                new.get("kind") == "F"
                and old.get("kind") == "L"
                and new.get("operation_ref") == old.get("operation_ref")
                and new.get("effect_ref") == old.get("effect_ref")
                and new.get("money") == old.get("money"),
                "R14",
                "realizes F -> L with same operation/effect/money",
            )
        elif kind == "retry_of":
            same = all(
                new.get(k) == old.get(k)
                for k in ("operation_ref", "effect_ref", "from", "to", "money")
            )
            require(
                new.get("kind") == old.get("kind") == "F"
                and old.get("knowledge") == "known"
                and old.get("state") in {"failed", "cancelled"}
                and bool(old.get("evidence"))
                and same,
                "R11",
                "retry needs authoritative non-execution and same payment unit",
            )
        elif kind in {"reverses", "returns"}:
            is_local = kind == "reverses"
            expected_kind = "L" if is_local else "F"
            valid = new.get("kind") == old.get("kind") == expected_kind
            if not valid:
                require(
                    False, "R12" if is_local else "R13", "wrong reversal/return kind"
                )
                continue
            same_money = new["money"]["currency"] == old["money"]["currency"]
            swapped = new["from"] == old["to"] and new["to"] == old["from"]
            if is_local:
                require(
                    same_money
                    and swapped
                    and new["money"] == old["money"]
                    and new["state"] == old["state"] == "posted",
                    "R12",
                    "invalid equal local reversal",
                )
                reversed_count[old["id"]] += 1
            else:
                require(
                    same_money
                    and swapped
                    and new["state"] == old["state"] == "confirmed"
                    and new["knowledge"] == old["knowledge"] == "known",
                    "R13",
                    "invalid external return",
                )
                returned[old["id"]] += new["money"]["minor"]
    for lid, amount in returned.items():
        require(amount <= legs[lid]["money"]["minor"], "R13", lid + " over-return")
    for lid, count in reversed_count.items():
        require(count <= 1, "R12", lid + " repeated full reversal")
    for operation in operations.values():
        require(
            all(
                lid in legs and legs[lid]["operation_ref"] == operation["id"]
                for lid in operation["required_legs"]
            ),
            "R14",
            operation["id"] + " required legs",
        )
    return errors


def outcomes(model):
    """Derive outcomes only for validated, explicitly scoped completion predicates."""
    legs = {leg["id"]: leg for leg in model["legs"]}
    result = {}
    for operation in model["operations"]:
        required = [legs[lid] for lid in operation["required_legs"]]
        success = [
            leg["state"] == "posted"
            if leg["kind"] == "L"
            else leg["knowledge"] == "known" and leg["state"] == "confirmed"
            for leg in required
        ]
        terminal = [
            ok or leg["state"] in {"voided", "failed", "cancelled"}
            for leg, ok in zip(required, success)
        ]
        result[operation["id"]] = (
            "completed"
            if all(success)
            else "closed_unsuccessful"
            if all(terminal)
            else "partial"
            if any(success)
            else "open"
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    failed = False
    for path in args.files:
        model = json.loads(path.read_text())
        errors = validate(model)
        failed |= bool(errors)
        print(path.name, "INVALID" if errors else "VALID", errors or outcomes(model))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
