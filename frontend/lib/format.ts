export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value < 10 ? value.toFixed(1) : Math.round(value)} ${units[unit]}`;
}

const dateFormatter = new Intl.DateTimeFormat("en", { dateStyle: "medium" });
const dateTimeFormatter = new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" });

export function formatDate(iso: string): string {
  return dateFormatter.format(new Date(iso));
}

export function formatDateTime(iso: string): string {
  return dateTimeFormatter.format(new Date(iso));
}

export function fileTypeLabel(ext: string): string {
  return { ".pdf": "PDF", ".docx": "Word", ".md": "Markdown", ".txt": "Text" }[ext] ?? ext.replace(".", "").toUpperCase();
}
