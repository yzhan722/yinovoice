import type { CallAnalysis, ClientProfile, QualityAnalysis } from "../domain/types.js";
import { renderCustomerReportSubject, renderQualityReportSubject } from "./html.js";

export type OutboundMailPlan = {
  dispatch: "disabled";
  customer: {
    subject: string;
    recipientRoles: string[];
    htmlFile: "customer-report.html";
  };
  quality: {
    subject: string;
    recipientRoles: string[];
    htmlFile: "quality-report.html";
  };
};

export function composeOutboundMailPlan(input: {
  profile: ClientProfile;
  analysis: CallAnalysis;
  quality: QualityAnalysis;
}): OutboundMailPlan {
  return {
    dispatch: "disabled",
    customer: {
      subject: renderCustomerReportSubject(input.analysis),
      recipientRoles: [...input.profile.legacyCustomerReportRecipients],
      htmlFile: "customer-report.html",
    },
    quality: {
      subject: renderQualityReportSubject(input.profile, input.analysis, input.quality),
      recipientRoles: [...input.profile.legacyQualityReportRecipients],
      htmlFile: "quality-report.html",
    },
  };
}
