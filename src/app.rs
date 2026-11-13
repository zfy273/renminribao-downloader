use crate::{
    config::{Config, Format, MergeMode, Outputs, TextKind},
    downloader::{Downloader, merge_pdfs},
    output,
    parse::{Edition, display_date, parse_batch_expr, validate_date},
};
use anyhow::{Context, Result, bail};
use chrono::Local;
use console::{Key, Term, style};
use dialoguer::theme::ColorfulTheme;
use std::{
    fs,
    io::{Read, Seek, SeekFrom, Write},
    path::{Path, PathBuf},
};

fn theme() -> ColorfulTheme {
    let mut theme = ColorfulTheme::default();
    theme.prompt_prefix = style("›".to_string()).for_stderr().cyan().bold();
    theme.prompt_suffix = style("".to_string()).for_stderr();
    theme.success_prefix = style("✓".to_string()).for_stderr().green().bold();
    theme.success_suffix = style("".to_string()).for_stderr();
    theme.error_prefix = style("✗".to_string()).for_stderr().red().bold();
    theme.prompt_style = console::Style::new().for_stderr().cyan().bold();
    theme.error_style = console::Style::new().for_stderr().red();
    theme.hint_style = console::Style::new().for_stderr().dim();
    theme.values_style = console::Style::new().for_stderr().yellow();
    theme.active_item_prefix = style("▸".to_string()).for_stderr().cyan().bold();
    theme.inactive_item_prefix = style(" ".to_string()).for_stderr();
    theme.active_item_style = console::Style::new().for_stderr().cyan().bold();
    theme.inactive_item_style = console::Style::new().for_stderr();
    theme
}

fn columns(text: &str) -> usize {
    console::measure_text_width(text)
}

fn banner(title: &str) {
    println!();
    println!("{}", style(title).bold());
    println!("{}", style("-".repeat(columns(title))).cyan());
}

fn section(title: &str) {
    println!("\n{}", style(format!("── {title} ")).cyan().bold());
}

fn label(name: &str, value: impl std::fmt::Display) {
    let pad = 12usize.saturating_sub(columns(name));
    println!("  {}{} {}", style(name).dim(), " ".repeat(pad), value);
}

fn note(message: &str) {
    println!("{} {message}", style("·").yellow().bold());
}

fn report_error(error: &anyhow::Error) {
    tracing::error!("{error:#}");
}

fn selected_outputs(config: &Config, outputs: Option<Outputs>) -> Outputs {
    outputs.unwrap_or_else(|| Outputs::from_format(config.default_format))
}

fn open_output(path: &PathBuf, enabled: bool) {
    if enabled && let Err(error) = opener::reveal(path) {
        tracing::warn!("无法打开输出位置: {error}");
    }
}

fn finish_notice(config: &Config, summary: &str) {
    println!("\n{} {summary}", style("✓ 完成").green().bold());
    if config.beep_on_done {
        print!("\u{7}");
        let _ = std::io::stdout().flush();
    }
}

fn issue_text(
    config: &Config,
    downloader: &Downloader,
    date: &str,
    editions: &[String],
    root: &PathBuf,
    kinds: &[TextKind],
) -> Result<(Vec<PathBuf>, Vec<Edition>)> {
    note(&format!("共 {} 个版面，开始抓取文章正文", editions.len()));
    let content = downloader.crawl_text(date, editions);
    if content.iter().all(|edition| edition.articles.is_empty()) {
        bail!("未抓到任何文章");
    }
    let mut paths = Vec::new();
    for kind in kinds {
        let lines = output::text_lines(
            &display_date(date),
            &content,
            config.text_include_edition,
            kind.markdown(),
        );
        let path = output::output_path(config, root, &display_date(date), kind.extension());
        output::write_text(&lines, &path)?;
        println!(
            "{} {} 行已保存  {}",
            style(format!("✓ {}", kind)).cyan().bold(),
            lines.len(),
            style(path.display()).underlined()
        );
        paths.push(path);
    }
    Ok((paths, content))
}

