export type CallRecordStatus = 'completed' | 'interrupted' | 'failed';
export type RecordingStatus = 'none' | 'uploading' | 'ready' | 'failed';
export type TranscriptRole = 'user' | 'assistant';

export type TtsVoiceId =
  | 'longanqian'
  | 'longanlingxin'
  | 'longanlingxi'
  | 'longanxiaoxin'
  | 'longanlufeng'
  | 'longanfengyue'
  | 'longanyuanfei'
  | 'longanhuan_v3.6'
  | 'longjielidou_v3.6'
  | 'longpaopao_v3.6'
  | 'longhuohuo_v3.6'
  | 'longchuanshu_v3.6'
  | 'loongmary'
  | 'loongeva_v3.6'
  | 'loongjohn';

export interface VoiceProfile {
  preset_id: string;
  locale: string;
  speaking_rate: number;
  volume: number;
  pitch: number;
  style: string;
  emotion: string;
  pause_profile: string;
  tts_voice: TtsVoiceId;
}

/** Only voices accepted by Qwen-Audio Realtime gateway. */
export const TTS_VOICE_OPTIONS: { value: TtsVoiceId; label: string }[] = [
  { value: 'longanqian', label: '龙安仟（沉稳女声）' },
  { value: 'longanlingxin', label: '龙安灵心' },
  { value: 'longanlingxi', label: '龙安灵犀' },
  { value: 'longanxiaoxin', label: '龙安晓昕' },
  { value: 'longanlufeng', label: '龙安庐风' },
  { value: 'longanfengyue', label: '龙安风月' },
  { value: 'longanyuanfei', label: '龙安远菲' },
  { value: 'longanhuan_v3.6', label: '龙安欢' },
  { value: 'longjielidou_v3.6', label: '龙杰力豆' },
  { value: 'longpaopao_v3.6', label: '龙泡泡' },
  { value: 'longhuohuo_v3.6', label: '龙火火' },
  { value: 'longchuanshu_v3.6', label: '龙川叔' },
  { value: 'loongmary', label: 'Mary（英文女声）' },
  { value: 'loongeva_v3.6', label: 'Eva（英文女声）' },
  { value: 'loongjohn', label: 'John（英文男声）' },
];

export interface ResponseProfile {
  brevity: 'concise' | 'balanced' | 'detailed';
  max_spoken_sentences: number;
  ask_one_question_at_a_time: true;
}

export interface CustomerServiceInstance {
  id: string;
  tenant_id: string;
  version: number;
  display_name: string;
  organization_name: string;
  business_profile: string;
  primary_language: string;
  greeting: string;
  platform_prompt: string;
  tenant_prompt: string;
  voice: VoiceProfile;
  response: ResponseProfile;
}

/** Name fields used by call-record normalization. */
export type CustomerServiceSummary = Pick<
  CustomerServiceInstance,
  'id' | 'tenant_id' | 'display_name' | 'organization_name'
>;

export interface CustomerServiceUpdateRequest {
  expected_version: number;
  display_name: string;
  organization_name: string;
  greeting: string;
  platform_prompt: string;
  tenant_prompt: string;
  voice: VoiceProfile;
  response: ResponseProfile;
}

export const CUSTOMER_SERVICE_VERSION_CONFLICT =
  '配置已被更新，请刷新后重试';

export interface LiveKitJoin {
  server_url: string;
  room_name: string;
  participant_identity: string;
  token: string;
}

export interface FinalTranscriptMessage {
  role: TranscriptRole;
  text: string;
  sequence: number;
}

export interface CreateCallRecordRequest {
  customer_service_id: string;
  room_name: string;
  status: CallRecordStatus;
  started_at: string;
  ended_at: string;
  duration_sec: number;
  messages: FinalTranscriptMessage[];
}

export interface PlatformCallRecord extends CreateCallRecordRequest {
  id: string;
  tenant_id: string;
  direction: 'web';
  created_at: string;
  recording_status: RecordingStatus;
  recording_mime_type: string | null;
  recording_size_bytes: number | null;
  recording_failure_code: string | null;
}

export interface PlatformCallRecordPage {
  items: PlatformCallRecord[];
  total: number;
}

export interface NormalizedCallRecordListItem {
  aacId: string;
  callId: string;
  assistantName: string;
  attId: string;
  direction: 'web';
  status: CallRecordStatus;
  startedAt: string;
  durationSec: number;
  customerPhone: '';
  success: 0 | 1;
  roomName: string;
  raw: PlatformCallRecord;
}

export interface NormalizedCallRecordPage {
  records: NormalizedCallRecordListItem[];
  list: NormalizedCallRecordListItem[];
  total: number;
  ready: true;
}

export interface NormalizedTranscriptMessage extends FinalTranscriptMessage {
  content: string;
}

export interface NormalizedCallRecordDetail extends PlatformCallRecord {
  aacId: string;
  aacCallId: string;
  callId: string;
  aacSuccess: 0 | 1;
  aacDurationSec: number;
  aacSummary: '';
  aacCustomerPhone: '';
  aacCustomerNumber: '';
  aacStartedAt: string;
  aacEndedAt: string;
  aacCreatedAt: string;
  aacUpdatedAt: string;
  aacCallType: 'webCall';
  aacStatus: CallRecordStatus;
  aacEndedReason: CallRecordStatus;
  attName: string;
  assistantName: string;
  messages: NormalizedTranscriptMessage[];
}

