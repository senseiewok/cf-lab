# Network conduct rules

These rules exist because a worker model will not infer them, and because the consequence of getting them wrong lands on the operator's IP address and the lab's name, not on the model. Every rule is enforced in `scripts/evidence/http.py` (R10 and R11 also in `shape.py` and `record.py`) and has a test in `tests/test_conduct.py`. If a rule here is not enforced in code, the code is wrong, not the rule.

The rules are written for three readers: the human who operates the machine, the orchestrating agent that writes commands, and the local worker that may be asked to draft them. The worker's part is simple: **it never writes a loop, never changes an environment variable, and never runs anything twice because the first run did not say what it hoped.**

## The rules

| # | Rule | Enforced by | Test |
| --- | --- | --- | --- |
| R1 | Only a source in the catalog with `access: api` or `access: fetch` and a `base_url` can be reached. Refusal happens before any socket opens. A source that is not in the catalog has no permission. A redirect is never followed: a 30x answer is reported as an error that names the `Location`, so a permitted host cannot send the client to an unpermitted one. | `catalog.base_url`, `Client._url` | `test_gate.py` |
| R2 | An `api` source is called only if its catalog entry records `terms_url` (the page stating the API's usage policy) and `max_rps` (our self-imposed ceiling). No paperwork, no call. The code checks that the fields are present; whether the page is the right policy page is a human judgement recorded in the catalog. | `Client._paperwork` | `test_r2_*` |
| R3 | A `fetch` source (documents, pages) is read only after the host's `robots.txt` is fetched once per process and allows the path under the group that matches our agent, falling back to `*` when no group names it (an agent-specific group replaces `*`, as in RFC 9309). `404`/`410`: no restrictions. `401`/`403`: refused. `5xx` or timeout: refused for this run. The `robots.txt` request itself is paced (R4), is not redirected (R1) and is capped (R10); a redirect or an oversized body counts as unreadable and is refused for this run. Matching follows RFC 9309, implemented here because the standard library accepted a path that clinicaltrials.gov's file disallows. | `Client._robots_ok`, `Client._load_robots`, `robots_allows` | `test_r3_*`, `test_a_robots_txt_*`, `test_an_oversized_robots_*` |
| R4 | Requests to one host are spaced by `1 / max_rps` (catalog sources that share a host share one pace, and a retry after `Retry-After` is paced too), never faster than the hard ceiling of 3 requests/second, default 1/second. The client is single-threaded; there is no concurrency to configure. | `Client._pace`, `HARD_MAX_RPS` | `test_r4_*` |
| R5 | A process may make at most 200 request attempts, including robots fetches and retries. `EVIDENCE_MAX_REQUESTS` may lower this, never raise it. Exhaustion raises; it does not wait and continue. | `Client._count`, `MAX_REQUESTS_PER_PROCESS` | `test_r5_*` |
| R6 | A host that answers `402` or `403` is in cooldown for the rest of the process. A host that answers `429` or `503` gets one retry after `Retry-After` (30 s maximum; a missing, negative or non-finite value trips cooldown at once); a second rate-limit response trips cooldown. Three consecutive errors trip cooldown. A host in cooldown is not contacted again, by any command, until the process ends. | `Client._trip`, `_check_cooldown` | `test_r6_*` |
| R7 | One user agent, naming the project and its repository, with an optional contact from `EVIDENCE_CONTACT`. No environment variable or option replaces it; `EVIDENCE_CONTACT` and `--contact` only append a contact address. Certificate verification is never disabled. | `PROJECT_UA`, `Client.__init__` | `test_r7_*` |
| R8 | Every request attempt is counted per host. The CLI prints a one-line summary to stderr at exit. `EVIDENCE_REQUEST_LOG`, if set, receives one JSON line per attempt so the operator can audit what left the machine. | `Accounting`, `Client._count` | `test_r8_*` |
| R9 | `EVIDENCE_DRY_RUN=1` makes every call return the planned URL without opening a socket. An orchestrator can see what a worker's command would do before it does it. The CLI prints every request as `planned: METHOD url` on stderr (a `fetch` source's robots.txt request included) and says that requests whose URLs depend on an earlier response (the summaries for the ids a search finds, further pages) cannot be listed. | `Client._do`, `Client.planned` | `test_r9_*`, `test_dry_run_*` |
| R10 | A response body larger than 5 MB (`MAX_BODY_BYTES`) is refused, not read to the end and not truncated: from a declared `Content-Length`, or when the streamed bytes pass the cap. A response whose JSON is not an object is an error record, and so is one whose search count or total is missing or not a number; a missing total is never read as zero. | `_read_capped`, `_classify`, `evidence/shape.py` | `test_an_oversized_*`, `test_a_json_list_*`, `test_search_with_a_bad_shape_*` |
| R11 | The contact in the User-Agent (`--contact`, `EVIDENCE_CONTACT`) must be a plain email address of at most 254 characters; anything else is refused before any request (CLI exit 2). Text from a publisher is cleaned of terminal escape sequences and control characters before the CLI prints it. | `validate_contact`, `clean_for_terminal` | `test_contact_*`, `test_one_line_*` |

## Why robots.txt is not enough, and not nothing

Two of the APIs this skill uses sit on hosts whose `robots.txt` forbids crawlers entirely or forbids the API path: NCBI E-utilities (`Disallow: /`) and ClinicalTrials.gov (`Disallow: /api/`). Both publishers also document those APIs for programmatic use. `robots.txt` is addressed to crawlers of web pages; an API's usage policy is addressed to API clients. So:

- For `api` sources the governing document is the API's published terms, which R2 requires the catalog to cite. The catalog entry's `published_limit` field records what that page says, or says plainly that no numeric limit was stated on the date it was read.
- For `fetch` sources there is no API policy; `robots.txt` is the publisher's statement, and R3 obeys it strictly, including treating an unreadable `robots.txt` as a refusal. This is deliberately stricter than RFC 9309, which permits fetching on a `4xx`. A `403` on `robots.txt` is how the CF Foundation's site answered us; the lab's position is that a publisher who will not even serve the policy file has not granted anything.

## What the rules do not cover, and who covers it

- **Across processes.** The budget and cooldown are per process. A scheduler that starts the tool every minute defeats them. Scheduled runs are a human decision; the lab's default is never more often than hourly for any one source, and never in parallel.
- **Other clients on the same IP.** The rules bind this tool. A browser, a different script, or an MCP server on the same machine is not paced by it. When evaluating any other tool (for example an MCP server), ask what *its* rules are before it shares your IP.
- **Keys.** With an API key, publishers allow higher rates. This tool does not raise its ceilings when a key is present; it has no API-key support at all.

## For the orchestrating agent

1. Run the command once. Read the stderr summary line. If it names a host in cooldown, stop; the publisher has answered.
2. Never wrap a command in a loop over a list longer than the budget allows. For a DOI list, pass all DOIs to one `retractions` call; the client paces them.
3. Use `EVIDENCE_DRY_RUN=1` on any command a worker drafted before running it for real.
4. Do not set `EVIDENCE_MAX_REQUESTS` upward. It cannot go upward, and asking is the signal that the task is too large for one process; split it across days, not threads.
5. A `blocked` or `rate_limited` status is a result to report, not a problem to solve.

## For the local worker

You may produce one command line from one question. You may not produce a script, a loop, a `while`, a `for`, a `sleep`, a `curl`, a user-agent string, or an environment variable assignment. If the question needs more than one command, say so and stop.
