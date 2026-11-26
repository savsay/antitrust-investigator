# Antitrust Investigator

A Claude skill for compliance and legal teams that reviews corporate email, Teams chats, SharePoint/OneDrive files, file shares and Microsoft Purview exports for competition-law (antitrust) risk. It finds bid rigging, price fixing, market and customer sharing, sensitive information exchange with competitors, wage-fixing and no-poach agreements, resale price maintenance, abuse-of-dominance indicators and gun-jumping.

Every finding carries a verbatim quote with character offsets, a control ID from a 147-control catalogue, a legal source with its version, the facts that are still missing and the innocent explanations to rule out. The skill produces **risk indicators for a qualified lawyer, not legal conclusions**.

The skill's instructions and catalogue are in Turkish (Turkish Competition Act No. 4054 and Rekabet Kurumu guidelines first), with EU, US, UK, OECD and World Bank sources. It reviews documents in Turkish, English and Russian, and you can talk to it in Turkish or English.

## Install

- **Claude (web, desktop, mobile):** add it from the directory on the Customize page, or upload `rekabet-ihlali-inceleme.zip` from the [latest release](https://github.com/savsay/antitrust-investigator/releases/latest) under Customize > Skills.
- **Claude Code:**

```
/plugin install rekabet-ihlali-inceleme --marketplace savsay/antitrust-investigator
```

## What it does

1. **Scope gate.** Before reading employee communications it asks who authorised the review and its limits (entities, custodians, dates, systems). Admin access is not treated as legal authority.
2. **Pre-scan.** `scripts/rekabet_tarama.py` builds a reading queue from concept co-occurrence (competitor + agreement + price/bid/territory/wages) across EML, MSG, DOCX, XLSX (hidden sheets and comments), PPTX, PDF, HTML and TXT, and writes a SHA-256 inventory.
3. **Bid-data screens.** `scripts/ihale_analiz.py` flags winner rotation, constant price gaps, near-identical bids, cover-bid profiles and repeated withdrawals in a CSV of tender results.
4. **Contextual reading and report.** Claude reads each hit in its full thread and writes a report (Claude doc and Word file) plus `bulgular.json`. Findings implicating senior management are routed to an independent channel, and whistleblower identities are kept out.

## What it runs, reads and sends

- **Runs** only the bundled Python scripts (standard library; optional `python-docx`, `openpyxl`, `pypdf`, `python-pptx`, `extract-msg` for document extraction). The scripts are read-only on your files and write only their own CSV output.
- **Reads** only the files, folders and connectors you point it to within the authorised scope.
- **Sends** nothing to third parties. When its legal sources are missing or out of date it may use Claude's web search on official sites (rekabet.gov.tr, mevzuat.gov.tr, europa.eu, justice.gov, gov.uk, oecd.org and similar). Those queries contain legal topics only, never names, projects, customers or amounts.
- No MCP servers, hooks, credentials or network calls from scripts.

## Limits

Output is not legal advice. Bundled sources are marked as pending legal approval. Reviewing employee communications needs a lawful basis and proportionality under KVKK/GDPR and local labour law.

Source, tests and documentation: https://github.com/savsay/antitrust-investigator · License: MIT
