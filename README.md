# CleanSheet

Programma per Windows che **ripulisce file Excel e CSV** di contatti, clienti e lead: spazi sbagliati, righe vuote, email non valide, telefoni scritti in dieci modi diversi, duplicati.

<!-- Sostituisci con una GIF del programma in uso (es. registrata con ScreenToGif) -->
![Demo](docs/demo.gif)

## Perché l'ho creato

Lavorando con CRM e campagne Google Ads / Meta Ads ho gestito ogni giorno export pieni di problemi: lo stesso cliente inserito due volte, numeri come `333 123 4567` e `+39 3331234567` trattati come diversi, email con spazi o maiuscole. CleanSheet automatizza questi controlli che prima facevo a mano in Excel.

## Download

Scarica `CleanSheet.exe` dalla pagina [Releases](../../releases): non serve installare Python.

> Al primo avvio Windows può mostrare l'avviso "PC protetto da Windows" perché il programma non è firmato digitalmente: clicca *Ulteriori informazioni → Esegui comunque*.

## Cosa fa

| Controllo | Esempio |
|---|---|
| Spazi superflui | `"  Mario   Rossi "` → `"Mario Rossi"` |
| Righe e colonne vuote | rimosse |
| Email | `" Mario.Rossi@Gmail.com"` → `"mario.rossi@gmail.com"`, `"luca@"` segnalata |
| Telefoni | `333 123 4567`, `0039 333-1234567` → `+393331234567` |
| Duplicati esatti | rimossi (dopo la normalizzazione) |
| Possibili duplicati | `Mario Rossi` / `Rossi Mario`, stessa email in più righe: **segnalati, mai cancellati** |
| Unione di più file | `E-mail`, `email`, `EMAIL` diventano un'unica colonna |

Il risultato è un file Excel con tre fogli:
- **Dati puliti**
- **Da verificare**: ogni problema con file e numero di riga originale, così lo ritrovi subito
- **Riepilogo**: cosa è stato modificato

I file originali non vengono mai modificati.

## Scelte tecniche

- **Tutto letto come testo** (`dtype=str`): Excel non trasforma CAP e telefoni in numeri perdendo gli zeri iniziali.
- **CSV italiani**: separatore (`;` `,` tab) e codifica (UTF-8 / Windows-1252) riconosciuti automaticamente.
- **I possibili duplicati non vengono cancellati**: la decisione resta all'utente, il programma la prepara.
- **Logica separata dall'interfaccia**: `cleaning.py` non dipende da Tkinter ed è coperta da test automatici.
- **Build automatica**: GitHub Actions esegue i test su Windows e genera l'`.exe` a ogni nuova versione.

## Struttura

```
cleansheet/
  cleaning.py   logica di pulizia (funzioni testabili)
  file_io.py    lettura CSV/Excel e salvataggio del report
  gui.py        interfaccia Tkinter
main.py         avvio
tests/          test con pytest
esempi/         file "sporchi" per provarlo
```

## Avviarlo da sorgente

```bash
pip install -r requirements.txt -r requirements-dev.txt
python main.py        # avvia il programma
python -m pytest      # esegue i test
```

Tecnologie: Python 3.12, Pandas, openpyxl, Tkinter, pytest, PyInstaller, GitHub Actions.

## Limiti noti (versione 0.1)

- Di un file Excel viene letto solo il primo foglio; i vecchi `.xls` non sono supportati.
- La normalizzazione dei telefoni è pensata per numeri italiani; gli internazionali sono accettati solo se scritti con il prefisso (`+44...`).
