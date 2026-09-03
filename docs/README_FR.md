# Téléchargeur de l'édition électronique du Quotidien du Peuple / People's Daily Downloader

> [中文](../README.md) | [English](README_EN.md) | [日本語](README_JA.md) | [한국어](README_KO.md) | Français | [Deutsch](README_DE.md) | [Italiano](README_IT.md) | [हिन्दी](README_HI.md) | [ไทย](README_TH.md) | [العربية](README_AR.md) | [Русский](README_RU.md) | [Español](README_ES.md)

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)]()
[![License](https://img.shields.io/badge/License-MIT-green)]()

Outil de téléchargement et de fusion automatique de l'édition électronique du 《Quotidien du Peuple》, écrit en Python pur. Prend en charge le téléchargement des pages PDF, l'extraction du corps des articles (TXT/DOC/DOCX), le téléchargement par lot de plages de dates, et une configuration complète. Aucun navigateur ni pilote requis.

---

## Fonctionnalités

- **Mode PDF** : télécharge automatiquement toutes les pages PDF du jour et les fusionne en un seul fichier complet
- **Mode texte** : extrait le corps de tous les articles et les sort en `TXT` / `DOC` / `DOCX` (zéro dépendance supplémentaire)
- **Mode both** : génère simultanément la version PDF et la version texte
- **Téléchargement par lot** : prend en charge les expressions de plage de dates ; fusion séparée par date ou fusion de toutes les pages en un seul fichier multi-dates
- **Configuration complète** : plus de 30 options de configuration (réseau, interface, sortie, limitation de débit, proxy, planification, etc.) ajustables via `config.json`
- **Installation automatique des dépendances** : installe automatiquement la bibliothèque de fusion `pypdf` lors de la première exécution (source officielle → repli sur le miroir Tsinghua)
- **Progrès en temps réel** : barre de progression de téléchargement, affichage du débit, ouverture automatique de l'emplacement du fichier à la fin
- **Gestion robuste des erreurs** : nouvelle tentative réseau, nouvelle tentative automatique en cas de fichier occupé, blocage des dates futures/dates invalides/expressions invalides, messages d'erreur conviviaux

---

## Configuration requise

| Élément | Exigence |
|---|---|
| Système d'exploitation | Windows 10 / 11 (le lanceur de commandes cmd est spécifique à Windows ; le script principal est multiplateforme) |
| Python | **3.8 ou supérieur** (recommandé 3.10+, vérifié sur 3.13 / 3.14) |
| Réseau | doit pouvoir accéder à `paper.people.com.cn` |
| Navigateur | **non requis** Chrome / Edge / aucun pilote de navigateur |

### Bibliothèques dépendantes

| Bibliothèque | Usage | Méthode d'installation |
|---|---|---|
| `pypdf` | Fusion PDF | **installation automatique lors de la première exécution** ; peut aussi être installé manuellement avec `pip install pypdf` |
| (aucune) | Version texte TXT/DOC/DOCX | implémentation en bibliothèque standard pure (OOXML écrit manuellement avec `zipfile`), zéro dépendance |
| `PyMuPDF` (optionnel) | utilisé uniquement pour le rendu des captures d'aperçu PDF lors des tests | `pip install pymupdf`, inutile pour un usage normal |

---

## Démarrage rapide

### Méthode 1 : double-clic sur le BAT (recommandé pour les utilisateurs Windows)

1. Vérifiez que Python est installé et ajouté au PATH (ou que le lanceur `py` est disponible)
2. Double-cliquez sur `下载人民日报.bat`
3. Saisissez la date selon les invites (Entrée = aujourd'hui), choisissez le format (T / PDF / B)
4. Attendez le téléchargement et la fusion ; l'emplacement du fichier s'ouvre automatiquement à la fin

### Méthode 2 : ligne de commande

```bash
# PDF d'un seul jour (par défaut aujourd'hui)
python rmrb_downloader.py

# Date spécifiée + format
python rmrb_downloader.py 20260903 pdf
python rmrb_downloader.py 20260903 text
python rmrb_downloader.py 20260903 both

# Téléchargement par lot (plage de dates, fusion séparée par date)
python rmrb_downloader.py --batch "20260901-20260903" pdf --merge-mode each

# Téléchargement par lot (tout fusionné en un seul fichier multi-dates)
python rmrb_downloader.py --batch "20260901-20260903,20260905" both --merge-mode all

# D'une date à aujourd'hui (extrémité droite vide)
python rmrb_downloader.py --batch "20260801-" pdf

# Générer/actualiser la configuration par défaut
python rmrb_downloader.py --init

# Enregistrer/supprimer la tâche planifiée de téléchargement automatique quotidien
python rmrb_downloader.py --task-install
python rmrb_downloader.py --task-remove
```

---

## Description de la configuration (config.json)

`config.json` est généré automatiquement lors de la première exécution. Toutes les options de configuration et leur signification :

### Crawling et réseau

| Clé | Type | Valeur par défaut | Description |
|---|---|---|---|
| `base_url` | string | `http://paper.people.com.cn/rmrb/pc` | Adresse de base de l'édition électronique du Quotidien du Peuple |
| `rate_limit_kbps` | number | `0` | Limite de débit de téléchargement (Ko/s), `0` = illimité |
| `timeout` | int | `30` | Délai d'expiration d'une seule requête réseau (secondes) |
| `retry` | int | `3` | Nombre de nouvelles tentatives en cas d'échec |
| `retry_interval` | float | `2.0` | Intervalle entre les nouvelles tentatives (secondes) |
| `request_interval` | float | `0.2` | Intervalle entre chaque requête (secondes), évite le blocage pour accès trop fréquent |
| `concurrent` | int | `1` | Nombre de threads de téléchargement simultanés (1–16) |
| `proxy` | string | `""` | Adresse du proxy HTTP/HTTPS, vide = pas de proxy |
| `user_agent` | string | Chrome UA | User-Agent des requêtes |

### Interface

| Clé | Type | Valeur par défaut | Description |
|---|---|---|---|
| `color_foreground` | string | `"A"` | Couleur de premier plan cmd (0–F hexadécimal) |
| `color_background` | string | `"0"` | Couleur d'arrière-plan cmd (0–F hexadécimal) |
| `window_title` | string | `人民日报电子版下载器` | Titre de la fenêtre de console |
| `show_progress` | bool | `true` | Afficher ou non la barre de progression de téléchargement |

### Date et contenu

| Clé | Type | Valeur par défaut | Description |
|---|---|---|---|
| `default_date` | string | `""` | Date par défaut `YYYYMMDD`, vide = aujourd'hui |
| `default_format` | string | `"pdf"` | Format par défaut : `pdf` / `text` / `both` |
| `edition_filter` | list | `[]` | **Liste blanche des pages** : si non vide, ne télécharge que les numéros de page listés (ex. `[1,2]` = pages 1 et 2 uniquement) ; vide = toutes les pages |
| `holiday_skip` | bool | `false` | En mode un-jour, ignorer silencieusement s'il n'y a pas de pages (retourne 0 au lieu d'une erreur) |

### Téléchargement par lot

| Clé | Type | Valeur par défaut | Description |
|---|---|---|---|
| `batch_enable` | bool | `false` | Si `true`, le double-clic sur BAT affiche l'**interface de téléchargement par lot** |
| `batch_merge_mode` | string | `"each"` | `each` = fusion séparée par date ; `all` = fusion de toutes les dates en un seul fichier |
| `download_path` | string | `""` | Répertoire racine de téléchargement ; vide = dossier du script ; chemin relatif par rapport au répertoire du script, chemin absolu également accepté |

### Sortie et fusion

| Clé | Type | Valeur par défaut | Description |
|---|---|---|---|
| `download_dir` | string | `"pdfs_{date}"` | Modèle de répertoire de stockage des PDF d'une seule page, `{date}` remplacé par la date |
| `merged_filename` | string | `"人民日报-{date}-完整版"` | Modèle de nom de fichier PDF fusionné (sans extension) |
| `auto_merge` | bool | `true` | Fusion automatique en mode un-jour |
| `keep_singles` | bool | `true` | Conserver le répertoire des PDF d'une seule page après fusion ; `false` = suppression automatique après fusion réussie |
| `open_folder_after` | bool | `true` | Ouvrir automatiquement l'emplacement du fichier à la fin |

### Sortie texte

| Clé | Type | Valeur par défaut | Description |
|---|---|---|---|
| `text_output_format` | string | `"TXT"` | Format de sortie de la version texte : `TXT` / `DOC` / `DOCX` |
| `text_filename` | string | `"人民日报-{date}-文字版"` | Modèle de nom de fichier de la version texte (sans extension) |
| `text_include_edition` | bool | `true` | Inclure ou non les séparateurs de titre de page dans la version texte |

### Journal et notifications

| Clé | Type | Valeur par défaut | Description |
|---|---|---|---|
| `log_file` | string | `"rmrb_download.log"` | Nom du fichier journal ; vide = pas de journal |
| `log_level` | string | `"normal"` | Niveau de journal : `quiet` / `normal` / `debug` |
| `beep_on_done` | bool | `false` | Émettre un bip à la fin |
| `msg_on_done` | bool | `false` | Afficher une boîte de message Windows à la fin |

### Planification

| Clé | Type | Valeur par défaut | Description |
|---|---|---|---|
| `auto_run` | bool | `false` | Activer le téléchargement automatique quotidien (nécessite d'abord d'enregistrer la tâche planifiée avec `--task-install`) |
| `auto_run_time` | string | `"08:00"` | Heure d'exécution automatique quotidienne `HH:MM` |

> Les valeurs de configuration invalides (telles que limitation de débit négative, concurrence hors limites, code couleur invalide) sont automatiquement ramenées aux valeurs par défaut au démarrage avec un avertissement, sans provoquer de plantage.

---

## Détails du téléchargement par lot

### Expression de plage de dates

Saisie dans l'interface de lot BAT ou avec l'argument `--batch`. Plusieurs segments séparés par des virgules :

| Expression | Signification |
|---|---|
| `20260901-20260903` | 2026-09-01 à 2026-09-03 (bornes incluses) |
| `20260905` | Seulement le 2026-09-05 |
| `20260801-` | 2026-08-01 à **aujourd'hui** (extrémité droite vide) |
| `20260901-20260903,20260905` | Combinaison plage + jour unique (déduplication automatique, tri par date) |

- Les dates doivent être des dates réellement existantes (ex. `20260134`, `20261301` sont bloquées et signalées en erreur)
- Une date de début postérieure à la date de fin provoque une erreur
- Les dates sans page (jour non publié/non paru) sont automatiquement ignorées et comptabilisées dans le résumé

### Mode de fusion

| Mode | Comportement | Exemple de nom de fichier généré |
|---|---|---|
| `each` | Téléchargement et fusion séparés pour chaque date | `人民日报-2026-09-02-完整版.pdf`, `人民日报-2026-09-03-完整版.pdf` |
| `all` | Toutes les pages de toutes les dates fusionnées en **un seul fichier multi-dates** | `人民日报-2026-09-02-2026-09-03-完整版.pdf` |

La version texte prend également en charge `each` / `all`.

### Activer l'interface de lot BAT

Modifiez `config.json`, passez `"batch_enable"` à `true`. Le double-clic sur BAT entre dans l'interface de téléchargement par lot (saisie de plage → choix du mode de fusion → choix du format).

---

## Formats de sortie de la version texte

| Format | Description | Dépendance |
|---|---|---|
| `TXT` | Texte brut UTF-8, inclut les titres de page et le corps des articles | aucune |
| `DOC` | Contenu HTML enregistré en `.doc`, ouvrable directement avec Microsoft Word / WPS | aucune |
| `DOCX` | OOXML standard (structure de document minimale écrite manuellement avec `zipfile`), ouvrable avec Word/WPS/LibreOffice | aucune |

Changez le format en définissant `"text_output_format": "DOCX"` etc. dans `config.json`.

---

## Erreurs courantes et solutions

| Message d'erreur | Cause | Solution |
|---|---|---|
| `未来日期，人民日报尚未出版` | Date postérieure à aujourd'hui saisie | Vérifiez la date, ou modifiez `default_date` |
| `日期不存在（月份或日期越界）` | ex. `20261301`, `20260134` | Saisissez une date réellement existante |
| `日期应为 8 位数字 YYYYMMDD` | Nombre de chiffres de la date incorrect | Saisissez au format `YYYYMMDD`, ex. `20260903` |
| `未找到任何版面` | Date non publiée/non parue, ou `edition_filter` a vidé les pages, ou anomalie réseau | Changez pour une date de jour ouvrable ; vérifiez `edition_filter` ; consultez l'invite `[网络]` ci-dessus |
| `无法安装合并库 pypdf` | Réseau indisponible, impossible d'installer via pip | Exécutez manuellement `pip install pypdf`, ou configurez un proxy puis réessayez |
| `合并失败：目标文件正被占用` | PDF de même nom ouvert dans un lecteur PDF / l'aperçu de l'explorateur | Fermez le fichier de même name ouvert puis réessayez, ou modifiez `merged_filename` / `download_path` |
| `域名解析失败 / 网络连接失败` | Réseau non connecté, anomalie DNS ou erreur de proxy | Vérifiez le réseau ; vérifiez la configuration `proxy` de `config.json` |
| `连接/读取超时` | Réseau lent ou réponse serveur lente | Augmentez `timeout` (ex. 60), réessayez plus tard |
| `服务器返回 HTTP 403/429` | Accès trop fréquent, limitation de débit | Augmentez `request_interval` (ex. 1.0), diminuez `concurrent` |
| `日期表达式错误：无效日期` | Expression de lot contient une date invalide | Saisissez au format `YYYYMMDD`, plusieurs plages séparées par des virgules |
| `格式参数应为 text / pdf / both` | Argument de format incorrect | Utilisez `text` / `pdf` / `both` (interface BAT : T / PDF / B) |
| `--merge-mode 应为 each / all` | Argument de mode de fusion incorrect | Utilisez `each` ou `all` |

---

## Structure du projet

```
rmrb_download/
├── rmrb_downloader.py      # Script principal (configuration complète + lot + PDF/texte)
├── 下载人民日报.bat          # Lanceur Windows par double-clic (interface un-jour/lot)
├── build_bat.py             # Générateur BAT (encodage GBK)
├── config.json              # Fichier de configuration (généré automatiquement à la première exécution)
├── create_shortcut.ps1      # Script de création de raccourci bureau (avec ICO)
├── 人民日报下载器.ico        # Icône multi-tailles (16–256)
├── icon_src.png             # Image source de l'icône
├── test_errors.py           # Tests de gestion d'erreurs et de limites
├── test_download.py         # Tests complets de téléchargement réel
├── rmrb_download.log        # Journal d'exécution (généré automatiquement)
└── pdfs_YYYYMMDD/           # Répertoire des PDF d'une seule page (conservé si keep_singles=true)
```

---

## Tests

```bash
# Tests de gestion d'erreurs et de limites (pas de téléchargement, instantané)
python test_errors.py

# Tests complets de téléchargement réel (utilisez edition_filter pour ne garder que la page 1 et accélérer, couvre un-jour/lot/chaque format)
python test_download.py
```

Couverture des tests : date future/date invalide/format invalide/analyse d'expression de lot/validation config/PDF un-jour/TXT/DOC/DOCX/both/lot each/all/syntaxe jusqu'à aujourd'hui/keep_singles/vérification du nom de fichier et du nombre de pages.

---

## Avertissement

- Cet outil est **réservé à l'usage personnel d'apprentissage et de recherche**, il ne peut être utilisé à aucune fin commerciale.
- Le droit d'auteur du 《Quotidien du Peuple》 appartient à l'Agence Quotidien du Peuple. Le contenu téléchargé doit respecter les lois et réglementations applicables ainsi que les conditions d'utilisation du site web.
- Veuillez contrôler raisonnablement la fréquence d'accès (`request_interval`) pour éviter de surcharger le site officiel.
- Si la structure du site officiel change, cet outil peut nécessiter des ajustements correspondants.

---

## License

MIT License
