import type { ReviewResult, RuleGroup, RuleStatus } from "./types";

/**
 * Compares two reviews rule by rule so a presenter can show that findings
 * change when a different packet is analyzed. Pure function, no AI.
 */

export type ChangeKind = "resolved" | "new_gap" | "changed" | "same";

export interface ComparedItem {
  id: string;
  label: string;
  group: RuleGroup;
  before: RuleStatus;
  after: RuleStatus;
  beforeValue: string | null;
  afterValue: string | null;
  beforePage: number | null;
  afterPage: number | null;
  change: ChangeKind;
}

export interface Comparison {
  items: ComparedItem[];
  resolved: number;
  newGaps: number;
  changed: number;
  same: number;
  attentionBefore: number;
  attentionAfter: number;
}

export function isFlagged(status: RuleStatus): boolean {
  return status === "not_found" || status === "needs_review";
}

export function compareReviews(before: ReviewResult, after: ReviewResult): Comparison {
  const prev = new Map(before.items.map((i) => [i.id, i]));
  const items: ComparedItem[] = [];

  for (const cur of after.items) {
    const old = prev.get(cur.id);
    if (!old) continue;
    const wasFlagged = isFlagged(old.status);
    const nowFlagged = isFlagged(cur.status);
    let change: ChangeKind = "same";
    if (wasFlagged && !nowFlagged) change = "resolved";
    else if (!wasFlagged && nowFlagged) change = "new_gap";
    else if (old.status !== cur.status || (old.value ?? null) !== (cur.value ?? null)) change = "changed";

    items.push({
      id: cur.id,
      label: cur.label,
      group: cur.group,
      before: old.status,
      after: cur.status,
      beforeValue: old.value,
      afterValue: cur.value,
      beforePage: old.evidence?.page ?? null,
      afterPage: cur.evidence?.page ?? null,
      change,
    });
  }

  const count = (k: ChangeKind) => items.filter((i) => i.change === k).length;
  return {
    items,
    resolved: count("resolved"),
    newGaps: count("new_gap"),
    changed: count("changed"),
    same: count("same"),
    attentionBefore: before.attentionCount,
    attentionAfter: after.attentionCount,
  };
}
