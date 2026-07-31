from lmio.sec_ownership import (
    parse_13f_information_table,
    parse_form4,
    parse_schedule_13,
)

SOURCE = "https://www.sec.gov/Archives/example.xml"


def test_parse_13f_information_table() -> None:
    document = """
    <informationTable>
      <infoTable>
        <nameOfIssuer>Example Corp</nameOfIssuer>
        <titleOfClass>COM</titleOfClass>
        <cusip>123456789</cusip>
        <value>125000</value>
        <shrsOrPrnAmt>
          <sshPrnamt>1000</sshPrnamt>
          <sshPrnamtType>SH</sshPrnamtType>
        </shrsOrPrnAmt>
        <investmentDiscretion>SOLE</investmentDiscretion>
        <votingAuthority>
          <Sole>900</Sole><Shared>50</Shared><None>50</None>
        </votingAuthority>
      </infoTable>
    </informationTable>
    """

    records = parse_13f_information_table(document, SOURCE)

    assert len(records) == 1
    assert records[0].issuer == "Example Corp"
    assert records[0].value_usd == 125_000
    assert records[0].shares == 1000
    assert records[0].voting_shared == 50


def test_parse_form4_non_derivative_and_derivative_transactions() -> None:
    document = """
    <ownershipDocument>
      <issuer>
        <issuerName>Example Corp</issuerName>
        <issuerTradingSymbol>TEST</issuerTradingSymbol>
      </issuer>
      <reportingOwner>
        <reportingOwnerId><rptOwnerName>Leon Example</rptOwnerName></reportingOwnerId>
      </reportingOwner>
      <nonDerivativeTable>
        <nonDerivativeTransaction>
          <securityTitle><value>Common Stock</value></securityTitle>
          <transactionDate><value>2026-07-30</value></transactionDate>
          <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
          <transactionAmounts>
            <transactionShares><value>100</value></transactionShares>
            <transactionPricePerShare><value>12.50</value></transactionPricePerShare>
            <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
          </transactionAmounts>
          <postTransactionAmounts>
            <sharesOwnedFollowingTransaction><value>1100</value></sharesOwnedFollowingTransaction>
          </postTransactionAmounts>
          <ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature>
        </nonDerivativeTransaction>
      </nonDerivativeTable>
      <derivativeTable>
        <derivativeTransaction>
          <securityTitle><value>Stock Option</value></securityTitle>
          <transactionDate><value>2026-07-30</value></transactionDate>
          <transactionCoding><transactionCode>M</transactionCode></transactionCoding>
          <transactionAmounts>
            <transactionShares><value>25</value></transactionShares>
            <transactionPricePerShare><value>5</value></transactionPricePerShare>
            <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
          </transactionAmounts>
          <ownershipNature><directOrIndirectOwnership><value>I</value></directOrIndirectOwnership></ownershipNature>
        </derivativeTransaction>
      </derivativeTable>
    </ownershipDocument>
    """

    records = parse_form4(document, SOURCE)

    assert len(records) == 2
    assert records[0].symbol == "TEST"
    assert records[0].transaction_code == "P"
    assert records[0].price == 12.5
    assert records[0].direct_ownership is True
    assert records[1].derivative is True
    assert records[1].direct_ownership is False


def test_parse_schedule_13_core_ownership_and_purpose() -> None:
    document = """
      Name of Reporting Person: Example Capital
      Name of Issuer: Example Corp
      CUSIP Number: 123456789
      Aggregate Amount Beneficially Owned: 1,250,000
      Percent of Class Represented: 7.5%
      Purpose of Transaction: The investor seeks board representation and
      operational improvements.
      Item 5: Interest in Securities of the Issuer
    """

    record = parse_schedule_13(document, form="SC 13D", source_url=SOURCE)

    assert record.form == "13D"
    assert record.reporting_person == "Example Capital"
    assert record.shares_beneficially_owned == 1_250_000
    assert record.percent_of_class == 7.5
    assert "board representation" in record.purpose_text


def test_parser_fails_closed_on_incomplete_ownership_documents() -> None:
    try:
        parse_13f_information_table("<informationTable />", SOURCE)
    except ValueError as error:
        assert "no holdings" in str(error)
    else:
        raise AssertionError("empty 13F should fail closed")
