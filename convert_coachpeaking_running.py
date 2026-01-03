"""
takes data from coachpeaking running export txt file
and converts it to a CSV with date and TRIMP columns
"""

import re
import csv
from pathlib import Path

DATE_RE = re.compile(r"^\s*(\d{2}/\d{2}/\d{4})\s*$")


def is_data_line(line: str) -> bool:
    # riconosce la riga che contiene una durata (mm:ss o hh:mm:ss) seguita da un numero (TRIMP)
    # es: "9.05 km - 47:18 104 116 %"
    return bool(re.search(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\b", line)) and bool(
        re.search(r"\b\d+\b", line)
    )


def extract_trimp(line: str) -> int | None:
    """
    Estrae il TRIMP come 'numero subito dopo la durata'.
    Esempio: "... 47:18 104 116 %" -> 104
             "... 01:07:36 138 103 %" -> 138
             "... 11:50 19" -> 19
    """
    m = re.search(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\s+(\d+)\b", line)
    if not m:
        return None
    return int(m.group(2))


def convert_file(input_path: str, output_csv: str = "coachpeaking_trimp.csv") -> None:
    in_path = Path(input_path)
    if not in_path.exists():
        raise FileNotFoundError(f"File not found: {input_path}")

    rows = []
    current_date = None

    with in_path.open("r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()

            if not line:
                continue

            dm = DATE_RE.match(line)
            if dm:
                current_date = dm.group(1)
                continue

            # finché non ho una data, ignoro
            if not current_date:
                continue

            if is_data_line(line):
                trimp = extract_trimp(line)
                if trimp is not None:
                    rows.append({"date": current_date, "trimp": trimp})
                    # dopo aver trovato il record, resetto la data per evitare accoppiamenti sbagliati
                    current_date = None

    if not rows:
        raise ValueError("No TRIMP entries found. Check input format.")

    with open(output_csv, "w", newline="", encoding="utf-8") as out:
        w = csv.DictWriter(out, fieldnames=["date", "trimp"])
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output_csv}")


if __name__ == "__main__":
    # modifica qui il nome del file di input
    convert_file("coachpeaking_running_2024_2025.txt", "coachpeaking_trimp_2024_2025.csv")
