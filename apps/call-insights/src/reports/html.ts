import type { Call, CallAnalysis, ClientProfile, QualityAnalysis } from "../domain/types.js";
import { assertPublicOrigin } from "../domain/public-origin.js";
import { YINO_LOGO_DATA_URI } from "./yino-logo.js";

const YINO_LOGO_DATA_URI_PATTERN = /^data:image\/png;base64,[A-Za-z0-9+/]+=*$/;

const LEMON = "#e4e84d";
const INK = "#1c1917";
const MUTE = "#6f6a62";
const CARD = "#ffffff";
const GUEST_BUBBLE = "#f3f1ea";
const SANS =
  "'Avenir Next', 'Segoe UI', 'Helvetica Neue', Helvetica, Arial, 'PingFang SC', 'Microsoft YaHei', sans-serif";

function sectionLabel(): string {
  return `font-family: ${SANS}; font-size: 10px; font-weight: 600; letter-spacing: 0.22em; text-transform: uppercase; color: ${MUTE}`;
}

export function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function emailHeaderText(value: string): string {
  return value.replace(/[\r\n\u0000-\u001f\u007f]+/g, " ").replace(/\s+/g, " ").trim();
}

export function renderCustomerReportSubject(analysis: CallAnalysis): string {
  return `Call Report for ${emailHeaderText(analysis.customerName)} ${emailHeaderText(analysis.localCallTime)}`;
}

export function renderQualityReportSubject(
  profile: ClientProfile,
  analysis: CallAnalysis,
  quality: QualityAnalysis,
): string {
  return `[质量分析] ${emailHeaderText(profile.assistantName)} 评分: ${quality.score}/10 - ${emailHeaderText(analysis.customerName)}`;
}

function recordingPlaybackHref(origin: string, profile: string, callId: string): string {
  return `${origin}/recording?call_id=${encodeURIComponent(callId)}&profile=${encodeURIComponent(profile)}`;
}

function yinoLogoImg(width: number, style: string): string {
  if (!YINO_LOGO_DATA_URI_PATTERN.test(YINO_LOGO_DATA_URI)) {
    throw new Error("invalid yino logo data uri");
  }
  return `<img src="${YINO_LOGO_DATA_URI}" alt="YINO AI AUTOMATION" width="${String(width)}" style="${style}; width: ${String(width)}px; max-width: 100%; height: auto;">`;
}

function qualityScoreTheme(score: number): { background: string; color: string } {
  if (score >= 8) {
    return { background: "#d4edda", color: "#155724" };
  }
  if (score >= 6) {
    return { background: "#fff3cd", color: "#856404" };
  }
  return { background: "#f8d7da", color: "#721c24" };
}

function qualityList(items: string[]): string {
  return items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
}

function isPresent(value: string | null | undefined): boolean {
  if (value == null) {
    return false;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 && !/^not mentioned$/i.test(trimmed);
}

export function formatCallDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return "";
  }
  const whole = Math.floor(seconds);
  if (whole < 60) {
    return `${whole}s`;
  }
  const minutes = Math.floor(whole / 60);
  const remain = whole % 60;
  return remain === 0 ? `${minutes} min` : `${minutes} min ${remain}s`;
}

export interface TranscriptTurn {
  speaker: string;
  body: string;
}

export function parseTranscriptTurns(text: string): TranscriptTurn[] {
  const turns: TranscriptTurn[] = [];
  const header = /^([^:\n]{1,80}):\s*(.*)$/;
  for (const rawLine of text.replaceAll("\r\n", "\n").split("\n")) {
    const match = header.exec(rawLine);
    const speaker = match?.[1]?.trim() ?? "";
    if (
      match &&
      speaker &&
      !/^https?$/i.test(speaker) &&
      !speaker.includes("://") &&
      !/^\d{1,2}$/.test(speaker)
    ) {
      turns.push({ speaker, body: match[2] ?? "" });
      continue;
    }
    if (turns.length > 0) {
      const current = turns[turns.length - 1]!;
      current.body = current.body ? `${current.body}\n${rawLine}` : rawLine;
    } else if (rawLine.trim()) {
      turns.push({ speaker: "Transcript", body: rawLine });
    }
  }
  return turns.filter((turn) => turn.body.trim().length > 0);
}

