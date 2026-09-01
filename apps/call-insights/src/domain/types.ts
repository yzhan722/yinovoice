export type EventAction = "analyze" | "skip";
export type JobStatus = "pending" | "running" | "succeeded" | "failed";

export interface ClientProfile {
  slug: string;
  displayName: string;
  assistantName: string;
  vapiAssistantId: string;
  vapiAcceptedAssistantIds?: string[];
  timezone: string;
  brandName: string;
  analysisLanguage: "en";
  qualityLanguage: "zh";
  companyAliases: string[];
  legacyCustomerReportRecipients: string[];
  legacyQualityReportRecipients: string[];
  mailEnabled?: boolean;
}

export type CallChannel = "vapi" | "yino";

export interface Call {
  profile: string;
  callId: string;
  eventId: string;
  channel: CallChannel;
  transcript: string;
  summary: string;
  startedAt: string;
  endedAt: string;
  durationSeconds: number;
  recordingUrl: string | null;
  receivedAt: string;
}

export interface CallAnalysis {
  customerName: string;
  contactInfo: string;
  mainTopics: string[];
  formattedTranscript: string;
  localCallTime: string;
}

export interface QualityAnalysis {
  score: number;
  strengths: string[];
  weaknesses: string[];
  suggestions: string[];
  shouldUpdatePrompt: boolean;
  summary: string;
}

export interface NormalizedEvent {
  eventId: string;
  payloadHash: string;
  profile: string;
  eventType: string;
  callId: string | null;
  receivedAt: string;
  action: EventAction;
  call: Call | null;
}

export interface IngestResult {
  status: "accepted" | "duplicate" | "skipped";
  eventId: string;
  callId: string | null;
  jobId: number | null;
}

export interface AnalysisJob {
  jobId: number;
  profile: string;
  callId: string;
  status: JobStatus;
  attempts: number;
  lastError: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface StoredAnalysis {
  profile: string;
  callId: string;
  provider: "mock" | "deepseek";
  callAnalysis: CallAnalysis;
  qualityAnalysis: QualityAnalysis;
  createdAt: string;
}

export interface Rating {
  profile: string;
  callId: string;
  score: number;
  ratedAt: string;
}

export interface ProfileRegistry {
  get(slug: string): ClientProfile | null;
  list(): ClientProfile[];
}
