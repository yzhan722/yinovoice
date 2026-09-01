import { YINO_LOGO_DATA_URI } from "./yino-logo.js";

export const YINO_LOGO_CONTENT_ID = "yino-logo@calls.yino.au";
const PNG_SIGNATURE = Buffer.from([
  0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,
]);
const DATA_URI_PREFIX = "data:image/png;base64,";

export interface InlineYinoLogoAttachment {
  filename: "yino-logo.png";
  content: Buffer;
  cid: typeof YINO_LOGO_CONTENT_ID;
  contentType: "image/png";
  contentDisposition: "inline";
}

export function inlineYinoLogoForSmtp(html: string): {
  html: string;
  attachments: InlineYinoLogoAttachment[];
} {
  if (!html.includes(YINO_LOGO_DATA_URI)) {
    return { html, attachments: [] };
  }
  if (!YINO_LOGO_DATA_URI.startsWith(DATA_URI_PREFIX)) {
    throw new Error("invalid yino logo data uri");
  }
  const content = Buffer.from(
    YINO_LOGO_DATA_URI.slice(DATA_URI_PREFIX.length),
    "base64",
  );
  if (
    content.length < PNG_SIGNATURE.length ||
    !content.subarray(0, PNG_SIGNATURE.length).equals(PNG_SIGNATURE)
  ) {
    throw new Error("invalid yino logo png");
  }
  return {
    html: html.replaceAll(YINO_LOGO_DATA_URI, `cid:${YINO_LOGO_CONTENT_ID}`),
    attachments: [
      {
        filename: "yino-logo.png",
        content,
        cid: YINO_LOGO_CONTENT_ID,
        contentType: "image/png",
        contentDisposition: "inline",
      },
    ],
  };
}