function isAssistantSpeaker(speaker: string, assistantName: string): boolean {
  const normalized = speaker.trim().toLowerCase();
  return (
    normalized === "assistant" ||
    normalized === assistantName.trim().toLowerCase() ||
    normalized === "ai" ||
    normalized === "ai 客服"
  );
}

function ratingHref(
  baseUrl: string,
  profile: string,
  callId: string,
  score: number,
): string {
  return escapeHtml(
    `${baseUrl}/rating?score=${score}&call_id=${encodeURIComponent(callId)}&profile=${encodeURIComponent(profile)}`,
  );
}

function ratingScoreButtons(baseUrl: string, profile: string, callId: string): string {
  return [1, 2, 3, 4, 5]
    .map((score) => {
      const href = ratingHref(baseUrl, profile, callId, score);
      return `<a href="${href}" target="_blank" title="${score} / 5" style="display: inline-block; width: 44px; height: 44px; margin: 0 4px; background-color: ${LEMON}; color: ${INK}; font-family: ${SANS}; font-size: 18px; font-weight: 600; line-height: 44px; text-align: center; text-decoration: none; border-radius: 10px; touch-action: manipulation;">${score}</a>`;
    })
    .join("");
}

function topicChips(topics: string[]): string {
  const chips = topics
    .map((topic) => topic.trim())
    .filter((topic) => topic.length > 0)
    .map(
      (topic) =>
        `<span style="display: inline-block; margin: 0 8px 8px 0; padding: 6px 12px; background-color: ${LEMON}; color: ${INK}; font-family: ${SANS}; font-size: 13px; font-weight: 500; border-radius: 999px;">${escapeHtml(topic)}</span>`,
    );
  if (chips.length === 0) {
    return "";
  }
  return `<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" style="margin: 0 0 22px 0;">
              <tr>
                <td style="${sectionLabel()}; padding-bottom: 10px;">Topics</td>
              </tr>
              <tr>
                <td>${chips.join("")}</td>
              </tr>
            </table>`;
}

function metaRow(label: string, value: string): string {
  return `<tr>
                  <td valign="top" style="padding: 2px 14px 8px 0; ${sectionLabel()}; width: 76px;">${escapeHtml(label)}</td>
                  <td style="font-family: ${SANS}; font-size: 15px; font-weight: 400; line-height: 1.4; color: ${INK}; padding-bottom: 8px; overflow-wrap: break-word; word-break: normal;">${escapeHtml(value)}</td>
                </tr>`;
}

function playRecordingButton(href: string): string {
  return `<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" style="margin: 0 0 24px 0;">
              <tr>
                <td align="center" bgcolor="${INK}" style="background-color: ${INK}; border-radius: 12px;">
                  <a href="${href}" target="_blank" style="display: block; padding: 16px 20px; font-family: ${SANS}; font-size: 13px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: ${LEMON}; text-decoration: none; line-height: 1.2;">Play recording</a>
                </td>
              </tr>
            </table>`;
}

function displaySpeaker(
  speaker: string,
  assistantName: string,
  customerName: string,
): string {
  if (isAssistantSpeaker(speaker, assistantName)) {
    return assistantName.trim() || "Assistant";
  }
  const normalized = speaker.trim().toLowerCase();
  if (
    normalized === "user" ||
    normalized === "customer" ||
    normalized === "guest" ||
    normalized === "caller" ||
    normalized === "human"
  ) {
    return customerName.trim() || "Customer";
  }
  return speaker.trim();
}

