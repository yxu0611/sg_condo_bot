from pathlib import Path

from sg_condo_agent.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "sample_ura.csv"


def test_cli_csv_produces_html(tmp_path):
    out = tmp_path / "florence.html"
    rc = main([
        "--condo", "florence",
        "--source", "csv",
        "--csv", str(FIXTURE),
        "--out", str(out),
    ])
    assert rc == 0
    html = out.read_text()
    assert "<!doctype html>" in html.lower()
    assert "Florence Residences" in html
    assert "trades-data" in html
    assert out.stat().st_size > 5_000


def test_cli_default_out_uses_condo_key(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = main([
        "--condo", "florence",
        "--source", "csv",
        "--csv", str(FIXTURE),
    ])
    assert rc == 0
    assert (tmp_path / "florence.html").exists()
