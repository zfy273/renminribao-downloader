# Descargador de la edición electrónica del Diario del Pueblo / People's Daily Downloader

> [中文](../README.md) | [English](README_EN.md) | [日本語](README_JA.md) | [한국어](README_KO.md) | [Français](README_FR.md) | [Deutsch](README_DE.md) | [Italiano](README_IT.md) | [हिन्दी](README_HI.md) | [ไทย](README_TH.md) | [العربية](README_AR.md) | [Русский](README_RU.md) | Español

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)]()
[![License](https://img.shields.io/badge/License-MIT-green)]()

Herramienta de descarga y fusión automática de la edición electrónica del 《Diario del Pueblo》, escrita en Python puro. Soporta descarga de páginas PDF, extracción de texto de artículos (TXT/DOC/DOCX), descarga por lotes de rangos de fechas y configuración completa. No requiere navegador ni controladores.

---

## Características

- **Modo PDF**: descarga automáticamente todas las páginas PDF del día actual y las fusiona en un único archivo completo
- **Modo texto**: extrae el texto de todos los artículos y lo exporta en `TXT` / `DOC` / `DOCX` (cero dependencias adicionales)
- **Modo both**: genera simultáneamente la versión PDF y la versión de texto
- **Descarga por lotes**: soporta expresiones de rango de fechas; fusión separada por fecha o fusión de todas las páginas en un único archivo grande entre fechas
- **Configuración completa**: más de 30 opciones de configuración (red, interfaz, salida, límite de velocidad, proxy, programación, etc.) ajustables a través de `config.json`
- **Instalación automática de dependencias**: instala automáticamente la biblioteca de fusión `pypdf` en la primera ejecución (fuente oficial → respaldo en espejo de Tsinghua)
- **Progreso en tiempo real**: barra de progreso de descarga, visualización de velocidad, apertura automática de la ubicación del archivo al finalizar
- **Gestión robusta de errores**: reintentos de red, reintentos automáticos cuando el archivo está ocupado, bloqueo de fechas futuras/fechas no válidas/expresiones no válidas, mensajes de error amigables

---

## Requisitos del sistema

| Elemento | Requisito |
|---|---|
| Sistema operativo | Windows 10 / 11 (el lanzador de lotes cmd es específico de Windows; el script principal es multiplataforma) |
| Python | **3.8 o superior** (recomendado 3.10+, verificado en 3.13 / 3.14) |
| Red | debe poder acceder a `paper.people.com.cn` |
| Navegador | **No requerido** Chrome / Edge / no se necesita ningún controlador de navegador |

### Bibliotecas dependientes

| Biblioteca | Propósito | Método de instalación |
|---|---|---|
| `pypdf` | Fusión PDF | **Instalación automática en la primera ejecución**; también se puede instalar manualmente con `pip install pypdf` |
| (ninguna) | Versión de texto TXT/DOC/DOCX | implementación en biblioteca estándar pura (OOXML escrito manualmente con `zipfile`), cero dependencias |
| `PyMuPDF` (opcional) | se usa solo para renderizar imágenes de vista previa PDF durante las pruebas | `pip install pymupdf`, no necesario para uso normal |

---

## Inicio rápido

### Método 1: doble clic en BAT (recomendado para usuarios de Windows)

1. Asegúrese de que Python esté instalado y añadido al PATH (o que el lanzador `py` esté disponible)
2. Haga doble clic en `下载人民日报.bat`
3. Introduzca la fecha según las indicaciones (Enter = hoy), elija el formato (T / PDF / B)
4. Espere a la descarga y la fusión; la ubicación del archivo se abrirá automáticamente al finalizar

### Método 2: línea de comandos

```bash
# PDF de un solo día (por defecto hoy)
python rmrb_downloader.py

# Fecha especificada + formato
python rmrb_downloader.py 20260903 pdf
python rmrb_downloader.py 20260903 text
python rmrb_downloader.py 20260903 both

# Descarga por lotes (rango de fechas, fusión separada por fecha)
python rmrb_downloader.py --batch "20260901-20260903" pdf --merge-mode each

# Descarga por lotes (todo fusionado en un único archivo grande entre fechas)
python rmrb_downloader.py --batch "20260901-20260903,20260905" both --merge-mode all

# Desde una fecha hasta hoy (extremo derecho vacío)
python rmrb_downloader.py --batch "20260801-" pdf

# Generar/actualizar la configuración por defecto
python rmrb_downloader.py --init

# Registrar/eliminar la tarea programada para descarga automática diaria
python rmrb_downloader.py --task-install
python rmrb_downloader.py --task-remove
```

---

## Descripción de la configuración (config.json)

`config.json` se genera automáticamente en la primera ejecución. Todas las opciones de configuración y su significado:

### Crawling y red

| Clave | Tipo | Valor por defecto | Descripción |
|---|---|---|---|
| `base_url` | string | `http://paper.people.com.cn/rmrb/pc` | Dirección base de la edición electrónica del Diario del Pueblo |
| `rate_limit_kbps` | number | `0` | Límite de velocidad de descarga (KB/s), `0` = ilimitado |
| `timeout` | int | `30` | Tiempo de espera para una sola solicitud de red (segundos) |
| `retry` | int | `3` | Número de reintentos en caso de fallo |
| `retry_interval` | float | `2.0` | Intervalo entre reintentos (segundos) |
| `request_interval` | float | `0.2` | Intervalo entre cada solicitud (segundos), evita el bloqueo por acceso demasiado frecuente |
| `concurrent` | int | `1` | Número de hilos de descarga simultáneos (1–16) |
| `proxy` | string | `""` | Dirección del proxy HTTP/HTTPS, vacío = sin proxy |
| `user_agent` | string | Chrome UA | User-Agent de las solicitudes |

### Interfaz

| Clave | Tipo | Valor por defecto | Descripción |
|---|---|---|---|
| `color_foreground` | string | `"A"` | Color de primer plano del cmd (0–F hexadecimal) |
| `color_background` | string | `"0"` | Color de fondo del cmd (0–F hexadecimal) |
| `window_title` | string | `人民日报电子版下载器` | Título de la ventana de consola |
| `show_progress` | bool | `true` | Mostrar o no la barra de progreso de descarga |

### Fecha y contenido

| Clave | Tipo | Valor por defecto | Descripción |
|---|---|---|---|
| `default_date` | string | `""` | Fecha por defecto `YYYYMMDD`, vacío = hoy |
| `default_format` | string | `"pdf"` | Formato por defecto: `pdf` / `text` / `both` |
| `edition_filter` | list | `[]` | **Lista blanca de páginas**: si no está vacía, solo descarga los números de página listados (ej. `[1,2]` = solo páginas 1 y 2); vacío = todas las páginas |
| `holiday_skip` | bool | `false` | En modo de un solo día, omitir silenciosamente si no hay páginas (devuelve 0 en lugar de error) |

### Descarga por lotes

| Clave | Tipo | Valor por defecto | Descripción |
|---|---|---|---|
| `batch_enable` | bool | `false` | Si es `true`, el doble clic en BAT muestra la **interfaz de descarga por lotes** |
| `batch_merge_mode` | string | `"each"` | `each` = fusión separada por fecha; `all` = fusionar todas las fechas en un único archivo grande |
| `download_path` | string | `""` | Directorio raíz de descarga; vacío = carpeta del script; ruta relativa respecto al directorio del script, ruta absoluta también aceptada |

### Salida y fusión

| Clave | Tipo | Valor por defecto | Descripción |
|---|---|---|---|
| `download_dir` | string | `"pdfs_{date}"` | Plantilla de directorio para almacenar PDF de una sola página, `{date}` se reemplaza por la fecha |
| `merged_filename` | string | `"人民日报-{date}-完整版"` | Plantilla de nombre de archivo del PDF fusionado (sin extensión) |
| `auto_merge` | bool | `true` | Fusión automática en modo de un solo día |
| `keep_singles` | bool | `true` | Mantener el directorio de PDF de una sola página después de la fusión; `false` = eliminación automática después de una fusión exitosa |
| `open_folder_after` | bool | `true` | Abrir automáticamente la ubicación del archivo al finalizar |

### Salida de texto

| Clave | Tipo | Valor por defecto | Descripción |
|---|---|---|---|
| `text_output_format` | string | `"TXT"` | Formato de salida de la versión de texto: `TXT` / `DOC` / `DOCX` |
| `text_filename` | string | `"人民日报-{date}-文字版"` | Plantilla de nombre de archivo de la versión de texto (sin extensión) |
| `text_include_edition` | bool | `true` | Incluir o no separadores de título de página en la versión de texto |

### Registro y notificaciones

| Clave | Tipo | Valor por defecto | Descripción |
|---|---|---|---|
| `log_file` | string | `"rmrb_download.log"` | Nombre del archivo de registro; vacío = sin registro |
| `log_level` | string | `"normal"` | Nivel de registro: `quiet` / `normal` / `debug` |
| `beep_on_done` | bool | `false` | Emitir un pitido al finalizar |
| `msg_on_done` | bool | `false` | Mostrar un cuadro de mensaje de Windows al finalizar |

### Programación

| Clave | Tipo | Valor por defecto | Descripción |
|---|---|---|---|
| `auto_run` | bool | `false` | Activar la descarga automática diaria (requiere primero registrar la tarea programada con `--task-install`) |
| `auto_run_time` | string | `"08:00"` | Hora de ejecución automática diaria `HH:MM` |

> Los valores de configuración no válidos (como límite de velocidad negativo, concurrencia fuera de rango, códigos de color no válidos) se restauran automáticamente a los valores por defecto al iniciar y se imprime una advertencia, sin causar un cierre.

---

## Detalles de la descarga por lotes

### Expresión de rango de fechas

Se introduce en la interfaz de lotes de BAT o con el argumento `--batch`. Varios segmentos separados por comas:

| Expresión | Significado |
|---|---|
| `20260901-20260903` | 2026-09-01 a 2026-09-03 (incluyendo ambos extremos) |
| `20260905` | Solo 2026-09-05 |
| `20260801-` | 2026-08-01 a **hoy** (extremo derecho vacío) |
| `20260901-20260903,20260905` | Combinación de rango + día único (eliminación automática de duplicados, ordenación por fecha) |

- Las fechas deben ser fechas realmente existentes (ej. `20260134`, `20261301` se bloquean y se notifican como error)
- Una fecha de inicio posterior a la fecha de fin causa un error
- Las fechas sin páginas (no publicadas/no salidas) se omiten automáticamente y se contabilizan en el resumen

### Modo de fusión

| Modo | Comportamiento | Ejemplo de nombre de archivo generado |
|---|---|---|
| `each` | Descarga y fusión separadas para cada fecha | `人民日报-2026-09-02-完整版.pdf`, `人民日报-2026-09-03-完整版.pdf` |
| `all` | Todas las páginas de todas las fechas fusionadas en **un único archivo grande entre fechas** | `人民日报-2026-09-02-2026-09-03-完整版.pdf` |

La versión de texto también soporta `each` / `all`.

### Activar la interfaz de lotes de BAT

Edite `config.json`, establezca `"batch_enable"` en `true`. El doble clic en BAT entra en la interfaz de descarga por lotes (introducir rango → elegir modo de fusión → elegir formato).

---

## Formatos de salida de la versión de texto

| Formato | Descripción | Dependencia |
|---|---|---|
| `TXT` | Texto plano UTF-8, incluye títulos de página y texto de artículos | ninguna |
| `DOC` | Contenido HTML guardado como `.doc`, se abre directamente con Microsoft Word / WPS | ninguna |
| `DOCX` | OOXML estándar (estructura de documento mínima escrita manualmente con `zipfile`), se abre con Word/WPS/LibreOffice | ninguna |

Cambie el formato estableciendo `"text_output_format": "DOCX"` etc. en `config.json`.

---

## Errores comunes y soluciones

| Mensaje de error | Causa | Solución |
|---|---|---|
| `未来日期，人民日报尚未出版` | Se introdujo una fecha posterior a hoy | Verifique la fecha o edite `default_date` |
| `日期不存在（月份或日期越界）` | ej. `20261301`, `20260134` | Introduzca una fecha realmente existente |
| `日期应为 8 位数字 YYYYMMDD` | Número incorrecto de dígitos de la fecha | Introduzca en formato `YYYYMMDD`, ej. `20260903` |
| `未找到任何版面` | Fecha no publicada/no salida, o `edition_filter` vació las páginas, o anomalía de red | Cambie a una fecha de día laborable; verifique `edition_filter`; consulte el aviso `[网络]` arriba |
| `无法安装合并库 pypdf` | Red no disponible, no se puede instalar a través de pip | Ejecute manualmente `pip install pypdf`, o reintente después de configurar un proxy |
| `合并失败：目标文件正被占用` | PDF con el mismo nombre está abierto en un lector PDF / vista previa del Explorer | Cierre el archivo con el mismo nombre que esté abierto y reintente, o edite `merged_filename` / `download_path` |
| `域名解析失败 / 网络连接失败` | Red no conectada, anomalía DNS o error de proxy | Verifique la red; verifique la configuración `proxy` en `config.json` |
| `连接/读取超时` | Red lenta o respuesta lenta del servidor | Aumente `timeout` (ej. 60), reintente más tarde |
| `服务器返回 HTTP 403/429` | Acceso demasiado frecuente, limitación de velocidad | Aumente `request_interval` (ej. 1.0), disminuya `concurrent` |
| `日期表达式错误：无效日期` | La expresión de lotes contiene una fecha no válida | Introduzca en formato `YYYYMMDD`, separe varios rangos con comas |
| `格式参数应为 text / pdf / both` | Argumento de formato incorrecto | Use `text` / `pdf` / `both` (interfaz BAT: T / PDF / B) |
| `--merge-mode 应为 each / all` | Argumento de modo de fusión incorrecto | Use `each` o `all` |

---

## Estructura del proyecto

```
rmrb_download/
├── rmrb_downloader.py      # Script principal (configuración completa + lotes + PDF/texto)
├── 下载人民日报.bat          # Lanzador de Windows con doble clic (interfaz de un solo día/lotes)
├── build_bat.py             # Generador BAT (codificación GBK)
├── config.json              # Archivo de configuración (generado automáticamente en la primera ejecución)
├── create_shortcut.ps1      # Script de creación de acceso directo de escritorio (con ICO)
├── 人民日报下载器.ico        # Icono de múltiples tamaños (16–256)
├── icon_src.png             # Imagen fuente del icono
├── test_errors.py           # Pruebas de gestión de errores y límites
├── test_download.py         # Pruebas completas de descarga real
├── rmrb_download.log        # Registro de ejecución (generado automáticamente)
└── pdfs_YYYYMMDD/           # Directorio de PDF de una sola página (se mantiene si keep_singles=true)
```

---

## Pruebas

```bash
# Pruebas de gestión de errores y límites (sin descarga, instantáneo)
python test_errors.py

# Pruebas completas de descarga real (use edition_filter para mantener solo la página 1 y acelerar, cubre un solo día/lotes/cada formato)
python test_download.py
```

Cobertura de pruebas: fecha futura/fecha no válida/formato no válido/análisis de expresión de lotes/validación de config/PDF de un solo día/TXT/DOC/DOCX/both/lotes each/all/sintaxis hasta hoy/keep_singles/verificación de nombre de archivo y número de páginas.

---

## Aviso legal

- Esta herramienta **solo está destinada al aprendizaje y la investigación personales**, no puede utilizarse para ninguna actividad comercial.
- Los derechos de autor del 《Diario del Pueblo》 pertenecen a la Editorial del Diario del Pueblo. El contenido descargado debe cumplir con las leyes correspondientes y los términos de uso del sitio web.
- Por favor, controle razonablemente la frecuencia de acceso (`request_interval`) para evitar sobrecargar el sitio oficial.
- Si la estructura del sitio oficial cambia, esta herramienta puede requerir ajustes correspondientes.

---

## License

MIT License
