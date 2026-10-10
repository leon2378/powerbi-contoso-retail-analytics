import pytest

import validate_report as vr


@pytest.fixture(autouse=True)
def clear_errors():
    vr.errors.clear()
    yield
    vr.errors.clear()


def pos(x, y, tab_order, width=100, height=50):
    return {"x": x, "y": y, "width": width, "height": height, "tabOrder": tab_order}


# --- tab order -----------------------------------------------------------------------------------
# Power BI moves focus from the highest tabOrder to the lowest, so reading order needs falling values.

def test_tab_order_in_reading_order_passes():
    vr.check_tab_order("page", {
        "title": pos(0, 0, 3000),
        "left": pos(0, 100, 2000),
        "right": pos(200, 110, 1000),  # same row as "left" (top edges within ROW_TOLERANCE)
    })
    assert vr.errors == []


def test_tab_order_rising_in_reading_order_fails():
    """The report's first numbering: it looked right, but Power BI walked every page backwards."""
    vr.check_tab_order("page", {"title": pos(0, 0, 1000), "chart": pos(0, 100, 2000)})
    assert len(vr.errors) == 1
    assert "'title' (above 'chart')" in vr.errors[0]


def test_tab_order_left_visual_in_a_row_comes_first():
    vr.check_tab_order("page", {"left": pos(0, 0, 1000), "right": pos(200, 10, 2000)})
    assert len(vr.errors) == 1
    assert "left of" in vr.errors[0]


@pytest.mark.parametrize("panel_tab_order", [3000, 2500, 500])
def test_tab_order_allows_either_order_for_staggered_visuals(panel_tab_order):
    # A tall panel starting lower than "upper" neither stacks with nor shares a row with the two
    # visuals beside it, so it may come before, between or after them.
    vr.check_tab_order("page", {
        "panel": pos(0, 40, panel_tab_order, height=300),
        "upper": pos(200, 0, 2000),
        "lower": pos(200, 150, 1000),
    })
    assert vr.errors == []


def test_tab_order_skips_visuals_without_one():
    vr.check_tab_order("page", {"title": pos(0, 0, None), "chart": pos(0, 100, 2000)})
    assert vr.errors == []


# --- field references ----------------------------------------------------------------------------

def test_field_references_finds_columns_measures_hierarchies_and_filter_entities():
    visual = {
        "query": {"projections": [
            {"field": {"Column": {"Expression": {"SourceRef": {"Entity": "Date"}}, "Property": "Year"}}},
            {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": "Sales Amount"}}},
            {"field": {"HierarchyLevel": {
                "Expression": {"Hierarchy": {"Expression": {"SourceRef": {"Entity": "Date"}}, "Hierarchy": "Calendar"}},
                "Level": "Year",
            }}},
        ]},
        "filter": {"From": [{"Name": "s", "Entity": "Store", "Type": 0}]},
    }
    found = vr.field_references(visual)
    assert sorted(found, key=str) == sorted(
        [("Date", "Year"), ("_Measures", "Sales Amount"), ("Date", "Calendar"), ("Store", None)], key=str
    )


# --- alt text ------------------------------------------------------------------------------------

def visual_with_alt_text(expr):
    return {"visual": {"visualContainerObjects": {"general": [{"properties": {"altText": {"expr": expr}}}]}}}


def literal(text):
    return {"Literal": {"Value": "'" + text.replace("'", "''") + "'"}}


def test_alt_text_missing_fails():
    vr.check_alt_text("visual.json", {"visual": {}})
    assert vr.errors and "missing alt text" in vr.errors[0]


def test_alt_text_typed_or_from_a_measure_passes():
    vr.check_alt_text("a.json", visual_with_alt_text(literal("Bar chart of sales by category.")))
    vr.check_alt_text("b.json", visual_with_alt_text(
        {"Measure": {"Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": "Alt Text Executive KPIs"}}
    ))
    assert vr.errors == []


def test_alt_text_over_power_bi_limit_fails():
    vr.check_alt_text("visual.json", visual_with_alt_text(literal("x" * 251)))
    assert vr.errors and "longer than 250" in vr.errors[0]


def test_alt_text_counts_an_escaped_quote_once():
    # 250 characters with 50 apostrophes, each stored as '' in the PBIR literal.
    vr.check_alt_text("visual.json", visual_with_alt_text(literal("It's " * 50)))
    assert vr.errors == []


# --- enumerated formatting values ----------------------------------------------------------------

THEME_SCHEMA = {"definitions": {
    "visual-lineChart": {"properties": {"categoryAxis": {"type": "array", "items": {"type": "object", "properties": {
        "axisType": {"anyOf": [{"const": "Scalar"}, {"const": "Categorical"}]},
        "show": {"type": "boolean"},
    }}}}},
    "commonCards": {"properties": {"visualTooltip": {"type": "array", "items": {"type": "object", "properties": {
        "type": {"$ref": "#/definitions/tooltipType"},
    }}}}},
    "tooltipType": {"anyOf": [{"const": "Default"}, {"const": "Canvas"}]},
}}


def setting(name, value):
    return [{"properties": {name: {"expr": {"Literal": {"Value": f"'{value}'"}}}}}]


def test_known_formatting_values_pass():
    vr.check_formatting_values("visual.json", "lineChart", {"categoryAxis": setting("axisType", "Scalar")},
                               {"visualTooltip": setting("type", "Canvas")}, THEME_SCHEMA)
    assert vr.errors == []


def test_unknown_axis_type_fails():
    """Desktop silently ignores 'Continuous' (the valid value is 'Scalar'); this once went unnoticed."""
    vr.check_formatting_values("visual.json", "lineChart", {"categoryAxis": setting("axisType", "Continuous")},
                               {}, THEME_SCHEMA)
    assert len(vr.errors) == 1
    assert "categoryAxis.axisType = 'Continuous'" in vr.errors[0]


def test_unknown_container_value_fails_through_a_shared_enum():
    vr.check_formatting_values("visual.json", "lineChart", {}, {"visualTooltip": setting("type", "ReportPage")},
                               THEME_SCHEMA)
    assert len(vr.errors) == 1
    assert "visualTooltip.type = 'ReportPage'" in vr.errors[0]
