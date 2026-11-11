# 人民日报电子版下载器

[![Rust](https://img.shields.io/badge/Rust-1.99%2B-orange)](https://www.rust-lang.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey)]()
[![License](https://img.shields.io/badge/License-MIT-green)]()

使用 Rust 编写的《人民日报》电子版下载器。支持 PDF 版面下载与合并、文章正文抓取、批量日期下载和 TOML 配置，无需浏览器或驱动。

## 功能

- 下载并合并指定日期的全部 PDF 版面
- 抓取文章正文并输出 TXT 或 MD，所有产物统一保存到 `output/`
- 支持单日和批量日期范围下载
- 支持按日期分别合并，或合并为跨日期文件
- 通过 `config.toml` 配置网络、代理、限速、输出和日志
- 支持网络重试、版面筛选和完成后打开输出目录

## 环境要求

- Linux、macOS 或 Windows 10/11
- Rust stable 工具链
- 能够访问 `paper.people.com.cn`

## 快速开始

### 从源码运行

```bash
# 生成默认配置
cargo run -- init

# 交互式下载
cargo run

# 下载今日 PDF
cargo run -- download

# 下载指定日期的 PDF、文字版或两者
cargo run -- download 20260903 pdf
cargo run -- download 20260903 text
cargo run -- download 20260903 both

# 批量下载，每个日期单独合并
cargo run -- batch --dates "20260901-20260903" pdf --merge-mode each

# 批量下载并合并为一个跨日期文件
cargo run -- batch --dates "20260901-20260903,20260905" both --merge-mode all
```

构建发布版本：

```bash
cargo build --release
```

可执行文件位于 `target/release/rmrb-downloader`。将其与 `config.toml` 放在同一目录后运行：

```bash
./rmrb-downloader
```

首次运行会自动生成默认的 `config.toml`。也可以使用 `init` 子命令重新生成或更新配置。

## 配置

配置文件为程序所在目录的 `config.toml`。常用配置如下：

| 配置项 | 说明 |
|---|---|
| `[network]` | 网络地址、超时、重试、限速和代理 |
| `[interface]` | 控制台颜色、窗口标题和进度显示 |
| `[task]` | 默认日期、下载格式、版面筛选和批量任务 |
| `[output]` | 输出路径、PDF 合并和文字版格式 |
| `[logging]` | 日志级别、日志文件和完成提示 |

例如，网络超时配置为 `network.timeout`，默认格式配置为
`task.default_format`，输出根目录配置为 `output.download_path`。

完整默认配置见 [config.toml](config.toml)。


## 批量日期表达式

`--dates` 支持逗号分隔的日期或日期范围：

| 表达式 | 含义 |
|---|---|
| `20260901-20260903` | 下载 2026-09-01 至 2026-09-03 |
| `20260905` | 只下载指定日期 |
| `20260801-` | 从指定日期下载到今天 |
| `20260901-20260903,20260905` | 日期范围与单日组合，自动去重排序 |

`--merge-mode` 可选 `each` 或 `all`：

- `each`：每个日期分别生成结果文件
- `all`：将所有日期的结果合并为一个文件


## 测试

```bash
cargo test
```

## 免责声明

- 本工具仅供个人学习和研究使用，不得用于任何商业活动。
- 《人民日报》版权归人民日报社所有，下载内容请遵守相关法律法规与网站使用条款。
- 请合理控制访问频率，避免对官网造成压力。

## License

MIT License