export interface RealtimeVoiceServiceOptions {
  baseUrl?: string;
  tenantId?: string;
  timeoutMs?: number;
}

export interface CallRecordFacade {
  listNormalizedCallRecords(
    page?: { limit?: number; offset?: number },
    signal?: AbortSignal,
  ): Promise<NormalizedCallRecordPage>;
  getNormalizedCallRecord(
    recordId: string,
    signal?: AbortSignal,
  ): Promise<NormalizedCallRecordDetail>;
}

export const DEMO_TENANT_ID =
  import.meta.env.VITE_DEMO_TENANT_ID || '00000000-0000-0000-0000-000000000001';
export const DEMO_CUSTOMER_SERVICE_ID =
  import.meta.env.VITE_DEMO_CUSTOMER_SERVICE_ID
  || '00000000-0000-0000-0000-000000000101';

const SAFE_PLATFORM_ERROR = '平台服务暂时不可用，请稍后重试';
const DEFAULT_TIMEOUT_MS = 10_000;

function normalizedBaseUrl(value: string): string {
  return value.replace(/\/+$/, '');
}

export class RealtimeVoiceService {
  private readonly baseUrl: string;

  private readonly tenantId: string;

  private readonly timeoutMs: number;

  constructor(options: RealtimeVoiceServiceOptions = {}) {
    this.baseUrl = normalizedBaseUrl(
      options.baseUrl
      || import.meta.env.VITE_PLATFORM_API_BASE
      || 'http://localhost:8000',
    );
    this.tenantId = options.tenantId || DEMO_TENANT_ID;
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  }

