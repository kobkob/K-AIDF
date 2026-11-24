from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

__all__ = ["__version__"]

# The Debian package has no distribution metadata, so build-deb.sh writes its version beside this
# file. A source checkout reads the installed distribution instead.
_PACKAGED_VERSION_FILE = Path(__file__).with_name("PACKAGED_VERSION")

try:
    __version__ = version("agent-aidf")
except PackageNotFoundError:
    try:
        __version__ = _PACKAGED_VERSION_FILE.read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        __version__ = "unknown"
