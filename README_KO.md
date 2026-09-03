# 인민일보 전자판 다운로더 / People's Daily Downloader

> [中文](README.md) | [English](README_EN.md) | [日本語](README_JA.md) | 한국어 | [Français](README_FR.md) | [Deutsch](README_DE.md) | [Italiano](README_IT.md) | [हिन्दी](README_HI.md) | [ไทย](README_TH.md) | [العربية](README_AR.md) | [Русский](README_RU.md) | [Español](README_ES.md)

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)]()
[![License](https://img.shields.io/badge/License-MIT-green)]()

순수 Python으로 작성된 《인민일보》 전자판 자동 다운로드 및 병합 도구. PDF 지면 다운로드, 기사 본문 추출(TXT/DOC/DOCX), 날짜 범위 일괄 다운로드, 완전 설정화를 지원. 브라우저나 드라이버가 필요 없습니다.

---

## 기능

- **PDF 모드**: 당일 전체 지면 PDF를 자동 다운로드하고 하나의 완전판 파일로 병합
- **텍스트 모드**: 전체 지면 기사 본문을 추출하여 `TXT` / `DOC` / `DOCX`로 출력(추가 의존성 제로)
- **both 모드**: PDF와 텍스트판을 동시에 생성
- **일괄 다운로드**: 날짜 범위 식 지원. 날짜별 개별 병합 또는 전체를 하나의 날짜 간격 대용량 파일로 병합 가능
- **완전 설정화**: 30+ 설정 항목(네트워크, UI, 출력, 속도 제한, 프록시, 스케줄 등)을 `config.json`으로 조정
- **의존성 자동 설치**: 첫 실행 시 `pypdf` 병합 라이브러리를 자동 설치(공식 소스 → 칭화 미러 폴백)
- **실시간 진행률**: 다운로드 진행률 바, 속도 표시, 완료 후 파일 위치 자동 열기
- **견고한 오류 처리**: 네트워크 재시도, 파일 점유 자동 재시도, 미래 날짜/잘못된 날짜/무효 식 차단, 친절한 오류 메시지

---

## 환경 요구사항

| 항목 | 요구사항 |
|---|---|
| 운영체제 | Windows 10 / 11(cmd 배치 실행기는 Windows 전용; 핵심 스크립트는 크로스 플랫폼) |
| Python | **3.8 이상**(권장 3.10+, 3.13 / 3.14에서 검증됨) |
| 네트워크 | `paper.people.com.cn`에 접근 가능해야 함 |
| 브라우저 | **필요 없음** Chrome / Edge / 어떤 브라우저 드라이버도 필요 없음 |

### 의존 라이브러리

| 라이브러리 | 용도 | 설치 방법 |
|---|---|---|
| `pypdf` | PDF 병합 | **첫 실행 시 자동 설치**; 수동으로 `pip install pypdf`도 가능 |
| (없음) | 텍스트판 TXT/DOC/DOCX | 순수 표준 라이브러리 구현(`zipfile`으로 OOXML 직접 작성), 의존성 제로 |
| `PyMuPDF`(선택) | 테스트 시 PDF 미리보기 이미지 렌더링에만 사용 | `pip install pymupdf`, 일반 사용에는 불필요 |

---

## 빠른 시작

### 방법 1: BAT 더블클릭(Windows 사용자 권장)

1. Python이 설치되고 PATH에 추가되었는지 확인(또는 `py` 런처 사용 가능)
2. `下载人民日报.bat`를 더블클릭
3. 프롬프트에 따라 날짜 입력(Enter = 오늘), 형식 선택(T / PDF / B)
4. 다운로드와 병합이 완료되면 파일 위치가 자동으로 열림

### 방법 2: 명령줄

```bash
# 단일일 PDF(기본 오늘)
python rmrb_downloader.py

# 날짜 지정 + 형식
python rmrb_downloader.py 20260903 pdf
python rmrb_downloader.py 20260903 text
python rmrb_downloader.py 20260903 both

# 일괄 다운로드(날짜 범위, 날짜별 개별 병합)
python rmrb_downloader.py --batch "20260901-20260903" pdf --merge-mode each

# 일괄 다운로드(전체를 하나의 날짜 간격 대용량 파일로 병합)
python rmrb_downloader.py --batch "20260901-20260903,20260905" both --merge-mode all

# 특정 날짜부터 오늘까지(우측 비움)
python rmrb_downloader.py --batch "20260801-" pdf

# 기본 설정 생성/새로고침
python rmrb_downloader.py --init

# 매일 자동 다운로드 예약 작업 등록/삭제
python rmrb_downloader.py --task-install
python rmrb_downloader.py --task-remove
```

---

## 설정 설명(config.json)

첫 실행 시 `config.json`이 자동 생성됩니다. 모든 설정 항목과 의미는 다음과 같습니다:

### 크롤링 및 네트워크

| 키 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `base_url` | string | `http://paper.people.com.cn/rmrb/pc` | 인민일보 전자판 기본 주소 |
| `rate_limit_kbps` | number | `0` | 다운로드 속도 상한(KB/s), `0` = 무제한 |
| `timeout` | int | `30` | 단일 네트워크 요청 제한 시간(초) |
| `retry` | int | `3` | 실패 시 재시도 횟수 |
| `retry_interval` | float | `2.0` | 재시도 간격(초) |
| `request_interval` | float | `0.2` | 요청 간 간격(초), 과도한 접근으로 차단 방지 |
| `concurrent` | int | `1` | 동시 다운로드 스레드 수(1–16) |
| `proxy` | string | `""` | HTTP/HTTPS 프록시 주소, 비움 = 프록시 미사용 |
| `user_agent` | string | Chrome UA | 요청 User-Agent |

### UI

| 키 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `color_foreground` | string | `"A"` | cmd 전경색(0–F 16진수) |
| `color_background` | string | `"0"` | cmd 배경색(0–F 16진수) |
| `window_title` | string | `人民日报电子版下载器` | 콘솔 창 제목 |
| `show_progress` | bool | `true` | 다운로드 진행률 바 표시 여부 |

### 날짜 및 콘텐츠

| 키 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `default_date` | string | `""` | 기본 날짜 `YYYYMMDD`, 비움 = 오늘 |
| `default_format` | string | `"pdf"` | 기본 형식: `pdf` / `text` / `both` |
| `edition_filter` | list | `[]` | **지면 화이트리스트**: 비어있지 않으면 나열된 지면 번호만 다운로드(예 `[1,2]`는 1,2면만); 비움 = 전체 지면 |
| `holiday_skip` | bool | `false` | 단일일 모드에서 지면이 없을 때 조용히 건너뛸지(오류 대신 0 반환) |

### 일괄 다운로드

| 키 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `batch_enable` | bool | `false` | `true`면 BAT 더블클릭 시 **일괄 다운로드 화면** 표시 |
| `batch_merge_mode` | string | `"each"` | `each` = 날짜별 개별 병합; `all` = 전체 날짜를 하나의 대용량 파일로 병합 |
| `download_path` | string | `""` | 다운로드 루트 디렉토리; 비움 = 스크립트所在 폴더; 상대 경로는 스크립트 디렉토리 기준, 절대 경로도 가능 |

### 출력 및 병합

| 키 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `download_dir` | string | `"pdfs_{date}"` | 단일판 PDF 저장 디렉토리 템플릿, `{date}`가 날짜로 치환 |
| `merged_filename` | string | `"人民日报-{date}-完整版"` | 병합 PDF 파일명 템플릿(확장자 제외) |
| `auto_merge` | bool | `true` | 단일일 모드에서 자동 병합 여부 |
| `keep_singles` | bool | `true` | 병합 후 단일판 PDF 디렉토리 유지 여부; `false`는 병합 성공 후 자동 삭제 |
| `open_folder_after` | bool | `true` | 완료 후 파일 위치 자동 열기 여부 |

### 텍스트 출력

| 키 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `text_output_format` | string | `"TXT"` | 텍스트판 출력 형식: `TXT` / `DOC` / `DOCX` |
| `text_filename` | string | `"人民日报-{date}-文字版"` | 텍스트판 파일명 템플릿(확장자 제외) |
| `text_include_edition` | bool | `true` | 텍스트판에 지면 제목 구분 포함 여부 |

### 로그 및 알림

| 키 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `log_file` | string | `"rmrb_download.log"` | 로그 파일명; 비움 = 로그 기록 안 함 |
| `log_level` | string | `"normal"` | 로그 레벨: `quiet` / `normal` / `debug` |
| `beep_on_done` | bool | `false` | 완료 시 비프음 |
| `msg_on_done` | bool | `false` | 완료 시 Windows 메시지 박스 표시 |

### 스케줄

| 키 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `auto_run` | bool | `false` | 매일 자동 다운로드 활성화 여부(먼저 `--task-install`로 예약 작업 등록 필요) |
| `auto_run_time` | string | `"08:00"` | 매일 자동 실행 시간 `HH:MM` |

> 설정에 잘못된 값(음수 속도 제한, 범위 초과 동시 실행 수, 잘못된 색상 코드 등)이 있으면 시작 시 자동으로 기본값으로 폴백하고 경고를 표시합니다. 크래시되지 않습니다.

---

## 일괄 다운로드 상세

### 날짜 범위 식

BAT 일괄 화면 또는 `--batch` 인수에 입력. 쉼표로 구분하여 여러 구간 지정 가능:

| 식 | 의미 |
|---|---|
| `20260901-20260903` | 2026-09-01 ~ 2026-09-03(양 끝 포함) |
| `20260905` | 2026-09-05 단일일만 |
| `20260801-` | 2026-08-01 ~ **오늘**(우측 비움) |
| `20260901-20260903,20260905` | 범위 + 단일일 조합(자동 중복 제거, 날짜순 정렬) |

- 날짜는 실제 존재하는 날짜여야 함(`20260134`, `20261301` 등은 차단되어 오류)
- 시작 날짜가 종료 날짜보다 늦으면 오류
- 지면이 없는 날짜(휴간/미출판)는 자동 건너뛰고 요약에 계상

### 병합 모드

| 모드 | 동작 | 생성물 파일명 예 |
|---|---|---|
| `each` | 날짜별 개별 다운로드, 개별 병합 | `人民日报-2026-09-02-完整版.pdf`, `人民日报-2026-09-03-完整版.pdf` |
| `all` | 모든 날짜의 지면을 전부 **하나의 날짜 간격 대용량 파일**로 병합 | `人民日报-2026-09-02-2026-09-03-完整版.pdf` |

텍스트판도 동일하게 `each` / `all` 지원.

### BAT 일괄 화면 활성화

`config.json`을 편집하여 `"batch_enable"`을 `true`로 변경. BAT를 더블클릭하면 일괄 다운로드 화면으로 진입(범위 입력 → 병합 모드 선택 → 형식 선택).

---

## 텍스트판 출력 형식

| 형식 | 설명 | 의존 |
|---|---|---|
| `TXT` | UTF-8 순수 텍스트, 지면 제목과 기사 본문 포함 | 없음 |
| `DOC` | HTML 콘텐츠를 `.doc`로 저장, Microsoft Word / WPS에서 직접 열기 가능 | 없음 |
| `DOCX` | 표준 OOXML(`zipfile`로 최소 문서 구조 직접 작성), Word/WPS/LibreOffice 모두 열기 가능 | 없음 |

`config.json`에서 `"text_output_format": "DOCX"` 등으로 설정하여 전환.

---

## 자주 발생하는 오류 및 해결책

| 오류 메시지 | 원인 | 해결 방법 |
|---|---|---|
| `未来日期，人民日报尚未出版` | 오늘 이후 날짜를 입력함 | 날짜 확인, 또는 `default_date` 수정 |
| `日期不存在（月份或日期越界）` | `20261301`, `20260134` 등 | 실제 존재하는 날짜 입력 |
| `日期应为 8 位数字 YYYYMMDD` | 날짜 자릿수가 잘못됨 | `YYYYMMDD` 형식으로 입력, 예 `20260903` |
| `未找到任何版面` | 해당 날짜 미출판/휴간, 또는 `edition_filter`로 지면이 비게 됨, 또는 네트워크 이상 | 평일 날짜로 변경; `edition_filter` 확인; 상단 `[网络]` 프롬프트 확인 |
| `无法安装合并库 pypdf` | 네트워크 불통으로 pip 설치 불가 | 수동으로 `pip install pypdf` 실행, 또는 프록시 설정 후 재시도 |
| `合并失败：目标文件正被占用` | 같은 이름 PDF가 PDF 리더/탐색기 미리보기에서 열려 있음 | 열려 있는 같은 이름 파일을 닫고 재시도, 또는 `merged_filename` / `download_path` 수정 |
| `域名解析失败 / 网络连接失败` | 네트워크 미연결, DNS 이상, 또는 프록시 오류 | 네트워크 확인; `config.json`의 `proxy` 설정 확인 |
| `连接/读取超时` | 네트워크가 느리거나 서버 응답이 느림 | `timeout` 증가(예 60), 나중에 재시도 |
| `服务器返回 HTTP 403/429` | 접근 과다로 속도 제한 | `request_interval` 증가(예 1.0), `concurrent` 감소 |
| `日期表达式错误：无效日期` | 일괄 식에 잘못된 날짜가 포함됨 | `YYYYMMDD` 형식으로 입력, 쉼표로 여러 범위 구분 |
| `格式参数应为 text / pdf / both` | 형식 인수 오류 | `text` / `pdf` / `both` 사용(BAT 화면에서는 T / PDF / B) |
| `--merge-mode 应为 each / all` | 병합 모드 인수 오류 | `each` 또는 `all` 사용 |

---

## 프로젝트 구조

```
rmrb_download/
├── rmrb_downloader.py      # 메인 스크립트(전체 설정 + 일괄 + PDF/텍스트)
├── 下载人民日报.bat          # Windows 더블클릭 실행기(단일일/일괄 화면)
├── build_bat.py             # BAT 생성기(GBK 인코딩)
├── config.json              # 설정 파일(첫 실행 시 자동 생성)
├── create_shortcut.ps1      # 바탕화면 바로가기 생성 스크립트(ICO 포함)
├── 人民日报下载器.ico        # 멀티 사이즈 아이콘(16–256)
├── icon_src.png             # 아이콘 원본 이미지
├── test_errors.py           # 오류 처리 및 경계 테스트
├── test_download.py         # 실제 다운로드 전체 테스트
├── rmrb_download.log        # 실행 로그(자동 생성)
└── pdfs_YYYYMMDD/           # 단일판 PDF 디렉토리(keep_singles=true 시 유지)
```

---

## 테스트

```bash
# 오류 처리 및 경계 테스트(다운로드 없음, 초 단위)
python test_errors.py

# 실제 다운로드 전체 테스트(edition_filter로 1면만 남겨 속도 향상, 단일일/일괄/각 형식 커버)
python test_download.py
```

테스트 커버리지: 미래 날짜/잘못된 날짜/잘못된 형식/일괄 식 분석/config 검증/단일일 PDF/TXT/DOC/DOCX/both/일괄 each/all/오늘까지 구문/keep_singles/파일명 및 페이지 수 검증.

---

## 면책 조항

- 본 도구는 **개인 학습 및 연구 목적으로만 사용 가능**, 어떠한 상업 활동에도 사용할 수 없습니다.
- 《인민일보》 저작권은 인민일보사에 귀속. 다운로드한 콘텐츠는 관련 법규 및 웹사이트 이용 약관을 준수하십시오.
- 접근 빈도(`request_interval`)를 적절히 제어하여 공식 사이트에 부하를 주지 마십시오.
- 공식 사이트 구조가 변경되면 본 도구는相应의 조정이 필요할 수 있습니다.

---

## License

MIT License
