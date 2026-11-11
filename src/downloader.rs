use crate::{config::Config, parse::{Edition, find_editions, article_ids, parse_article}};
use anyhow::{Context, Result, anyhow};
use indicatif::{ProgressBar, ProgressStyle};
use reqwest::blocking::Client;
use std::{fs::{self, File}, io::Write, path::Path, thread, time::{Duration, Instant}};

pub struct Downloader {
    cfg: Config,
    client: Client,
}

impl Downloader {
    pub fn new(cfg: &Config) -> Result<Self> {
        let mut builder = Client::builder()
            .timeout(Duration::from_secs(cfg.timeout.max(1)))
            .user_agent(&cfg.user_agent);
        if !cfg.proxy.trim().is_empty() {
            builder = builder.proxy(reqwest::Proxy::all(&cfg.proxy).context("代理地址无效")?);
        }
        Ok(Self { cfg: cfg.clone(), client: builder.build()? })
    }

    pub fn fetch(&self, url: &str) -> Result<Vec<u8>> {
        self.fetch_with_timeout(url, Duration::from_secs(self.cfg.timeout.max(1)))
    }

    fn fetch_with_timeout(&self, url: &str, timeout: Duration) -> Result<Vec<u8>> {
        let mut last = None;
        for attempt in 0..=self.cfg.retry {
            match self.client.get(url).header(reqwest::header::REFERER, &self.cfg.base_url)
                .timeout(timeout).send().and_then(|r| r.error_for_status()).and_then(|r| r.bytes()) {
                Ok(bytes) => return Ok(bytes.to_vec()),
                Err(error) => {
                    last = Some(error);
                    if attempt < self.cfg.retry { thread::sleep(Duration::from_secs_f64(self.cfg.retry_interval)); }
                }
            }
        }
        Err(anyhow!("网络请求失败: {}", last.unwrap()))
    }

    pub fn editions(&self, date: &str) -> Result<(Vec<String>, bool)> {
        let url = format!("{}/layout/{}/{}/node_01.html", self.cfg.base_url, &date[..6], &date[6..]);
        let mut network_ok = false;
        let mut editions = match self.fetch(&url) {
            Ok(bytes) => { network_ok = true; find_editions(&String::from_utf8_lossy(&bytes)) },
            Err(error) => { eprintln!("  [网络] 读取版面列表失败：{error}"); Vec::new() }
        };
        if editions.is_empty() {
            let index = format!("{}/layout/index.html", self.cfg.base_url);
            if let Ok(bytes) = self.fetch(&index) {
                let text = String::from_utf8_lossy(&bytes);
                let pattern = format!(r"{}/node_(\d+)\.html", regex::escape(&format!("{}/{}", &date[..6], &date[6..])));
                if let Ok(re) = regex::Regex::new(&pattern) {
                    editions = re.captures_iter(&text).map(|m| m[1].to_string()).collect();
                    editions.sort_by_key(|n| n.parse::<u32>().unwrap_or(u32::MAX));
                    editions.dedup();
                }
            }
        }
        if !self.cfg.edition_filter.is_empty() {
            editions.retain(|number| number.parse::<u32>().ok().is_some_and(|n| self.cfg.edition_filter.contains(&n)));
        }
        Ok((editions, network_ok))
    }

    fn node_url(&self, date: &str, edition: &str) -> String {
        format!("{}/layout/{}/{}/node_{}.html", self.cfg.base_url, &date[..6], &date[6..], edition)
    }

