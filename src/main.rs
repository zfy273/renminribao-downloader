mod app;
mod config;
mod downloader;
mod output;
mod parse;

use anyhow::{Context, Result};
use console::style;
use clap::{Parser, Subcommand};
use config::{Config, Format, MergeMode, Outputs};
use std::{fs, path::Path};
use tracing_subscriber::{EnvFilter, Layer, fmt, layer::SubscriberExt, util::SubscriberInitExt};

#[derive(Parser)]
#[command(name = "rmrb-downloader", version, about = "人民日报电子版下载器")]
struct Cli {
    #[command(subcommand)]
    command: Option<Command>,
}

#[derive(Subcommand)]
enum Command {
    Download {
        #[arg(value_name = "DATE")]
        date: Option<String>,
        #[arg(value_name = "FORMAT", value_enum, num_args = 0..)]
        format: Vec<Format>,
        #[arg(long, value_name = "DATE", conflicts_with = "date")]
        on: Option<String>,
        #[arg(long, value_name = "FORMAT", value_enum, conflicts_with = "format")]
        output: Vec<Format>,
    },
    Batch {
        #[arg(long, value_name = "EXPR")]
        dates: String,
        #[arg(value_name = "FORMAT", value_enum, num_args = 0..)]
        format: Vec<Format>,
        #[arg(long, value_name = "MODE", value_enum)]
        merge_mode: Option<MergeMode>,
        #[arg(long, value_name = "FORMAT", value_enum, conflicts_with = "format")]
        output: Vec<Format>,
    },
    /// Validate a date without downloading
    CheckDate {
        #[arg(value_name = "DATE")]
        date: String,
    },
    /// Show the effective configuration file
    Config,
    /// List generated files in the output directory
    List,
    Init,
}

fn main() {
    if let Err(error) = run() {
        if tracing::dispatcher::has_been_set() {
            tracing::error!("{error:#}");
        } else {
            eprintln!("{} {error:#}", style("✗ 错误").red().bold());
        }
        std::process::exit(1);
    }
}

fn resolve_outputs(positional: &[Format], flags: &[Format]) -> Result<Option<Outputs>> {
    let selected = if flags.is_empty() { positional } else { flags };
    if selected.is_empty() {
        Ok(None)
    } else {
        Ok(Some(Outputs::from_formats(selected)?))
    }
}

fn list_output(root: &Path) -> Result<()> {
    if !root.exists() {
        println!("{} 输出目录不存在  {}", style("·").yellow().bold(), root.display());
        return Ok(());
    }
    let mut entries = fs::read_dir(root)
        .with_context(|| format!("无法读取输出目录: {}", root.display()))?
        .collect::<std::io::Result<Vec<_>>>()?;
    entries.sort_by_key(|entry| entry.file_name());
    if entries.is_empty() {
        println!("{} 输出目录为空  {}", style("·").yellow().bold(), root.display());
        return Ok(());
    }
    println!("\n{}", style(format!("── {} ", root.display())).cyan().bold());
    for entry in entries {
        let metadata = entry.metadata()?;
        let kind = if metadata.is_dir() {
            style("目录").yellow()
        } else {
            style("文件").green()
        };
        println!("  {kind}  {:>10}  {}", metadata.len(), entry.path().display());
    }
    Ok(())
}


fn init_logging(config: &Config) -> Result<Option<tracing_appender::non_blocking::WorkerGuard>> {
    let console = fmt::layer()
        .with_target(false)
        .with_level(true)
        .compact()
        .with_ansi(console::colors_enabled())
        .with_filter(EnvFilter::new(config.log_level.filter()));
    if config.log_file.trim().is_empty() {
        tracing_subscriber::registry().with(console).init();
        return Ok(None);
    }
    let directory = Config::path()?
        .parent()
        .context("无法确定程序目录")?
        .to_path_buf();
    let appender = tracing_appender::rolling::never(&directory, &config.log_file);
    let (writer, guard) = tracing_appender::non_blocking(appender);
    let file = fmt::layer()
        .with_ansi(false)
        .with_writer(writer)
        .with_filter(EnvFilter::new("info"));
    tracing_subscriber::registry().with(console).with(file).init();
    Ok(Some(guard))
}

fn run() -> Result<()> {
    let cli = Cli::parse();
    let mut config = Config::load()?;
    config.validate();
    let _log_guard = if matches!(cli.command, Some(Command::Init)) {
        None
    } else {
        init_logging(&config)?
    };
    config.report_warnings();

    match cli.command {
        Some(Command::Init) => {
            config.save()?;
            println!("{} 已生成/更新 config.toml", style("✓").green().bold());
        }
        Some(Command::Download {
            date,
            format,
            on,
            output,
        }) => {
            let outputs = resolve_outputs(&format, &output)?;
            app::download_one(&config, on.as_deref().or(date.as_deref()), outputs)?;
        }
        Some(Command::Batch {
            dates,
            format,
            merge_mode,
            output,
        }) => {
            let outputs = resolve_outputs(&format, &output)?;
            app::download_batch(
                &config,
                &dates,
                outputs,
                merge_mode.as_ref().map(MergeMode::to_string).as_deref(),
            )?;
        }
        Some(Command::CheckDate { date }) => {
            let parsed = parse::validate_date(&date)?;
            println!("{} 有效日期: {}", style("✓").green().bold(), parsed.format("%Y-%m-%d"));
        }
        Some(Command::Config) => {
            println!(
                "\n{} {}\n\n{}",
                style("配置文件").cyan().bold(),
                Config::path()?.display(),
                config.to_toml()?
            );
        }
        Some(Command::List) => list_output(&config.output_root()?)?,
        None => app::interactive(&mut config)?,
    }
    Ok(())
}
