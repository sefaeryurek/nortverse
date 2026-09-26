import type { MetadataRoute } from "next";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: "/bulten", changeFrequency: "daily", priority: 1.0 },
    { url: "/sonuclar", changeFrequency: "daily", priority: 0.8 },
  ];
}
