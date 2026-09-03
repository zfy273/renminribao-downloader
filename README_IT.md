# Downloader dell'edizione elettronica del Quotidiano del Popolo / People's Daily Downloader

> [中文](README.md) | [English](README_EN.md) | [日本語](README_JA.md) | [한국어](README_KO.md) | [Français](README_FR.md) | [Deutsch](README_DE.md) | Italiano | [हिन्दी](README_HI.md) | [ไทย](README_TH.md) | [العربية](README_AR.md) | [Русский](README_RU.md) | [Español](README_ES.md)

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)]()
[![License](https://img.shields.io/badge/License-MIT-green)]()

Uno strumento scritto in puro Python per il download e l'unione automatica dell'edizione elettronica del «Quotidiano del Popolo». Supporta il download delle pagine PDF, l'estrazione del testo degli articoli (TXT/DOC/DOCX), il download massivo per intervalli di date e la configurazione completa. Nessun browser o driver richiesto.

---

## Funzionalità

- **Modalità PDF**: scarica automaticamente tutte le pagine PDF del giorno e le unisce in un unico file completo
- **Modalità testo**: estrae il testo di tutti gli articoli e lo esporta in `TXT` / `DOC` / `DOCX` (zero dipendenze aggiuntive)
- **Modalità both**: genera contemporaneamente la versione PDF e quella testo
- **Download massivo**: supporta espressioni di intervallo di date; unione separata per data o unione di tutte le pagine in un unico file multi-data
- **Configurazione completa**: oltre 30 opzioni di configurazione (rete, interfaccia, output, limite di velocità, proxy, pianificazione, ecc.) regolabili tramite `config.json`
- **Installazione automatica delle dipendenze**: installa automaticamente la libreria di unione `pypdf` al primo avvio (fonte ufficiale → fallback sul mirror Tsinghua)
- **Avanzamento in tempo reale**: barra di avanzamento download, visualizzazione della velocità, apertura automatica della posizione del file al completamento
- **Gestione robusta degli errori**: ritentativi di rete, ritentativi automatici in caso di file occupato, blocco delle date future/date non valide/espressioni non valide, messaggi di errore intuitivi

---

## Requisiti di sistema

| Elemento | Requisito |
|---|---|
| Sistema operativo | Windows 10 / 11 (il launcher batch cmd è specifico di Windows; lo script principale è multipiattaforma) |
| Python | **3.8 o superiore** (consigliato 3.10+, verificato su 3.13 / 3.14) |
| Rete | Deve poter accedere a `paper.people.com.cn` |
| Browser | **Non richiesto** Chrome / Edge / nessun driver browser |

### Librerie dipendenti

| Libreria | Scopo | Metodo di installazione |
|---|---|---|
| `pypdf` | Unione PDF | **Installazione automatica al primo avvio**; può anche essere installata manualmente con `pip install pypdf` |
| (nessuna) | Versione testo TXT/DOC/DOCX | implementazione in pura libreria standard (OOXML scritto manualmente con `zipfile`), zero dipendenze |
| `PyMuPDF` (opzionale) | utilizzato solo per il rendering delle anteprime PDF durante i test | `pip install pymupdf`, non necessario per l'uso normale |

---

## Avvio rapido

### Metodo 1: doppio clic sul BAT (consigliato per utenti Windows)

1. Assicurarsi che Python sia installato e aggiunto al PATH (o che il launcher `py` sia disponibile)
2. Fare doppio clic su `下载人民日报.bat`
3. Inserire la data secondo le istruzioni (Invio = oggi), scegliere il formato (T / PDF / B)
4. Attendere il download e l'unione; la posizione del file si apre automaticamente al completamento

### Metodo 2: riga di comando

```bash
# PDF di un solo giorno (predefinito oggi)
python rmrb_downloader.py

# Data specificata + formato
python rmrb_downloader.py 20260903 pdf
python rmrb_downloader.py 20260903 text
python rmrb_downloader.py 20260903 both

# Download massivo (intervallo di date, unione separata per data)
python rmrb_downloader.py --batch "20260901-20260903" pdf --merge-mode each

# Download massivo (tutto unito in un unico file multi-data)
python rmrb_downloader.py --batch "20260901-20260903,20260905" both --merge-mode all

# Da una data a oggi (estremo destro vuoto)
python rmrb_downloader.py --batch "20260801-" pdf

# Generare/aggiornare la configurazione predefinita
python rmrb_downloader.py --init

# Registrare/rimuovere l'attività pianificata per il download automatico giornaliero
python rmrb_downloader.py --task-install
python rmrb_downloader.py --task-remove
```

---

## Descrizione della configurazione (config.json)

`config.json` viene generato automaticamente al primo avvio. Tutte le opzioni di configurazione e il loro significato:

### Crawling e rete

| Chiave | Tipo | Valore predefinito | Descrizione |
|---|---|---|---|
| `base_url` | string | `http://paper.people.com.cn/rmrb/pc` | Indirizzo base dell'edizione elettronica del Quotidiano del Popolo |
| `rate_limit_kbps` | number | `0` | Limite di velocità di download (KB/s), `0` = illimitato |
| `timeout` | int | `30` | Timeout per una singola richiesta di rete (secondi) |
| `retry` | int | `3` | Numero di ritentativi in caso di errore |
| `retry_interval` | float | `2.0` | Intervallo tra i ritentativi (secondi) |
| `request_interval` | float | `0.2` | Intervallo tra ogni richiesta (secondi), evita il blocco per accesso troppo frequente |
| `concurrent` | int | `1` | Numero di thread di download simultanei (1–16) |
| `proxy` | string | `""` | Indirizzo proxy HTTP/HTTPS, vuoto = nessun proxy |
| `user_agent` | string | Chrome UA | User-Agent delle richieste |

### Interfaccia

| Chiave | Tipo | Valore predefinito | Descrizione |
|---|---|---|---|
| `color_foreground` | string | `"A"` | Colore primo piano del cmd (0–F esadecimale) |
| `color_background` | string | `"0"` | Colore sfondo del cmd (0–F esadecimale) |
| `window_title` | string | `人民日报电子版下载器` | Titolo della finestra della console |
| `show_progress` | bool | `true` | Mostrare o meno la barra di avanzamento del download |

### Data e contenuto

| Chiave | Tipo | Valore predefinito | Descrizione |
|---|---|---|---|
| `default_date` | string | `""` | Data predefinita `YYYYMMDD`, vuoto = oggi |
| `default_format` | string | `"pdf"` | Formato predefinito: `pdf` / `text` / `both` |
| `edition_filter` | list | `[]` | **Whitelist delle pagine**: se non vuoto, scarica solo i numeri di pagina elencati (es. `[1,2]` = solo pagine 1 e 2); vuoto = tutte le pagine |
| `holiday_skip` | bool | `false` | In modalità un-giorno, saltare silenziosamente se non ci sono pagine (restituisce 0 invece di errore) |

### Download massivo

| Chiave | Tipo | Valore predefinito | Descrizione |
|---|---|---|---|
| `batch_enable` | bool | `false` | Se `true`, il doppio clic sul BAT mostra l'**interfaccia di download massivo** |
| `batch_merge_mode` | string | `"each"` | `each` = unione separata per data; `all` = unione di tutte le date in un unico file |
| `download_path` | string | `""` | Directory radice di download; vuoto = cartella dello script; percorso relativo rispetto alla directory dello script, percorso assoluto anch'esso accettato |

### Output e unione

| Chiave | Tipo | Valore predefinito | Descrizione |
|---|---|---|---|
| `download_dir` | string | `"pdfs_{date}"` | Modello di directory per il salvataggio dei PDF a pagina singola, `{date}` sostituito dalla data |
| `merged_filename` | string | `"人民日报-{date}-完整版"` | Modello di nome file del PDF unito (senza estensione) |
| `auto_merge` | bool | `true` | Unione automatica in modalità un-giorno |
| `keep_singles` | bool | `true` | Mantenere la directory dei PDF a pagina singola dopo l'unione; `false` = eliminazione automatica dopo unione riuscita |
| `open_folder_after` | bool | `true` | Aprire automaticamente la posizione del file al completamento |

### Output testo

| Chiave | Tipo | Valore predefinito | Descrizione |
|---|---|---|---|
| `text_output_format` | string | `"TXT"` | Formato di output della versione testo: `TXT` / `DOC` / `DOCX` |
| `text_filename` | string | `"人民日报-{date}-文字版"` | Modello di nome file della versione testo (senza estensione) |
| `text_include_edition` | bool | `true` | Includere o meno i separatori di titolo di pagina nella versione testo |

### Log e notifiche

| Chiave | Tipo | Valore predefinito | Descrizione |
|---|---|---|---|
| `log_file` | string | `"rmrb_download.log"` | Nome del file di log; vuoto = nessun log |
| `log_level` | string | `"normal"` | Livello di log: `quiet` / `normal` / `debug` |
| `beep_on_done` | bool | `false` | Emissione di un segnale acustico al completamento |
| `msg_on_done` | bool | `false` | Visualizzazione di una finestra di messaggio Windows al completamento |

### Pianificazione

| Chiave | Tipo | Valore predefinito | Descrizione |
|---|---|---|---|
| `auto_run` | bool | `false` | Attivare il download automatico giornaliero (richiede prima la registrazione dell'attività pianificata con `--task-install`) |
| `auto_run_time` | string | `"08:00"` | Ora di esecuzione automatica giornaliera `HH:MM` |

> I valori di configurazione non validi (come limite di velocità negativo, concorrenza fuori intervallo, codici colore non validi) vengono automaticamente ripristinati ai valori predefiniti all'avvio con un avviso, senza causare arresti anomali.

---

## Dettagli del download massivo

### Espressione di intervallo di date

Inserita nell'interfaccia massiva del BAT o con l'argomento `--batch`. Più segmenti separati da virgola:

| Espressione | Significato |
|---|---|
| `20260901-20260903` | 2026-09-01 a 2026-09-03 (estremi inclusi) |
| `20260905` | Solo 2026-09-05 |
| `20260801-` | 2026-08-01 a **oggi** (estremo destro vuoto) |
| `20260901-20260903,20260905` | Combinazione intervallo + giorno singolo (dedup automatico, ordinamento per data) |

- Le date devono essere date realmente esistenti (es. `20260134`, `20261301` vengono bloccate e segnalate con errore)
- Una data di inizio successiva alla data di fine causa un errore
- Le date senza pagine (non pubblicate/non uscite) vengono automaticamente saltate e conteggiate nel riepilogo

### Modalità di unione

| Modalità | Comportamento | Esempio di nome file generato |
|---|---|---|
| `each` | Download e unione separati per ogni data | `人民日报-2026-09-02-完整版.pdf`, `人民日报-2026-09-03-完整版.pdf` |
| `all` | Tutte le pagine di tutte le date unite in **un unico file multi-data** | `人民日报-2026-09-02-2026-09-03-完整版.pdf` |

La versione testo supporta anch'essa `each` / `all`.

### Attivare l'interfaccia massiva del BAT

Modificare `config.json`, impostare `"batch_enable"` su `true`. Il doppio clic sul BAT entra nell'interfaccia di download massivo (inserimento intervallo → scelta modalità unione → scelta formato).

---

## Formati di output della versione testo

| Formato | Descrizione | Dipendenza |
|---|---|---|
| `TXT` | Testo semplice UTF-8, include titoli di pagina e testo degli articoli | nessuna |
| `DOC` | Contenuto HTML salvato come `.doc`, apribile direttamente con Microsoft Word / WPS | nessuna |
| `DOCX` | OOXML standard (struttura documento minima scritta manualmente con `zipfile`), apribile con Word/WPS/LibreOffice | nessuna |

Impostare `"text_output_format": "DOCX"` ecc. in `config.json` per cambiare formato.

---

## Errori comuni e soluzioni

| Messaggio di errore | Causa | Soluzione |
|---|---|---|
| `未来日期，人民日报尚未出版` | Inserita una data successiva a oggi | Controllare la data o modificare `default_date` |
| `日期不存在（月份或日期越界）` | es. `20261301`, `20260134` | Inserire una data realmente esistente |
| `日期应为 8 位数字 YYYYMMDD` | Numero di cifre della data non corretto | Inserire nel formato `YYYYMMDD`, es. `20260903` |
| `未找到任何版面` | Data non pubblicata/non uscita, o `edition_filter` ha svuotato le pagine, o anomalia di rete | Passare a una data feriale; controllare `edition_filter`; consultare il prompt `[网络]` sopra |
| `无法安装合并库 pypdf` | Rete non disponibile, impossibile installare tramite pip | Eseguire manualmente `pip install pypdf` o riprovare dopo aver configurato un proxy |
| `合并失败：目标文件正被占用` | PDF con lo stesso nome è aperto in un lettore PDF / nell'anteprima di Explorer | Chiudere il file con lo stesso nome aperto e riprovare, o modificare `merged_filename` / `download_path` |
| `域名解析失败 / 网络连接失败` | Rete non connessa, anomalia DNS o errore proxy | Controllare la rete; controllare la configurazione `proxy` in `config.json` |
| `连接/读取超时` | Rete lenta o risposta server lenta | Aumentare `timeout` (es. 60), riprovare più tardi |
| `服务器返回 HTTP 403/429` | Accesso troppo frequente, limitazione della velocità | Aumentare `request_interval` (es. 1.0), diminuire `concurrent` |
| `日期表达式错误：无效日期` | L'espressione massiva contiene una data non valida | Inserire nel formato `YYYYMMDD`, più intervalli separati da virgola |
| `格式参数应为 text / pdf / both` | Argomento di formato non corretto | Usare `text` / `pdf` / `both` (interfaccia BAT: T / PDF / B) |
| `--merge-mode 应为 each / all` | Argomento di modalità unione non corretto | Usare `each` o `all` |

---

## Struttura del progetto

```
rmrb_download/
├── rmrb_downloader.py      # Script principale (configurazione completa + massivo + PDF/testo)
├── 下载人民日报.bat          # Launcher Windows per doppio clic (interfaccia un-giorno/massivo)
├── build_bat.py             # Generatore BAT (codifica GBK)
├── config.json              # File di configurazione (generato automaticamente al primo avvio)
├── create_shortcut.ps1      # Script per la creazione di collegamenti desktop (con ICO)
├── 人民日报下载器.ico        # Icona multi-dimensione (16–256)
├── icon_src.png             # Immagine sorgente dell'icona
├── test_errors.py           # Test di gestione errori e limiti
├── test_download.py         # Test completi di download reale
├── rmrb_download.log        # Log di esecuzione (generato automaticamente)
└── pdfs_YYYYMMDD/           # Directory dei PDF a pagina singola (mantenuta se keep_singles=true)
```

---

## Test

```bash
# Test di gestione errori e limiti (nessun download, istantaneo)
python test_errors.py

# Test completi di download reale (usare edition_filter per mantenere solo la pagina 1 e accelerare, copre un-giorno/massivo/ogni formato)
python test_download.py
```

Copertura dei test: data futura/data non valida/formato non valido/analisi espressione massiva/validazione config/PDF un-giorno/TXT/DOC/DOCX/both/massivo each/all/sintassi fino a oggi/keep_singles/verifica nome file e numero pagine.

---

## Dichiarazione di non responsabilità

- Questo strumento è **riservato all'uso personale per apprendimento e ricerca**, non può essere utilizzato per alcuna attività commerciale.
- Il diritto d'autore del «Quotidiano del Popolo» appartiene all'Editrice del Quotidiano del Popolo. I contenuti scaricati devono rispettare le leggi e i regolamenti applicabili e i termini di utilizzo del sito web.
- Si prega di controllare ragionevolmente la frequenza di accesso (`request_interval`) per evitare di sovraccaricare il sito ufficiale.
- Se la struttura del sito ufficiale cambia, questo strumento potrebbe richiedere adeguamenti corrispondenti.

---

## License

MIT License
