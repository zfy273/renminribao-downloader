use crate::{config::Config, downloader::{Downloader, merge_pdfs}, output, parse::{display_date, parse_batch_expr, validate_date}};
use anyhow::{Context, Result, bail};
use chrono::Local;
use std::{fs, path::PathBuf, process::Command, thread, time::Duration};

fn select_format(config: &Config, value: Option<&str>) -> Result<String> {
    let format = value.unwrap_or(&config.default_format).to_ascii_lowercase();
    if !["text", "md", "pdf", "both"].contains(&format.as_str()) { bail!("格式参数应为 text / md / pdf / both"); }
    Ok(format)
}

fn open_output(path: &PathBuf, enabled: bool) {
    if !enabled { return; }
    #[cfg(target_os = "windows")]
    { let _ = Command::new("explorer").arg(format!("/select,{}", path.display())).spawn(); }
    #[cfg(target_os = "macos")]
    { let _ = Command::new("open").arg("-R").arg(path).spawn(); }
    #[cfg(all(unix, not(target_os = "macos")))]
    { if let Some(parent) = path.parent() { let _ = Command::new("xdg-open").arg(parent).spawn(); } }
}

fn record(config: &Config, message: &str) {
    if config.log_file.trim().is_empty() || config.log_level == "quiet" { return; }
    let path = Config::path().ok().and_then(|p| p.parent().map(|d| d.join(&config.log_file)));
    if let Some(path) = path {
        use std::io::Write;
        if let Ok(mut file) = fs::OpenOptions::new().create(true).append(true).open(path) {
            let _ = writeln!(file, "[{}] {}", Local::now().format("%Y-%m-%d %H:%M:%S"), message);
        }
    }
}

fn issue_text(config: &Config, downloader: &Downloader, date: &str, editions: &[String], root: &PathBuf, requested_format: Option<&str>) -> Result<Option<PathBuf>> {
    println!("  共 {} 个版面，开始抓取文章正文...", editions.len());
    let content = downloader.crawl_text(date, editions);
    if content.iter().all(|e| e.articles.is_empty()) { bail!("未抓到任何文章"); }
    let format = requested_format
        .unwrap_or(config.text_output_format.as_str())
        .to_ascii_uppercase();
    let lines = output::text_lines(&display_date(date), &content, config.text_include_edition, format == "MD");
    let path = output::output_path(config, root, &display_date(date), &format);
    output::write_text(&lines, &path)?;
    println!("[文字] {} 行已保存: {}", lines.len(), path.display());
    Ok(Some(path))
}

fn issue_pdf(config: &Config, downloader: &Downloader, date: &str, editions: &[String], root: &PathBuf, merge: bool) -> Result<Option<PathBuf>> {
    println!("  共 {} 个版面，开始下载 PDF...", editions.len());
    let (files, failed) = downloader.download_editions(date, editions, root)?;
    if !failed.is_empty() { eprintln!("[提示] {} 个版面未下载成功: {}", failed.len(), failed.join(", ")); }
    if files.is_empty() { bail!("没有任何版面下载成功"); }
    if !merge { return Ok(None); }
    let name = config.merged_filename.replace("{date}", &display_date(date));
    let path = root.join(format!("{name}.pdf"));
    match merge_pdfs(&files, &path) {
        Ok(pages) => {
            println!("[合并] {} 个版面已合并为 {pages} 页: {}", files.len(), path.display());
            if !config.keep_singles {
                let dir = root.join(config.download_dir.replace("{date}", date));
                let _ = fs::remove_dir_all(dir);
            }
            Ok(Some(path))
        }
        Err(error) => { eprintln!("[错误] 合并失败，单版文件保留: {error:#}"); Ok(None) }
    }
}

