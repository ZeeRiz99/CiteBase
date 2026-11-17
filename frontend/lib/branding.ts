/**
 * White-label branding. Values come from PRODUCT_NAME / PRODUCT_TAGLINE in the root .env,
 * passed to the web build as NEXT_PUBLIC_* (see compose.yaml). Never hardcode the name elsewhere.
 */
export const branding = {
  productName: process.env.NEXT_PUBLIC_PRODUCT_NAME || "CiteBase",
  tagline: process.env.NEXT_PUBLIC_PRODUCT_TAGLINE || "Ask your documents. Get answers you can verify.",
  // Public address of this deployment (APP_BASE_URL); makes share-preview image URLs absolute.
  siteUrl: process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:8080",
} as const;
