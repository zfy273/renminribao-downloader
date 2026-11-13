use crate::{
    config::Config,
    parse::{Edition, article_ids, find_editions, parse_article},
};
use anyhow::{Context, Result, anyhow};
use indicatif::{ProgressBar, ProgressStyle};
use rayon::prelude::*;
use reqwest::blocking::{Client, Response};
use std::{
    fs::{self, File},
    io::{Read, Write},
    path::{Path, PathBuf},
    sync::Mutex,
    thread,
    time::{Duration, Instant},
};

pub struct Downloader {
    cfg: Config,
    client: Client,
    pace: Mutex<Instant>,
    bandwidth: Mutex<Instant>,
}

impl Downloader {
    pub fn new(cfg: &Config) -> Result<Self> {
        let mut builder = Client::builder()
            .timeout(Duration::from_secs(cfg.timeout.max(1)))
            .user_agent(&cfg.user_agent);
        if !cfg.proxy.trim().is_empty() {
            builder = builder.proxy(reqwest::Proxy::all(&cfg.proxy).context("代理地址无效")?);
        }
        Ok(Self {
            cfg: cfg.clone(),
            client: builder.build()?,
            pace: Mutex::new(Instant::now()),
            bandwidth: Mutex::new(Instant::now()),
        })
    }

    pub fn fetch(&self, url: &str) -> Result<Vec<u8>> {
        self.fetch_with_timeout(url, Duration::from_secs(self.cfg.timeout.max(1)))
    }

    fn fetch_with_timeout(&self, url: &str, timeout: Duration) -> Result<Vec<u8>> {
        let mut last = None;
        for attempt in 0..=self.cfg.retry {
            self.wait_turn();
            match self.read_limited(url, timeout) {
                Ok(bytes) => return Ok(bytes),
                Err(error) => {
                    tracing::warn!(attempt, retry = self.cfg.retry, %url, "请求失败: {error:#}");
                    last = Some(error);
                    if attempt < self.cfg.retry {
                        thread::sleep(self.retry_delay());
                    }
                }
            }
        }
        Err(anyhow!("网络请求失败: {}", last.unwrap()))
    }

    fn read_limited(&self, url: &str, timeout: Duration) -> Result<Vec<u8>> {
        let response = self
            .client
            .get(url)
            .header(reqwest::header::REFERER, &self.cfg.base_url)
            .timeout(timeout)
            .send()
            .and_then(Response::error_for_status)
            .with_context(|| format!("请求失败: {url}"))?;
        let mut bytes = Vec::new();
        let mut reader = response;
        let mut buffer = [0_u8; 16 * 1024];
        loop {
            let read = reader.read(&mut buffer).context("读取响应失败")?;
            if read == 0 {
                return Ok(bytes);
            }
            self.limit_bandwidth(read);
            bytes.extend_from_slice(&buffer[..read]);
        }
    }

    fn retry_delay(&self) -> Duration {
        Duration::from_secs_f64(self.cfg.retry_interval.clamp(0.0, 300.0))
    }

    fn wait_turn(&self) {
        let delay = Duration::from_secs_f64(self.cfg.request_interval.clamp(0.0, 300.0));
        if delay.is_zero() {
            return;
        }
        let mut next = self.pace.lock().expect("请求间隔锁已损坏");
        let now = Instant::now();
        let wait = next.saturating_duration_since(now);
        *next = now.max(*next) + delay;
        drop(next);
        thread::sleep(wait);
    }

    fn limit_bandwidth(&self, bytes: usize) {
        if self.cfg.rate_limit_kbps <= 0.0 || bytes == 0 {
            return;
        }
        let seconds = bytes as f64 / (self.cfg.rate_limit_kbps * 1024.0);
        let reserve = Duration::from_secs_f64(seconds.min(300.0));
        let mut available = self.bandwidth.lock().expect("限速锁已损坏");
        let start = Instant::now().max(*available);
        *available = start + reserve;
        drop(available);
        thread::sleep(start.saturating_duration_since(Instant::now()));
    }

    fn progress(&self, total: u64, message: &str) -> Option<ProgressBar> {
        if !self.cfg.show_progress {
            return None;
        }
        let bar = ProgressBar::new(total);
        if let Ok(style) = ProgressStyle::with_template(
            "  {spinner:.cyan} {msg}  {bar:28.cyan/blue}  {pos}/{len}",
        ) {
            bar.set_style(
                style
                    .progress_chars("━╸ ")
                    .tick_chars("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"),
            );
        }
        bar.set_message(message.to_string());
        Some(bar)
    }

    fn run_parallel<T, F>(&self, items: &[String], work: F) -> Vec<T>
    where
        T: Send,
        F: Fn(&Self, &str) -> T + Sync,
    {
        let workers = self.cfg.concurrent.clamp(1, 16);
        let pool = rayon::ThreadPoolBuilder::new()
            .num_threads(workers)
            .build()
            .expect("无法创建下载线程池");
        pool.install(|| items.par_iter().map(|item| work(self, item)).collect())
    }

