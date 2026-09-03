# 人民日報電子版ダウンローダー / People's Daily Downloader

> [中文](README.md) | [English](README_EN.md) | 日本語 | [한국어](README_KO.md) | [Français](README_FR.md) | [Deutsch](README_DE.md) | [Italiano](README_IT.md) | [हिन्दी](README_HI.md) | [ไทย](README_TH.md) | [العربية](README_AR.md) | [Русский](README_RU.md) | [Español](README_ES.md)

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)]()
[![License](https://img.shields.io/badge/License-MIT-green)]()

純 Python で書かれた『人民日報』電子版の自動ダウンロード＆結合ツール。PDF 版面のダウンロード、記事本文の抽出（TXT/DOC/DOCX）、日付範囲の一括ダウンロード、完全設定化に対応。ブラウザやドライバーは不要。

---

## 機能

- **PDF モード**：当日の全版面 PDF を自動ダウンロードし、1 つの完全版ファイルに結合
- **テキストモード**：全版面の記事本文を抽出し、`TXT` / `DOC` / `DOCX` で出力（追加依存ゼロ）
- **both モード**：PDF とテキスト版を同時に生成
- **一括ダウンロード**：日付範囲式に対応。日付ごとに個別結合、または全てを 1 つの跨日付大ファイルに結合可能
- **完全設定化**：30+ の設定項目（ネットワーク、UI、出力、速度制限、プロキシ、スケジュール等）を `config.json` で調整
- **依存関係の自動インストール**：初回実行時に `pypdf` 結合ライブラリを自動インストール（公式ソース → 清华ミラーにフォールバック）
- **リアルタイム進捗**：ダウンロード進捗バー、速度表示、完了後にファイル場所を自動で開く
- **堅牢なエラー処理**：ネットワークリトライ、ファイル占有の自動リトライ、未来日付/不正日付/無効式の遮断、日本語（中国語）フレンドリーなエラー表示

---

## 環境要件

| 項目 | 要件 |
|---|---|
| OS | Windows 10 / 11（cmd バッチ起動器は Windows 専用；コアスクリプトはクロスプラットフォーム） |
| Python | **3.8 以上**（推奨 3.10+、3.13 / 3.14 で検証済み） |
| ネットワーク | `paper.people.com.cn` にアクセス可能 |
| ブラウザ | **不要** Chrome / Edge / いかなるブラウザドライバーも不要 |

### 依存ライブラリ

| ライブラリ | 用途 | インストール方法 |
|---|---|---|
| `pypdf` | PDF 結合 | **初回実行時に自動インストール**；手動で `pip install pypdf` も可 |
| （なし） | テキスト版 TXT/DOC/DOCX | 標準ライブラリのみで実装（`zipfile` で OOXML を手書き）、依存ゼロ |
| `PyMuPDF`（任意） | テスト時の PDF プレビュー画像レンダリングのみ | `pip install pymupdf`、通常使用では不要 |

---

## クイックスタート

### 方法 1：BAT をダブルクリック（Windows ユーザー推奨）

1. Python がインストールされ PATH に追加されていることを確認（または `py` ランチャーが利用可能）
2. `下载人民日报.bat` をダブルクリック
3. プロンプトに従って日付を入力（Enter = 今日）、フォーマットを選択（T / PDF / B）
4. ダウンロードと結合が完了すると、ファイルの場所が自動で開く

### 方法 2：コマンドライン

```bash
# 单日 PDF（デフォルト今日）
python rmrb_downloader.py

# 日付指定 + フォーマット
python rmrb_downloader.py 20260903 pdf
python rmrb_downloader.py 20260903 text
python rmrb_downloader.py 20260903 both

# 一括ダウンロード（日付範囲、日付ごとに個別結合）
python rmrb_downloader.py --batch "20260901-20260903" pdf --merge-mode each

# 一括ダウンロード（全てを 1 つの跨日付大ファイルに結合）
python rmrb_downloader.py --batch "20260901-20260903,20260905" both --merge-mode all

# 某日付から今日まで（右端を空欄に）
python rmrb_downloader.py --batch "20260801-" pdf

# デフォルト設定を生成/リフレッシュ
python rmrb_downloader.py --init

# 毎日の自動ダウンロード計画タスクを登録/削除
python rmrb_downloader.py --task-install
python rmrb_downloader.py --task-remove
```

---

## 設定说明（config.json）

初回実行時に `config.json` が自動生成されます。全設定項目と意味は以下の通り：

### クロールとネットワーク

| キー | 型 | デフォルト値 | 说明 |
|---|---|---|---|
| `base_url` | string | `http://paper.people.com.cn/rmrb/pc` | 人民日報電子版のベース URL |
| `rate_limit_kbps` | number | `0` | ダウンロード速度上限（KB/s）、`0` = 制限なし |
| `timeout` | int | `30` | 1 回のネットワークリクエストのタイムアウト（秒） |
| `retry` | int | `3` | 失敗時のリトライ回数 |
| `retry_interval` | float | `2.0` | リトライ間隔（秒） |
| `request_interval` | float | `0.2` | リクエストごとの間隔（秒）、アクセス過多による BAN 防止 |
| `concurrent` | int | `1` | 同時ダウンロードスレッド数（1–16） |
| `proxy` | string | `""` | HTTP/HTTPS プロキシアドレス、空 = プロキシ不使用 |
| `user_agent` | string | Chrome UA | リクエスト User-Agent |

### UI

| キー | 型 | デフォルト値 | 说明 |
|---|---|---|---|
| `color_foreground` | string | `"A"` | cmd 前景色（0–F 16 進数） |
| `color_background` | string | `"0"` | cmd 背景色（0–F 16 進数） |
| `window_title` | string | `人民日报电子版下载器` | コンソールウィンドウタイトル |
| `show_progress` | bool | `true` | ダウンロード進捗バーを表示するか |

### 日付とコンテンツ

| キー | 型 | デフォルト値 | 说明 |
|---|---|---|---|
| `default_date` | string | `""` | デフォルト日付 `YYYYMMDD`、空 = 今日 |
| `default_format` | string | `"pdf"` | デフォルトフォーマット：`pdf` / `text` / `both` |
| `edition_filter` | list | `[]` | **版面ホワイトリスト**：空でない場合、リストされた版面番号のみダウンロード（例 `[1,2]` は第1、2版のみ）；空 = 全版面 |
| `holiday_skip` | bool | `false` | 单日モードで版面がない場合にサイレントスキップするか（エラーではなく 0 を返す） |

### 一括ダウンロード

| キー | 型 | デフォルト値 | 说明 |
|---|---|---|---|
| `batch_enable` | bool | `false` | `true` の場合、BAT ダブルクリックで**一括ダウンロード画面**を表示 |
| `batch_merge_mode` | string | `"each"` | `each` = 日付ごとに個別結合；`all` = 全日付を 1 つの大ファイルに結合 |
| `download_path` | string | `""` | ダウンロードルートディレクトリ；空 = スクリプトのあるフォルダ；相対パスはスクリプトディレクトリ基準、絶対パスも可 |

### 出力と結合

| キー | 型 | デフォルト値 | 说明 |
|---|---|---|---|
| `download_dir` | string | `"pdfs_{date}"` | 単版 PDF 保存ディレクトリテンプレート、`{date}` が日付に置換 |
| `merged_filename` | string | `"人民日报-{date}-完整版"` | 結合 PDF ファイル名テンプレート（拡張子なし） |
| `auto_merge` | bool | `true` | 单日モードで自動結合するか |
| `keep_singles` | bool | `true` | 結合後に単版 PDF ディレクトリを保持するか；`false` は結合成功後に自動削除 |
| `open_folder_after` | bool | `true` | 完了後にファイルの場所を自動で開くか |

### テキスト出力

| キー | 型 | デフォルト値 | 说明 |
|---|---|---|---|
| `text_output_format` | string | `"TXT"` | テキスト版出力フォーマット：`TXT` / `DOC` / `DOCX` |
| `text_filename` | string | `"人民日报-{date}-文字版"` | テキスト版ファイル名テンプレート（拡張子なし） |
| `text_include_edition` | bool | `true` | テキスト版に版面タイトル区切りを含めるか |

### ログと通知

| キー | 型 | デフォルト値 | 说明 |
|---|---|---|---|
| `log_file` | string | `"rmrb_download.log"` | ログファイル名；空 = ログ記録なし |
| `log_level` | string | `"normal"` | ログレベル：`quiet` / `normal` / `debug` |
| `beep_on_done` | bool | `false` | 完了時にビープ音を鳴らす |
| `msg_on_done` | bool | `false` | 完了時に Windows メッセージボックスを表示 |

### スケジュール

| キー | 型 | デフォルト値 | 说明 |
|---|---|---|---|
| `auto_run` | bool | `false` | 毎日の自動ダウンロードを有効にするか（先に `--task-install` で計画タスクを登録する必要あり） |
| `auto_run_time` | string | `"08:00"` | 毎日の自動実行時刻 `HH:MM` |

> 設定に不正値（負の速度制限、範囲外の同時実行数、不正なカラーコード等）がある場合、起動時に自動でデフォルト値にフォールバックし警告を表示します。クラッシュはしません。

---

## 一括ダウンロード詳細

### 日付範囲式

BAT 一括画面または `--batch` 引数で入力。カンマ区切りで複数の区間を指定可能：

| 式 | 意味 |
|---|---|
| `20260901-20260903` | 2026-09-01 ～ 2026-09-03（両端含む） |
| `20260905` | 2026-09-05 のみ |
| `20260801-` | 2026-08-01 ～**今日**（右端を空欄に） |
| `20260901-20260903,20260905` | 範囲 + 单日の組み合わせ（自動重複除去、日付順ソート） |

- 日付は実在する日付である必要があります（`20260134`、`20261301` 等は遮断されエラーになります）
- 開始日付が終了日付より後の場合はエラー
- 版面のない日付（休刊/未出版）は自動スキップされ、サマリーに計上されます

### 結合モード

| モード | 動作 | 生成物ファイル名例 |
|---|---|---|
| `each` | 日付ごとに個別ダウンロード、個別結合 | `人民日报-2026-09-02-完整版.pdf`、`人民日报-2026-09-03-完整版.pdf` |
| `all` | 全日付の版面を全て**1 つの跨日付大ファイル**に結合 | `人民日报-2026-09-02-2026-09-03-完整版.pdf` |

テキスト版も同様に `each` / `all` に対応。

### BAT 一括画面の有効化

`config.json` を編集し、`"batch_enable"` を `true` に変更。BAT をダブルクリックすると一括ダウンロード画面になります（範囲入力 → 結合モード選択 → フォーマット選択）。

---

## テキスト版出力フォーマット

| フォーマット | 说明 | 依存 |
|---|---|---|
| `TXT` | UTF-8 プレーンテキスト、版面タイトルと記事本文を含む | なし |
| `DOC` | HTML コンテンツを `.doc` として保存、Microsoft Word / WPS で直接開ける | なし |
| `DOCX` | 標準 OOXML（`zipfile` で最小ドキュメント構造を手書き）、Word/WPS/LibreOffice 全てで開ける | なし |

`config.json` で `"text_output_format": "DOCX"` 等を設定して切り替え。

---

## よくあるエラーと解決策

| エラーメッセージ | 原因 | 解決方法 |
|---|---|---|
| `未来日期，人民日报尚未出版` | 今日以降の日付を入力した | 日付を確認、または `default_date` を修正 |
| `日期不存在（月份或日期越界）` | `20261301`、`20260134` 等 | 実在する日付を入力 |
| `日期应为 8 位数字 YYYYMMDD` | 日付の桁数が不正 | `YYYYMMDD` 形式で入力、例 `20260903` |
| `未找到任何版面` | 該当日付が未出版/休刊、または `edition_filter` で版面が空になった、またはネットワーク異常 | 平日の日付に変更；`edition_filter` を確認；上部の `[网络]` プロンプトを確認 |
| `无法安装合并库 pypdf` | ネットワーク不通で pip インストール不可 | 手動で `pip install pypdf` を実行、またはプロキシ設定後にリトライ |
| `合并失败：目标文件正被占用` | 同名 PDF が PDF リーダー/エクスプローラープレビューで開かれている | 開いている同名ファイルを閉じてリトライ、または `merged_filename` / `download_path` を修正 |
| `域名解析失败 / 网络连接失败` | ネットワーク未接続、DNS 異常、またはプロキシエラー | ネットワークを確認；`config.json` の `proxy` 設定を確認 |
| `连接/读取超时` | ネットワークが遅い、またはサーバー応答が遅い | `timeout` を増やす（例 60）、後でリトライ |
| `服务器返回 HTTP 403/429` | アクセス過多でレート制限 | `request_interval` を増やす（例 1.0）、`concurrent` を下げる |
| `日期表达式错误：无效日期` | 一括式に不正日付が含まれる | `YYYYMMDD` 形式で入力、カンマ区切りで複数範囲を指定 |
| `格式参数应为 text / pdf / both` | フォーマット引数が不正 | `text` / `pdf` / `both` を使用（BAT 画面では T / PDF / B） |
| `--merge-mode 应为 each / all` | 結合モード引数が不正 | `each` または `all` を使用 |

---

## プロジェクト構造

```
rmrb_download/
├── rmrb_downloader.py      # メインスクリプト（全設定 + 一括 + PDF/テキスト）
├── 下载人民日报.bat          # Windows ダブルクリック起動器（单日/一括画面）
├── build_bat.py             # BAT ジェネレーター（GBK エンコード）
├── config.json              # 設定ファイル（初回実行時に自動生成）
├── create_shortcut.ps1      # デスクトップショートカット生成スクリプト（ICO 含む）
├── 人民日报下载器.ico        # マルチサイズアイコン（16–256）
├── icon_src.png             # アイコン元画像
├── test_errors.py           # エラー処理と境界テスト
├── test_download.py         # 実ダウンロード全量テスト
├── rmrb_download.log        # 実行ログ（自動生成）
└── pdfs_YYYYMMDD/           # 単版 PDF ディレクトリ（keep_singles=true の場合に保持）
```

---

## テスト

```bash
# エラー処理と境界テスト（ダウンロードなし、秒級）
python test_errors.py

# 実ダウンロード全量テスト（edition_filter で第1版のみにして高速化、单日/一括/各フォーマットをカバー）
python test_download.py
```

テストカバレッジ：未来日付/不正日付/不正フォーマット/一括式解析/config 検証/单日 PDF/TXT/DOC/DOCX/both/一括 each/all/今日まで構文/keep_singles/ファイル名とページ数検証。

---

## 免責事項

- 本ツールは**個人の学習と研究目的でのみ使用可能**、いかなる営利活動にも使用できません。
- 『人民日報』の著作権は人民日報社に帰属します。ダウンロードしたコンテンツは関連法規とウェブサイト利用規約を遵守してください。
- アクセス頻度（`request_interval`）を適切に制御し、公式サイトに負荷をかけないでください。
- 公式サイトの構造が変更された場合、本ツールは相应の調整が必要になる可能性があります。

---

## License

MIT License