fn issue_pdf(
    config: &Config,
    downloader: &Downloader,
    date: &str,
    editions: &[String],
    root: &PathBuf,
    merge: bool,
) -> Result<Option<PathBuf>> {
    note(&format!("共 {} 个版面，开始下载 PDF", editions.len()));
    let (files, failed) = downloader.download_editions(date, editions, root)?;
    if !failed.is_empty() {
        note(&format!(
            "{} 个版面未下载成功: {}",
            failed.len(),
            failed.join(", ")
        ));
    }
    if files.is_empty() {
        bail!("没有任何版面下载成功");
    }
    if !merge {
        return Ok(None);
    }
    let name = config
        .merged_filename
        .replace("{date}", &display_date(date));
    let path = root.join(format!("{name}.pdf"));
    match merge_pdfs(&files, &path) {
        Ok(pages) => {
            println!(
                "{} {} 个版面已合并为 {pages} 页  {}",
                style("✓ 合并").green().bold(),
                files.len(),
                style(path.display()).underlined()
            );
            if !config.keep_singles {
                let dir = root.join(config.download_dir.replace("{date}", date));
                let _ = fs::remove_dir_all(dir);
            }
            Ok(Some(path))
        }
        Err(error) => {
            tracing::error!("合并失败，单版文件保留: {error:#}");
            Ok(None)
        }
    }
}

pub fn download_one(config: &Config, date: Option<&str>, outputs: Option<Outputs>) -> Result<()> {
    let date = date
        .map(str::to_string)
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| {
            if config.default_date.is_empty() {
                Local::now().format("%Y%m%d").to_string()
            } else {
                config.default_date.clone()
            }
        });
    let parsed_date = validate_date(&date)?;
    if parsed_date > Local::now().date_naive() {
        bail!("未来日期，人民日报尚未出版");
    }
    let outputs = selected_outputs(config, outputs);
    let root = config.output_root()?;
    fs::create_dir_all(&root)?;
    tracing::debug!("开始单日下载 日期={date} 格式={outputs}");
    let downloader = Downloader::new(config)?;
    let (editions, network_ok) = downloader.editions(&date)?;
    if editions.is_empty() {
        if config.holiday_skip {
            note("无版面，按 holiday_skip 忽略");
            return Ok(());
        }
        bail!(
            "{}",
            if network_ok {
                "未找到任何版面（休刊或版面筛选为空）"
            } else {
                "版面列表读取失败，请检查网络或代理"
            }
        );
    }
    banner("人民日报电子版下载器");
    label("日期", display_date(&date));
    label("格式", &outputs);
    let mut produced = Vec::new();
    if outputs.pdf
        && let Some(path) = issue_pdf(config, &downloader, &date, &editions, &root, config.auto_merge)?
    {
        produced.push(path);
    }
    if outputs.wants_text() {
        let (paths, _) = issue_text(config, &downloader, &date, &editions, &root, &outputs.kinds)?;
        produced.extend(paths);
    }
    let produced: Vec<_> = produced.into_iter().filter(|path| path.exists()).collect();
    if let Some(path) = produced.last() {
        open_output(path, config.open_folder_after);
        let files = produced
            .iter()
            .map(|path| path.display().to_string())
            .collect::<Vec<_>>()
            .join(", ");
        tracing::info!("任务完成 日期={date} 格式={outputs} 产物={files}");
        finish_notice(config, &format!("文件已生成: {files}"));
    } else {
        bail!("本次未生成任何文件");
    }
    Ok(())
}