function transcriptBubbles(
  turns: TranscriptTurn[],
  assistantName: string,
  customerName: string,
): string {
  if (turns.length === 0) {
    return "";
  }
  const rows = turns.map((turn) => {
    const assistant = isAssistantSpeaker(turn.speaker, assistantName);
    const name = displaySpeaker(turn.speaker, assistantName, customerName);
    const background = assistant ? INK : GUEST_BUBBLE;
    const color = assistant ? "#fffdf2" : INK;
    const radius = assistant ? "16px 16px 4px 16px" : "16px 16px 16px 4px";
    const nameAlign = assistant ? "right" : "left";
    const body = escapeHtml(turn.body).replaceAll("\n", "<br>");
    const bubbleCell = `<div style="font-family: ${SANS}; font-size: 11px; font-weight: 600; letter-spacing: 0.04em; color: ${MUTE}; padding: 0 2px 5px 2px; text-align: ${nameAlign};">${escapeHtml(name)}</div>
                    <table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation">
                      <tr>
                        <td bgcolor="${background}" style="background-color: ${background}; border-radius: ${radius}; padding: 13px 15px; font-family: ${SANS}; font-size: 15px; font-weight: 400; line-height: 1.55; color: ${color}; overflow-wrap: anywhere; word-break: break-word;">${body}</td>
                      </tr>
                    </table>`;
    const guestRow = `<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" style="margin: 0 0 12px 0; table-layout: fixed;">
                  <tr>
                    <td width="78%" valign="top">${bubbleCell}</td>
                    <td width="22%" style="font-size: 0; line-height: 0;">&nbsp;</td>
                  </tr>
                </table>`;
    const assistantRow = `<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" style="margin: 0 0 12px 0; table-layout: fixed;">
                  <tr>
                    <td width="22%" style="font-size: 0; line-height: 0;">&nbsp;</td>
                    <td width="78%" valign="top">${bubbleCell}</td>
                  </tr>
                </table>`;
    return assistant ? assistantRow : guestRow;
  });
  return `<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" style="margin: 8px 0 8px 0;">
              <tr>
                <td style="${sectionLabel()}; padding-bottom: 14px;">Transcript</td>
              </tr>
              <tr>
                <td>${rows.join("\n                ")}</td>
              </tr>
            </table>`;
}

function summaryBlock(summary: string): string {
  if (!isPresent(summary)) {
    return "";
  }
  const body = escapeHtml(summary.trim()).replaceAll("\n", "<br>");
  return `<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" style="margin: 0 0 22px 0;">
              <tr>
                <td style="${sectionLabel()}; padding-bottom: 10px;">Summary</td>
              </tr>
              <tr>
                <td bgcolor="${GUEST_BUBBLE}" style="background-color: ${GUEST_BUBBLE}; border-left: 3px solid ${LEMON}; padding: 14px 16px; font-family: ${SANS}; font-size: 16px; font-weight: 400; line-height: 1.65; color: ${INK}; overflow-wrap: break-word; word-break: normal;">${body}</td>
              </tr>
            </table>`;
}

function lemonPage(
  inner: string,
  options: { title?: string; fillViewport?: boolean } = {},
): string {
  const title = options.title
    ? `\n  <title>${escapeHtml(options.title)}</title>`
    : "";
  const htmlStyle = options.fillViewport ? ' style="height: 100%;"' : "";
  const bodyStyle = options.fillViewport
    ? `margin: 0; padding: 0; height: 100%; min-height: 100vh; background-color: ${LEMON}; font-family: ${SANS}; -webkit-text-size-adjust: 100%;`
    : `margin: 0; padding: 0; background-color: ${LEMON}; font-family: ${SANS}; -webkit-text-size-adjust: 100%;`;
  const tableStyle = options.fillViewport
    ? `background-color: ${LEMON}; height: 100%; min-height: 100vh; table-layout: fixed;`
    : `background-color: ${LEMON}; table-layout: fixed;`;
  const tableHeight = options.fillViewport ? ' height="100%"' : "";
  const cellValign = options.fillViewport ? ' valign="middle"' : "";
  return `<!doctype html>
<html lang="en"${htmlStyle}>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">${title}
  <style>
    img { max-width: 100% !important; height: auto !important; }
  </style>
</head>
<body style="${bodyStyle}">
  <table width="100%"${tableHeight} cellpadding="0" cellspacing="0" border="0" role="presentation" bgcolor="${LEMON}" style="${tableStyle}">
    <tr>
      <td width="4%" style="font-size: 0; line-height: 0; width: 4%;">&nbsp;</td>
      <td width="92%" align="center"${cellValign} style="padding: 28px 0; width: 92%;">
        ${inner}
      </td>
      <td width="4%" style="font-size: 0; line-height: 0; width: 4%;">&nbsp;</td>
    </tr>
  </table>
</body>
</html>`;
}

