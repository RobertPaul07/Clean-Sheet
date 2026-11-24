"""Logica di pulizia: funzioni senza interfaccia grafica, quindi facili da testare.

Ordine delle operazioni (in clean_files):
1. unione dei file (colonne con nomi simili vengono allineate)
2. spazi superflui
3. righe e colonne completamente vuote
4. email e telefoni (normalizzati, gli invalidi vengono segnalati)
5. duplicati esatti (rimossi)
6. possibili duplicati (solo segnalati, mai rimossi: decide l'utente)
"""

import re
import unicodedata
from dataclasses import dataclass, field

import pandas as pd

from .file_io import SOURCE_FILE_COL, SOURCE_ROW_COL

TECH_COLS = [SOURCE_FILE_COL, SOURCE_ROW_COL]

EMAIL_RE = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$")
EMAIL_HEADER_RE = re.compile(r"\b(e-?mail|mail|pec)\b")
PHONE_HEADER_RE = re.compile(r"\b(tel|telefono|cell|cellulare|phone|mobile|fax)\b")


@dataclass
class Options:
    trim_spaces: bool = True
    drop_empty: bool = True
    check_emails: bool = True
    normalize_phones: bool = True
    remove_duplicates: bool = True
    flag_similar: bool = True


@dataclass
class CleanResult:
    data: pd.DataFrame
    issues: pd.DataFrame
    summary: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- funzioni base

def normalize_header(name) -> str:
    """'  E-mail  Cliente ' -> 'e-mail cliente' (usato solo per confrontare i nomi)."""
    return re.sub(r"\s+", " ", str(name)).strip().casefold()


def header_key(name) -> str:
    """Chiave per unire le colonne di file diversi: 'E-mail', 'email ', 'EMAIL' -> 'email'."""
    return re.sub(r"[^a-z0-9]", "", strip_accents(str(name)).casefold())


def strip_accents(text: str) -> str:
    """'Niccolò' -> 'Niccolo'."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def row_key(values) -> str:
    """Chiave per trovare righe 'quasi uguali'.

    Minuscole, niente accenti né punteggiatura, parole in ordine alfabetico:
    'Mario Rossi' e 'ROSSI, mario' producono la stessa chiave.
    """
    words = []
    for v in values:
        if pd.isna(v):
            continue
        text = strip_accents(str(v)).casefold()
        words.extend(re.findall(r"[a-z0-9@.]+", text))
    return " ".join(sorted(words))


def normalize_email(value) -> tuple[str, bool]:
    """Restituisce (email normalizzata, è valida?)."""
    text = str(value).strip().casefold().removeprefix("mailto:")
    return text, bool(EMAIL_RE.match(text))


def normalize_phone(value) -> tuple[str, bool]:
    """Porta i numeri al formato +39XXXXXXXXXX. Restituisce (numero, è valido?).

    Se il numero non è riconoscibile viene restituito invariato e segnalato.
    """
    original = str(value).strip()
    # "3331234567.0": numero salvato come decimale da Excel. Va tolto PRIMA di
    # eliminare i punti, altrimenti diventerebbe "33312345670".
    s = original.removesuffix(".0") if original.removesuffix(".0").isdigit() else original
    s = re.sub(r"[\s.\-/()]", "", s)

    if s.startswith("00"):
        s = "+" + s[2:]

    if s.startswith("+"):
        digits = s[1:]
        if digits.isdigit() and 8 <= len(digits) <= 15:
            return s, True
        return original, False

    if s.isdigit():
        if s.startswith("39") and len(s) in (11, 12) and s[2] in "03":
            return "+" + s, True          # prefisso 39 senza il +
        if s.startswith("3") and len(s) in (9, 10):
            return "+39" + s, True        # cellulare italiano
        if s.startswith("0") and 6 <= len(s) <= 11:
            return "+39" + s, True        # fisso italiano
    return original, False


def find_columns(columns, pattern: re.Pattern) -> list[str]:
    return [c for c in columns if c not in TECH_COLS and pattern.search(normalize_header(c))]


# ---------------------------------------------------------------- pipeline

def merge_files(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Unisce più tabelle. 'E-mail', 'email ' ed 'EMAIL' diventano la stessa colonna,
    che prende il nome con cui compare nel primo file."""
    canonical: dict[str, str] = {}   # chiave -> primo nome incontrato
    renamed = []
    for df in frames:
        mapping = {}
        for col in df.columns:
            if col in TECH_COLS:
                continue
            key = header_key(col) or normalize_header(col)
            canonical.setdefault(key, re.sub(r"\s+", " ", str(col)).strip())
            mapping[col] = canonical[key]
        renamed.append(df.rename(columns=mapping))
    return pd.concat(renamed, ignore_index=True)


