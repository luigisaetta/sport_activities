import pandas as pd


def add_trimp_to_running(
    running_csv: str = "running_activities.csv",
    coach_trimp_csv: str = "coachpeaking_trimp.csv",
    output_csv: str = "running_activities_completed.csv",
) -> None:
    # --- Load running activities ---
    g = pd.read_csv(running_csv)

    required = {"activity_id", "end_time_gmt"}
    missing = required - set(g.columns)
    if missing:
        raise ValueError(f"{running_csv} missing columns: {sorted(missing)}")

    g["activity_date"] = pd.to_datetime(g["end_time_gmt"], errors="coerce").dt.date
    if g["activity_date"].isna().any():
        bad = g[g["activity_date"].isna()][["activity_id", "end_time_gmt"]].head(10)
        raise ValueError(f"Unparseable end_time_gmt values. Examples:\n{bad}")

    # --- Load CoachPeaking TRIMP (date,trimp) ---
    c = pd.read_csv(coach_trimp_csv)

    if not {"date", "trimp"}.issubset(c.columns):
        raise ValueError(f"{coach_trimp_csv} must contain columns: date,trimp")

    c["activity_date"] = pd.to_datetime(
        c["date"], format="%d/%m/%Y", errors="coerce"
    ).dt.date
    if c["activity_date"].isna().any():
        bad = c[c["activity_date"].isna()][["date", "trimp"]].head(10)
        raise ValueError(f"Unparseable CoachPeaking dates. Examples:\n{bad}")

    # Se ci sono più righe coach per lo stesso giorno, teniamo la prima (e avvisiamo)
    dup = c["activity_date"].duplicated(keep=False)
    if dup.any():
        dups = c.loc[dup, ["date", "trimp"]].sort_values("date")
        print("WARNING: multiple CoachPeaking TRIMP rows for the same date.")
        print("Keeping the first TRIMP per date. Duplicates:")
        print(dups.to_string(index=False))

    c1 = c.sort_values("activity_date").drop_duplicates("activity_date", keep="first")[
        ["activity_date", "trimp"]
    ]

    # --- Left join: keep ONLY Garmin rows ---
    out = g.merge(c1, on="activity_date", how="left")

    # (opzionale) togli activity_date se non ti serve nel file finale
    out = out.drop(columns=["activity_date"])

    out.to_csv(output_csv, index=False)

    matched = out["trimp"].notna().sum()
    total = len(out)
    print(
        f"Wrote {output_csv} with {total} rows. TRIMP matched on {matched}/{total} rows."
    )


if __name__ == "__main__":
    add_trimp_to_running(
        running_csv="running_activities.csv",
        coach_trimp_csv="coachpeaking_trimp.csv",
        output_csv="running_activities_completed.csv",
    )
