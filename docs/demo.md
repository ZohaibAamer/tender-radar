# Demo: the flagship question, answered live

**Setup:** Claude Desktop connected to the hosted MCP connector
(`https://tender-radar-lime.vercel.app/mcp`). Data snapshot: notices
published 2026-10-04 → 2026-11-03 across Find a Tender, Contracts Finder,
and TED. Asked on 2026-11-04. Reproducible output, not a mock-up.

**Question:**

> Which open tenders fit a 50-person UK data consultancy? Use the example
> profile and give deadlines.

**Answer (verbatim):**

The tool matched 15 open tenders to the example profile. Its matching is
loose, since it only checks the tender's category code (CPV) and keyword
overlap. So I've sorted the results by how well they actually fit a data
consultancy.

### Strong fit (data, analytics, AI)

| Deadline | Tender | Buyer | Est. value |
|---|---|---|---|
| 11 Nov | Tech support for NHS Supplier Roadmap (PCF requirements) | NHS England | £96k |
| 19 Nov | World Model for SCAT | Velindre NHS Trust | £50k |
| 20 Nov | Digital Analytics Tool | BBC | Not stated |
| 27 Nov | AI Creator Control | Intellectual Property Office | £80k |
| 30 Nov | Embedded product team, Alpha/Beta digital service | Education Endowment Foundation | £730k |

### Possible fit (research and evaluation work where data analysis is central)

| Deadline | Tender | Buyer | Est. value |
|---|---|---|---|
| 16 Nov | Borderlands Phase 2 Evaluation | Teesside University | £25k |
| 23 Nov | Belfast Stories – Story Engine | Belfast City Council | £550k |
| 2 Dec | VRU Learning Partner | Mayor's Office for Policing and Crime | £300k |
| 3 Dec | Evaluation Scoping Studies (2 lots) | Gambling Commission | £50k |

### Weak fit (I'd skip these)

These matched only because they share a broad consulting category: HR and
payroll system (NI Assembly), candidate assessment (Ingeus), coaching
consultancy (Sport Wales), youth engagement (Maidstone), training providers
(Growth Company, closing 6 Nov), MoD Culture Toolkit.

### How to read these results

- CPV codes are the EU/UK procurement category codes. The profile uses three
  divisions: 72 (IT services), 73 (research and development), and
  79 (business consulting). Division 79 is very broad, which is why HR and
  training tenders appear.
- "Planned" status (the MoD and NI Assembly tenders) means the buyer has
  given early notice and the deadline may still move. Notices marked
  "active" have firm deadlines.
- Value matters for a 50-person firm. The EEF (£730k) and Belfast (£550k)
  contracts suit your size. The £25–50k lots are often won by smaller
  specialists or sole traders.

The most urgent strong fit is NHS England on 11 Nov, with only a week left.

---

**Why this demo matters:** the division of labor is the architecture. The
MCP server did the governed retrieval (`match_profile`: CPV + keyword
matching with reasons, citations included); the model layered judgment on
top — fit-ranking, status caveats, value-vs-firm-size. Even the model's
critique of the matcher ("loose") restates the documented limitation in
this repo's README.
