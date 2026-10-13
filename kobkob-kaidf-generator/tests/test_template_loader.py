import pytest

from kaidf_gen.errors import TemplateNotFoundError, UnsafePathError
from kaidf_gen.template_loader import list_library_keys, load_template_by_key

# Deeper than the packaged library's location on any realistic filesystem, so a
# vulnerable loader would reach the filesystem root and read /etc/passwd.
DEEP_UP = "../" * 40

TRAVERSAL_KEYS = [
    "../../etc/passwd",
    DEEP_UP + "etc/passwd",
    "root/" + DEEP_UP + "etc/passwd",
    "root/../../README.md",
    "..\\..\\etc\\passwd",
    "root\\" + "..\\" * 40 + "etc\\passwd",
    "/" + DEEP_UP + "etc/passwd",
]


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


@pytest.mark.parametrize("key", TRAVERSAL_KEYS)
def test_load_template_by_key_blocks_path_traversal(key: str) -> None:
    with pytest.raises(UnsafePathError, match="escapes output dir"):
        load_template_by_key(key)


def test_load_template_by_key_allows_dot_segments_that_stay_inside_library() -> None:
    expected = load_template_by_key("root/README.md")

    assert load_template_by_key("root/../root/README.md") == expected
