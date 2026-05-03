"""Metadata for insecure_tree."""

__all__ = [
    "__credits__",
    "__dependencies__",
    "__description__",
    "__keywords__",
    "__license__",
    "__readme__",
    "__requires_python__",
    "__status__",
    "__title__",
    "__version__",
]

__title__ = "insecure_tree"
__version__ = "0.1.0"
__description__ = "Audit GitHub Actions security posture of your Python dependency tree using zizmor"
__readme__ = "README.md"
__credits__ = [{"name": "Matthew Martin", "email": "matthewdeanmartin@gmail.com"}]
__keywords__ = ["security", "supply-chain", "github-actions", "zizmor", "dependencies", "audit", "devsecops"]
__license__ = "MIT"
__requires_python__ = ">=3.10"
__status__ = "3 - Alpha"
__dependencies__ = [
    "pydantic>=2.0",
    "packaging>=23.0",
    "httpx>=0.27",
    "jinja2>=3.1",
    "rich>=13.0",
    "tomli>=2.0; python_version < '3.11'",
    "zizmor>=1.0",
]
