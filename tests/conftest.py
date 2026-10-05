import tempfile
from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    if getattr(config.option, "basetemp", None) is None:
        custom_tmp = Path(tempfile.gettempdir()) / "cpo_pytest_tmp"
        custom_tmp.mkdir(parents=True, exist_ok=True)
        config.option.basetemp = str(custom_tmp)