pub fn download_batch(
    config: &Config,
    expression: &str,
    outputs: Option<Outputs>,
    requested_mode: Option<&str>,
) -> Result<()> {
    let outputs = selected_outputs(config, outputs);
    let mode = requested_mode
        .map(str::parse)
        .transpose()?
        .unwrap_or(config.batch_merge_mode);
    let dates = parse_batch_expr(expression).context("日期表达式错误")?;
    if dates.is_empty() {
        bail!("未解析到任何日期");
    }
    tracing::debug!("开始批量下载 日期={} 格式={outputs} 合并={mode}", dates.len());
    let root = config.output_root()?;
    fs::create_dir_all(&root)?;
    let downloader = Downloader::new(config)?;
    let mut success = Vec::new();
    let mut skipped = Vec::new();
    let mut failed = Vec::new();
    let mut all_pdfs = Vec::new();
    let mut all_text: Vec<(String, Vec<Edition>)> = Vec::new();

    for (index, date) in dates.iter().enumerate() {
        section(&format!(
            "[{}/{}] {}",
            index + 1,
            dates.len(),
            display_date(date)
        ));
        let (editions, _) = downloader.editions(date)?;
        if editions.is_empty() {
            if config.holiday_skip {
                note("无版面，按 holiday_skip 忽略");
                skipped.push(date.clone());
                continue;
            }
            tracing::error!("{date} 无版面");
            failed.push(date.clone());
            continue;
        }
        let mut day_ok = true;
        if outputs.pdf {
            if mode == MergeMode::All {
                let (files, missing) = downloader.download_editions(date, &editions, &root)?;
                all_pdfs.extend(files);
                if !missing.is_empty() {
                    day_ok = false;
                }
            } else if issue_pdf(config, &downloader, date, &editions, &root, true)?.is_none() {
                day_ok = false;
            }
        }
        if outputs.wants_text() {
            match issue_text(config, &downloader, date, &editions, &root, &outputs.kinds) {
                Ok((paths, content)) if mode == MergeMode::All => {
                    all_text.push((date.clone(), content));
                    for path in paths {
                        let _ = fs::remove_file(path);
                    }
                }
                Ok(_) => {}
                Err(error) => {
                    tracing::error!("{date} 文字抓取失败: {error:#}");
                    day_ok = false;
                }
            }
        }
        if day_ok {
            success.push(date.clone());
        } else {
            failed.push(date.clone());
        }
    }

    let span = format!(
        "{}-{}",
        display_date(dates.first().unwrap()),
        display_date(dates.last().unwrap())
    );
    let mut final_result = None;
    let mut pdf_merge_ok = true;
    if mode == MergeMode::All && outputs.pdf && !all_pdfs.is_empty() {
        let path = root.join(format!("人民日报-{span}-完整版.pdf"));
        match merge_pdfs(&all_pdfs, &path) {
            Ok(pages) => {
                println!(
                    "{} {} 个版面 → {pages} 页  {}",
                    style("✓ 全部合并").green().bold(),
                    all_pdfs.len(),
                    style(path.display()).underlined()
                );
                final_result = Some(path);
            }
            Err(error) => {
                pdf_merge_ok = false;
                tracing::error!("全部合并失败，单版 PDF 已保留: {error:#}");
            }
        }
    }
    if mode == MergeMode::All && outputs.wants_text() && !all_text.is_empty() {
        for kind in &outputs.kinds {
            let path = root.join(format!("人民日报-{span}-文字版.{}", kind.extension()));
            let mut lines = Vec::new();
            for (date, content) in &all_text {
                lines.extend(output::text_lines(
                    &display_date(date),
                    content,
                    config.text_include_edition,
                    kind.markdown(),
                ));
                lines.push(String::new());
            }
            output::write_text(&lines, &path)?;
            final_result = Some(path);
        }
    }
    if mode == MergeMode::All && !config.keep_singles && pdf_merge_ok {
        for date in &dates {
            let _ = fs::remove_dir_all(root.join(config.download_dir.replace("{date}", date)));
        }
    }
    banner("批量汇总");
    label("成功", style(success.len()).green());
    label("无报跳过", style(skipped.len()).yellow());
    label("失败", style(failed.len()).red());
    if !skipped.is_empty() {
        label("跳过日期", skipped.join(", "));
    }
    if !failed.is_empty() {
        label("失败日期", failed.join(", "));
    }
    if let Some(path) = final_result {
        open_output(&path, config.open_folder_after);
    }
    tracing::info!(
        "批量完成 成功={} 跳过={} 失败={} 格式={outputs} 合并={mode}",
        success.len(),
        skipped.len(),
        failed.len()
    );
    if success.is_empty() {
        bail!("批量下载没有任何日期成功");
    }
    finish_notice(config, "批量下载完成");
    Ok(())
}

