import type { Metadata } from "next";
import { Suspense } from "react";

import { ConfirmEmailChange } from "@/components/auth/confirm-email-change";

export const metadata: Metadata = { title: "Confirm your new email" };

export default function ConfirmEmailChangePage() {
  return (
    <Suspense>
      <ConfirmEmailChange />
    </Suspense>
  );
}
