# brisart_ai/web/

This folder handles optional public-web research. Search providers return leads, the crawler selects and indexes usable pages, and the fetcher applies the destination and redirect rules before reading responses. The application can use its local index without invoking this pipeline.

## `search.py`

`search_public_web(query, limit=5, with_titles=False)` returns result URLs, or `(url, title)` pairs when `with_titles` is true. The limit is kept between 1 and 50. An empty query returns an empty list.

**Providers.** Tried in this order, each asked only for the results still missing: Startpage, Brave Search, DuckDuckGo HTML, DuckDuckGo Lite, Bing HTML, Mojeek, then the Wikipedia API. The first six are HTML pages that are read by their markup, with no API key. DuckDuckGo and Bing results are found by their result-link classes and headings; Startpage, Brave and Mojeek are read by a general rule that takes links to hosts other than the search engine's own and skips help, support, account, login, static and asset hosts. The Wikipedia API is the last resort.

**Filtering.** A provider whose page contains a challenge or rate-limit marker ("captcha", "unusual traffic", "too many requests" and similar) is skipped. Each result is then judged on its own: it is kept only if its URL or title contains a word of more than three letters from the query (or that word without a trailing `s`) that is not a function word, so a batch that mixes good and off-topic results loses only the off-topic ones. A batch with no related result is discarded and the next provider is tried.

**Cleaning.** DuckDuckGo's `uddg` and Bing's `/ck/a` redirect wrappers are unwrapped, tracking parameters (`utm_*`, `fbclid`, `gclid` and others) are removed, and non-HTTP schemes, search-engine hosts and blocked hosts are dropped. Results are de-duplicated, ignoring a trailing slash and case.

---

## `crawler.py`

**Query forms.** `clean_search_query(query)` keeps the question's wording and removes only extra spaces and outer punctuation, because the natural phrasing matches pages that contain the answer. `search_keyword_fallback(query)` removes function words and adds hint words for some questions: "how many" adds *number*, "how much" *amount*, "how old" *age*, "how tall" *height*, "how long" *length duration*, "how far" *distance* and "population of" *population*.

**Scoring.** `score_result(url, topic_terms, query="", title="")` is a hand-tuned integer score, not a learned model:

| Signal | Points |
|---|---|
| Topic term in the URL path | +3 each |
| Topic term in the host or title | +2 each |
| More than one term matched | +2 for each term after the first |
| An article-shaped path segment (hyphens or underscores, over eight characters) when a term matched | +2 |
| The query as a phrase in the URL and title | +4 |
| Intent adjustment from `intent.score_intent` | scaled by 2 and rounded |
| No topic term matched | -2 |
| Account or login host prefix | -4 |
| Low-value host | -4 |
| Listing, search or shop path | -3 |

`rank_results()` de-duplicates and sorts best first, keeping input order on ties. `explain_ranking()` returns the same numbers as a per-URL breakdown, which the replay script prints.

**Indexing.** `crawl_urls_to_index(urls, index, limit=20, depth=0, delay=1.0, same_domain_only=True, topic_terms=None)` visits each URL once and returns the number of pages indexed. For each page it:

1. skips it when the blocklist rejects it, `robots.txt` disallows it, or a redirect ends at a disallowed address;
2. fetches it and counts errors and empty pages;
3. skips it as a duplicate when a source with the same content hash is already indexed;
4. otherwise adds it as a `web` source.

With `depth` above 0 it also follows the page's links, within the same site by default. The limit counts pages indexed, not pages requested. A pause of `delay` seconds follows each page that was fetched and had text.

`web_search_and_ingest(query, index, limit=5, crawl_depth=0)` is the whole path: it searches the natural form and, if different, the keyword form, drops rejected hosts, ranks the results using their titles, and crawls the top `limit`. It returns the number of pages indexed, and 0 when no usable result was found. It prints its progress.

---

## `fetcher.py`

`fetch_url(url)` returns a `FetchResult` and never raises; every failure is recorded in its `error` field.

- Only `http` and `https` are fetched. A local or private destination is refused before any connection is opened, and a redirect to one is refused as well.
- Reading stops at 2,000,000 bytes and the page is reported as too large; the request times out after 15 seconds.
- `text/html` and `application/xhtml` pages go through `html_to_text()`; `text/plain` is returned as it is; anything else is `unsupported content type`.
- The text is decoded with the charset the server declares, or UTF-8.

---

## `policy.py`

- **`USER_AGENT`** names BrisartAI and its version.
- **`is_local_or_private_host(hostname)`** is true for an empty host, `localhost` and its variants, names ending in `.local` or `.localhost`, and IP addresses that are private, loopback, link-local, multicast, reserved or unspecified. It runs before any network access. `is_localhost` is an older name for it.
- **`RobotsCache`** fetches `robots.txt` once per site and keeps it for the life of the cache. `allowed(url)` is false for non-HTTP schemes and private hosts. For a public host it answers from the parsed rules; if `robots.txt` is missing, unreachable, larger than 512,000 bytes, forbidden (401 or 403), malformed or fails to evaluate, fetching is allowed. Only a successfully parsed `Disallow` blocks a page. The `robots.txt` request times out after 8 seconds.

---

## `models.py` and `stats.py`

`FetchResult` is a dataclass with `url`, `status`, `content_type`, `title`, `text`, `links` and `error` (empty on success). `CrawlStats` holds `requested`, `indexed`, `skipped_duplicates`, `skipped_empty` and `errors`, all starting at 0, and `print_summary()` prints them as a "Web Crawl Summary".

---

## Limits

- The providers are public web pages that change their markup and block automated requests without notice, so results can be empty or vary from one run to the next.
- A hostname is checked before the request and again after redirects, but the address a name resolves to is not pinned, so DNS rebinding is not prevented.
- Search-result snippets are not used in ranking; only URLs and titles are.

---

## `tests/`

| File | Covers |
|---|---|
| `test_search.py` | Redirect unwrapping, tracking removal, result cleaning, de-duplication and per-result relevance, with no network |
| `test_crawler.py` | Query cleaning, the keyword form, scoring, ranking, rejection, duplicate detection, with no network |
| `test_fetcher.py` | Error handling for an empty URL, a bad URL and an unreachable reserved address (`198.51.100.1`) |
| `test_public_fetch_policy.py` | A private address never opens a connection and a redirect to one is rejected |
| `test_policy.py` | Private-host detection and the user agent |
| `test_models.py`, `test_stats.py` | `FetchResult` and `CrawlStats` |

The live provider requests are not exercised by any test.