fn prompt_text(prompt: &str, default: &str) -> Result<Option<String>> {
    let term = Term::stderr();
    let theme = theme();
    let head = format!(
        "{} {} {} ",
        theme.prompt_prefix,
        theme.prompt_style.apply_to(prompt),
        theme.hint_style.apply_to(format!("({default})"))
    );
    term.write_str(&head)?;
    term.flush()?;
    let mut chars = Vec::new();
    let mut position = 0usize;
    loop {
        match term.read_key()? {
            Key::Escape => {
                term.clear_line()?;
                term.flush()?;
                return Ok(None);
            }
            Key::Enter => {
                term.clear_line()?;
                term.flush()?;
                break;
            }
            Key::Backspace if position > 0 => {
                position -= 1;
                chars.remove(position);
                redraw_input(&term, &head, &chars, position)?;
            }
            Key::ArrowLeft if position > 0 => {
                position -= 1;
                redraw_input(&term, &head, &chars, position)?;
            }
            Key::ArrowRight if position < chars.len() => {
                position += 1;
                redraw_input(&term, &head, &chars, position)?;
            }
            Key::Char(chr) if !chr.is_control() => {
                chars.insert(position, chr);
                position += 1;
                redraw_input(&term, &head, &chars, position)?;
            }
            _ => {}
        }
    }
    let typed: String = chars.iter().collect();
    let value = if typed.is_empty() { default.to_string() } else { typed };
    Ok(Some(value))
}

fn redraw_input(term: &Term, head: &str, chars: &[char], position: usize) -> Result<()> {
    term.clear_line()?;
    term.write_str(head)?;
    let typed: String = chars.iter().collect();
    term.write_str(&typed)?;
    let tail: String = chars[position..].iter().collect();
    let tail_columns = columns(&tail);
    if tail_columns > 0 {
        term.move_cursor_left(tail_columns)?;
    }
    term.flush()?;
    Ok(())
}

fn prompt_outputs(default: Format) -> Result<Option<Outputs>> {
    let defaults = [
        default == Format::Pdf,
        default == Format::Text,
        default == Format::Md,
    ];
    let picked = dialoguer::MultiSelect::with_theme(&theme())
        .with_prompt("选择输出（空格勾选，回车确认）")
        .items(&["PDF", "文字 TXT", "Markdown"])
        .defaults(&defaults)
        .report(false)
        .interact_opt()?;
    let Some(picked) = picked else {
        return Ok(None);
    };
    let outputs = Outputs {
        pdf: picked.contains(&0),
        kinds: [TextKind::Txt, TextKind::Md]
            .into_iter()
            .enumerate()
            .filter(|(index, _)| picked.contains(&(index + 1)))
            .map(|(_, kind)| kind)
            .collect(),
    };
    if !outputs.pdf && outputs.kinds.is_empty() {
        bail!("至少选择一种输出");
    }
    Ok(Some(outputs))
}

fn show_records(config: &Config) -> Result<()> {
    let path = Config::path()?.parent().unwrap().join(&config.log_file);
    if !path.is_file() {
        note("尚无下载记录");
        return Ok(());
    }
    let text = read_log_tail(&path, 256 * 1024)?;
    let mut tasks = Vec::new();
    let mut problems = Vec::new();
    for line in text.lines() {
        let Some((time, level, message)) = split_log(line) else {
            continue;
        };
        if message.contains("任务完成") || message.contains("批量完成") {
            tasks.push((time.to_string(), message.to_string()));
        } else if level == "ERROR" || level == "WARN" {
            problems.push((time.to_string(), level.to_string(), message.to_string()));
        }
    }
    banner("下载记录");
    label("日志", path.display());
    if tasks.is_empty() && problems.is_empty() {
        note("日志里还没有任务结果");
        return Ok(());
    }
    if !tasks.is_empty() {
        section(&format!("最近任务（{}）", tasks.len()));
        for (time, message) in tasks.iter().skip(tasks.len().saturating_sub(12)) {
            println!("  {}  {}", style(format_log_time(time)).dim(), message);
        }
    }
    if !problems.is_empty() {
        section(&format!("最近异常（{}）", problems.len()));
        for (time, level, message) in problems.iter().skip(problems.len().saturating_sub(8)) {
            let mark = if level == "ERROR" {
                style("失败").red().bold()
            } else {
                style("警告").yellow().bold()
            };
            println!("  {}  {mark}  {message}", style(format_log_time(time)).dim());
        }
    }
    Ok(())
}

