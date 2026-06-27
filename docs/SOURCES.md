# Structural Source Registry

This document tracks the verified CSS selectors and cleaning strategies for each news source integrated into the pipeline.

## Regional (Northeast India)

| Source | Title | Body | Cleaning Rules |
| :--- | :--- | :--- | :--- |
| **EastMojo** | `h1.entry-title` | `div.entry-content` | Strip Premium widgets, "Dear Reader" blocks, and social share bars. Preserve internal image placeholders. |
| **Shillong Times** | `h1.tdb-title-text` | `div.td-post-content` | Strip TagDiv ad blocks, meta tags, and inline style blocks. Blacklist generic TST logos. |
| **Arunachal Times** | `h1.entry-title` | `div.td-post-content` | Handle TagDiv sharing bars and next/prev links. Extract date from `itemprop` metadata. |
| **Nagaland Post** | `h1.tdb-title-text` | `div.td-post-content` | Prioritize `data-src` for lazy-loaded images. Strip TagDiv author/ad blocks. |
| **Sikkim Express** | `h1.news-details-title` | `div.news-details-text` | *Research Complete* |

## National (India)

| Source | Title | Body | Cleaning Rules |
| :--- | :--- | :--- | :--- |
| **The Hindu** | `h1.title` | `div[itemprop="articleBody"]` | Strip comments-shares and embedded picture meta. |
| **Indian Express** | `h1.native_story_title` | `div#pcl-full-content` | Handle synopsis and remove ev-engagement blocks. |
| **The Print** | `h1.tdb-title-text` | `div.td-post-content` | Strip TagDiv author/meta data. |

## International

| Source | Title | Body | Cleaning Rules |
| :--- | :--- | :--- | :--- |
| **BBC Asia** | `h1` | `article` | Remove React/Next.js boilerplate and internal header/footer. |
| **The Guardian** | `h1` | `div#maincontent` | Strip submeta and affiliate tags. |
| **Al Jazeera** | `h1` | `div.wysiwyg` | Strip social floating bars and sidebar widgets. |
| **AP News** | `h1.Page-headline` | `div.RichTextStoryBody` | Preserve LinkEnhancement text but strip ad placeholders. |
