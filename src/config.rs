use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::{fs, path::PathBuf};

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
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
    pub color_foreground: String,
    pub color_background: String,
    pub window_title: String,
    pub show_progress: bool,
    pub default_date: String,
    pub default_format: String,
    pub edition_filter: Vec<u32>,
    pub holiday_skip: bool,
    pub batch_enable: bool,
    pub batch_merge_mode: String,
    pub download_path: String,
    pub download_dir: String,
    pub merged_filename: String,
    pub auto_merge: bool,
    pub keep_singles: bool,
    pub open_folder_after: bool,
    pub text_output_format: String,
    pub text_filename: String,
    pub text_include_edition: bool,
    pub log_file: String,
    pub log_level: String,
    pub beep_on_done: bool,
    pub msg_on_done: bool,
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
    color_foreground: String,
    color_background: String,
    window_title: String,
    show_progress: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
struct TaskConfig {
    default_date: String,
    default_format: String,
    edition_filter: Vec<u32>,
    holiday_skip: bool,
    batch_enable: bool,
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
    text_output_format: String,
    text_filename: String,
    text_include_edition: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
struct LoggingConfig {
    log_file: String,
    log_level: String,
    beep_on_done: bool,
    msg_on_done: bool,
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
            color_foreground: "A".into(),
            color_background: "0".into(),
            window_title: "人民日报电子版下载器".into(),
            show_progress: true,
            default_date: String::new(),
            default_format: "pdf".into(),
            edition_filter: Vec::new(),
            holiday_skip: false,
            batch_enable: false,
            batch_merge_mode: "each".into(),
            download_path: "output".into(),
                        download_dir: "{date}".into(),
            merged_filename: "人民日报-{date}-完整版".into(),
            auto_merge: true,
            keep_singles: false,
            open_folder_after: true,
            text_output_format: "TXT".into(),
            text_filename: "人民日报-{date}-文字版".into(),
            text_include_edition: true,
            log_file: "rmrb_download.log".into(),
            log_level: "normal".into(),
            beep_on_done: false,
            msg_on_done: false,
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
                color_foreground: config.color_foreground.clone(),
                color_background: config.color_background.clone(),
                window_title: config.window_title.clone(),
                show_progress: config.show_progress,
            },
            task: TaskConfig {
                default_date: config.default_date.clone(),
                default_format: config.default_format.clone(),
                edition_filter: config.edition_filter.clone(),
                holiday_skip: config.holiday_skip,
                batch_enable: config.batch_enable,
                batch_merge_mode: config.batch_merge_mode.clone(),
            },
            output: OutputConfig {
                download_path: config.download_path.clone(),
                download_dir: config.download_dir.clone(),
                merged_filename: config.merged_filename.clone(),
                auto_merge: config.auto_merge,
                keep_singles: config.keep_singles,
                open_folder_after: config.open_folder_after,
                text_output_format: config.text_output_format.clone(),
                text_filename: config.text_filename.clone(),
                text_include_edition: config.text_include_edition,
            },
            logging: LoggingConfig {
                log_file: config.log_file.clone(),
                log_level: config.log_level.clone(),
                beep_on_done: config.beep_on_done,
                msg_on_done: config.msg_on_done,
            },
        }
    }
}

impl From<ConfigFile> for Config {
    fn from(file: ConfigFile) -> Self {
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
            color_foreground: file.interface.color_foreground,
            color_background: file.interface.color_background,
            window_title: file.interface.window_title,
            show_progress: file.interface.show_progress,
            default_date: file.task.default_date,
            default_format: file.task.default_format,
            edition_filter: file.task.edition_filter,
            holiday_skip: file.task.holiday_skip,
            batch_enable: file.task.batch_enable,
            batch_merge_mode: file.task.batch_merge_mode,
            download_path: file.output.download_path,
            download_dir: file.output.download_dir,
            merged_filename: file.output.merged_filename,
            auto_merge: file.output.auto_merge,
            keep_singles: file.output.keep_singles,
            open_folder_after: file.output.open_folder_after,
            text_output_format: file.output.text_output_format,
            text_filename: file.output.text_filename,
            text_include_edition: file.output.text_include_edition,
            log_file: file.logging.log_file,
            log_level: file.logging.log_level,
            beep_on_done: file.logging.beep_on_done,
            msg_on_done: file.logging.msg_on_done,
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
        let config = Config::default();
        Self {
            color_foreground: config.color_foreground,
            color_background: config.color_background,
            window_title: config.window_title,
            show_progress: config.show_progress,
        }
    }
}

