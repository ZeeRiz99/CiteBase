import { ImageResponse } from "next/og";

import { MARK_DATA_URI } from "@/components/brand/mark-svg";
import { branding } from "@/lib/branding";

// Generated at build time from the deployment's branding (product name and tagline).
export const alt = `${branding.productName}: ${branding.tagline}`;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: 72,
          background: "linear-gradient(135deg, #061128 0%, #0b1b33 55%, #12284a 100%)",
          color: "white",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
          <img src={MARK_DATA_URI} width={88} height={88} alt="" />
          <span style={{ fontSize: 48, fontWeight: 700 }}>{branding.productName}</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
          <span style={{ fontSize: 68, fontWeight: 700, lineHeight: 1.1, maxWidth: 1000 }}>{branding.tagline}</span>
          <div style={{ display: "flex", gap: 16, fontSize: 28, color: "#c9d4e5" }}>
            <span style={{ display: "flex", padding: "8px 18px", borderRadius: 999, background: "rgba(20,184,166,0.18)", color: "#ccfbf1" }}>
              Answers with citations
            </span>
            <span style={{ display: "flex", padding: "8px 18px", borderRadius: 999, background: "rgba(255,255,255,0.08)" }}>
              Honest when it does not know
            </span>
          </div>
        </div>
      </div>
    ),
    size,
  );
}
