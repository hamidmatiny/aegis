#!/usr/bin/env node
/**
 * After Vite build, emit per-route HTML shells so curl/view-source and non-JS
 * crawlers see the correct <title> and canonical — not only the homepage defaults.
 */
import { mkdirSync, readFileSync, writeFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const dist = join(__dirname, "..", "dist");
const indexPath = join(dist, "index.html");

const ROUTES = [
  {
    path: "guides/smb-cve-exposure-checklist",
    title: "How to check SMB CVE exposure — AEGIS checklist",
    description:
      "A plain-language checklist for small businesses: inventory what you run, match a CVE to your versions, and decide patch vs mitigate in 24–72 hours.",
    canonical: "https://defenseaegis.org/guides/smb-cve-exposure-checklist",
  },
];

function applyMeta(html, { title, description, canonical }) {
  let out = html;
  out = out.replace(/<title>[^<]*<\/title>/, `<title>${title}</title>`);
  out = out.replace(
    /<meta\s+name="description"\s+content="[^"]*"\s*\/>/,
    `<meta name="description" content="${description.replace(/"/g, "&quot;")}" />`,
  );
  out = out.replace(
    /<link\s+rel="canonical"\s+href="[^"]*"\s*\/>/,
    `<link rel="canonical" href="${canonical}" />`,
  );
  out = out.replace(
    /<meta\s+property="og:url"\s+content="[^"]*"\s*\/>/,
    `<meta property="og:url" content="${canonical}" />`,
  );
  out = out.replace(
    /<meta\s+property="og:title"\s+content="[^"]*"\s*\/>/,
    `<meta property="og:title" content="${title.replace(/"/g, "&quot;")}" />`,
  );
  out = out.replace(
    /<meta\s+property="og:description"\s+content="[^"]*"\s*\/>/,
    `<meta property="og:description" content="${description.replace(/"/g, "&quot;")}" />`,
  );
  out = out.replace(
    /<meta\s+name="twitter:title"\s+content="[^"]*"\s*\/>/,
    `<meta name="twitter:title" content="${title.replace(/"/g, "&quot;")}" />`,
  );
  out = out.replace(
    /<meta\s+name="twitter:description"\s+content="[^"]*"\s*\/>/,
    `<meta name="twitter:description" content="${description.replace(/"/g, "&quot;")}" />`,
  );
  return out;
}

const base = readFileSync(indexPath, "utf8");
for (const route of ROUTES) {
  const outDir = join(dist, route.path);
  mkdirSync(outDir, { recursive: true });
  const html = applyMeta(base, route);
  writeFileSync(join(outDir, "index.html"), html);
  console.log(`emitted ${route.path}/index.html`);
}

// Sanity: ensure homepage still has homepage canonical
if (!base.includes('href="https://defenseaegis.org/"')) {
  console.warn("warning: homepage canonical may have changed unexpectedly");
}
console.log("route shells:", readdirSync(join(dist, "guides")));
