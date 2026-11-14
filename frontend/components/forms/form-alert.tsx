import { AlertCircle, CheckCircle2 } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";

export function FormAlert({ message, tone = "error" }: { message: string | null; tone?: "error" | "success" }) {
  if (!message) return null;
  const Icon = tone === "error" ? AlertCircle : CheckCircle2;
  return (
    <Alert
      variant={tone === "error" ? "destructive" : "default"}
      className={tone === "success" ? "border-teal-100 bg-teal-50 text-navy-900" : undefined}
      role={tone === "error" ? "alert" : "status"}
    >
      <Icon aria-hidden />
      <AlertDescription className={tone === "success" ? "text-navy-900" : undefined}>{message}</AlertDescription>
    </Alert>
  );
}
