mod app;
mod config;
mod downloader;
mod output;
mod parse;

use anyhow::{Context, Result, bail};
use clap::{Parser, Subcommand};
use config::Config;
use std::{fs, path::Path};

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
        #[arg(value_name = "FORMAT")]
        format: Option<String>,
        #[arg(long, value_name = "DATE", conflicts_with = "date")]
        on: Option<String>,
        #[arg(long, value_name = "FORMAT", conflicts_with = "format")]
        output: Option<String>,
    },
    Batch {
        #[arg(long, value_name = "EXPR")]
        dates: String,
        #[arg(value_name = "FORMAT")]
        format: Option<String>,
        #[arg(long, value_name = "MODE")]
        merge_mode: Option<String>,
        #[arg(long, value_name = "FORMAT", conflicts_with = "format")]
        output: Option<String>,
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
        eprintln!("[错误] {error:#}");
        std::process::exit(1);
    }
}

fn list_output(root: &Path) -> Result<()> {
    if !root.exists() {
        println!("输出目录不存在: {}", root.display());
        return Ok(());
    }
    let mut entries = fs::read_dir(root)
        .with_context(|| format!("无法读取输出目录: {}", root.display()))?
        .collect::<std::io::Result<Vec<_>>>()?;
    entries.sort_by_key(|entry| entry.file_name());
    if entries.is_empty() {
        println!("输出目录为空: {}", root.display());
        return Ok(());
    }
    for entry in entries {
        let metadata = entry.metadata()?;
        let kind = if metadata.is_dir() {
            "目录"
        } else {
            "文件"
        };
        println!("{kind:4} {:>10} {}", metadata.len(), entry.path().display());
    }
    Ok(())
}

fn run() -> Result<()> {
    let cli = Cli::parse();
    let mut config = Config::load()?;
    config.validate();

    match cli.command {
        Some(Command::Init) => {
            config.save()?;
            println!("已生成/更新 config.toml");
        }
        Some(Command::Download {
            date,
            format,
            on,
            output,
        }) => {
            app::download_one(
                &config,
                on.as_deref().or(date.as_deref()),
                output.as_deref().or(format.as_deref()),
            )?;
        }
        Some(Command::Batch {
            dates,
            format,
            merge_mode,
            output,
        }) => {
            app::download_batch(
                &config,
                &dates,
                output.as_deref().or(format.as_deref()),
                merge_mode.as_deref(),
            )?;
        }
        Some(Command::CheckDate { date }) => {
            let parsed = parse::validate_date(&date)?;
            println!("有效日期: {}", parsed.format("%Y-%m-%d"));
        }
        Some(Command::Config) => {
            println!(
                "配置文件: {}\n\n{}",
                Config::path()?.display(),
                toml::to_string_pretty(&config)?
            );
        }
        Some(Command::List) => list_output(&config.output_root()?)?,
        None => app::interactive(&mut config)?,
    }
    Ok(())
}
