import { describe, expect, it } from "vitest";
import { composeOutboundMailPlan } from "../src/reports/outbound.js";
import { lucaplusProfile, makeAnalysis, makeQuality } from "./fixtures.js";

describe("composeOutboundMailPlan", () => {
  it("records n8n subjects and role labels with dispatch disabled", () => {
    const plan = composeOutboundMailPlan({
      profile: lucaplusProfile,
      analysis: makeAnalysis(),
      quality: makeQuality(),
    });
    expect(plan).toEqual({
      dispatch: "disabled",
      customer: {
        subject: "Call Report for Demo Customer 2026-08-13 11:00 AEST",
        recipientRoles: lucaplusProfile.legacyCustomerReportRecipients,
        htmlFile: "customer-report.html",
      },
      quality: {
        subject: "[质量分析] Luca AI 评分: 8/10 - Demo Customer",
        recipientRoles: lucaplusProfile.legacyQualityReportRecipients,
        htmlFile: "quality-report.html",
      },
    });
    expect(JSON.stringify(plan)).not.toContain("@");
    expect(JSON.stringify(plan)).not.toMatch(/lucaplus\.com|inpgroup\.com\.au/i);
  });
});
