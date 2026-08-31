const BLOCKED_CUSTOMER_RECIPIENT =
  /@(?:lucaplus\.com|inpgroup\.com\.au)$/i;

export type MailDispatchErrorCode =
  | "mail_dispatch_disabled"
  | "customer_recipient_blocked";

export class MailDispatchError extends Error {
  constructor(readonly code: MailDispatchErrorCode) {
    super(code);
    this.name = "MailDispatchError";
  }
}

export function dispatchOutboundMail(env: NodeJS.ProcessEnv): never {
  for (const value of [env.MAIL_TO, env.MAIL_CC, env.MAIL_BCC]) {
    if (typeof value !== "string") {
      continue;
    }
    for (const part of value.split(/[,;]/)) {
      if (BLOCKED_CUSTOMER_RECIPIENT.test(part.trim())) {
        throw new MailDispatchError("customer_recipient_blocked");
      }
    }
  }
  throw new MailDispatchError("mail_dispatch_disabled");
}
