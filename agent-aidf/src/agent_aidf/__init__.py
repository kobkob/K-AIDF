from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__"]

try:
    __version__ = version("agent-aidf")
except PackageNotFoundError:
    __version__ = "unknown"
