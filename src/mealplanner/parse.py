"""Parse ``content/meal-plan.md`` into the structured data the web app consumes.

The markdown document is the source of truth for human-readable content; this
module turns it into JSON. It fails loudly rather than emitting partial data,
because a silent parse failure previously rendered empty recipe cards in the app.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import prices

MEAL_CODE = re.compile(r"\*\*([WLD]\d) — ([^*]+)\*\*")
DAY_ROW = re.compile(
    r"\| \*\*(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\*\* \| ([^|]+) \| ([^|]+) \| ([^|]+) \| (\d+) \| (\d+) g \|"  # noqa: E501
)
SNACK_ROW = re.compile(r"\| \*\*(S[A-Z])\*\* ([^|]+) \| ([^|]+) \| (\d+) \| (\d+) g \|")

LISTS = [
    ("lidl", "Lidl — Saturday", "Covers Sat–Wed", "### Saturday list", "### Wednesday list"),
    ("tesco", "Tesco — Wednesday", "Covers Thu–Fri", "### Wednesday list", "### As-needed"),
    ("asneeded", "As needed", "Lasts longer than a week", "### As-needed", None),
]


class ParseError(RuntimeError):
    """Raised when the document does not match the expected structure."""


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


def _resolve_meal(text: str, names: dict[str, str]) -> str:
    """Map a week-table cell to a recipe code.

    Leftover entries are written as prose with no meal code (for example
    "Leftover turkey chilli"), so fall back to token overlap against recipe names.
    """
    text = text.strip().replace("**", "")
    direct = re.match(r"([WLD]\d)", text)
    if direct:
        return direct.group(1)

    key = _tokens(re.sub(r"\*.*$", "", text))
    best, score = None, 0
    for code, name in names.items():
        overlap = len(key & _tokens(name))
        if overlap > score:
            best, score = code, overlap
    if not best or score < 2:
        raise ParseError(f"could not resolve meal in week table: {text!r}")
    return best


def _section(md: str, start: str, end: str | None = None) -> str:
    if start not in md:
        raise ParseError(f"missing section heading: {start!r}")
    begin = md.index(start)
    return md[begin : md.index(end)] if end else md[begin:]


def _parse_days(md: str, names: dict[str, str]) -> list[dict]:
    days = []
    for m in DAY_ROW.finditer(md):
        day, first, dinner, snacks, kcal, protein = m.groups()
        days.append(
            {
                "day": day,
                "first": _resolve_meal(first, names),
                "dinner": _resolve_meal(dinner, names),
                "snacks": snacks.strip(),
                "kcal": int(kcal),
                "protein": int(protein),
            }
        )
    if len(days) != 7:
        raise ParseError(f"expected 7 days in the week table, found {len(days)}")
    return days


def _parse_recipes(md: str) -> dict[str, dict]:
    body = _section(md, "## 3. Recipes", "## 4. Shopping List")
    recipes: dict[str, dict] = {}
    for block in re.split(r"\n(?=\*\*[WLD]\d — )", body)[1:]:
        head = re.match(r"\*\*([WLD]\d) — ([^*]+)\*\*(.*)", block)
        if not head:
            continue
        code, name, rest = head.group(1), head.group(2).strip(), head.group(3)
        macros = re.search(r"(\d+) kcal · (\d+) g protein", rest)
        meta = re.search(r"\*([^*]+)\*\s*$", rest.strip())
        alias = re.search(r"see (D\d)", rest)
        text = block[len(head.group(0)) :]
        lines = text.splitlines()

        ingredients = [ln[1:].strip() for ln in lines if ln.startswith(">") and ln[1:].strip()]
        steps = [re.sub(r"^\d+\.\s*", "", ln).strip() for ln in lines if re.match(r"^\d+\. ", ln)]
        per_portion = [ln.strip() for ln in lines if ln.startswith("Per portion:")]
        sauce = [ln.strip() for ln in lines if ln.startswith("**Sauce")]
        notes = [
            ln.strip()
            for ln in lines
            if ln.strip()
            and not ln.startswith((">", "Per portion:", "**Sauce"))
            and not re.match(r"^\d+\. ", ln)
        ]

        recipes[code] = {
            "code": code,
            "name": name,
            "kcal": int(macros.group(1)) if macros else None,
            "protein": int(macros.group(2)) if macros else None,
            "meta": meta.group(1).strip() if meta else "",
            "alias": alias.group(1) if alias else None,
            "ingredients": per_portion + ingredients + sauce,
            "steps": steps,
            "notes": notes,
        }
    if not recipes:
        raise ParseError("no recipes parsed")
    return recipes


def _parse_snacks(md: str) -> dict[str, dict]:
    snacks = {}
    for m in SNACK_ROW.finditer(md):
        code, name, contents, kcal, protein = m.groups()
        snacks[code] = {
            "code": code,
            "name": name.strip(),
            "contents": contents.strip(),
            "kcal": int(kcal),
            "protein": int(protein),
        }
    if not snacks:
        raise ParseError("no snacks parsed")
    return snacks


def _parse_list(shop: str, start: str, end: str | None) -> list[dict]:
    table = _section(shop, start, end)
    items = []
    for line in table.splitlines():
        m = re.match(r"\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|", line)
        if not m or m.group(1) in ("Item", "List"):
            continue
        if not set(m.group(1)) - set("- "):  # separator row
            continue
        items.append(
            {
                "item": m.group(1).replace("*", ""),
                "qty": m.group(2).replace("*", ""),
                "forr": m.group(3).replace("*", ""),
            }
        )
    return items


def _apply_prices(lists: list[dict]) -> dict[str, float]:
    missing = []
    for shopping_list in lists:
        total = 0.0
        for item in shopping_list["items"]:
            name = item["item"].strip()
            price = prices.OVERRIDES.get((shopping_list["id"], name), prices.PRICES.get(name))
            if price is None:
                missing.append((shopping_list["id"], name))
                continue
            item["price"] = round(price, 2)
            total += price
            if name in prices.WEEKS:
                item["weeks"] = prices.WEEKS[name]
        shopping_list["total"] = round(total, 2)
    if missing:
        raise ParseError(f"unpriced items: {missing}")

    totals = {sl["id"]: sl["total"] for sl in lists}
    amortised = sum(prices.PRICES[n] / prices.WEEKS[n] for n in prices.WEEKS)
    weekly = totals["lidl"] + totals["tesco"]
    return {
        "lidl": totals["lidl"],
        "tesco": totals["tesco"],
        "asneeded": totals["asneeded"],
        "weekly": round(weekly, 2),
        "amortised": round(amortised, 2),
        "true": round(weekly + amortised, 2),
        "perday": round((weekly + amortised) / 7, 2),
    }


def parse(md_path: Path) -> dict:
    """Parse the meal plan markdown into the app's data structure."""
    md = Path(md_path).read_text(encoding="utf-8")
    names = {m.group(1): m.group(2).strip() for m in MEAL_CODE.finditer(md)}
    if not names:
        raise ParseError("no recipe headings found")

    shop = _section(md, "## 4. Shopping List", "### Meal codes")
    lists = [
        {"id": lid, "name": name, "sub": sub, "items": _parse_list(shop, start, end)}
        for lid, name, sub, start, end in LISTS
    ]
    cost = _apply_prices(lists)

    return {
        "days": _parse_days(md, names),
        "recipes": _parse_recipes(md),
        "snacks": _parse_snacks(md),
        "lists": lists,
        "cost": cost,
    }


def to_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1)