    pub fn download_editions(&self, date: &str, editions: &[String], root: &Path) -> Result<(Vec<std::path::PathBuf>, Vec<String>)> {
        let dir = root.join(self.cfg.download_dir.replace("{date}", date));
        fs::create_dir_all(&dir)?;
        let progress = ProgressBar::new(editions.len() as u64);
        progress.set_style(ProgressStyle::with_template("{spinner:.green} [{bar:40.cyan/blue}] {pos}/{len} {msg}")?);
        let mut files = Vec::new();
        let mut failed = Vec::new();
        for edition in editions {
            progress.set_message(format!("第{edition}版"));
            let outcome = (|| -> Result<std::path::PathBuf> {
                let html = String::from_utf8_lossy(&self.fetch(&self.node_url(date, edition))?).into_owned();
                let re = regex::Regex::new(r"attachement/\d{6}/\d{2}/[0-9a-f-]+\.pdf")?;
                let relative = re.find(&html).context("未找到 PDF 链接")?.as_str();
                let bytes = self.fetch_with_timeout(&format!("{}/{}", self.cfg.base_url, relative), Duration::from_secs(self.cfg.timeout.max(120)))?;
                let path = dir.join(format!("rmrb_{date}_{edition}.pdf"));
                let mut file = File::create(&path)?;
                let start = Instant::now();
                file.write_all(&bytes)?;
                if self.cfg.rate_limit_kbps > 0.0 {
                    let expected = bytes.len() as f64 / (self.cfg.rate_limit_kbps * 1024.0);
                    let remaining = expected - start.elapsed().as_secs_f64();
                    if remaining > 0.0 { thread::sleep(Duration::from_secs_f64(remaining)); }
                }
                Ok(path)
            })();
            match outcome {
                Ok(path) => files.push(path),
                Err(error) => { eprintln!("  第{edition}版下载失败: {error:#}"); failed.push(edition.clone()); }
            }
            progress.inc(1);
            if self.cfg.concurrent == 1 && self.cfg.request_interval > 0.0 {
                thread::sleep(Duration::from_secs_f64(self.cfg.request_interval));
            }
        }
        progress.finish_and_clear();
        Ok((files, failed))
    }

    pub fn crawl_text(&self, date: &str, editions: &[String]) -> Vec<Edition> {
        let mut result = Vec::new();
        for number in editions {
            let html = match self.fetch(&self.node_url(date, number)) {
                Ok(bytes) => String::from_utf8_lossy(&bytes).into_owned(),
                Err(error) => { eprintln!("  第{number}版抓取失败: {error}"); continue; }
            };
            let name = regex::Regex::new(&format!(r"第{}版[：:]\s*([^<]+)", regex::escape(number)))
                .ok().and_then(|re| re.captures(&html).map(|m| m[1].trim().to_string()))
                .unwrap_or_else(|| format!("第{number}版"));
            let mut articles = Vec::new();
            for id in article_ids(&html) {
                let url = format!("{}/content/{}/{}/content_{}.html", self.cfg.base_url, &date[..6], &date[6..], id);
                if let Ok(bytes) = self.fetch(&url) {
                    if let Some(article) = parse_article(&String::from_utf8_lossy(&bytes)) { articles.push(article); }
                }
                if self.cfg.request_interval > 0.0 { thread::sleep(Duration::from_secs_f64(self.cfg.request_interval)); }
            }
            println!("  第{number}版({name}): 抓取 {} 篇文章", articles.len());
            result.push(Edition { name, articles });
        }
        result
    }

}

pub fn merge_pdfs(inputs: &[std::path::PathBuf], output: &Path) -> Result<usize> {
    let first = inputs.first().context("没有可合并的 PDF 文件")?;
    let mut merged = lopdf::Document::load(first)
        .with_context(|| format!("读取 PDF 失败: {}", first.display()))?;
    let mut pages = merged.get_pages().len();

    for path in inputs.iter().skip(1) {
        let mut document = lopdf::Document::load(path).with_context(|| format!("读取 PDF 失败: {}", path.display()))?;
        document.renumber_objects_with(merged.max_id + 1);
        let source_pages_root = document
            .catalog()?
            .get(b"Pages")?
            .as_reference()?;
        pages += document.get_pages().len();
        let root_pages = merged
            .catalog()?
            .get(b"Pages")?
            .as_reference()?;

        let source_max_id = document.max_id;
        merged.objects.append(&mut document.objects);
        merged.max_id = source_max_id;
        merged
            .get_object_mut(source_pages_root)?
            .as_dict_mut()?
            .set("Parent", root_pages);

        let kids = merged
            .get_object_mut(root_pages)?
            .as_dict_mut()?
            .get_mut(b"Kids")?
            .as_array_mut()?;
        kids.push(source_pages_root.into());
        merged
            .get_object_mut(root_pages)?
            .as_dict_mut()?
            .set("Count", pages as i64);
    }

    merged.save(output).context("写入合并 PDF 失败")?;
    Ok(pages)
}
