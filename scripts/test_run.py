import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "tjk_v2", "src"))

from tjk.cli import app
from typer.testing import CliRunner

runner = CliRunner()

def test_cli():
    # This is just a smoke test to see if it runs without import errors
    # It won't actually scrape successfully without real URLs/Selectors
    result = runner.invoke(app, ["scrape-day", "2025-12-19", "Izmir"])
    print(result.stdout)

if __name__ == "__main__":
    test_cli()
