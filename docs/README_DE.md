# People's Daily E-Paper Downloader / People's Daily Downloader

> [中文](../README.md) | [English](README_EN.md) | [日本語](README_JA.md) | [한국어](README_KO.md) | [Français](README_FR.md) | Deutsch | [Italiano](README_IT.md) | [हिन्दी](README_HI.md) | [ไทย](README_TH.md) | [العربية](README_AR.md) | [Русский](README_RU.md) | [Español](README_ES.md)

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)]()
[![License](https://img.shields.io/badge/License-MIT-green)]()

Ein in reinem Python geschriebenes Tool zum automatischen Herunterladen und Zusammenführen der elektronischen Ausgabe der „Volkszeitung" (People's Daily). Unterstützt das Herunterladen von PDF-Seiten, das Extrahieren von Artikeltexten (TXT/DOC/DOCX), das Massenherunterladen von Datumsbereichen und vollständige Konfigurierbarkeit. Kein Browser oder Treiber erforderlich.

---

## Funktionen

- **PDF-Modus**: Lädt automatisch alle PDF-Seiten des aktuellen Tages herunter und führt sie zu einer einzigen vollständigen Datei zusammen
- **Textmodus**: Extrahiert den Text aller Artikel und gibt ihn als `TXT` / `DOC` / `DOCX` aus (ohne zusätzliche Abhängigkeiten)
- **Both-Modus**: Erzeugt gleichzeitig PDF- und Textversion
- **Massenherunterladen**: Unterstützt Datumsbereichsausdrücke; separate Zusammenführung pro Datum oder Zusammenführung aller Seiten in eine einzige große dateiübergreifende Datei
- **Vollständige Konfigurierbarkeit**: Über 30 Konfigurationsoptionen (Netzwerk, Oberfläche, Ausgabe, Geschwindigkeitsbegrenzung, Proxy, Zeitplanung etc.) über `config.json` einstellbar
- **Automatische Abhängigkeitsinstallation**: Installiert die `pypdf`-Zusammenführungsbibliothek automatisch bei der ersten Ausführung (offizielle Quelle → Fallback auf Tsinghua-Spiegel)
- **Echtzeit-Fortschritt**: Download-Fortschrittsbalken, Geschwindigkeitsanzeige, automatisches Öffnen des Dateispeicherorts nach Abschluss
- **Robuste Fehlerbehandlung**: Netzwerk-Wiederholversuche, automatische Wiederholversuche bei belegten Dateien, Blockierung von Zukunftsdatums/unzulässigen Datums/ungültigen Ausdrücken, benutzerfreundliche Fehlermeldungen

---

## Systemanforderungen

| Element | Anforderung |
|---|---|
| Betriebssystem | Windows 10 / 11 (cmd-Batch-Starter ist Windows-spezifisch; das Kernskript ist plattformübergreifend) |
| Python | **3.8 oder höher** (empfohlen 3.10+, getestet auf 3.13 / 3.14) |
| Netzwerk | Muss auf `paper.people.com.cn` zugreifen können |
| Browser | **Nicht erforderlich** Chrome / Edge / keine Browser-Treiber |

### Abhängigkeitsbibliotheken

| Bibliothek | Zweck | Installationsmethode |
|---|---|---|
| `pypdf` | PDF-Zusammenführung | **Automatische Installation bei erster Ausführung**; kann auch manuell mit `pip install pypdf` installiert werden |
| (keine) | Textversion TXT/DOC/DOCX | Reine Standardbibliotheksimplementierung (OOXML manuell mit `zipfile` geschrieben), null Abhängigkeiten |
| `PyMuPDF` (optional) | Nur zum Rendern von PDF-Vorschaubildern bei Tests | `pip install pymupdf`, für den normalen Gebrauch nicht erforderlich |

---

## Schnellstart

### Methode 1: Doppelklick auf BAT (empfohlen für Windows-Benutzer)

1. Stellen Sie sicher, dass Python installiert und zum PATH hinzugefügt ist (oder dass der `py`-Launcher verfügbar ist)
2. Doppelklicken Sie auf `下载人民日报.bat`
3. Geben Sie das Datum gemäß den Aufforderungen ein (Enter = heute), wählen Sie das Format (T / PDF / B)
4. Warten Sie auf Download und Zusammenführung; der Dateispeicherort wird nach Abschluss automatisch geöffnet

### Methode 2: Befehlszeile

```bash
# Ein-Tages-PDF (standardmäßig heute)
python rmrb_downloader.py

# Bestimmtes Datum + Format
python rmrb_downloader.py 20260903 pdf
python rmrb_downloader.py 20260903 text
python rmrb_downloader.py 20260903 both

# Massenherunterladen (Datumsbereich, separate Zusammenführung pro Datum)
python rmrb_downloader.py --batch "20260901-20260903" pdf --merge-mode each

# Massenherunterladen (alles zu einer einzigen dateiübergreifenden Datei zusammenführen)
python rmrb_downloader.py --batch "20260901-20260903,20260905" both --merge-mode all

# Von einem Datum bis heute (rechtes Ende leer)
python rmrb_downloader.py --batch "20260801-" pdf

# Standardkonfiguration generieren/aktualisieren
python rmrb_downloader.py --init

# Geplante Aufgabe für täglichen automatischen Download registrieren/entfernen
python rmrb_downloader.py --task-install
python rmrb_downloader.py --task-remove
```

---

## Konfigurationsbeschreibung (config.json)

`config.json` wird bei der ersten Ausführung automatisch generiert. Alle Konfigurationsoptionen und ihre Bedeutung:

### Crawling und Netzwerk

| Schlüssel | Typ | Standardwert | Beschreibung |
|---|---|---|---|
| `base_url` | string | `http://paper.people.com.cn/rmrb/pc` | Basisadresse der elektronischen Ausgabe der Volkszeitung |
| `rate_limit_kbps` | number | `0` | Download-Geschwindigkeitsbegrenzung (KB/s), `0` = unbegrenzt |
| `timeout` | int | `30` | Timeout für eine einzelne Netzwerkanfrage (Sekunden) |
| `retry` | int | `3` | Anzahl der Wiederholversuche bei Fehler |
| `retry_interval` | float | `2.0` | Intervall zwischen Wiederholversuchen (Sekunden) |
| `request_interval` | float | `0.2` | Intervall zwischen jeder Anfrage (Sekunden), verhindert Sperrung durch zu häufigen Zugriff |
| `concurrent` | int | `1` | Anzahl der gleichzeitigen Download-Threads (1–16) |
| `proxy` | string | `""` | HTTP/HTTPS-Proxy-Adresse, leer = kein Proxy |
| `user_agent` | string | Chrome UA | User-Agent der Anfragen |

### Oberfläche

| Schlüssel | Typ | Standardwert | Beschreibung |
|---|---|---|---|
| `color_foreground` | string | `"A"` | Vordergrundfarbe der cmd (0–F hexadezimal) |
| `color_background` | string | `"0"` | Hintergrundfarbe der cmd (0–F hexadezimal) |
| `window_title` | string | `人民日报电子版下载器` | Titel des Konsolenfensters |
| `show_progress` | bool | `true` | Download-Fortschrittsbalken anzeigen oder nicht |

### Datum und Inhalt

| Schlüssel | Typ | Standardwert | Beschreibung |
|---|---|---|---|
| `default_date` | string | `""` | Standarddatum `YYYYMMDD`, leer = heute |
| `default_format` | string | `"pdf"` | Standardformat: `pdf` / `text` / `both` |
| `edition_filter` | list | `[]` | **Seiten-Whitelist**: Wenn nicht leer, werden nur die aufgelisteten Seitennummern heruntergeladen (z.B. `[1,2]` = nur Seite 1 und 2); leer = alle Seiten |
| `holiday_skip` | bool | `false` | Im Ein-Tages-Modus still überspringen, wenn keine Seiten vorhanden sind (gibt 0 zurück statt Fehler) |

### Massenherunterladen

| Schlüssel | Typ | Standardwert | Beschreibung |
|---|---|---|---|
| `batch_enable` | bool | `false` | Bei `true` zeigt der Doppelklick auf BAT die **Massen-Download-Oberfläche** an |
| `batch_merge_mode` | string | `"each"` | `each` = separate Zusammenführung pro Datum; `all` = alle Daten zu einer großen Datei zusammenführen |
| `download_path` | string | `""` | Download-Stammverzeichnis; leer = Ordner des Skripts; relativer Pfad bezieht sich auf das Skriptverzeichnis, absoluter Pfad ebenfalls möglich |

### Ausgabe und Zusammenführung

| Schlüssel | Typ | Standardwert | Beschreibung |
|---|---|---|---|
| `download_dir` | string | `"pdfs_{date}"` | Vorlage für das Verzeichnis zur Speicherung von Ein-Seiten-PDFs, `{date}` wird durch das Datum ersetzt |
| `merged_filename` | string | `"人民日报-{date}-完整版"` | Vorlage für den Dateinamen des zusammengeführten PDFs (ohne Erweiterung) |
| `auto_merge` | bool | `true` | Automatische Zusammenführung im Ein-Tages-Modus |
| `keep_singles` | bool | `true` | Verzeichnis mit Ein-Seiten-PDFs nach der Zusammenführung behalten; `false` = automatische Löschung nach erfolgreicher Zusammenführung |
| `open_folder_after` | bool | `true` | Dateispeicherort nach Abschluss automatisch öffnen |

### Textausgabe

| Schlüssel | Typ | Standardwert | Beschreibung |
|---|---|---|---|
| `text_output_format` | string | `"TXT"` | Ausgabeformat der Textversion: `TXT` / `DOC` / `DOCX` |
| `text_filename` | string | `"人民日报-{date}-文字版"` | Vorlage für den Dateinamen der Textversion (ohne Erweiterung) |
| `text_include_edition` | bool | `true` | Seitentitel-Trennzeichen in die Textversion aufnehmen oder nicht |

### Protokoll und Benachrichtigungen

| Schlüssel | Typ | Standardwert | Beschreibung |
|---|---|---|---|
| `log_file` | string | `"rmrb_download.log"` | Protokolldateiname; leer = keine Protokollierung |
| `log_level` | string | `"normal"` | Protokollstufe: `quiet` / `normal` / `debug` |
| `beep_on_done` | bool | `false` | Piepton bei Abschluss |
| `msg_on_done` | bool | `false` | Windows-Meldungsfeld bei Abschluss anzeigen |

### Zeitplanung

| Schlüssel | Typ | Standardwert | Beschreibung |
|---|---|---|---|
| `auto_run` | bool | `false` | Täglichen automatischen Download aktivieren (erfordert vorherige Registrierung der geplanten Aufgabe mit `--task-install`) |
| `auto_run_time` | string | `"08:00"` | Tägliche automatische Ausführungszeit `HH:MM` |

> Ungültige Konfigurationswerte (wie negative Geschwindigkeitsbegrenzung, außerhalb des gültigen Bereichs liegende Nebenläufigkeit, ungültige Farbcodes) werden beim Start automatisch auf die Standardwerte zurückgesetzt und eine Warnung ausgegeben, ohne einen Absturz zu verursachen.

---

## Details zum Massenherunterladen

### Datumsbereichsausdruck

In der BAT-Massenoberfläche oder mit dem Argument `--batch` eingeben. Mehrere durch Kommas getrennte Segmente:

| Ausdruck | Bedeutung |
|---|---|
| `20260901-20260903` | 2026-09-01 bis 2026-09-03 (einschließlich beider Enden) |
| `20260905` | Nur 2026-09-05 |
| `20260801-` | 2026-08-01 bis **heute** (rechtes Ende leer) |
| `20260901-20260903,20260905` | Kombination aus Bereich und Einzeltag (automatische Deduplizierung, Sortierung nach Datum) |

- Daten müssen tatsächlich existierende Daten sein (z.B. `20260134`, `20261301` werden blockiert und mit Fehler gemeldet)
- Ein Startdatum nach dem Enddatum verursacht einen Fehler
- Daten ohne Seiten (nicht veröffentlicht/nicht erschienen) werden automatisch übersprungen und in die Zusammenfassung aufgenommen

### Zusammenführungsmodus

| Modus | Verhalten | Beispiel für generierten Dateinamen |
|---|---|---|
| `each` | Separate Download und Zusammenführung für jedes Datum | `人民日报-2026-09-02-完整版.pdf`, `人民日报-2026-09-03-完整版.pdf` |
| `all` | Alle Seiten aller Daten zu **einer einzigen dateiübergreifenden großen Datei** zusammenführen | `人民日报-2026-09-02-2026-09-03-完整版.pdf` |

Die Textversion unterstützt ebenfalls `each` / `all`.

### BAT-Massenoberfläche aktivieren

Bearbeiten Sie `config.json`, setzen Sie `"batch_enable"` auf `true`. Beim Doppelklick auf BAT gelangen Sie in die Massen-Download-Oberfläche (Bereich eingeben → Zusammenführungsmodus wählen → Format wählen).

---

## Textversion-Ausgabeformate

| Format | Beschreibung | Abhängigkeit |
|---|---|---|
| `TXT` | UTF-8-Klartext, enthält Seitentitel und Artikeltexte | keine |
| `DOC` | HTML-Inhalt als `.doc` gespeichert, direkt mit Microsoft Word / WPS öffenbar | keine |
| `DOCX` | Standard-OOXML (minimale Dokumentstruktur manuell mit `zipfile` geschrieben), mit Word/WPS/LibreOffice öffenbar | keine |

Stellen Sie in `config.json` `"text_output_format": "DOCX"` usw. ein, um zu wechseln.

---

## Häufige Fehler und Lösungen

| Fehlermeldung | Ursache | Lösung |
|---|---|---|
| `未来日期，人民日报尚未出版` | Datum nach heute eingegeben | Datum prüfen oder `default_date` ändern |
| `日期不存在（月份或日期越界）` | z.B. `20261301`, `20260134` | Tatsächlich existierendes Datum eingeben |
| `日期应为 8 位数字 YYYYMMDD` | Falsche Stellenzahl des Datums | Im Format `YYYYMMDD` eingeben, z.B. `20260903` |
| `未找到任何版面` | Datum nicht veröffentlicht/nicht erschienen, oder `edition_filter` hat die Seiten geleert, oder Netzwerkanomalie | Auf ein Werktagsdatum wechseln; `edition_filter` prüfen; die `[网络]`-Aufforderung oben prüfen |
| `无法安装合并库 pypdf` | Netzwerk nicht verfügbar, Installation über pip nicht möglich | Manuell `pip install pypdf` ausführen oder nach Proxy-Konfiguration erneut versuchen |
| `合并失败：目标文件正被占用` | Gleichnamiges PDF ist in einem PDF-Reader / der Explorer-Vorschau geöffnet | Geöffnete gleichnamige Datei schließen und erneut versuchen oder `merged_filename` / `download_path` ändern |
| `域名解析失败 / 网络连接失败` | Netzwerk nicht verbunden, DNS-Anomalie oder Proxy-Fehler | Netzwerk prüfen; `proxy`-Konfiguration in `config.json` prüfen |
| `连接/读取超时` | Langsames Netzwerk oder langsame Serverantwort | `timeout` erhöhen (z.B. 60), später erneut versuchen |
| `服务器返回 HTTP 403/429` | Zu häufiger Zugriff, Drosselung | `request_interval` erhöhen (z.B. 1.0), `concurrent` verringern |
| `日期表达式错误：无效日期` | Massenausdruck enthält ungültiges Datum | Im Format `YYYYMMDD` eingeben, mehrere Bereiche durch Kommas trennen |
| `格式参数应为 text / pdf / both` | Falsches Format-Argument | `text` / `pdf` / `both` verwenden (BAT-Oberfläche: T / PDF / B) |
| `--merge-mode 应为 each / all` | Falsches Zusammenführungsmodus-Argument | `each` oder `all` verwenden |

---

## Projektstruktur

```
rmrb_download/
├── rmrb_downloader.py      # Hauptskript (vollständige Konfiguration + Massen + PDF/Text)
├── 下载人民日报.bat          # Windows-Doppelklick-Starter (Ein-Tag/Massen-Oberfläche)
├── build_bat.py             # BAT-Generator (GBK-Kodierung)
├── config.json              # Konfigurationsdatei (bei erster Ausführung automatisch generiert)
├── create_shortcut.ps1      # Skript zur Erstellung von Desktop-Verknüpfungen (mit ICO)
├── 人民日报下载器.ico        # Mehrgrößen-Symbol (16–256)
├── icon_src.png             # Quellbild des Symbols
├── test_errors.py           # Tests für Fehlerbehandlung und Grenzen
├── test_download.py         # Vollständige Tests für echten Download
├── rmrb_download.log        # Ausführungsprotokoll (automatisch generiert)
└── pdfs_YYYYMMDD/           # Verzeichnis für Ein-Seiten-PDFs (beibehalten bei keep_singles=true)
```

---

## Tests

```bash
# Tests für Fehlerbehandlung und Grenzen (kein Download, sekundenschnell)
python test_errors.py

# Vollständige Tests für echten Download (mit edition_filter nur Seite 1 zur Beschleunigung, deckt Ein-Tag/Massen/jedes Format ab)
python test_download.py
```

Testabdeckung: Zukunftsdatum/ungültiges Datum/ungültiges Format/Analyse von Massenausdrücken/config-Validierung/Ein-Tag-PDF/TXT/DOC/DOCX/both/Massen each/all/Bis-heute-Syntax/keep_singles/Überprüfung von Dateiname und Seitenzahl.

---

## Haftungsausschluss

- Dieses Tool ist **nur für persönliches Lernen und Forschung bestimmt**, es darf nicht für kommerzielle Zwecke verwendet werden.
- Das Urheberrecht der „Volkszeitung" liegt bei der Volkszeitung-Verlagsgesellschaft. Heruntergeladene Inhalte müssen die geltenden Gesetze und Nutzungsbedingungen der Website einhalten.
- Bitte kontrollieren Sie die Zugriffshäufigkeit (`request_interval`) angemessen, um die offizielle Website nicht zu belasten.
- Wenn sich die Struktur der offiziellen Website ändert, muss dieses Tool möglicherweise entsprechend angepasst werden.

---

## License

MIT License
