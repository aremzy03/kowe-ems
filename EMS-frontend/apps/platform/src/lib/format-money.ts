/** Format kobo/naira amounts for Paper Brutalism money surfaces (JetBrains Mono). */
export function formatNaira(amount: number): string {
  const formatted = new Intl.NumberFormat("en-NG", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
  return `₦${formatted}`;
}
