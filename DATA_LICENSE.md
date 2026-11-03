# Data licensing and attribution

The **code** in this repository is MIT-licensed (see `LICENSE`). The **tender
data** — in the committed test fixture under `fixtures/`, in the GitHub
Release assets, and in anything you ingest yourself — belongs to its source
portals and is reused under their terms:

## UK Find a Tender and UK Contracts Finder

Contains public sector information licensed under the
**Open Government Licence v3.0**:
<http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/>

Both portals declare this licence in their OCDS API responses (the package
`license` field). Attribution: data originally published on
[Find a Tender](https://www.find-tender.service.gov.uk/) and
[Contracts Finder](https://www.contractsfinder.service.gov.uk/).

## EU TED (Tenders Electronic Daily)

Data from [TED](https://ted.europa.eu/), © European Union. Reuse is permitted
provided the source is acknowledged, under the European Commission's reuse
policy (Commission Decision 2011/833/EU); see TED's legal notice for details.

## Synthetic rows

The fixture contains one synthetic notice (`SYNTHETIC-INJECTION-001`,
listed in `fixtures/manifest.json`) created for prompt-injection testing.
It is not real procurement data and links to `example.invalid`.
