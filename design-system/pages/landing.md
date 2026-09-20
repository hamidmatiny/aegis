# Landing page overrides

Overrides `design-system/aegis/MASTER.md` for `defenseaegis.org/` only.

## Atmosphere

- Full-bleed light canvas (`#F8FAFC`) with a **navy hero band** (`#0F172A`) for the first viewport — brand-first, one headline, one supporting sentence, one primary CTA (GitHub), one dominant interception diagram.
- Below the fold: white cards on muted canvas; accent blue for interactive chrome only.

## Section order

1. Hero (navy) — gateway identity + GitHub CTA
2. Proof strip — GitHub activity, awesome-llm-security `emerging.md`, issue #63
3. How it works — **InterceptionDemo** (four scenarios + try-it-yourself)
4. What you get — three feature cards (existing copy)
5. Applied example + pricing — existing substance, restyled
6. Privacy + OSS + footer

## Interception demo

- Nodes: App → AEGIS → Provider
- Outcomes: ALLOW (green), BLOCK (red), HOLD (amber)
- Motion: packet slides along the path; active node opacity/transform only
- Try-it: live `POST /v1/chat/completions` via existing `sendChatCompletion`

## Nav

Sticky light header on scroll past hero; on hero band use translucent navy header with light text (handled in Layout + `.lp` classes).
