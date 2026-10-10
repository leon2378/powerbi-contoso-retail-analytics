import generate_data_dictionary as gdd

SALES = "\n".join([
    "/// Order lines.",
    "table Sales",
    "\tlineageTag: x",
    "",
    "\t/// Net sales after discounts.",
    "\tmeasure 'Sales Amount' = SUM ( Sales[Net Amount] )",
    "\t\tformatString: \\$#,0",
    "\t\tdisplayFolder: Sales",
    "\t\tlineageTag: y",
    "",
    "\tmeasure Margin =",
    "\t\t\t[Sales Amount] - [Total Cost]",
    "\t\tdisplayFolder: Margin",
    "",
    '\t\tformatStringDefinition = "0"',
    "",
    "\t/// Order number.",
    "\tcolumn 'Order Number'",
    "\t\tdataType: int64",
    "",
    "\tcolumn 'Line Number'",
    "\t\tdataType: int64",
    "\t\tisHidden",
    "",
])


def parse(tmp_path):
    path = tmp_path / "Sales.tmdl"
    path.write_text(SALES, encoding="utf-8")
    return gdd.parse(path)


def test_parse_reads_descriptions_folders_formats_and_expressions(tmp_path):
    table = parse(tmp_path)
    assert (table.name, table.description, table.hidden) == ("Sales", "Order lines.", False)
    sales, margin = table.measures
    assert (sales.name, sales.description, sales.folder, sales.format) == (
        "Sales Amount", "Net sales after discounts.", "Sales", "\\$#,0")
    assert sales.expression == "SUM ( Sales[Net Amount] )"
    assert (margin.folder, margin.format, margin.expression) == ("Margin", "dynamic", "[Sales Amount] - [Total Cost]")
    assert [(c.name, c.data_type, c.description, c.hidden) for c in table.columns] == [
        ("Order Number", "int64", "Order number.", False),
        ("Line Number", "int64", "", True),
    ]


def test_render_lists_measures_and_only_visible_columns(tmp_path):
    markdown = gdd.render([parse(tmp_path)])
    assert "| **Sales Amount** | Net sales after discounts. | `\\$#,0` |" in markdown
    assert "| **Margin** |  | dynamic |" in markdown
    assert "| Order Number | int64 | Order number. |" in markdown
    assert "Line Number" not in markdown
