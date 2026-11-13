use anyhow::{Context, Result, bail};
use clap::ValueEnum;
use figment::{
    Figment,
    providers::{Format as ConfigFormat, Serialized, Toml},
};
use serde::{Deserialize, Serialize};
use std::{fmt, fs, path::PathBuf, str::FromStr};

#[derive(Clone, Copy, Debug, PartialEq, Eq, ValueEnum, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
#[value(rename_all = "lowercase")]
pub enum Format {
    Text,
    Md,
    Pdf,
}

impl Format {
    pub fn wants_pdf(self) -> bool {
        self == Self::Pdf
    }

    pub fn text_kind(self) -> Option<TextKind> {
        match self {
            Self::Md => Some(TextKind::Md),
            Self::Text => Some(TextKind::Txt),
            Self::Pdf => None,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Outputs {
    pub pdf: bool,
    pub kinds: Vec<TextKind>,
}

impl Outputs {
    pub fn from_format(format: Format) -> Self {
        Self {
            pdf: format.wants_pdf(),
            kinds: format.text_kind().into_iter().collect(),
        }
    }

    pub fn from_formats(formats: &[Format]) -> Result<Self> {
        let mut outputs = Self {
            pdf: false,
            kinds: Vec::new(),
        };
        for format in formats {
            outputs.pdf |= format.wants_pdf();
            if let Some(kind) = format.text_kind()
                && !outputs.kinds.contains(&kind)
            {
                outputs.kinds.push(kind);
            }
        }
        if !outputs.pdf && outputs.kinds.is_empty() {
            bail!("至少选择一种输出");
        }
        Ok(outputs)
    }

    pub fn wants_text(&self) -> bool {
        !self.kinds.is_empty()
    }

    pub fn label(&self) -> String {
        let mut parts = Vec::new();
        if self.pdf {
            parts.push("pdf");
        }
        for kind in &self.kinds {
            parts.push(match kind {
                TextKind::Txt => "txt",
                TextKind::Md => "md",
            });
        }
        parts.join("+")
    }
}

impl fmt::Display for Outputs {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(&self.label())
    }
}

impl fmt::Display for Format {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(match self {
            Self::Text => "text",
            Self::Md => "md",
            Self::Pdf => "pdf",
        })
    }
}

impl FromStr for Format {
    type Err = anyhow::Error;

