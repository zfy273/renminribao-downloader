mod app;
mod config;
mod downloader;
mod output;
mod parse;

use anyhow::Result;
use clap::{Parser, Subcommand};
use config::Config;

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
    },
    Batch {
        #[arg(long, value_name = "EXPR")]
        dates: String,
        #[arg(value_name = "FORMAT")]
        format: Option<String>,
        #[arg(long, value_name = "MODE")]
        merge_mode: Option<String>,
    },
    Init,
}

fn main() {
    if let Err(error) = run() {
        eprintln!("[错误] {error:#}");
        std::process::exit(1);
    }
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
        Some(Command::Download { date, format }) => {
            app::download_one(&config, date.as_deref(), format.as_deref())?;
        }
        Some(Command::Batch { dates, format, merge_mode }) => {
            app::download_batch(
                &config,
                &dates,
                format.as_deref(),
                merge_mode.as_deref(),
            )?;
        }
        None => app::interactive(&mut config)?,
    }
    Ok(())
}
