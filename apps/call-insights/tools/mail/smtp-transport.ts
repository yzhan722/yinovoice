import nodemailer from "nodemailer";
import { MAIL_SENDER } from "./recipient-config.js";

export interface MailInlinePngAttachment {
  filename: "yino-logo.png";
  content: Buffer;
  cid: string;
  contentType: "image/png";
  contentDisposition: "inline";
}

export interface MailMessage {
  from: typeof MAIL_SENDER;
  to: string[];
  cc?: string[];
  subject: string;
  html: string;
  messageId: string;
  attachments?: MailInlinePngAttachment[];
}

export interface MailTransport {
  verify(): Promise<unknown>;
  sendMail(message: MailMessage): Promise<{ messageId?: string }>;
  close(): void;
}

export type GmailTransportFactory = (
  options: {
    host: "smtp.gmail.com";
    port: 465;
    secure: true;
    auth: {
      user: typeof MAIL_SENDER;
      pass: string;
    };
  },
) => MailTransport;

const DEFAULT_TRANSPORT_FACTORY: GmailTransportFactory = (options) =>
  nodemailer.createTransport(options);

export function createGmailTransport(
  password: string,
  createTransport: GmailTransportFactory = DEFAULT_TRANSPORT_FACTORY,
): MailTransport {
  const normalizedPassword = password.replace(/\s/g, "");
  if (!normalizedPassword) {
    throw new Error("smtp_credentials_missing");
  }
  return createTransport({
    host: "smtp.gmail.com",
    port: 465,
    secure: true,
    auth: {
      user: MAIL_SENDER,
      pass: normalizedPassword,
    },
  });
}

export async function verifyGmailSmtp(
  password: string,
  createTransport: GmailTransportFactory = DEFAULT_TRANSPORT_FACTORY,
): Promise<void> {
  const transport = createGmailTransport(password, createTransport);
  try {
    await transport.verify();
  } finally {
    transport.close();
  }
}
