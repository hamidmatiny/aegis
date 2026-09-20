# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** AEGIS  
**Generated:** 2026-09-20 (ui-ux-pro-max `--design-system`)  
**Category:** B2B security / infrastructure (LLM enforcer-gateway)  
**Audience:** Technical buyers — platform, security, and AI-infra engineers

---

## Craft decisions (locked)

| Decision | Choice | Why |
|----------|--------|-----|
| Style | Trust & Authority + high-craft precision | Security product; no playful SaaS kitsch |
| Palette | Navy primary `#0F172A` + blue CTA `#0369A1` + light canvas `#F8FAFC` | First generator hit for B2B trust; stronger than soft “accessible blue/green” variant |
| Type | **IBM Plex Sans** (override from Roboto) | Financial/infra seriousness; Roboto reads consumer-MD3 |
| Mode | Light marketing surfaces; dark reserved for in-product Q&A chrome | Landing must catch the eye; product UI stays focused |
| Motion | CSS transform/opacity only; 1–2 elements per view; respect `prefers-reduced-motion` | No GSAP dependency yet; same rules as prototype |

---

## Global Rules

### Color Palette

| Role | Hex | CSS Variable |
|------|-----|--------------|
| Primary | `#0F172A` | `--color-primary` |
| On Primary | `#FFFFFF` | `--color-on-primary` |
| Secondary | `#334155` | `--color-secondary` |
| On Secondary | `#FFFFFF` | `--color-on-secondary` |
| Accent/CTA | `#0369A1` | `--color-accent` |
| On Accent/CTA | `#FFFFFF` | `--color-on-accent` |
| Background | `#F8FAFC` | `--color-background` |
| Foreground | `#020617` | `--color-foreground` |
| Card | `#FFFFFF` | `--color-card` |
| Card Foreground | `#020617` | `--color-card-foreground` |
| Muted | `#E8ECF1` | `--color-muted` |
| Muted Foreground | `#475569` | `--color-muted-foreground` |
| Border | `#E2E8F0` | `--color-border` |
| Destructive | `#DC2626` | `--color-destructive` |
| On Destructive | `#FFFFFF` | `--color-on-destructive` |
| Success | `#15803D` | `--color-success` |
| Hold/Warn | `#B45309` | `--color-hold` |
| Ring | `#0F172A` | `--color-ring` |

**Color Notes:** Professional navy + blue CTA. No purple/pink AI gradients.

### Typography

- **Heading Font:** IBM Plex Sans (600/700)
- **Body Font:** IBM Plex Sans (400/500)
- **Mono:** ui-monospace / SF Mono / Menlo
- **Mood:** trustworthy, precise, corporate-infra — not playful
- **Google Fonts:** [IBM Plex Sans](https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap)

**CSS Import:**
```css
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
```

### Spacing Variables

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `4px` | Tight gaps |
| `--space-sm` | `8px` | Icon gaps |
| `--space-md` | `16px` | Standard padding |
| `--space-lg` | `24px` | Section padding |
| `--space-xl` | `32px` | Large gaps |
| `--space-2xl` | `48px` | Section margins |
| `--space-3xl` | `64px` | Hero padding |

### Shadow Depths

| Level | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(15,23,42,0.06)` | Subtle lift |
| `--shadow-md` | `0 4px 12px rgba(15,23,42,0.08)` | Cards |
| `--shadow-lg` | `0 12px 28px rgba(15,23,42,0.12)` | Featured panels |
| `--shadow-xl` | `0 24px 48px rgba(15,23,42,0.16)` | Hero visual |

---

## Component Specs

### Buttons

```css
.btn-primary {
  background: #0369A1;
  color: #FFFFFF;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: background 200ms ease, transform 200ms ease;
  cursor: pointer;
}
.btn-primary:hover { background: #075985; }
.btn-primary:focus-visible {
  outline: 3px solid #0F172A;
  outline-offset: 2px;
}

.btn-secondary {
  background: transparent;
  color: #0F172A;
  border: 2px solid #0F172A;
  padding: 10px 22px;
  border-radius: 8px;
  font-weight: 600;
  transition: background 200ms ease, color 200ms ease;
  cursor: pointer;
}
.btn-secondary:hover { background: #0F172A; color: #FFFFFF; }
```

### Cards

```css
.card {
  background: #FFFFFF;
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  padding: 24px;
  box-shadow: var(--shadow-sm);
  transition: box-shadow 200ms ease, border-color 200ms ease;
}
.card:hover {
  box-shadow: var(--shadow-md);
  border-color: #CBD5E1;
}
```

---

## Style Guidelines

**Style:** Trust & Authority + Conversion (security/infra)

**Keywords:** Precise, high contrast, evidence-first, keyboard-friendly, reduced-motion aware

**Key Effects:** Visible focus rings (3px), skip link, 44×44 touch targets, meaningful motion only

### Page Pattern (landing)

From `--domain landing` → **Hero + Features + CTA** (closest DB match; no dedicated “security infra” row):

1. Hero — mission + primary CTA (GitHub)
2. Proof — real evidence (repo, awesome-list, external issue)
3. Solution / how-it-works — interception demo (App → AEGIS → Provider)
4. Features → optional applied example / pricing (unchanged substance)
5. Footer CTA

---

## Motion (interception / GSAP guidance applied in CSS)

- Animate **transform + opacity only**
- **1–2** focal motions at a time (packet + active node)
- Pause when offscreen / `prefers-reduced-motion: reduce`
- No decorative parallax; hero stays static under reduced motion

---

## Anti-Patterns (Do NOT Use)

- ❌ Playful / consumer kitsch
- ❌ AI purple/pink gradients
- ❌ Empty “trusted by” logo walls
- ❌ Emojis as icons
- ❌ Layout-shifting hover scales
- ❌ Invisible focus states

---

## Pre-Delivery Checklist

- [ ] No emoji icons
- [ ] `cursor: pointer` on clickables
- [ ] Hover 150–300ms
- [ ] Contrast ≥ 4.5:1
- [ ] Visible focus
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive 375 / 768 / 1024 / 1440 — no horizontal scroll
- [ ] Content not hidden under sticky nav