pub fn download_one(config: &Config, date: Option<&str>, format: Option<&str>) -> Result<()> {
    let date = date.map(str::to_string).filter(|s| !s.is_empty()).unwrap_or_else(|| {
        if config.default_date.is_empty() { Local::now().format("%Y%m%d").to_string() } else { config.default_date.clone() }
    });
    let parsed_date = validate_date(&date)?;
    if parsed_date > Local::now().date_naive() { bail!("未来日期，人民日报尚未出版"); }
    let format = select_format(config, format)?;
    let root = config.output_root()?;
    fs::create_dir_all(&root)?;
    let downloader = Downloader::new(config)?;
    let (editions, network_ok) = downloader.editions(&date)?;
    if editions.is_empty() {
        if config.holiday_skip { println!("[信息] 无版面，按 holiday_skip 忽略"); return Ok(()); }
        bail!("{}", if network_ok { "未找到任何版面（休刊或版面筛选为空）" } else { "版面列表读取失败，请检查网络或代理" });
    }
    println!("{}  日期: {}  格式: {}", "人民日报电子版下载器", display_date(&date), format.to_uppercase());
    let mut result = None;
    if ["pdf", "both"].contains(&format.as_str()) {
        if let Some(path) = issue_pdf(config, &downloader, &date, &editions, &root, config.auto_merge)? { result = Some(path); }
    }
    if ["text", "md", "both"].contains(&format.as_str()) {
        let text_format = (format == "md").then_some("MD");
        if let Some(path) = issue_text(config, &downloader, &date, &editions, &root, text_format)? { result = Some(path); }
    }
    if let Some(path) = result.filter(|p| p.exists()) {
        open_output(&path, config.open_folder_after);
        record(config, &format!("任务完成 日期={} 格式={} 产物={}", date, format, path.display()));
        println!("[完成] 文件已生成: {}", path.display());
        #[cfg(target_os = "windows")]
        if config.beep_on_done { let _ = Command::new("rundll32").arg("user32.dll,MessageBeep").spawn(); }
    } else {
        bail!("本次未生成任何文件");
    }
    Ok(())
}

pub fn download_batch(config: &Config, expression: &str, requested_format: Option<&str>, requested_mode: Option<&str>) -> Result<()> {
    let format = select_format(config, requested_format)?;
    let mode = requested_mode.unwrap_or(&config.batch_merge_mode).to_ascii_lowercase();
    if !["each", "all"].contains(&mode.as_str()) { bail!("--merge-mode 应为 each / all"); }
    let dates = parse_batch_expr(expression).context("日期表达式错误")?;
    if dates.is_empty() { bail!("未解析到任何日期"); }
    let root = config.output_root()?;
    fs::create_dir_all(&root)?;
    let downloader = Downloader::new(config)?;
    let mut success = Vec::new();
    let mut skipped = Vec::new();
    let mut failed = Vec::new();
    let mut all_pdfs = Vec::new();
    let mut all_text = Vec::new();

    for (index, date) in dates.iter().enumerate() {
        println!("\n----------- [{}/{}] {} -----------", index + 1, dates.len(), display_date(date));
        let (editions, _) = downloader.editions(date)?;
        if editions.is_empty() { println!("[跳过] 无版面"); skipped.push(date.clone()); continue; }
        let mut day_ok = true;
        if ["pdf", "both"].contains(&format.as_str()) {
            if mode == "all" {
                let (files, missing) = downloader.download_editions(date, &editions, &root)?;
                all_pdfs.extend(files);
                if !missing.is_empty() { day_ok = false; }
            } else if issue_pdf(config, &downloader, date, &editions, &root, true)?.is_none() { day_ok = false; }
        }
        if ["text", "md", "both"].contains(&format.as_str()) {
            let text_format = (format == "md").then_some("MD");
            match issue_text(config, &downloader, date, &editions, &root, text_format) {
                Ok(Some(path)) if mode == "all" => {
                    let text = fs::read_to_string(&path)?;
                    all_text.push(text);
                    let _ = fs::remove_file(path);
                }
                Ok(Some(_)) => {}
                _ => day_ok = false,
            }
        }
        if day_ok { success.push(date.clone()); } else { failed.push(date.clone()); }
    }

    let span = format!("{}-{}", display_date(dates.first().unwrap()), display_date(dates.last().unwrap()));
    let mut final_result = None;
    let mut pdf_merge_ok = true;
    if mode == "all" && ["pdf", "both"].contains(&format.as_str()) && !all_pdfs.is_empty() {
        let path = root.join(format!("人民日报-{span}-完整版.pdf"));
        match merge_pdfs(&all_pdfs, &path) {
            Ok(pages) => { println!("[全部合并] {} 个版面 -> {} 页: {}", all_pdfs.len(), pages, path.display()); final_result = Some(path); }
            Err(error) => { pdf_merge_ok = false; eprintln!("[错误] 全部合并失败，单版 PDF 已保留: {error:#}"); }
        }
    }
    if mode == "all" && ["text", "md", "both"].contains(&format.as_str()) && !all_text.is_empty() {
        let output_format = if format == "md" { "MD".into() } else { config.text_output_format.to_ascii_uppercase() };
        let path = root.join(format!("人民日报-{span}-文字版.{}", output_format.to_ascii_lowercase()));
        let mut lines = Vec::new();
        for (index, content) in all_text.iter().enumerate() {
            if index > 0 { lines.push(String::new()); }
            lines.extend(content.lines().map(str::to_string));
        }
        output::write_text(&lines, &path)?;
        final_result = Some(path);
    }
    if mode == "all" && !config.keep_singles && pdf_merge_ok {
        for date in &dates { let _ = fs::remove_dir_all(root.join(config.download_dir.replace("{date}", date))); }
    }
    println!("\n========== 批量汇总 ==========\n成功 {} 天 | 无报跳过 {} 天 | 失败 {} 天", success.len(), skipped.len(), failed.len());
    if !skipped.is_empty() { println!("跳过日期: {}", skipped.join(", ")); }
    if !failed.is_empty() { println!("失败日期: {}", failed.join(", ")); }
    if let Some(path) = final_result { open_output(&path, config.open_folder_after); }
    record(config, &format!("批量完成 成功={} 跳过={} 失败={} 格式={} 合并={}", success.len(), skipped.len(), failed.len(), format, mode));
    if success.is_empty() { bail!("批量下载没有任何日期成功"); }
    println!("[完成] 批量下载完成");
    Ok(())
}

