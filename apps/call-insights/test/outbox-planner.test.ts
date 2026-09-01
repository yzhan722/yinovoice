import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  OutboxPlanner,
  type CompletedReportInput,
} from "../src/outbound/outbox-planner.js";
import { SqliteStore } from "../src/storage/sqlite-store.js";
import {
  lucaplusProfile,
  makeAnalysis,
  makeCall,
  makeQuality,
  tempDatabase,
} from "./fixtures.js";

describe("OutboxPlanner", () => {
  it("keeps off mode empty and shadow mode permanently suppressed", () => {
    const database = tempDatabase();
    const store = new SqliteStore(database.path);
    try {
      new OutboxPlanner(store, { mode: "off", cutoverNotBefore: null })
        .plan(makeCompletedReportInput());
      expect(store.countMail()).toBe(0);

      const shadow = new OutboxPlanner(store, {
        mode: "shadow",
        cutoverNotBefore: null,
      });
      shadow.plan(makeCompletedReportInput());
      shadow.plan(makeCompletedReportInput());

      expect(store.listMail("lucaplus", "call_demo_001")).toMatchObject([
        {
          kind: "customer",
          status: "suppressed",
          recipientRoles: lucaplusProfile.legacyCustomerReportRecipients,
          messageId: expect.stringMatching(
            /^<[a-f0-9]{64}@calls\.yino\.au>$/,
          ),
        },
        {
          kind: "quality",
          status: "suppressed",
          recipientRoles: lucaplusProfile.legacyQualityReportRecipients,
          messageId: expect.stringMatching(
            /^<[a-f0-9]{64}@calls\.yino\.au>$/,
          ),
        },
      ]);
    } finally {
      store.close();
      database.close();
    }
  });

  it("queues only live calls completed at or after the cutover timestamp", () => {
    const database = tempDatabase();
    const store = new SqliteStore(database.path);
    try {
      const planner = new OutboxPlanner(store, {
        mode: "live",
        cutoverNotBefore: "2026-08-13T02:00:00.000Z",
      });
      planner.plan(makeCompletedReportInput({
        callId: "call_before_cutover",
        endedAt: "2026-08-13T01:59:59.999Z",
        receivedAt: "2026-08-13T03:00:00.000Z",
      }));
      planner.plan(makeCompletedReportInput({
        callId: "call_at_cutover",
        endedAt: "2026-08-13T02:00:00.000Z",
        receivedAt: "2026-08-13T03:00:00.000Z",
      }));

      expect(
        store.listMail("lucaplus", "call_before_cutover"),
      ).toMatchObject([
        { kind: "customer", status: "suppressed" },
        { kind: "quality", status: "suppressed" },
      ]);
      expect(
        store.listMail("lucaplus", "call_at_cutover"),
      ).toMatchObject([
        { kind: "customer", status: "pending" },
        { kind: "quality", status: "pending" },
      ]);
    } finally {
      store.close();
      database.close();
    }
  });

  it("requires an exact UTC cutover timestamp in live mode", () => {
    const database = tempDatabase();
    const store = new SqliteStore(database.path);
    try {
      expect(() => new OutboxPlanner(store, {
        mode: "live",
        cutoverNotBefore: null,
      })).toThrow(/cutover/i);
      expect(() => new OutboxPlanner(store, {
        mode: "live",
        cutoverNotBefore: "not-a-date",
      })).toThrow(/cutover/i);
      expect(() => new OutboxPlanner(store, {
        mode: "live",
        cutoverNotBefore: "2026-02-30T00:00:00.000Z",
      })).toThrow(/cutover/i);
      new OutboxPlanner(store, {
        mode: "live",
        cutoverNotBefore: "2026-08-17T00:00:00.000Z",
      });
      expect(() => new OutboxPlanner(store, {
        mode: "live",
        cutoverNotBefore: "2026-08-18T00:00:00.000Z",
      })).toThrow(/cutover/i);
    } finally {
      store.close();
      database.close();
    }
  });

  it("does not enqueue mail for yino channel unless mailEnabled is true", () => {
    const database = tempDatabase();
    const store = new SqliteStore(database.path);
    try {
      const planner = new OutboxPlanner(store, {
        mode: "shadow",
        cutoverNotBefore: null,
      });
      planner.plan(makeCompletedReportInput({
        channel: "yino",
        callId: "yino_call_1",
      }));
      expect(store.listMail("lucaplus", "yino_call_1")).toEqual([]);

      planner.plan(
        makeCompletedReportInput(
          { channel: "yino", callId: "yino_call_2" },
          { ...lucaplusProfile, mailEnabled: true },
        ),
      );
      expect(store.listMail("lucaplus", "yino_call_2")).toHaveLength(2);
    } finally {
      store.close();
      database.close();
    }
  });
});

function makeCompletedReportInput(
  callOverrides: Parameters<typeof makeCall>[0] = {},
  profile = lucaplusProfile,
): CompletedReportInput {
  const call = makeCall(callOverrides);
  return {
    profile,
    call,
    analysis: makeAnalysis(),
    quality: makeQuality(),
    artifacts: {
      directory: join("artifacts", call.profile, call.callId),
      files: [
        "call.json",
        "customer-report.html",
        "quality-report.html",
        "manifest.json",
      ],
    },
  };
}