    pub fn editions(&self, date: &str) -> Result<(Vec<String>, bool)> {
        let url = format!(
            "{}/layout/{}/{}/node_01.html",
            self.cfg.base_url,
            &date[..6],
            &date[6..]
        );
        let mut network_ok = false;
        let mut editions = match self.fetch(&url) {
            Ok(bytes) => {
                network_ok = true;
                find_editions(&String::from_utf8_lossy(&bytes))
            }
            Err(error) => {
                tracing::warn!("读取版面列表失败：{error}");
                Vec::new()
            }
        };
        if editions.is_empty() {
            let index = format!("{}/layout/index.html", self.cfg.base_url);
            if let Ok(bytes) = self.fetch(&index) {
                let text = String::from_utf8_lossy(&bytes);
                let pattern = format!(
                    r"{}/node_(\d+)\.html",
                    regex::escape(&format!("{}/{}", &date[..6], &date[6..]))
                );
                if let Ok(re) = regex::Regex::new(&pattern) {
                    editions = re.captures_iter(&text).map(|m| m[1].to_string()).collect();
                    editions.sort_by_key(|n| n.parse::<u32>().unwrap_or(u32::MAX));
                    editions.dedup();
                }
            }
        }
        if !self.cfg.edition_filter.is_empty() {
            editions.retain(|number| {
                number
                    .parse::<u32>()
                    .ok()
                    .is_some_and(|n| self.cfg.edition_filter.contains(&n))
            });
        }
        Ok((editions, network_ok))
    }

    fn node_url(&self, date: &str, edition: &str) -> String {
        format!(
            "{}/layout/{}/{}/node_{}.html",
            self.cfg.base_url,
            &date[..6],
            &date[6..],
            edition
        )
    }

    pub fn download_editions(
        &self,
        date: &str,
        editions: &[String],
        root: &Path,
    ) -> Result<(Vec<PathBuf>, Vec<String>)> {
        let dir = root.join(self.cfg.download_dir.replace("{date}", date));
        fs::create_dir_all(&dir)?;
        let progress = self.progress(editions.len() as u64, "下载 PDF");
        let outcomes = self.run_parallel(editions, |downloader, edition| {
            let result = downloader.download_one_pdf(date, edition, &dir);
            if let Some(bar) = &progress {
                bar.inc(1);
            }
            result
        });
        if let Some(bar) = progress {
            bar.finish_and_clear();
        }
        let mut files = Vec::new();
        let mut failed = Vec::new();
        for (edition, outcome) in editions.iter().zip(outcomes) {
            match outcome {
                Ok(path) => files.push(path),
                Err(error) => {
                    tracing::error!("第{edition}版下载失败: {error:#}");
                    failed.push(edition.clone());
                }
            }
        }
        Ok((files, failed))
    }

    fn download_one_pdf(&self, date: &str, edition: &str, dir: &Path) -> Result<PathBuf> {
        let html = String::from_utf8_lossy(&self.fetch(&self.node_url(date, edition))?).into_owned();
        let re = regex::Regex::new(r"attachement/\d{6}/\d{2}/[0-9a-f-]+\.pdf")?;
        let relative = re.find(&html).context("未找到 PDF 链接")?.as_str();
        let bytes = self.fetch_with_timeout(
            &format!("{}/{}", self.cfg.base_url, relative),
            Duration::from_secs(self.cfg.timeout.max(120)),
        )?;
        let path = dir.join(format!("rmrb_{date}_{edition}.pdf"));
        File::create(&path)?.write_all(&bytes)?;
        Ok(path)
    }

    pub fn crawl_text(&self, date: &str, editions: &[String]) -> Vec<Edition> {
        let progress = self.progress(editions.len() as u64, "抓取正文");
        let result = self.run_parallel(editions, |downloader, number| {
            let edition = downloader.crawl_edition(date, number);
            if let Some(bar) = &progress {
                bar.inc(1);
            }
            tracing::info!(
                "第{number}版({}): 抓取 {} 篇文章",
                edition.name,
                edition.articles.len()
            );
            edition
        });
        if let Some(bar) = progress {
            bar.finish_and_clear();
        }
        result
    }

    fn crawl_edition(&self, date: &str, number: &str) -> Edition {
        let html = match self.fetch(&self.node_url(date, number)) {
            Ok(bytes) => String::from_utf8_lossy(&bytes).into_owned(),
            Err(error) => {
                tracing::error!("第{number}版抓取失败: {error}");
                return Edition {
                    name: format!("第{number}版"),
                    articles: Vec::new(),
                };
            }
        };
        let name = regex::Regex::new(&format!(r"第{}版[：:]\s*([^<]+)", regex::escape(number)))
            .ok()
            .and_then(|re| re.captures(&html).map(|m| m[1].trim().to_string()))
            .unwrap_or_else(|| format!("第{number}版"));
        let mut articles = Vec::new();
        for id in article_ids(&html) {
            let url = format!(
                "{}/content/{}/{}/content_{}.html",
                self.cfg.base_url,
                &date[..6],
                &date[6..],
                id
            );
            if let Ok(bytes) = self.fetch(&url) {
                if let Some(article) = parse_article(&String::from_utf8_lossy(&bytes)) {
                    articles.push(article);
                }
            }
        }
        Edition { name, articles }
    }
}

pub fn merge_pdfs(inputs: &[std::path::PathBuf], output: &Path) -> Result<usize> {
    let first = inputs.first().context("没有可合并的 PDF 文件")?;
    let mut merged = lopdf::Document::load(first)
        .with_context(|| format!("读取 PDF 失败: {}", first.display()))?;
    let mut pages = merged.get_pages().len();

    for path in inputs.iter().skip(1) {
        let mut document = lopdf::Document::load(path)
            .with_context(|| format!("读取 PDF 失败: {}", path.display()))?;
        document.renumber_objects_with(merged.max_id + 1);
        let source_pages_root = document.catalog()?.get(b"Pages")?.as_reference()?;
        pages += document.get_pages().len();
        let root_pages = merged.catalog()?.get(b"Pages")?.as_reference()?;

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
