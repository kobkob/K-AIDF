import pytest

from kaidf_gen.errors import TemplateNotFoundError
from kaidf_gen.template_loader import list_library_keys, load_template_by_key


def test_list_library_keys_is_sorted() -> None:
    keys = list_library_keys()

    assert keys == sorted(keys)


def test_load_template_by_key_normalizes_slashes() -> None:
    expected = load_template_by_key("root/README.md")

    assert load_template_by_key("/root/README.md") == expected
    assert load_template_by_key(r"root\README.md") == expected


def test_load_template_by_key_rejects_missing_key() -> None:
    with pytest.raises(TemplateNotFoundError, match="Template key not found"):
        load_template_by_key("missing/template.md")
