use crate::{config::Config, parse::{Article, Edition}};
use anyhow::{Context, Result};
use std::{fs, path::Path};

pub fn text_lines(date: &str, editions: &[Edition], include_edition: bool, markdown: bool) -> Vec<String> {
    let mut lines = if markdown { vec![format!("# 人民日报 {date}"), String::new()] }
        else { vec![format!("人民日报  {date}"), "=".repeat(46)] };
    for edition in editions {
        if edition.articles.is_empty() { continue; }
        if include_edition {
            lines.push(String::new());
            lines.push(if markdown { format!("## {}", edition.name) } else { format!("【{}】", edition.name) });
            if !markdown { lines.push("-".repeat(46)); }
        }
        for article in &edition.articles { append_article(&mut lines, article, markdown); }
    }
    lines
}

fn append_article(lines: &mut Vec<String>, article: &Article, markdown: bool) {
    lines.extend([String::new(), if markdown { format!("### {}", article.title) } else { article.title.clone() }, String::new()]);
    for paragraph in &article.paragraphs {
        if markdown {
            lines.extend([
                if paragraph.heading { format!("#### {}", paragraph.text) } else { paragraph.text.clone() },
                String::new(),
            ]);
        } else {
            lines.push(paragraph.text.clone());
        }
    }
}

pub fn write_text(lines: &[String], path: &Path) -> Result<()> {
    fs::write(path, lines.join("\n"))
        .with_context(|| format!("写入文件失败: {}", path.display()))
}

pub fn output_path(config: &Config, root: &Path, date_display: &str, format: &str) -> std::path::PathBuf {
    root.join(format!("{}.{}", config.text_filename.replace("{date}", date_display), format.to_ascii_lowercase()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parse::Paragraph;

    #[test]
    fn text_export_preserves_editions_titles_and_heading_paragraphs() {
        let editions = vec![Edition { name: "要闻".into(), articles: vec![Article {
            title: "新闻".into(), paragraphs: vec![Paragraph { text: "导语".into(), heading: true }, Paragraph { text: "正文".into(), heading: false }]
        }] }];
        let lines = text_lines("2026-09-03", &editions, true, true);
        assert!(lines.contains(&"## 要闻".to_string()));
        assert!(lines.contains(&"#### 导语".to_string()));
        assert!(lines.contains(&"### 新闻".to_string()));
        assert!(lines.windows(2).any(|pair| pair == ["#### 导语", ""]));
        assert!(lines.windows(2).any(|pair| pair == ["正文", ""]));
    }
}
