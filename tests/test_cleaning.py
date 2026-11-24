import pandas as pd
import pytest

from cleansheet.cleaning import (Options, clean_files, merge_files, normalize_email,
                                 normalize_phone, row_key)
from cleansheet.file_io import SOURCE_FILE_COL, SOURCE_ROW_COL, load_file, save_result


def make_df(rows, name="test.csv"):
    df = pd.DataFrame(rows, dtype="object")
    df[SOURCE_FILE_COL] = name
    df[SOURCE_ROW_COL] = range(2, len(df) + 2)
    return df


@pytest.mark.parametrize("raw, expected, ok", [
    ("333 123 4567", "+393331234567", True),
    ("+39 333-1234567", "+393331234567", True),
    ("0039 3331234567", "+393331234567", True),
    ("393331234567", "+393331234567", True),
    ("011.555.1234", "+390115551234", True),
    ("(011) 5551234", "+390115551234", True),
    ("3331234567.0", "+393331234567", True),
    ("+44 20 7946 0958", "+442079460958", True),
    ("123", "123", False),
    ("chiamare dopo le 18", "chiamare dopo le 18", False),
])
def test_normalize_phone(raw, expected, ok):
    assert normalize_phone(raw) == (expected, ok)


@pytest.mark.parametrize("raw, expected, ok", [
    (" Mario.Rossi@Gmail.com ", "mario.rossi@gmail.com", True),
    ("mailto:info@azienda.it", "info@azienda.it", True),
    ("mario.rossi@gmail", "mario.rossi@gmail", False),
    ("mario rossi@gmail.com", "mario rossi@gmail.com", False),
    ("@gmail.com", "@gmail.com", False),
])
def test_normalize_email(raw, expected, ok):
    assert normalize_email(raw) == (expected, ok)


def test_row_key_ignores_order_case_and_accents():
    assert row_key(["Mario Rossi", "Torino"]) == row_key(["ROSSI, mario", "torino"])
    assert row_key(["Niccolò"]) == row_key(["niccolo"])


def test_merge_aligns_similar_headers():
    a = make_df([{"Email": "a@b.it"}], "a.csv")
    b = make_df([{" email ": "c@d.it", "Città": "Torino"}], "b.csv")
    merged = merge_files([a, b])
    assert "Email" in merged.columns and " email " not in merged.columns
    assert merged["Email"].tolist() == ["a@b.it", "c@d.it"]


def test_merge_ignores_hyphens_and_accents():
    a = make_df([{"E-mail": "a@b.it", "Città": "Torino"}], "a.csv")
    b = make_df([{"email": "c@d.it", "citta": "Asti", "Cellulare": "333"}], "b.xlsx")
    merged = merge_files([a, b])
    assert [c for c in merged.columns if not c.startswith("_")] == ["E-mail", "Città", "Cellulare"]


def test_full_pipeline():
    df = make_df([
        {"Nome": "  Mario   Rossi ", "Email": "Mario.Rossi@gmail.com", "Telefono": "333 1234567", "Vuota": None},
        {"Nome": "Mario Rossi", "Email": "mario.rossi@gmail.com ", "Telefono": "+39 333 1234567", "Vuota": None},
        {"Nome": None, "Email": None, "Telefono": None, "Vuota": None},
        {"Nome": "Rossi Mario", "Email": "mario.rossi@gmail.com", "Telefono": "3331234567", "Vuota": None},
        {"Nome": "Anna Bianchi", "Email": "anna@", "Telefono": "123", "Vuota": None},
    ])
    result = clean_files([df], Options())
    data, issues = result.data, result.issues

    assert "Vuota" not in data.columns                     # colonna vuota rimossa
    assert len(data) == 3                                  # 1 vuota + 1 duplicato esatto rimossi
    assert data.loc[0, "Nome"] == "Mario Rossi"            # spazi sistemati
    assert data.loc[0, "Telefono"] == "+393331234567"      # telefono normalizzato

    problems = issues["Problema"].tolist()
    assert "Email non valida" in problems
    assert "Telefono non riconosciuto" in problems
    assert any(p.startswith("Duplicato esatto") for p in problems)
    assert any(p.startswith("Possibile duplicato") for p in problems)
    # la riga duplicata indica la riga Excel giusta (riga 3 = seconda riga di dati)
    assert issues.loc[issues["Problema"].str.startswith("Duplicato esatto"), "Riga originale"].tolist() == [3]


def test_options_can_be_disabled():
    df = make_df([{"Nome": " a "}, {"Nome": " a "}])
    result = clean_files([df], Options(trim_spaces=False, remove_duplicates=False, flag_similar=False))
    assert result.data["Nome"].tolist() == [" a ", " a "]


def test_csv_semicolon_cp1252_roundtrip(tmp_path):
    path = tmp_path / "clienti.csv"
    path.write_bytes("Nome;Telefono;CAP\nNiccolò;0115551234;00100\n".encode("cp1252"))
    df = load_file(path)
    assert df.loc[0, "Nome"] == "Niccolò"
    assert df.loc[0, "CAP"] == "00100"                     # zeri iniziali conservati

    result = clean_files([df])
    out = tmp_path / "out.xlsx"
    save_result(out, result.data, result.issues, result.summary)
    sheets = pd.read_excel(out, sheet_name=None, dtype=str)
    assert set(sheets) == {"Dati puliti", "Da verificare", "Riepilogo"}
    assert sheets["Dati puliti"].loc[0, "CAP"] == "00100"
