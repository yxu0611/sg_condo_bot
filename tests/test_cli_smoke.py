from pathlib import Path
from florence_agent.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "sample_ura.csv"


def test_cli_csv_produces_html(tmp_path):
    out = tmp_path / "florence.html"
    rc = main(["--source", "csv", "--csv", str(FIXTURE), "--out", str(out)])
    assert rc == 0
    html = out.read_text()
    assert "<!doctype html>" in html.lower()
    assert "Florence Residences" in html
    assert "trades-data" in html
    assert out.stat().st_size > 5_000
