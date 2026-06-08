from app.services.config.weight_versions import list_weight_config_versions


def test_list_weight_config_versions_returns_matrix_and_dynamic_factors():
    payload = list_weight_config_versions()

    assert len(payload["items"]) == 2
    keys = {item["config_key"] for item in payload["items"]}
    assert keys == {"project_type_matrix", "dynamic_factors"}

    matrix = next(item for item in payload["items"] if item["config_key"] == "project_type_matrix")
    assert matrix["version"] == "1.0.0"
    assert matrix["project_type_count"] == 4
    assert "housing" in matrix["project_types"]

    dynamic = next(item for item in payload["items"] if item["config_key"] == "dynamic_factors")
    assert dynamic["version"] == "1.0.0"
    assert dynamic["factor_count"] == 5
    assert "DF-HZD-001" in dynamic["factor_codes"]