fn read_log_tail(path: &Path, limit: u64) -> Result<String> {
    let mut file = fs::File::open(path)?;
    let length = file.metadata()?.len();
    if length > limit {
        file.seek(SeekFrom::Start(length - limit))?;
    }
    let mut text = String::new();
    file.read_to_string(&mut text)?;
    if length > limit
        && let Some(index) = text.find('\n')
    {
        text.drain(..=index);
    }
    Ok(text)
}

fn split_log(line: &str) -> Option<(&str, &str, &str)> {
    let time = line.split_whitespace().next()?;
    let rest = line[time.len()..].trim_start();
    let level = rest.split_whitespace().next()?;
    let rest = rest[level.len()..].trim_start();
    let message = rest.split_once(':').map(|(_, message)| message.trim()).unwrap_or(rest);
    Some((time, level, message))
}

fn format_log_time(value: &str) -> String {
    chrono::DateTime::parse_from_rfc3339(value)
        .map(|time| time.with_timezone(&Local).format("%m-%d %H:%M").to_string())
        .unwrap_or_else(|_| value.to_string())
}

fn prompt_mode(default: MergeMode) -> Result<Option<MergeMode>> {
    let options = [MergeMode::Each, MergeMode::All];
    let index = dialoguer::Select::with_theme(&theme())
        .with_prompt("选择合并方式")
        .items(&["每天单独生成", "全部日期合并"])
        .default(usize::from(default == MergeMode::All))
        .report(false)
        .interact_opt()?;
    Ok(index.map(|index| options[index]))
}

pub fn interactive(config: &mut Config) -> Result<()> {
    banner("人民日报电子版下载器");
    loop {
        let choice = dialoguer::Select::with_theme(&theme())
            .with_prompt("请选择操作")
            .items(&["单日下载", "批量下载", "查看配置", "打开输出目录", "查看下载记录", "退出"])
            .default(0)
            .report(false)
            .interact_opt()?;
        match choice {
            Some(0) => {
                let today = Local::now().format("%Y%m%d").to_string();
                loop {
                    let Some(date) = prompt_text("日期 YYYYMMDD", &today)? else {
                        break;
                    };
                    let Some(outputs) = prompt_outputs(config.default_format)? else {
                        continue;
                    };
                    if let Err(error) = download_one(config, Some(&date), Some(outputs)) {
                        report_error(&error);
                    }
                    break;
                }
            }
            Some(1) => {
                let today = Local::now().format("%Y%m%d").to_string();
                'dates: loop {
                    let Some(dates) = prompt_text("日期范围", &today)? else {
                        break;
                    };
                    loop {
                        let Some(mode) = prompt_mode(config.batch_merge_mode)? else {
                            continue 'dates;
                        };
                        let Some(outputs) = prompt_outputs(config.default_format)? else {
                            continue;
                        };
                        if let Err(error) = download_batch(
                            config,
                            &dates,
                            Some(outputs),
                            Some(&mode.to_string()),
                        ) {
                            report_error(&error);
                        }
                        break 'dates;
                    }
                }
            }
            Some(2) => {
                banner("当前配置");
                label("默认格式", config.default_format);
                label("输出目录", &config.download_path);
                label("批量合并", config.batch_merge_mode);
                label("网络超时", format!("{} 秒", config.timeout));
                label("重试次数", config.retry);
                label("并发", config.concurrent);
                label("限速", format!("{} KB/s", config.rate_limit_kbps));
                label(
                    "进度条",
                    if config.show_progress { "显示" } else { "关闭" },
                );
                label("配置文件", Config::path()?.display());
            }
            Some(3) => {
                let root = config.output_root()?;
                fs::create_dir_all(&root)?;
                open_output(&root, true);
                label("输出目录", root.display());
            }
            Some(4) => {
                if let Err(error) = show_records(config) {
                    report_error(&error);
                }
            }
            Some(5) | None => break,
            _ => {}
        }
    }
    Ok(())
}