impl Default for TaskConfig {
    fn default() -> Self {
        let config = Config::default();
        Self {
            default_date: config.default_date,
            default_format: config.default_format,
            edition_filter: config.edition_filter,
            holiday_skip: config.holiday_skip,
            batch_enable: config.batch_enable,
            batch_merge_mode: config.batch_merge_mode,
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
            text_output_format: config.text_output_format,
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
            log_level: config.log_level,
            beep_on_done: config.beep_on_done,
            msg_on_done: config.msg_on_done,
        }
    }
}

impl Config {
    pub fn path() -> Result<PathBuf> {
        Ok(std::env::current_exe()?
            .parent()
            .context("无法确定程序所在目录")?
            .join("config.toml"))
    }

    pub fn load() -> Result<Self> {
        let path = Self::path()?;
        if path.exists() {
            let text = fs::read_to_string(&path)
                .with_context(|| format!("读取配置失败: {}", path.display()))?;
            let value: toml::Value = toml::from_str(&text)
                .with_context(|| format!("解析 TOML 配置失败: {}", path.display()))?;
            if value.as_table().is_some_and(|table| {
                ["network", "interface", "task", "output", "logging"]
                    .iter()
                    .any(|section| table.contains_key(*section))
            }) {
                return toml::from_str::<ConfigFile>(&text)
                    .map(Into::into)
                    .with_context(|| format!("解析 TOML 配置失败: {}", path.display()));
            }
            return toml::from_str(&text)
                .with_context(|| format!("解析旧版 TOML 配置失败: {}", path.display()));
        }

        let config = Self::default();
        println!("[提示] 将生成默认配置 config.toml");
        config.save()?;
        Ok(config)
    }

    pub fn save(&self) -> Result<()> {
        let text = toml::to_string_pretty(&ConfigFile::from(self))?;
        fs::write(Self::path()?, text).context("写入 config.toml 失败")
    }

    pub fn validate(&mut self) {
        macro_rules! bound {
            ($field:ident, $min:expr, $max:expr, $default:expr) => {
                if !self.$field.is_finite() || self.$field < $min || self.$field > $max {
                    eprintln!("[配置警告] {} 越界，恢复默认值", stringify!($field));
                    self.$field = $default;
                }
            };
        }
        bound!(rate_limit_kbps, 0.0, f64::MAX, 0.0);
        bound!(retry_interval, 0.0, f64::MAX, 2.0);
        bound!(request_interval, 0.0, f64::MAX, 0.2);
        if !(1..=86400).contains(&self.timeout) {
            eprintln!("[配置警告] timeout 越界，恢复默认值");
            self.timeout = 30;
        }
        if self.retry > 20 {
            eprintln!("[配置警告] retry 越界，恢复默认值");
            self.retry = 3;
        }
        if !(1..=16).contains(&self.concurrent) {
            eprintln!("[配置警告] concurrent 越界，恢复默认值");
            self.concurrent = 1;
        }
        if !["text", "md", "pdf", "both"].contains(&self.default_format.to_lowercase().as_str()) {
            self.default_format = "pdf".into();
        }
        if !["TXT", "MD"].contains(&self.text_output_format.to_uppercase().as_str()) {
            self.text_output_format = "TXT".into();
        }
        if !["each", "all"].contains(&self.batch_merge_mode.to_lowercase().as_str()) {
            self.batch_merge_mode = "each".into();
        }
        if self.log_file.trim().is_empty() {
            self.log_level = "quiet".into();
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
