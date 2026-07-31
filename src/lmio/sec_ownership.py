"""Deterministic parsers for SEC ownership filings used by LMIO research."""

from __future__ import annotations

import html
import re
from datetime import date
from typing import Literal
from xml.etree import ElementTree

from pydantic import BaseModel, ConfigDict, Field


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _descendant_text(node: ElementTree.Element, name: str) -> str | None:
    for child in node.iter():
        if _local_name(child.tag) == name and child.text and child.text.strip():
            return child.text.strip()
    return None


def _required_text(node: ElementTree.Element, name: str) -> str:
    value = _descendant_text(node, name)
    if value is None:
        raise ValueError(f"SEC ownership filing is missing {name}")
    return value


def _wrapped_text(node: ElementTree.Element, wrapper_name: str) -> str | None:
    for child in node.iter():
        if _local_name(child.tag) != wrapper_name:
            continue
        return _descendant_text(child, "value")
    return None


def _required_wrapped_text(node: ElementTree.Element, wrapper_name: str) -> str:
    value = _wrapped_text(node, wrapper_name)
    if value is None:
        raise ValueError(f"SEC ownership filing is missing {wrapper_name}")
    return value


def _number(value: str, field: str) -> float:
    try:
        return float(value.replace(",", "").strip())
    except ValueError as error:
        raise ValueError(f"SEC ownership filing contains invalid {field}") from error


class InstitutionalHolding(BaseModel):
    model_config = ConfigDict(frozen=True)

    issuer: str
    title_of_class: str
    cusip: str
    value_usd: float = Field(ge=0)
    shares: float = Field(ge=0)
    share_type: str
    investment_discretion: str
    voting_sole: float = Field(ge=0)
    voting_shared: float = Field(ge=0)
    voting_none: float = Field(ge=0)
    source_url: str


