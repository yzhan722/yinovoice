export type MailKind = "customer" | "quality";

export type MailStatus =
  | "suppressed"
  | "pending"
  | "sending"
  | "sent"
  | "failed"
  | "uncertain";

export interface MailOutboxInput {
  profile: string;
  callId: string;
  kind: MailKind;
  subject: string;
  htmlPath: string;
  recipientRoles: string[];
  messageId: string;
  status: "suppressed" | "pending";
  nextAttemptAt: string | null;
}

export interface MailOutboxRecord {
  outboxId: number;
  profile: string;
  callId: string;
  kind: MailKind;
  subject: string;
  htmlPath: string;
  recipientRoles: string[];
  messageId: string;
  status: MailStatus;
  attempts: number;
  nextAttemptAt: string | null;
  lastError: string | null;
  providerMessageId: string | null;
  createdAt: string;
  updatedAt: string;
  sentAt: string | null;
}
