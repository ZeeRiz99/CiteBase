import type { FieldValues, Path, UseFormSetError } from "react-hook-form";

import { errorMessage, isApiError } from "@/lib/api";

/**
 * Map backend field errors onto form fields. Returns a form-level message for anything that
 * is not tied to a known field (or null when every error was placed on a field).
 */
export function applyServerErrors<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  knownFields: readonly Path<T>[],
): string | null {
  if (!isApiError(error)) return errorMessage(error);
  const unplaced = error.fields.filter((f) => !knownFields.includes(f.field as Path<T>));
  for (const field of error.fields) {
    if (knownFields.includes(field.field as Path<T>)) {
      setError(field.field as Path<T>, { type: "server", message: field.message });
    }
  }
  if (error.fields.length > 0 && unplaced.length === 0) return null;
  return error.message;
}