class Form4Transaction(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    issuer: str
    reporting_owner: str
    security_title: str
    transaction_date: date
    transaction_code: str
    shares: float = Field(gt=0)
    price: float | None = Field(default=None, ge=0)
    acquired_or_disposed: Literal["A", "D"]
    shares_owned_after: float | None = Field(default=None, ge=0)
    direct_ownership: bool
    derivative: bool
    source_url: str


class BeneficialOwnershipFiling(BaseModel):
    model_config = ConfigDict(frozen=True)

    form: str
    reporting_person: str
    issuer: str
    cusip: str
    shares_beneficially_owned: float = Field(ge=0)
    percent_of_class: float = Field(ge=0, le=100)
    purpose_text: str
    source_url: str


def parse_13f_information_table(xml_text: str, source_url: str) -> list[InstitutionalHolding]:
    """Parse the official 13F information-table XML into auditable holdings."""

    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as error:
        raise ValueError("SEC 13F information table is not valid XML") from error
    records: list[InstitutionalHolding] = []
    for item in root.iter():
        if _local_name(item.tag) != "infoTable":
            continue
        raw_value = _number(_required_text(item, "value"), "13F value")
        records.append(
            InstitutionalHolding(
                issuer=_required_text(item, "nameOfIssuer"),
                title_of_class=_required_text(item, "titleOfClass"),
                cusip=_required_text(item, "cusip"),
                value_usd=raw_value,
                shares=_number(_required_text(item, "sshPrnamt"), "13F shares"),
                share_type=_required_text(item, "sshPrnamtType"),
                investment_discretion=_required_text(item, "investmentDiscretion"),
                voting_sole=_number(_descendant_text(item, "Sole") or "0", "sole votes"),
                voting_shared=_number(_descendant_text(item, "Shared") or "0", "shared votes"),
                voting_none=_number(_descendant_text(item, "None") or "0", "non-votes"),
                source_url=source_url,
            )
        )
    if not records:
        raise ValueError("SEC 13F information table contains no holdings")
    return records


def parse_form4(xml_text: str, source_url: str) -> list[Form4Transaction]:
    """Parse non-derivative and derivative Form 4 transactions."""

    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as error:
        raise ValueError("SEC Form 4 document is not valid XML") from error
    symbol = _required_text(root, "issuerTradingSymbol").upper()
    issuer = _required_text(root, "issuerName")
    owner = _required_text(root, "rptOwnerName")
    records: list[Form4Transaction] = []
    for node in root.iter():
        local = _local_name(node.tag)
        if local not in {"nonDerivativeTransaction", "derivativeTransaction"}:
            continue
        acquired = _required_wrapped_text(node, "transactionAcquiredDisposedCode").upper()
        if acquired not in {"A", "D"}:
            raise ValueError("SEC Form 4 has an invalid acquired/disposed code")
        ownership = (_wrapped_text(node, "directOrIndirectOwnership") or "D").upper()
        price_text = _wrapped_text(node, "transactionPricePerShare")
        shares_after = _wrapped_text(node, "sharesOwnedFollowingTransaction")
        records.append(
            Form4Transaction(
                symbol=symbol,
                issuer=issuer,
                reporting_owner=owner,
                security_title=_required_wrapped_text(node, "securityTitle"),
                transaction_date=date.fromisoformat(
                    _required_wrapped_text(node, "transactionDate")
                ),
                transaction_code=_required_text(node, "transactionCode").upper(),
                shares=_number(
                    _required_wrapped_text(node, "transactionShares"),
                    "Form 4 shares",
                ),
                price=_number(price_text, "Form 4 price") if price_text else None,
                acquired_or_disposed=acquired,
                shares_owned_after=(
                    _number(shares_after, "Form 4 post-transaction shares")
                    if shares_after
                    else None
                ),
                direct_ownership=ownership == "D",
                derivative=local == "derivativeTransaction",
                source_url=source_url,
            )
        )
    if not records:
        raise ValueError("SEC Form 4 contains no reportable transactions")
    return records


def _plain_text(document: str) -> str:
    without_markup = re.sub(r"<[^>]+>", " ", document)
    return re.sub(r"\s+", " ", html.unescape(without_markup)).strip()


def _label_value(text: str, labels: tuple[str, ...], *, until: tuple[str, ...]) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    stop_pattern = "|".join(re.escape(label) for label in until)
    match = re.search(
        rf"(?:{label_pattern})\s*:?\s*(.+?)(?=\s+(?:{stop_pattern})\s*:?|$)",
        text,
        flags=re.IGNORECASE,
    )
    if match is None or not match.group(1).strip():
        raise ValueError(f"SEC Schedule 13 filing is missing {labels[0]}")
    return match.group(1).strip(" .;")


def parse_schedule_13(
    document: str,
    *,
    form: str,
    source_url: str,
) -> BeneficialOwnershipFiling:
    """Parse the core ownership and purpose fields from Schedule 13D/13G text."""

    normalised_form = form.upper().replace("SC ", "")
    if normalised_form not in {"13D", "13D/A", "13G", "13G/A"}:
        raise ValueError("Schedule parser only supports 13D/13G forms")
    text = _plain_text(document)
    reporting_person = _label_value(
        text,
        ("Name of Reporting Person",),
        until=("Name of Issuer",),
    )
    issuer = _label_value(
        text,
        ("Name of Issuer",),
        until=("CUSIP Number",),
    )
    cusip = _label_value(
        text,
        ("CUSIP Number",),
        until=("Aggregate Amount Beneficially Owned",),
    )
    shares_text = _label_value(
        text,
        ("Aggregate Amount Beneficially Owned",),
        until=("Percent of Class Represented",),
    )
    percent_text = _label_value(
        text,
        ("Percent of Class Represented",),
        until=("Purpose of Transaction", "Item 4"),
    )
    purpose = _label_value(
        text,
        ("Purpose of Transaction", "Item 4"),
        until=("Item 5", "Interest in Securities of the Issuer"),
    )
    return BeneficialOwnershipFiling(
        form=normalised_form,
        reporting_person=reporting_person,
        issuer=issuer,
        cusip=cusip,
        shares_beneficially_owned=_number(shares_text, "beneficially owned shares"),
        percent_of_class=_number(percent_text.rstrip("%"), "ownership percentage"),
        purpose_text=purpose,
        source_url=source_url,
    )


def parse_ownership_filing(
    form: str,
    document: str,
    source_url: str,
) -> list[InstitutionalHolding | Form4Transaction | BeneficialOwnershipFiling]:
    """Dispatch an SEC ownership document to the form-specific parser."""

    normalised = form.upper().strip()
    if normalised in {"13F-HR", "13F-HR/A"}:
        return parse_13f_information_table(document, source_url)
    if normalised in {"4", "4/A"}:
        return parse_form4(document, source_url)
    if normalised in {"SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A", "13D", "13D/A", "13G", "13G/A"}:
        return [parse_schedule_13(document, form=normalised, source_url=source_url)]
    raise ValueError(f"unsupported SEC ownership form: {form}")
