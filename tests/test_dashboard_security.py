from pathlib import Path

import pytest

from dashboard.app import safe_input_csv_path


@pytest.mark.parametrize(
    "filename",
    ["../outside.csv", "..\\outside.csv", "folder/file.csv", "not-a-csv.txt", ""],
)
def test_input_csv_path_rejects_traversal_and_non_csv(filename):
    with pytest.raises(ValueError):
        safe_input_csv_path(filename)


def test_input_csv_path_stays_inside_configured_directory():
    resolved = safe_input_csv_path("Athos.csv")

    assert resolved.name == "Athos.csv"
    assert resolved.parent == Path("data/input").resolve()
