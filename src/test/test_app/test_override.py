from typing import Any, Dict

from regrid_wrapper.app.override import apply_overrides


def test_apply_overrides() -> None:
    base: Dict[str, Any] = {"key1": "value1", "nested": {"key2": "value2"}}
    # Create a tuple of overrides
    overrides = ("nested:key2=overridden", "new:key=new_value", "foo=bar")

    apply_overrides(overrides, base)

    assert base["nested"]["key2"] == "overridden"
    assert base["new"]["key"] == "new_value"
    assert base["key1"] == "value1"
    assert base["foo"] == "bar"

    # Test ValueError
    try:
        apply_overrides(("no_equals_sign",), base)
    except ValueError as e:
        assert str(e) == "Override string must contain an equals sign: no_equals_sign"
    else:
        assert False, "ValueError was not raised"