export function renderCustomerReport(input: {
  profile: ClientProfile;
  call: Call;
  analysis: CallAnalysis;
  ratingBaseUrl: string;
}): string {
  const ratingBase = assertPublicOrigin(input.ratingBaseUrl);
  const recordingHref = escapeHtml(
    recordingPlaybackHref(ratingBase, input.profile.slug, input.call.callId),
  );
  const showRecording = isPresent(input.call.recordingUrl);
  const duration = formatCallDuration(input.call.durationSeconds);
  const turns = parseTranscriptTurns(input.analysis.formattedTranscript);
  const meta: string[] = [];
  if (isPresent(input.analysis.localCallTime)) {
    meta.push(metaRow("Time", input.analysis.localCallTime.trim()));
  }
  if (duration) {
    meta.push(metaRow("Length", duration));
  }
  if (isPresent(input.analysis.contactInfo)) {
    meta.push(metaRow("Contact", input.analysis.contactInfo.trim()));
  }
  const card = `<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" style="max-width: 560px; width: 100%; table-layout: fixed; background-color: ${CARD}; border-radius: 18px;">
          <tr>
            <td style="padding: 24px 22px 8px 22px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation">
                <tr>
                  <td align="center" style="padding-bottom: 18px;">
                    ${yinoLogoImg(132, "display: block; margin: 0 auto;")}
                  </td>
                </tr>
                <tr>
                  <td align="center" style="${sectionLabel()}; padding-bottom: 10px; text-align: center;">AI Call Report</td>
                </tr>
              </table>
              <div style="font-family: ${SANS}; font-size: 28px; font-weight: 600; line-height: 1.25; letter-spacing: -0.02em; color: ${INK}; padding-bottom: 20px; overflow-wrap: break-word; word-break: normal;">${escapeHtml(input.analysis.customerName)}</div>
              ${
                meta.length > 0
                  ? `<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" style="margin: 0 0 18px 0;">${meta.join("")}</table>`
                  : ""
              }
              ${summaryBlock(input.call.summary)}
              ${topicChips(input.analysis.mainTopics)}
              ${showRecording ? playRecordingButton(recordingHref) : ""}
              ${transcriptBubbles(turns, input.profile.assistantName, input.analysis.customerName)}
              <table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" style="margin: 8px 0 0 0;">
                <tr>
                  <td style="border-top: 1px solid #ebe7df; padding: 22px 0 8px 0; font-family: ${SANS}; font-size: 13px; font-weight: 400; line-height: 1.55; color: ${MUTE};">
                    Best regards,<br>The Yino Digital Receptionist
                  </td>
                </tr>
                <tr>
                  <td style="padding: 14px 0 6px 0; font-family: ${SANS}; font-size: 15px; font-weight: 500; line-height: 1.4; color: ${INK};">Scale Faster, Staff Lighter.</td>
                </tr>
                <tr>
                  <td style="font-family: ${SANS}; font-size: 12px; letter-spacing: 0.04em; color: ${MUTE}; padding-bottom: 16px;">www.yino.au</td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td bgcolor="${INK}" style="background-color: ${INK}; padding: 22px 12px 26px 12px; border-radius: 0 0 18px 18px;" align="center">
              <div style="font-family: ${SANS}; font-size: 15px; font-weight: 600; line-height: 1.4; color: ${LEMON}; margin-bottom: 16px;">How did your agent perform?</div>
              <div style="text-align: center; font-size: 0; line-height: 0;">
              ${ratingScoreButtons(ratingBase, input.profile.slug, input.call.callId)}
              </div>
            </td>
          </tr>
        </table>`;

  return lemonPage(card);
}

export function renderRatingConfirmation(
  profile: string,
  callId: string,
  score: number,
): string {
  const action =
    "/rating?profile=" +
    encodeURIComponent(profile) +
    "&amp;call_id=" +
    encodeURIComponent(callId) +
    "&amp;score=" +
    String(score);
  const card = `<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" style="max-width: 480px; width: 100%; background-color: ${CARD}; border-radius: 18px; overflow: hidden;">
          <tr>
            <td style="padding: 36px 32px 32px 32px;" align="center">
              ${yinoLogoImg(120, "display: block; margin: 0 auto 18px auto;")}
              <div style="font-family: ${SANS}; font-size: 11px; font-weight: 500; letter-spacing: 0.22em; text-transform: uppercase; color: ${MUTE}; padding-bottom: 8px;">Saving rating</div>
              <div style="font-family: ${SANS}; font-size: 28px; font-weight: 600; letter-spacing: -0.02em; color: ${INK}; padding-bottom: 12px;">Saving…</div>
              <form id="yino-rate" method="post" action="${action}" style="margin: 0;">
                <noscript>
                  <button type="submit" style="display: block; width: 100%; min-height: 48px; padding: 16px 20px; border: 0; background: ${INK}; color: ${LEMON}; font-family: ${SANS}; font-size: 13px; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; cursor: pointer; border-radius: 12px; touch-action: manipulation;">Save</button>
                </noscript>
              </form>
              <script>
