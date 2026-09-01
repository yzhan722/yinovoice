import { describe, expect, it } from "vitest";
import {
  MailDispatchError,
  dispatchOutboundMail,
} from "../tools/dispatch-outbound.js";

describe("dispatchOutboundMail", () => {
  it("stays disabled even when MAIL_DISPATCH=on", () => {
    expect(() =>
      dispatchOutboundMail({
        MAIL_DISPATCH: "on",
        MAIL_TO: "867542127@qq.com",
      }),
    ).toThrow(MailDispatchError);
    try {
      dispatchOutboundMail({ MAIL_DISPATCH: "on" });
      expect.unreachable();
    } catch (error) {
      expect(error).toMatchObject({ code: "mail_dispatch_disabled" });
    }
  });

  it("blocks lucaplus and inpgroup recipient addresses before any send", () => {
    try {
      dispatchOutboundMail({
        MAIL_DISPATCH: "on",
        MAIL_TO: "ops@lucaplus.com",
      });
      expect.unreachable();
    } catch (error) {
      expect(error).toMatchObject({ code: "customer_recipient_blocked" });
    }

    try {
      dispatchOutboundMail({
        MAIL_DISPATCH: "on",
        MAIL_CC: "team@inpgroup.com.au",
      });
      expect.unreachable();
    } catch (error) {
      expect(error).toMatchObject({ code: "customer_recipient_blocked" });
    }
  });
});