fn input(prompt: &str) -> Result<Option<String>> {
    use std::io::{self, Write};
    print!("{prompt}"); io::stdout().flush()?;
    let mut line = String::new();
    if io::stdin().read_line(&mut line)? == 0 { return Ok(None); }
    Ok(Some(line.trim().to_string()))
}

pub fn interactive(config: &mut Config) -> Result<()> {
    loop {
        println!("\n================ 人民日报电子版下载器 ================\n1. 单日下载\n2. 批量下载\n3. 配置管理\n4. 退出");
        match input("请选择 [1-4]: ")?.as_deref() {
            Some("1") => {
                let date = input("请输入日期（YYYYMMDD，回车=今日）: ")?.unwrap_or_default();
                let format = input("格式 [T]文字 / [M]MD / [P]PDF / [B]两者（回车=PDF）: ")?.unwrap_or_default();
                let format = match format.to_ascii_uppercase().as_str() { "T" => "text", "M" => "md", "B" => "both", _ => "pdf" };
                if let Err(error) = download_one(config, Some(&date), Some(format)) { eprintln!("[错误] {error:#}"); }
                let _ = input("按回车返回...");
            }
            Some("2") => {
                let dates = input("请输入日期范围: ")?.unwrap_or_default();
                let mode = input("合并模式 [E]每天单独 / [A]全部合并（回车=默认）: ")?.unwrap_or_default();
                let format = input("格式 [T]文字 / [M]MD / [P]PDF / [B]两者（回车=PDF）: ")?.unwrap_or_default();
                let format = match format.to_ascii_uppercase().as_str() { "T" => "text", "M" => "md", "B" => "both", _ => "pdf" };
                let mode = match mode.to_ascii_uppercase().as_str() { "A" => "all", "E" => "each", _ => &config.batch_merge_mode };
                if let Err(error) = download_batch(config, &dates, Some(format), Some(mode)) { eprintln!("[错误] {error:#}"); }
                let _ = input("按回车返回...");
            }
            Some("3") => {
                println!("默认格式: {} | 输出目录: {} | 批量: {} | 文字格式: {}", config.default_format, config.download_path, config.batch_merge_mode, config.text_output_format);
                println!("编辑 config.toml 后重启程序可修改所有选项。按回车继续。");
                let _ = input("");
            }
            Some("4") | None => break,
            _ => eprintln!("无效选项"),
        }
        thread::sleep(Duration::from_millis(30));
    }
    Ok(())
}