def clean_files(frames: list[pd.DataFrame], options: Options | None = None) -> CleanResult:
    opt = options or Options()
    df = merge_files(frames)
    data_cols = [c for c in df.columns if c not in TECH_COLS]
    issues: list[dict] = []
    summary = [f"Righe lette: {len(df)} da {df[SOURCE_FILE_COL].nunique()} file"]

    def add_issue(idx, column, value, problem):
        issues.append({
            "File": df.at[idx, SOURCE_FILE_COL],
            "Riga originale": df.at[idx, SOURCE_ROW_COL],
            "Colonna": column,
            "Valore": value,
            "Problema": problem,
        })

    # 2. spazi superflui (anche gli spazi "invisibili" copiati dal web)
    if opt.trim_spaces:
        changed = 0
        for col in data_cols:
            before = df[col]
            after = before.str.replace(r"\s+", " ", regex=True).str.strip()
            after = after.mask(after == "")
            changed += int(((before != after) & before.notna()).sum())
            df[col] = after
        summary.append(f"Celle con spazi corretti: {changed}")

    # 3. righe e colonne vuote
    if opt.drop_empty:
        empty_rows = df[data_cols].isna().all(axis=1)
        df = df[~empty_rows]
        empty_cols = [c for c in data_cols if df[c].isna().all()]
        df = df.drop(columns=empty_cols)
        data_cols = [c for c in data_cols if c not in empty_cols]
        summary.append(f"Righe vuote rimosse: {int(empty_rows.sum())}")
        summary.append(f"Colonne vuote rimosse: {len(empty_cols)}"
                       + (f" ({', '.join(map(str, empty_cols))})" if empty_cols else ""))

    # 4a. email
    if opt.check_emails:
        cols = find_columns(data_cols, EMAIL_HEADER_RE)
        invalid = 0
        for col in cols:
            for idx, value in df[col].dropna().items():
                normalized, ok = normalize_email(value)
                if ok:
                    df.at[idx, col] = normalized
                else:
                    invalid += 1
                    add_issue(idx, col, value, "Email non valida")
        summary.append(f"Colonne email controllate: {', '.join(cols) or 'nessuna trovata'}"
                       f" — email non valide: {invalid}")

    # 4b. telefoni
    if opt.normalize_phones:
        cols = find_columns(data_cols, PHONE_HEADER_RE)
        invalid = 0
        for col in cols:
            for idx, value in df[col].dropna().items():
                normalized, ok = normalize_phone(value)
                if ok:
                    df.at[idx, col] = normalized
                else:
                    invalid += 1
                    add_issue(idx, col, value, "Telefono non riconosciuto")
        summary.append(f"Colonne telefono controllate: {', '.join(cols) or 'nessuna trovata'}"
                       f" — numeri non riconosciuti: {invalid}")

    # 5. duplicati esatti (dopo la normalizzazione, quindi "Mario@x.it " = "mario@x.it")
    if opt.remove_duplicates:
        dup = df.duplicated(subset=data_cols, keep="first")
        for idx in df.index[dup]:
            add_issue(idx, "", "", "Duplicato esatto: riga rimossa")
        df = df[~dup]
        summary.append(f"Duplicati esatti rimossi: {int(dup.sum())}")

    # 6. possibili duplicati: solo segnalati
    if opt.flag_similar:
        flagged = set()
        keys = df[data_cols].apply(row_key, axis=1)
        for _, group in df[keys.duplicated(keep=False) & (keys != "")].groupby(keys):
            rows = ", ".join(f"{f} r.{r}" for f, r in zip(group[SOURCE_FILE_COL], group[SOURCE_ROW_COL]))
            for idx in group.index:
                flagged.add(idx)
                add_issue(idx, "", "", f"Possibile duplicato (stessi dati in ordine o forma diversa): {rows}")

        for col in find_columns(data_cols, EMAIL_HEADER_RE):
            emails = df[col].where(df[col].str.contains("@", na=False))
            for email, group in df[emails.duplicated(keep=False) & emails.notna()].groupby(emails):
                for idx in group.index:
                    if idx not in flagged:
                        flagged.add(idx)
                        add_issue(idx, col, email, "Stessa email presente in più righe")
        summary.append(f"Righe da verificare come possibili duplicati: {len(flagged)}")

    # output: le colonne tecniche servono solo per il report
    out = df.drop(columns=TECH_COLS)
    if df[SOURCE_FILE_COL].nunique() > 1:
        out.insert(0, "File origine", df[SOURCE_FILE_COL])
    summary.append(f"Righe nel file pulito: {len(out)}")

    issues_df = pd.DataFrame(issues, columns=["File", "Riga originale", "Colonna", "Valore", "Problema"])
    issues_df = issues_df.sort_values(["File", "Riga originale"], kind="stable").reset_index(drop=True)
    return CleanResult(out.reset_index(drop=True), issues_df, summary)
