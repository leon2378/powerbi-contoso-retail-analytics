import add_lineage_tags as alt

TMDL = "\n".join([
    "table Sales",
    "\tlineageTag: 11111111-1111-1111-1111-111111111111",
    "",
    "\tmeasure 'Sales Amount' = SUM ( Sales[Net Amount] )",
    "\t\tformatString: \\$#,0",
    "",
    "\tmeasure Orders =",
    "\t\t\tIF (",
    "\t\t\t    TRUE (),",
    "\t\t\t    1",
    "\t\t\t)",
    "\t\tformatString: #,0",
    "",
    "\tcolumn Quantity",
    "\t\tdataType: int64",
    "\t\tlineageTag: 22222222-2222-2222-2222-222222222222",
    "",
])


def test_tags_only_the_objects_that_lack_one():
    fixed, added = alt.process(TMDL)
    assert added == ["measure 'Sales Amount'", "measure Orders"]
    assert fixed.count("lineageTag:") == 4
    assert "11111111-1111-1111-1111-111111111111" in fixed
    assert "22222222-2222-2222-2222-222222222222" in fixed


def test_tag_goes_after_a_multi_line_expression():
    fixed, _ = alt.process(TMDL)
    lines = fixed.split("\n")
    closing = lines.index("\t\t\t)")
    assert lines[closing + 1] == f"\t\tlineageTag: {alt.tag_for('Sales', 'measure', 'Orders')}"
    assert lines[closing + 2] == "\t\tformatString: #,0"


def test_tags_are_deterministic_and_rerunning_changes_nothing():
    first, _ = alt.process(TMDL)
    again, _ = alt.process(TMDL)
    assert first == again
    refixed, added = alt.process(first)
    assert refixed == first and added == []
