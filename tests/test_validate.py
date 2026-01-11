from kaidf_gen.loader import load_yaml
from kaidf_gen.schema import validate_spec

def test_default_spec_valid():
    spec = load_yaml("specs/kaidf.default.yaml")
    validate_spec(spec)
