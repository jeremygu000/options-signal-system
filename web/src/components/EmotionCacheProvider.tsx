"use client";

import { useState } from "react";
import createCache from "@emotion/cache";
import { useServerInsertedHTML } from "next/navigation";
import { CacheProvider } from "@emotion/react";

export default function EmotionCacheProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [cache] = useState(() => {
    const c = createCache({ key: "mui" });
    c.compat = true;
    return c;
  });

  useServerInsertedHTML(() => {
    const entries = (cache as Record<string, unknown>).inserted as
      | Record<string, string | boolean>
      | undefined;
    if (!entries) return null;

    const names: string[] = [];
    const styles: string[] = [];

    for (const [name, value] of Object.entries(entries)) {
      if (typeof value === "string") {
        names.push(name);
        styles.push(value);
      }
    }

    if (styles.length === 0) return null;

    return (
      <style
        key={cache.key}
        data-emotion={`${cache.key} ${names.join(" ")}`}
        dangerouslySetInnerHTML={{ __html: styles.join("") }}
      />
    );
  });

  return <CacheProvider value={cache}>{children}</CacheProvider>;
}
