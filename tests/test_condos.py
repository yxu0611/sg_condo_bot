from sg_condo_agent.condos import REGISTRY, get, list_keys


def test_florence_is_registered():
    assert "florence" in REGISTRY
    c = get("florence")
    assert c.name == "The Florence Residences"
    assert c.ura_project_name == "FLORENCE RESIDENCES"
    assert c.edgeprop_asset_id == 291412
    assert c.squarefoot_slug == "florence-residences-singapore"


def test_get_is_case_insensitive():
    assert get("FLORENCE").key == "florence"
    assert get("Florence").key == "florence"


def test_get_returns_adhoc_for_unknown_name():
    c = get("Mystery Heights")
    assert c.ura_project_name == "MYSTERY HEIGHTS"
    assert c.edgeprop_asset_id is None
    assert c.squarefoot_slug is None
    assert c.key == "mystery_heights"


def test_subtitle_omits_missing_fields():
    c = get("Mystery Heights")
    # No location/district/tenure/top_year/units → subtitle is empty.
    assert c.subtitle == ""


def test_list_keys_sorted():
    assert list_keys() == sorted(list_keys())