(function () {
  if (location.protocol === "file:") return;
  var form = document.getElementById("yino-rate");
  if (form) form.submit();
})();
              </script>
            </td>
          </tr>
        </table>`;
  return lemonPage(card, { title: "Saving rating", fillViewport: true });
}

export function renderRatingSavedHtml(): string {
  const card = `<table width="100%" cellpadding="0" cellspacing="0" border="0" role="presentation" style="max-width: 480px; width: 100%; background-color: ${CARD}; border-radius: 18px; overflow: hidden;">
          <tr>
            <td style="padding: 36px 32px;" align="center">
              ${yinoLogoImg(120, "display: block; margin: 0 auto 18px auto;")}
              <div style="font-family: ${SANS}; font-size: 11px; font-weight: 500; letter-spacing: 0.22em; text-transform: uppercase; color: ${MUTE}; padding-bottom: 8px;">Thank you</div>
              <div style="font-family: ${SANS}; font-size: 28px; font-weight: 600; letter-spacing: -0.02em; color: ${INK}; padding-bottom: 12px;">Rating saved</div>
              <p style="margin: 0; font-family: ${SANS}; font-size: 15px; font-weight: 400; line-height: 1.5; color: ${MUTE};">You can close this page.</p>
            </td>
          </tr>
        </table>`;
  return lemonPage(card, { title: "Rating saved", fillViewport: true });
}

export function renderQualityReport(input: {
  profile: ClientProfile;
  call: Call;
  analysis: CallAnalysis;
  quality: QualityAnalysis;
}): string {
  const theme = qualityScoreTheme(input.quality.score);
  const promptBanner = input.quality.shouldUpdatePrompt
    ? { background: "#cce5ff", text: "⚠️ 建议更新Prompt" }
    : { background: "#e2e3e5", text: "✅ 当前Prompt表现良好，无需更新" };

  return `<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; padding: 20px;">
  <div style="max-width: 600px; margin: 0 auto; background: #f9f9f9; border-radius: 12px; padding: 30px;">
    <h1 style="color: #333; border-bottom: 2px solid #e4e84d; padding-bottom: 10px;">
      📊 AI客服质量分析报告
    </h1>
    <p style="color: #666;">客户: ${escapeHtml(input.analysis.customerName)} | 时间: ${escapeHtml(input.analysis.localCallTime)}</p>
    
    <div style="background: ${theme.background}; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center;">
      <h2 style="margin: 0; font-size: 48px; color: ${theme.color};">
        ${escapeHtml(String(input.quality.score))}/10
      </h2>
      <p style="margin: 10px 0 0 0; color: #666;">${escapeHtml(input.quality.summary)}</p>
    </div>
    
    <h3 style="color: #28a745;">✅ 优点</h3>
    <ul style="color: #333;">
      ${qualityList(input.quality.strengths)}
    </ul>
    
    <h3 style="color: #dc3545;">❌ 问题</h3>
    <ul style="color: #333;">
      ${qualityList(input.quality.weaknesses)}
    </ul>
    
    <h3 style="color: #007bff;">💡 改进建议</h3>
    <ul style="color: #333;">
      ${qualityList(input.quality.suggestions)}
    </ul>
    
    <div style="margin-top: 20px; padding: 15px; background: ${promptBanner.background}; border-radius: 8px;">
      <strong>Prompt更新建议:</strong> ${promptBanner.text}
    </div>
    
    <p style="color: #999; font-size: 12px; margin-top: 30px; text-align: center;">
      此报告由AI自动生成 | Yino AI Quality Monitor
    </p>
  </div>
</body>
</html>
`;
}
