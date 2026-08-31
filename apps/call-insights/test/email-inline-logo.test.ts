import { describe, expect, it } from "vitest";
import {
  YINO_LOGO_CONTENT_ID,
  inlineYinoLogoForSmtp,
} from "../src/reports/email-inline-logo.js";
import { YINO_LOGO_DATA_URI } from "../src/reports/yino-logo.js";
import { renderCustomerReport, renderQualityReport } from "../src/reports/html.js";
import {
  lucaplusProfile,
  makeAnalysis,
  makeCall,
  makeQuality,
} from "./fixtures.js";

describe("inlineYinoLogoForSmtp", () => {
  it("replaces the customer-report data-uri logo with one inline CID PNG", () => {
    const html = renderCustomerReport({
      profile: lucaplusProfile,
      call: makeCall(),
      analysis: makeAnalysis(),
      ratingBaseUrl: "http://127.0.0.1:3210",
    });
    expect(html).toContain(YINO_LOGO_DATA_URI);

    const prepared = inlineYinoLogoForSmtp(html);

    expect(prepared.html.match(/<img\b[^>]*\bsrc="cid:yino-logo@calls\.yino\.au"/g)).toHaveLength(
      1,
    );
    expect(prepared.html).not.toContain("data:image/png;base64,");
    expect(prepared.html).toContain(`cid:${YINO_LOGO_CONTENT_ID}`);
    expect(prepared.attachments).toHaveLength(1);
    const [logo] = prepared.attachments;
    expect(logo).toMatchObject({
      filename: "yino-logo.png",
      cid: YINO_LOGO_CONTENT_ID,
      contentType: "image/png",
      contentDisposition: "inline",
    });
    expect(Buffer.isBuffer(logo?.content)).toBe(true);
    expect(logo?.content.subarray(0, 8).equals(Buffer.from([
      0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
    ]))).toBe(true);
  });

  it("leaves quality reports without attachments", () => {
    const html = renderQualityReport({
      profile: lucaplusProfile,
      call: makeCall(),
      analysis: makeAnalysis(),
      quality: makeQuality(),
    });
    expect(inlineYinoLogoForSmtp(html)).toEqual({
      html,
      attachments: [],
    });
  });
});
