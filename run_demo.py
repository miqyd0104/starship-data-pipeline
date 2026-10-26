"""Run this file in PyCharm to demonstrate the complete project offline."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = [
    (
        "Import 36 starships and resolve pilots",
        ["starships.py", "--offline", "--seed-snapshot"],
    ),
    ("Run all 12 aggregation tasks", ["aggregations.py"]),
    ("Independently verify live MongoDB results", ["verify.py"]),
    ("Export and check the relational SQL database", ["sql_extension.py"]),
    ("Run the 15 unit tests", ["-m", "unittest", "discover", "-s", "tests", "-v"]),
]


def main():
    for title, arguments in STEPS:
        print(f"\n{'=' * 60}\n{title}\n{'=' * 60}", flush=True)
        subprocess.run([sys.executable, *arguments], cwd=ROOT, check=True)
    print(
        "\nALL DEMO STEPS PASSED. MongoDB: sparta_week06; 36 ships, 30 valid pilot links.",
        flush=True,
    )


if __name__ == "__main__":
    main()
