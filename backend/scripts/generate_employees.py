"""Write a CSV of fictional employees for import testing.

    uv run python -m scripts.generate_employees 20000 ../samples/employees-20000.csv

The output is deterministic, so the file can be regenerated instead of committed.
"""

import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

FIRST_NAMES = [
    "Anna", "Lukas", "Mia", "Jonas", "Lea", "Felix", "Sophie", "Noah", "Emma", "Paul",
    "Hannah", "Leon", "Marie", "Finn", "Clara", "Elias", "Lena", "Ben", "Laura", "Max",
    "Jürgen", "Özlem", "François", "Käthe", "Mehmet", "Aylin", "Luca", "Giulia", "Piotr", "Zofia",
]  # fmt: skip
LAST_NAMES = [
    "Schmidt", "Müller", "Weber", "Fischer", "Wagner", "Becker", "Hoffmann", "Schulz", "Koch",
    "Richter", "Klein", "Wolf", "Schröder", "Neumann", "Schwarz", "Braun", "Zimmermann", "Krüger",
    "Hartmann", "Lange", "Werner", "Krause", "Lehmann", "Köhler", "Yilmaz", "Rossi", "Nowak",
]  # fmt: skip
DEPARTMENTS = ["Digital Industries", "Smart Infrastructure", "Mobility", "Healthineers"]
JOB_TITLES = [
    "Software Engineer", "Senior Software Engineer", "DevOps Engineer", "Data Engineer",
    "Cloud Architect", "QA Engineer", "Product Owner", "Frontend Developer", "Security Engineer",
]  # fmt: skip
LOCATIONS = ["Munich", "Berlin", "Erlangen", "Nuremberg", "Zug", "Vienna", "Prague", None]
ASCII = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "ç": "c", "Ö": "Oe", "Ä": "Ae"})


def rows(count: int) -> list[list[str]]:
    rng = random.Random(20_000)
    result = []
    for n in range(1, count + 1):
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        location = rng.choice(LOCATIONS)
        hired = date(2005, 1, 1) + timedelta(days=rng.randrange(7_300))
        email = f"{first}.{last}.{n}@example.com".translate(ASCII).lower()
        result.append(
            [
                f"E-{100_000 + n}",
                first,
                last,
                email,
                rng.choice(DEPARTMENTS),
                rng.choice(JOB_TITLES),
                location or "",
                hired.isoformat(),
            ]
        )
    return result


def main() -> None:
    count, target = int(sys.argv[1]), Path(sys.argv[2])
    with target.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(
            [
                "employee_number",
                "first_name",
                "last_name",
                "email",
                "department",
                "job_title",
                "location",
                "hire_date",
            ]
        )
        writer.writerows(rows(count))
    print(f"Wrote {count} employees to {target}")


if __name__ == "__main__":
    main()
