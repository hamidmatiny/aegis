# Landing redesign evidence (2026-09-20)

## Design system

Generated via `ui-ux-pro-max` `--design-system` and persisted at:

- `design-system/aegis/MASTER.md`
- `design-system/pages/landing.md` (page overrides)

| Token | Value |
|-------|-------|
| Style | Trust & Authority + high-craft precision |
| Primary | `#0F172A` navy |
| CTA | `#0369A1` |
| Canvas | `#F8FAFC` |
| Type | IBM Plex Sans (craft override from Roboto) |

Landing pattern guidance: Hero + Features + CTA (`--domain landing`). Motion: transform/opacity only; reduced-motion respected (`--domain gsap` principles applied in CSS, no GSAP dependency).

## Screenshots

| Shot | Source | File |
|------|--------|------|
| Before desktop | Live `https://defenseaegis.org` | `before-desktop.png` |
| Before mobile | Live `https://defenseaegis.org` | `before-mobile.png` |
| After desktop | Local Vite preview of this branch (`npm run build && preview`) | `after-desktop.png` |
| After interception | Same preview, scrolled to `#how-it-works` | `after-interception.png` |
| After mobile | Same preview @ 375×812 | `after-mobile.png` |

Live **after** shots require this PR merged and the portal redeployed to Oracle — Track A is PR-only; do not treat local preview as production until deploy.

## Checklist

- [x] Contrast-oriented navy/light surfaces; focus rings on interactive controls
- [x] `prefers-reduced-motion` disables packet/node motion
- [x] Sticky nav + skip link; no emoji icons
- [x] Interception demo: 4 scenarios + try-it box restyled to system
- [x] Responsive stacking at ≤900 / ≤640 / ≤560