    fn from_str(value: &str) -> Result<Self> {
        match value.trim().to_ascii_lowercase().as_str() {
            "text" | "txt" | "t" => Ok(Self::Text),
            "md" | "markdown" | "m" => Ok(Self::Md),
            "pdf" | "p" => Ok(Self::Pdf),
            "both" | "b" => bail!("已不再支持 both，请同时指定 pdf、text 或 md"),
            _ => bail!("格式应为 text / md / pdf"),
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum TextKind {
    Txt,
    Md,
}

impl TextKind {
    pub fn markdown(self) -> bool {
        self == Self::Md
    }

    pub fn extension(self) -> &'static str {
        match self {
            Self::Txt => "txt",
            Self::Md => "md",
        }
    }
}

impl fmt::Display for TextKind {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(match self {
            Self::Txt => "TXT",
            Self::Md => "MD",
        })
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, ValueEnum, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
#[value(rename_all = "lowercase")]
pub enum MergeMode {
    Each,
    All,
}

impl fmt::Display for MergeMode {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(match self {
            Self::Each => "each",
            Self::All => "all",
        })
    }
}

impl FromStr for MergeMode {
    type Err = anyhow::Error;

    fn from_str(value: &str) -> Result<Self> {
        match value.trim().to_ascii_lowercase().as_str() {
            "each" | "e" => Ok(Self::Each),
            "all" | "a" => Ok(Self::All),
            _ => bail!("合并模式应为 each / all"),
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LogLevel {
    Error,
    Warn,
    Info,
    Debug,
    Trace,
}

impl LogLevel {
    pub fn filter(self) -> &'static str {
        match self {
            Self::Error => "error",
            Self::Warn => "warn",
            Self::Info => "info",
            Self::Debug => "debug",
            Self::Trace => "trace",
        }
    }
}

impl fmt::Display for LogLevel {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(match self {
            Self::Error => "error",
            Self::Warn => "warn",
            Self::Info => "info",
            Self::Debug => "debug",
            Self::Trace => "trace",
        })
    }
}

impl FromStr for LogLevel {
    type Err = anyhow::Error;

    fn from_str(value: &str) -> Result<Self> {
        match value.trim().to_ascii_lowercase().as_str() {
            "error" => Ok(Self::Error),
            "warn" => Ok(Self::Warn),
            "info" => Ok(Self::Info),
            "debug" => Ok(Self::Debug),
            "trace" => Ok(Self::Trace),
            _ => bail!("日志级别应为 error / warn / info / debug / trace"),
        }
    }
}

#[derive(Clone, Debug)]
pub struct Config {
    pub base_url: String,
    pub rate_limit_kbps: f64,
    pub timeout: u64,
    pub retry: u32,
    pub retry_interval: f64,
    pub request_interval: f64,
    pub concurrent: usize,
    pub proxy: String,
    pub user_agent: String,
    pub show_progress: bool,
    pub default_date: String,
    pub default_format: Format,
    pub edition_filter: Vec<u32>,
    pub holiday_skip: bool,
    pub batch_merge_mode: MergeMode,
    pub download_path: String,
    pub download_dir: String,
    pub merged_filename: String,
    pub auto_merge: bool,
    pub keep_singles: bool,
    pub open_folder_after: bool,
    pub text_filename: String,
    pub text_include_edition: bool,
    pub log_file: String,
    pub log_level: LogLevel,
    pub beep_on_done: bool,
    warnings: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
struct ConfigFile {
    network: NetworkConfig,
    interface: InterfaceConfig,
    task: TaskConfig,
    output: OutputConfig,
    logging: LoggingConfig,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
struct NetworkConfig {
    base_url: String,
    rate_limit_kbps: f64,
    timeout: u64,
    retry: u32,
    retry_interval: f64,
    request_interval: f64,
    concurrent: usize,
    proxy: String,
    user_agent: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
struct InterfaceConfig {
    show_progress: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
struct TaskConfig {
    default_date: String,
    default_format: String,
    edition_filter: Vec<u32>,
    holiday_skip: bool,
    batch_merge_mode: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
struct OutputConfig {
    download_path: String,
    download_dir: String,
    merged_filename: String,
    auto_merge: bool,
    keep_singles: bool,
    open_folder_after: bool,
    text_filename: String,
    text_include_edition: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
struct LoggingConfig {
    log_file: String,
    log_level: String,
    beep_on_done: bool,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            base_url: "http://paper.people.com.cn/rmrb/pc".into(),
            rate_limit_kbps: 0.0,
            timeout: 30,
            retry: 3,
            retry_interval: 2.0,
            request_interval: 0.2,
            concurrent: 1,
            proxy: String::new(),
            user_agent: "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36".into(),
            show_progress: true,
            default_date: String::new(),
            default_format: Format::Pdf,
            edition_filter: Vec::new(),
            holiday_skip: false,
            batch_merge_mode: MergeMode::Each,
            download_path: "output".into(),
                        download_dir: "{date}".into(),
            merged_filename: "人民日报-{date}-完整版".into(),
            auto_merge: true,
            keep_singles: false,
            open_folder_after: true,
            text_filename: "人民日报-{date}-文字版".into(),
            text_include_edition: true,
            log_file: "rmrb_download.log".into(),
            log_level: LogLevel::Info,
            beep_on_done: false,
            warnings: Vec::new(),
        }
    }
}

impl From<&Config> for ConfigFile {
    fn from(config: &Config) -> Self {
        Self {
            network: NetworkConfig {
                base_url: config.base_url.clone(),
                rate_limit_kbps: config.rate_limit_kbps,
                timeout: config.timeout,
                retry: config.retry,
                retry_interval: config.retry_interval,
                request_interval: config.request_interval,
                concurrent: config.concurrent,
                proxy: config.proxy.clone(),
                user_agent: config.user_agent.clone(),
            },
            interface: InterfaceConfig {
                show_progress: config.show_progress,
            },
            task: TaskConfig {
                default_date: config.default_date.clone(),
                default_format: config.default_format.to_string(),
                edition_filter: config.edition_filter.clone(),
                holiday_skip: config.holiday_skip,
                batch_merge_mode: config.batch_merge_mode.to_string(),
            },
            output: OutputConfig {
                download_path: config.download_path.clone(),
                download_dir: config.download_dir.clone(),
                merged_filename: config.merged_filename.clone(),
                auto_merge: config.auto_merge,
                keep_singles: config.keep_singles,
                open_folder_after: config.open_folder_after,
                text_filename: config.text_filename.clone(),
                text_include_edition: config.text_include_edition,
            },
            logging: LoggingConfig {
                log_file: config.log_file.clone(),
                log_level: config.log_level.to_string(),
                beep_on_done: config.beep_on_done,
            },
        }
    }
}

impl From<ConfigFile> for Config {
    fn from(file: ConfigFile) -> Self {
        let mut warnings = Vec::new();
        Self {
            base_url: file.network.base_url,
            rate_limit_kbps: file.network.rate_limit_kbps,
            timeout: file.network.timeout,
            retry: file.network.retry,
            retry_interval: file.network.retry_interval,
            request_interval: file.network.request_interval,
            concurrent: file.network.concurrent,
            proxy: file.network.proxy,
            user_agent: file.network.user_agent,
            show_progress: file.interface.show_progress,
            default_date: file.task.default_date,
            default_format: parse_or_default(&file.task.default_format, Format::Pdf, &mut warnings),
            edition_filter: file.task.edition_filter,
            holiday_skip: file.task.holiday_skip,
            batch_merge_mode: parse_or_default(
                &file.task.batch_merge_mode,
                MergeMode::Each,
                &mut warnings,
            ),
            download_path: file.output.download_path,
            download_dir: file.output.download_dir,
            merged_filename: file.output.merged_filename,
            auto_merge: file.output.auto_merge,
            keep_singles: file.output.keep_singles,
            open_folder_after: file.output.open_folder_after,
            text_filename: file.output.text_filename,
            text_include_edition: file.output.text_include_edition,
            log_file: file.logging.log_file,
            log_level: parse_or_default(&file.logging.log_level, LogLevel::Info, &mut warnings),
            beep_on_done: file.logging.beep_on_done,
            warnings,
        }
    }
}

fn parse_or_default<T>(value: &str, default: T, warnings: &mut Vec<String>) -> T
where
    T: FromStr + fmt::Display,
    <T as FromStr>::Err: fmt::Display,
{
    match value.parse() {
        Ok(parsed) => parsed,
        Err(error) => {
            warnings.push(format!("{error:#}，恢复默认值 {default}"));
            default
        }
    }
}

impl Default for ConfigFile {
    fn default() -> Self {
        Self::from(&Config::default())
    }
}

impl Default for NetworkConfig {
    fn default() -> Self {
        let config = Config::default();
        Self {
            base_url: config.base_url,
            rate_limit_kbps: config.rate_limit_kbps,
            timeout: config.timeout,
            retry: config.retry,
            retry_interval: config.retry_interval,
            request_interval: config.request_interval,
            concurrent: config.concurrent,
            proxy: config.proxy,
            user_agent: config.user_agent,
        }
    }
}

impl Default for InterfaceConfig {
    fn default() -> Self {
        Self {
            show_progress: Config::default().show_progress,
        }
    }
}

impl Default for TaskConfig {
    fn default() -> Self {
        let config = Config::default();
        Self {
            default_date: config.default_date,
            default_format: config.default_format.to_string(),
            edition_filter: config.edition_filter,
            holiday_skip: config.holiday_skip,
            batch_merge_mode: config.batch_merge_mode.to_string(),
        }
    }
}

impl Default for OutputConfig {
    fn default() -> Self {
        let config = Config::default();
        Self {
            download_path: config.download_path,
            download_dir: config.download_dir,
            merged_filename: config.merged_filename,
            auto_merge: config.auto_merge,
            keep_singles: config.keep_singles,
            open_folder_after: config.open_folder_after,
            text_filename: config.text_filename,
            text_include_edition: config.text_include_edition,
        }
    }
}

impl Default for LoggingConfig {
    fn default() -> Self {
        let config = Config::default();
        Self {
            log_file: config.log_file,
            log_level: config.log_level.to_string(),
            beep_on_done: config.beep_on_done,
        }
    }
}

impl Config {
    pub fn path() -> Result<PathBuf> {
        Ok(std::env::current_dir()
            .context("无法确定当前工作目录")?
            .join("config.toml"))
    }

    fn sources() -> Result<Vec<PathBuf>> {
        let mut paths = Vec::new();
        if let Some(directory) = std::env::current_exe()?.parent() {
            paths.push(directory.join("config.toml"));
        }
        let current = Self::path()?;
        if !paths.iter().any(|path| path == &current) {
            paths.push(current);
        }
        Ok(paths)
    }

    pub fn load() -> Result<Self> {
        let mut figment = Figment::from(Serialized::defaults(ConfigFile::default()));
        let sources = Self::sources()?;
        for path in &sources {
            if path.exists() {
                figment = figment.merge(Toml::file(path));
            }
        }
        let destination = Self::path()?;
        if !destination.exists() {
            tracing::info!("将生成默认配置 config.toml");
        }
        let file: ConfigFile = figment
            .extract()
            .with_context(|| format!("解析 TOML 配置失败: {}", destination.display()))?;
        let config = Self::from(file);
        if !destination.exists() {
            config.save()?;
        }
        Ok(config)
    }

    pub fn save(&self) -> Result<()> {
        fs::write(Self::path()?, self.to_toml()?).context("写入 config.toml 失败")
    }

    pub fn to_toml(&self) -> Result<String> {
        Ok(toml::to_string_pretty(&ConfigFile::from(self))?)
    }

    pub fn validate(&mut self) {
        macro_rules! bound {
            ($field:ident, $min:expr, $max:expr, $default:expr) => {
                if !self.$field.is_finite() || self.$field < $min || self.$field > $max {
                    self.warnings
                        .push(format!("{} 越界，恢复默认值", stringify!($field)));
                    self.$field = $default;
                }
            };
        }
        bound!(rate_limit_kbps, 0.0, 102_400.0, 0.0);
        bound!(retry_interval, 0.0, 300.0, 2.0);
        bound!(request_interval, 0.0, 300.0, 0.2);
        if !(1..=86400).contains(&self.timeout) {
            self.warnings.push("timeout 越界，恢复默认值".into());
            self.timeout = 30;
        }
        if self.retry > 20 {
            self.warnings.push("retry 越界，恢复默认值".into());
            self.retry = 3;
        }
        if !(1..=16).contains(&self.concurrent) {
            self.warnings.push("concurrent 越界，恢复默认值".into());
            self.concurrent = 1;
        }
    }

    pub fn report_warnings(&mut self) {
        for warning in self.warnings.drain(..) {
            tracing::warn!("{warning}");
        }
    }

    pub fn output_root(&self) -> Result<PathBuf> {
        let root = if self.download_path.trim().is_empty() {
            Self::path()?
                .parent()
                .context("无法确定程序目录")?
                .to_path_buf()
        } else {
            let path = PathBuf::from(&self.download_path);
            if path.is_absolute() {
                path
            } else {
                Self::path()?
                    .parent()
                    .context("无法确定程序目录")?
                    .join(path)
            }
        };
        Ok(root)
    }
}
