/** Notes date stamp: "m/d - " with no leading zeros. */
export function formatNoteDateStamp(d: Date = new Date()): string {
  return `${d.getMonth() + 1}/${d.getDate()} - `;
}
