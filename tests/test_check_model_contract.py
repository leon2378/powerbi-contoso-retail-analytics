import pytest

import check_model_contract as cmc


@pytest.mark.parametrize("contract, tmdl", [
    ("integer", "int64"),
    ("bigint", "int64"),
    ("decimal(18, 4)", "decimal"),
    ("DECIMAL(18,4)", "decimal"),
    ("varchar", "string"),
    ("date", "dateTime"),
    ("double", "double"),
    ("boolean", "boolean"),
    ("hugeint", "?hugeint"),
])
def test_contract_types_map_to_tmdl(contract, tmdl):
    assert cmc.contract_type(contract) == tmdl


BUDGET = "\n".join([
    "table Budget",
    "\tlineageTag: x",
    "",
    "\tcolumn 'Budget Amount'",
    "\t\tdataType: decimal",
    "\t\tsourceColumn: budget_amount_usd",
    "",
    "\tpartition Budget = m",
    "\t\tmode: import",
    "\t\tsource =",
    "\t\t\t\tlet",
    '\t\t\t\t    Source = fnLoadTable("fct_sales_budget"),',
    '\t\t\t\t    Selected = Table.SelectColumns(Source, {"month_start_date", "budget_amount_usd"}, MissingField.Error),',
    '\t\t\t\t    Typed = Table.TransformColumnTypes(Selected, {{"month_start_date", type date}, {"budget_amount_usd", Currency.Type}})',
    "\t\t\t\tin",
    "\t\t\t\t    Typed",
    "",
])


def test_parse_reads_the_mart_columns_and_m_columns():
    mart, columns, m_columns = cmc.parse_tmdl_table(BUDGET)
    assert mart == "fct_sales_budget"
    assert columns == [("Budget Amount", "budget_amount_usd", "decimal")]
    assert m_columns == {"month_start_date", "budget_amount_usd"}


def test_tables_without_a_mart_are_skipped():
    mart, _, _ = cmc.parse_tmdl_table("table _Measures\n\tlineageTag: x\n")
    assert mart is None


def test_the_committed_model_matches_the_dbt_contracts(capsys):
    assert cmc.main() == 0
    assert "OK" in capsys.readouterr().out