  private async request<T>(
    path: string,
    init: RequestInit = {},
    externalSignal?: AbortSignal,
  ): Promise<T> {
    const controller = new AbortController();
    const relayAbort = () => controller.abort();
    const timer = window.setTimeout(relayAbort, this.timeoutMs);
    if (externalSignal?.aborted) relayAbort();
    else externalSignal?.addEventListener('abort', relayAbort, { once: true });

    try {
      const response = await fetch(this.baseUrl + path, {
        ...init,
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-ID': this.tenantId,
          ...init.headers,
        },
        signal: controller.signal,
      });
      if (!response.ok) throw new Error('unsafe response');
      return await response.json() as T;
    } catch {
      throw new Error(SAFE_PLATFORM_ERROR);
    } finally {
      window.clearTimeout(timer);
      externalSignal?.removeEventListener('abort', relayAbort);
    }
  }

  private async fetchWithTenant<T>(
    path: string,
    init: RequestInit,
    externalSignal: AbortSignal | undefined,
    consume: (response: Response) => Promise<T>,
  ): Promise<T> {
    const controller = new AbortController();
    const relayAbort = () => controller.abort();
    const timer = window.setTimeout(relayAbort, this.timeoutMs);
    if (externalSignal?.aborted) relayAbort();
    else externalSignal?.addEventListener('abort', relayAbort, { once: true });

    try {
      const response = await fetch(this.baseUrl + path, {
        ...init,
        headers: {
          'X-Tenant-ID': this.tenantId,
          ...init.headers,
        },
        signal: controller.signal,
      });
      return await consume(response);
    } finally {
      window.clearTimeout(timer);
      externalSignal?.removeEventListener('abort', relayAbort);
    }
  }

  async uploadCallRecording(
    recordId: string,
    file: Blob,
    signal?: AbortSignal,
  ): Promise<PlatformCallRecord> {
    const formData = new FormData();
    formData.append('file', file);
    try {
      return await this.fetchWithTenant(
        '/api/v1/call-records/' + encodeURIComponent(recordId) + '/recording',
        { method: 'POST', body: formData },
        signal,
        async (response) => {
          if (!response.ok) throw new Error('unsafe response');
          return await response.json() as PlatformCallRecord;
        },
      );
    } catch {
      throw new Error(SAFE_PLATFORM_ERROR);
    }
  }

  async fetchCallRecordingBlob(recordId: string, signal?: AbortSignal): Promise<Blob> {
    try {
      return await this.fetchWithTenant(
        '/api/v1/call-records/' + encodeURIComponent(recordId) + '/recording',
        { method: 'GET' },
        signal,
        async (response) => {
          if (!response.ok) throw new Error('unsafe response');
          return await response.blob();
        },
      );
    } catch {
      throw new Error(SAFE_PLATFORM_ERROR);
    }
  }

  getCustomerService(
    customerServiceId: string,
    signal?: AbortSignal,
  ): Promise<CustomerServiceInstance> {
    return this.request(
      '/api/v1/customer-services/' + encodeURIComponent(customerServiceId),
      { method: 'GET' },
      signal,
    );
  }

  async updateCustomerService(
    customerServiceId: string,
    update: CustomerServiceUpdateRequest,
    signal?: AbortSignal,
  ): Promise<CustomerServiceInstance> {
    try {
      return await this.fetchWithTenant(
        '/api/v1/customer-services/' + encodeURIComponent(customerServiceId),
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(update),
        },
        signal,
        async (response) => {
          if (response.status === 409) {
            throw new Error(CUSTOMER_SERVICE_VERSION_CONFLICT);
          }
          if (!response.ok) throw new Error('unsafe response');
          return await response.json() as CustomerServiceInstance;
        },
      );
    } catch (error) {
      if (
        error instanceof Error
        && error.message === CUSTOMER_SERVICE_VERSION_CONFLICT
      ) {
        throw error;
      }
      throw new Error(SAFE_PLATFORM_ERROR);
    }
  }

  issueLiveKitToken(
    customerServiceId: string,
    participantIdentity: string,
    signal?: AbortSignal,
  ): Promise<LiveKitJoin> {
    return this.request(
      '/api/v1/customer-services/'
        + encodeURIComponent(customerServiceId)
        + '/livekit-token',
      {
        method: 'POST',
        body: JSON.stringify({ participant_identity: participantIdentity }),
      },
      signal,
    );
  }

  createDemoCallRecord(
    record: CreateCallRecordRequest,
    signal?: AbortSignal,
  ): Promise<PlatformCallRecord> {
    return this.request(
      '/api/v1/call-records',
      {
        method: 'POST',
        body: JSON.stringify(record),
      },
      signal,
    );
  }

  listCallRecords(
    page: { limit?: number; offset?: number } = {},
    signal?: AbortSignal,
  ): Promise<PlatformCallRecordPage> {
    const params = new URLSearchParams({
      limit: String(page.limit ?? 20),
      offset: String(page.offset ?? 0),
    });
    return this.request(
      '/api/v1/call-records?' + params.toString(),
      { method: 'GET' },
      signal,
    );
  }

  getCallRecord(recordId: string, signal?: AbortSignal): Promise<PlatformCallRecord> {
    return this.request(
      '/api/v1/call-records/' + encodeURIComponent(recordId),
      { method: 'GET' },
      signal,
    );
  }

  async listNormalizedCallRecords(
    page: { limit?: number; offset?: number } = {},
    signal?: AbortSignal,
  ) {
    const records = await this.listCallRecords(page, signal);
    const services = await this.loadServiceNames(records.items, signal);
    return normalizePlatformCallListResponse(records, services);
  }

  async getNormalizedCallRecord(recordId: string, signal?: AbortSignal) {
    const record = await this.getCallRecord(recordId, signal);
    let serviceName = record.customer_service_id;
    try {
      const service = await this.getCustomerService(record.customer_service_id, signal);
      serviceName = service.display_name;
    } catch {
      // The record remains readable if its demo service was removed.
    }
    return normalizePlatformCallDetail(record, serviceName);
  }

  private async loadServiceNames(
    records: PlatformCallRecord[],
    signal?: AbortSignal,
  ): Promise<Map<string, string>> {
    const ids = Array.from(new Set(records.map((record) => record.customer_service_id)));
    const entries = await Promise.all(ids.map(async (id) => {
      try {
        const service = await this.getCustomerService(id, signal);
        return [id, service.display_name] as const;
      } catch {
        return [id, id] as const;
      }
    }));
    return new Map(entries);
  }
}

function normalizePlatformCallListItem(
  record: PlatformCallRecord,
  serviceName: string,
): NormalizedCallRecordListItem {
  return {
    aacId: record.id,
    callId: record.id,
    assistantName: serviceName,
    attId: record.customer_service_id,
    direction: 'web',
    status: record.status,
    startedAt: record.started_at,
    durationSec: record.duration_sec,
    customerPhone: '',
    success: record.status === 'completed' ? 1 : 0,
    roomName: record.room_name,
    raw: record,
  };
}

export function normalizePlatformCallListResponse(
  page: PlatformCallRecordPage,
  serviceNames: ReadonlyMap<string, string> = new Map(),
): NormalizedCallRecordPage {
  const records = page.items.map((record) => normalizePlatformCallListItem(
    record,
    serviceNames.get(record.customer_service_id) || record.customer_service_id,
  ));
  return {
    records,
    list: records,
    total: page.total,
    ready: true,
  };
}

export function normalizePlatformCallDetail(
  record: PlatformCallRecord,
  serviceName = record.customer_service_id,
): NormalizedCallRecordDetail {
  return {
    ...record,
    aacId: record.id,
    aacCallId: record.id,
    callId: record.id,
    aacSuccess: record.status === 'completed' ? 1 : 0,
    aacDurationSec: record.duration_sec,
    aacSummary: '',
    aacCustomerPhone: '',
    aacCustomerNumber: '',
    aacStartedAt: record.started_at,
    aacEndedAt: record.ended_at,
    aacCreatedAt: record.created_at,
    aacUpdatedAt: record.created_at,
    aacCallType: 'webCall',
    aacStatus: record.status,
    aacEndedReason: record.status,
    attName: serviceName,
    assistantName: serviceName,
    messages: record.messages.map((message) => ({
      ...message,
      content: message.text,
    })),
  };
}
