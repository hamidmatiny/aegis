import { useEffect } from "react";

export type PageMetaProps = {
  title: string;
  description: string;
  canonicalPath: string; // e.g. "/" or "/guides/smb-cve-exposure-checklist"
};

const ORIGIN = "https://defenseaegis.org";

function upsertMeta(attr: "name" | "property", key: string, content: string) {
  let el = document.head.querySelector<HTMLMetaElement>(
    `meta[${attr}="${key}"]`,
  );
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  el.setAttribute("content", content);
}

function upsertCanonical(href: string) {
  let el = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (!el) {
    el = document.createElement("link");
    el.setAttribute("rel", "canonical");
    document.head.appendChild(el);
  }
  el.setAttribute("href", href);
}

/** Client-side head tags for SPA routes (complements build-time route shells). */
export function PageMeta({ title, description, canonicalPath }: PageMetaProps) {
  useEffect(() => {
    const canonical = `${ORIGIN}${canonicalPath === "/" ? "/" : canonicalPath}`;
    document.title = title;
    upsertMeta("name", "description", description);
    upsertCanonical(canonical);
    upsertMeta("property", "og:url", canonical);
    upsertMeta("property", "og:title", title);
    upsertMeta("property", "og:description", description);
    upsertMeta("name", "twitter:title", title);
    upsertMeta("name", "twitter:description", description);
  }, [title, description, canonicalPath]);

  return null;
}
