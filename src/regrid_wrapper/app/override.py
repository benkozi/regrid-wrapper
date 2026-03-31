from typing import Iterable


def apply_overrides(overrides: Iterable[str], base_dict: dict) -> None:
    """
    Applies overrides from an iterable of strings to a base dictionary in-place.
    Overrides are expected to be in the format 'key:to:override=value'.
    """
    for override in overrides:
        if "=" not in override:
            raise ValueError(f"Override string must contain an equals sign: {override}")
        key_path, value = override.split("=", 1)
        keys = key_path.split(":")
        current = base_dict
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            # Ensure the current key points to a dictionary if we're descending further
            elif not isinstance(current[k], dict):
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value
