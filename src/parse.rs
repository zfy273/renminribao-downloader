use anyhow::{Context, Result, bail};
use chrono::{NaiveDate, Local, Duration};
use regex::Regex;
use scraper::{Html, Selector};
use std::collections::HashSet;

#[derive(Clone, Debug)]
pub struct Paragraph {
    pub text: String,
    pub heading: bool,
}

#[derive(Clone, Debug)]
pub struct Article {
    pub title: String,
    pub paragraphs: Vec<Paragraph>,
}

#[derive(Clone, Debug)]
pub struct Edition {
    pub name: String,
    pub articles: Vec<Article>,
}

pub fn validate_date(raw: &str) -> Result<NaiveDate> {
    if raw.len() != 8 || !raw.bytes().all(|b| b.is_ascii_digit()) {
        bail!("日期应为 8 位数字 YYYYMMDD");
    }
    NaiveDate::parse_from_str(raw, "%Y%m%d").context("日期不存在（月份或日期越界）")
}

pub fn display_date(raw: &str) -> String {
    format!("{}-{}-{}", &raw[..4], &raw[4..6], &raw[6..])
}

pub fn parse_batch_expr(expr: &str) -> Result<Vec<String>> {
    let today = Local::now().date_naive();
    let mut result = Vec::new();
    let mut seen = HashSet::new();
    for part in expr.split(',').map(str::trim).filter(|s| !s.is_empty()) {
        if let Some((start, end)) = part.split_once('-') {
            let first = validate_date(start.trim()).context("无效起始日期")?;
            let last = if end.trim().is_empty() { today } else { validate_date(end.trim()).context("无效结束日期")? };
            if first > last { bail!("起始日期晚于结束日期"); }
            let mut date = first;
            while date <= last {
                let value = date.format("%Y%m%d").to_string();
                if seen.insert(value.clone()) { result.push(value); }
                date += Duration::days(1);
            }
        } else {
            let date = validate_date(part)?;
            let value = date.format("%Y%m%d").to_string();
            if seen.insert(value.clone()) { result.push(value); }
        }
    }
    Ok(result)
}

pub fn find_editions(html: &str) -> Vec<String> {
    let re = Regex::new(r#"href="node_(\d+)\.html""#).unwrap();
    let mut values: Vec<String> = re.captures_iter(html).map(|c| c[1].to_string()).collect();
    values.sort_by_key(|v| v.parse::<u32>().unwrap_or(u32::MAX));
    values.dedup();
    values
}

pub fn article_ids(html: &str) -> Vec<String> {
    let re = Regex::new(r"content/\d{6}/\d{2}/content_(\d+)\.html").unwrap();
    let mut values: Vec<String> = re.captures_iter(html).map(|c| c[1].to_string()).collect();
    values.sort_by_key(|v| v.parse::<u64>().unwrap_or(u64::MAX));
    values.dedup();
    values
}

pub fn parse_article(html: &str) -> Option<Article> {
    let document = Html::parse_document(html);
    let title_selector = Selector::parse("h1 p").unwrap();
    let title = document.select(&title_selector).next().map(|e| e.text().collect::<String>().trim().to_string())
        .filter(|s| !s.is_empty())
        .or_else(|| Selector::parse("title").ok().and_then(|s| document.select(&s).next().map(|e| e.text().collect::<String>().trim().to_string())))?;
    let marker = html.find("<!--enpcontent-->")?;
    let tail = &html[marker + "<!--enpcontent-->".len()..];
    let end = tail.find("<!--/enpcontent-->")?;
    let body = Html::parse_fragment(&tail[..end]);
    let p = Selector::parse("p").unwrap();
    let strong = Selector::parse("strong").unwrap();
    let paragraphs = body.select(&p).filter_map(|node| {
        let text = node.text().collect::<String>().trim().replace('\u{3000}', "　");
        (!text.is_empty()).then(|| Paragraph { text, heading: node.select(&strong).next().is_some() })
    }).collect::<Vec<_>>();
    (!paragraphs.is_empty()).then_some(Article { title, paragraphs })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_date_and_rejects_invalid() {
        assert!(validate_date("20260903").is_ok());
        assert!(validate_date("20261301").is_err());
        assert!(validate_date("2026093").is_err());
    }

    #[test]
    fn expands_and_deduplicates_batch_ranges() {
        let values = parse_batch_expr("20260901-20260903,20260902,20260905").unwrap();
        assert_eq!(values, ["20260901", "20260902", "20260903", "20260905"]);
    }

    #[test]
    fn extracts_ordered_unique_editions_and_articles() {
        assert_eq!(find_editions(r#"href="node_02.html" href="node_01.html" href="node_02.html""#), ["01", "02"]);
        assert_eq!(article_ids("content/202609/03/content_123.html content/202609/03/content_2.html"), ["2", "123"]);
    }

    #[test]
    fn parses_article_title_and_heading_paragraph() {
        let article = parse_article("<h1><p>标题</p></h1><!--enpcontent--><p><strong>导语</strong></p><p>正文</p><!--/enpcontent-->").unwrap();
        assert_eq!(article.title, "标题");
        assert_eq!(article.paragraphs.len(), 2);
        assert!(article.paragraphs[0].heading);
    }
}
