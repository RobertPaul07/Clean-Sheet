"""Lettura e scrittura dei file.

Tutto viene letto come testo (dtype=str): così Excel/pandas non trasformano
"0115551234" in 115551234 e non perdiamo gli zeri iniziali dei telefoni o dei CAP.
"""

from pathlib import Path

import pandas as pd

SUPPORTED_EXTENSIONS = {".csv", ".txt", ".xlsx", ".xlsm"}

# Colonne tecniche aggiunte in lettura, usate per il report (non finiscono nel file pulito)
SOURCE_FILE_COL = "_file"
SOURCE_ROW_COL = "_riga"


def load_file(path: str | Path) -> pd.DataFrame:
    """Legge un CSV o un Excel (primo foglio) e aggiunge file e riga d'origine."""
    path = Path(path)
    ext = path.suffix.lower()

    if ext in {".csv", ".txt"}:
        df = _read_csv(path)
    elif ext in {".xlsx", ".xlsm"}:
        df = pd.read_excel(path, sheet_name=0, dtype=str, keep_default_na=False, na_values=[""])
    else:
        raise ValueError(f"Formato non supportato: {ext}")

    # Numero di riga come lo vede l'utente in Excel (riga 1 = intestazioni)
    df[SOURCE_FILE_COL] = path.name
    df[SOURCE_ROW_COL] = range(2, len(df) + 2)
    return df


def _read_csv(path: Path) -> pd.DataFrame:
    """I CSV italiani usano spesso ';' e la codifica Windows (cp1252): proviamo entrambe."""
    last_error = None
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return pd.read_csv(
                path,
                sep=None,            # pandas individua da solo il separatore (, ; tab |)
                engine="python",
                dtype=str,
                encoding=encoding,
                keep_default_na=False,  # "NA" o "null" restano testo, non diventano vuoti
                na_values=[""],
            )
        except UnicodeDecodeError as e:
            last_error = e
    raise ValueError(f"Impossibile leggere {path.name}: codifica non riconosciuta") from last_error


def save_result(path: str | Path, clean_df: pd.DataFrame, issues_df: pd.DataFrame,
                summary: list[str]) -> None:
    """Salva un Excel con tre fogli: dati puliti, righe da verificare, riepilogo."""
    path = Path(path)
    summary_df = pd.DataFrame({"Riepilogo": summary})

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        clean_df.to_excel(writer, sheet_name="Dati puliti", index=False)
        issues_df.to_excel(writer, sheet_name="Da verificare", index=False)
        summary_df.to_excel(writer, sheet_name="Riepilogo", index=False)

        for sheet in writer.sheets.values():
            _autofit(sheet)


def _autofit(sheet) -> None:
    """Allarga le colonne in base al contenuto (massimo 60 caratteri)."""
    for column in sheet.columns:
        longest = max((len(str(c.value)) for c in column if c.value is not None), default=0)
        sheet.column_dimensions[column[0].column_letter].width = min(longest + 2, 60)
    sheet.freeze_panes = "A2"
