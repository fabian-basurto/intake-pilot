/**
 * Offline check of the client-side compare logic with hand-built reviews.
 * Rules, drafts, and extraction live in the backend and are tested with pytest.
 * Run: npm test
 */
import { compareReviews } from "../src/lib/compare";
import type { ReviewResult, RuleResult, RuleStatus } from "../src/lib/types";

let failures = 0;
function expect(name: string, cond: boolean | undefined, extra?: unknown) {
  if (cond === true) console.log(`  ok   ${name}`);
  else {
    failures++;
    console.log(`  FAIL ${name}`, extra ?? "");
  }
}

function item(id: string, status: RuleStatus, value: string | null = null, page: number | null = null): RuleResult {
  return {
    id,
    label: id,
    group: "documents",
    level: status === "info" ? "info" : "required",
    status,
    detail: "",
    value,
    evidence: page === null ? null : { page, excerpt: null },
    source: [{ pdf: "B", page: 1, section: "test" }],
    request: id,
    override: null,
    fieldRecords: [],
    documentRecords: [],
  };
}

function review(items: RuleResult[]): ReviewResult {
  const counts: Record<RuleStatus, number> = { ok: 0, not_found: 0, needs_review: 0, info: 0 };
  for (const i of items) counts[i.status] += 1;
  const attention = counts.not_found + counts.needs_review;
  return { status: attention ? "attention" : "clear", headline: "", subline: "", attentionCount: attention, counts, items };
}

console.log("compare: incomplete -> complete");
{
  const before = review([item("labs", "not_found"), item("insurance", "not_found"), item("notes", "ok", "note", 5), item("email", "info")]);
  const after = review([item("labs", "ok", null, 4), item("insurance", "ok", "DemoCare", 3), item("notes", "ok", "note", 5), item("email", "info")]);
  const cmp = compareReviews(before, after);
  expect("one row per shared rule", cmp.items.length === 4, cmp.items.length);
  expect("two resolved", cmp.resolved === 2, cmp.resolved);
  expect("no new gaps", cmp.newGaps === 0);
  expect("two unchanged", cmp.same === 2, cmp.same);
  expect("attention counts carried", cmp.attentionBefore === 2 && cmp.attentionAfter === 0);
  expect("resolved row has current page", cmp.items.find((i) => i.id === "labs")?.afterPage === 4);

  const reverse = compareReviews(after, before);
  expect("reverse shows two new gaps", reverse.newGaps === 2 && reverse.resolved === 0);

  const same = compareReviews(after, after);
  expect("identical -> all unchanged", same.same === 4 && same.changed === 0);
}

console.log("compare: value change without status change");
{
  const before = review([item("phone", "ok", "(555) 010-2231", 1)]);
  const after = review([item("phone", "ok", "555-010-2231", 1)]);
  const cmp = compareReviews(before, after);
  expect("reported as changed", cmp.changed === 1 && cmp.items[0].change === "changed");
}

console.log("compare: rule missing on one side is skipped");
{
  const before = review([item("a", "ok"), item("b", "ok")]);
  const after = review([item("a", "ok")]);
  expect("only shared rules compared", compareReviews(before, after).items.length === 1);
}

console.log(failures ? `\n${failures} failure(s)` : "\nall compare checks passed");
process.exit(failures ? 1 : 0);
