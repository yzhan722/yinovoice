import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  CUSTOMER_SERVICE_VERSION_CONFLICT,
  RealtimeVoiceService,
  normalizePlatformCallDetail,
  normalizePlatformCallListResponse,
  type CustomerServiceInstance,
  type CustomerServiceUpdateRequest,
  type NormalizedCallRecordDetail,
  type NormalizedCallRecordListItem,
  type PlatformCallRecord,
} from './RealtimeVoiceService';

const tenantId = '00000000-0000-0000-0000-000000000001';
const serviceId = '00000000-0000-0000-0000-000000000101';

function jsonResponse(value: unknown, ok = true) {
  return {
    ok,
    json: vi.fn().mockResolvedValue(value),
  } as unknown as Response;
}

function customerService(overrides: Partial<CustomerServiceInstance> = {}): CustomerServiceInstance {
  return {
    id: serviceId,
    tenant_id: tenantId,
    version: 1,
    display_name: '常州太平洋口腔语音客服',
    organization_name: '常州太平洋口腔',
    business_profile: 'generic-receptionist',
    primary_language: 'zh-CN',
    greeting: '您好，这里是常州太平洋口腔客服，请问有什么可以帮您？',
    platform_prompt: '原始平台 Prompt',
    tenant_prompt: '原始业务 Prompt',
    voice: {
      preset_id: 'mandarin-standard',
      locale: 'zh-CN',
      speaking_rate: 1,
      volume: 1,
      pitch: 0,
      style: 'professional-friendly',
      emotion: 'neutral',
      pause_profile: 'receptionist',
      tts_voice: 'longanqian',
    },
    response: {
      brevity: 'concise',
      max_spoken_sentences: 3,
      ask_one_question_at_a_time: true,
    },
    ...overrides,
  };
}

function updateFromInstance(
  instance: CustomerServiceInstance,
  tenantPrompt: string,
): CustomerServiceUpdateRequest {
  return {
    expected_version: instance.version,
    display_name: instance.display_name,
    organization_name: instance.organization_name,
    greeting: instance.greeting,
    platform_prompt: instance.platform_prompt,
    tenant_prompt: tenantPrompt,
    voice: instance.voice,
    response: instance.response,
  };
}

function record(): PlatformCallRecord {
  return {
    id: '00000000-0000-0000-0000-000000000900',
    tenant_id: tenantId,
    customer_service_id: serviceId,
    room_name: 'demo-room',
    status: 'completed',
    started_at: '2026-08-03T01:00:00Z',
    ended_at: '2026-08-03T01:00:12Z',
    duration_sec: 12,
    direction: 'web',
    messages: [
      { role: 'user', text: '你好', sequence: 1 },
      { role: 'assistant', text: '您好', sequence: 2 },
    ],
    created_at: '2026-08-03T01:00:13Z',
    recording_status: 'none',
    recording_mime_type: null,
    recording_size_bytes: null,
    recording_failure_code: null,
  };
}

describe('RealtimeVoiceService', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('uses tenant-scoped Platform API routes for token and call records', async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({
          server_url: 'ws://localhost:7880',
          room_name: 'room-1',
          participant_identity: 'browser-1',
          token: 'short-lived-token',
        }),
      )
      .mockResolvedValueOnce(jsonResponse(record()))
      .mockResolvedValueOnce(jsonResponse({ items: [record()], total: 1 }))
      .mockResolvedValueOnce(jsonResponse(record()));
    const service = new RealtimeVoiceService({
      baseUrl: 'http://api.test/',
      tenantId,
    });
    const createRequest = {
      customer_service_id: serviceId,
      room_name: 'demo-room',
      status: 'completed' as const,
      started_at: '2026-08-03T01:00:00Z',
      ended_at: '2026-08-03T01:00:12Z',
      duration_sec: 12,
      messages: [{ role: 'user' as const, text: '你好', sequence: 1 }],
    };

    await service.issueLiveKitToken(serviceId, 'browser-1');
    await service.createDemoCallRecord(createRequest);
    await service.listCallRecords({ limit: 10, offset: 20 });
    await service.getCallRecord(record().id);

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      'http://api.test/api/v1/customer-services/' + serviceId + '/livekit-token',
      'http://api.test/api/v1/call-records',
      'http://api.test/api/v1/call-records?limit=10&offset=20',
      'http://api.test/api/v1/call-records/' + record().id,
    ]);
    for (const [, init] of fetchMock.mock.calls) {
      expect(new Headers(init?.headers).get('X-Tenant-ID')).toBe(tenantId);
    }
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      participant_identity: 'browser-1',
    });
  });

  it('lists tenant customer services with pagination and preserves UUID ids', async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(jsonResponse({
      items: [customerService()],
      total: 1,
    }));
    const service = new RealtimeVoiceService({
      baseUrl: 'http://api.test',
      tenantId,
    });

    const page = await service.listCustomerServices({ limit: 10, offset: 20 });

    expect(page.total).toBe(1);
    expect(page.items[0].id).toBe(serviceId);
    expect(fetchMock.mock.calls[0][0]).toBe(
      'http://api.test/api/v1/customer-services?limit=10&offset=20',
    );
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).get('X-Tenant-ID')).toBe(tenantId);
  });

  it('creates a tenant customer service without server-owned fields', async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(jsonResponse(customerService()));
    const service = new RealtimeVoiceService({ baseUrl: 'http://api.test', tenantId });
    const input = {
      display_name: 'Synthetic Support',
      organization_name: 'Demo Organization',
      greeting: 'Hello, how may I help you?',
      platform_prompt: '',
      tenant_prompt: '',
      voice: customerService().voice,
      response: customerService().response,
    };

    await service.createCustomerService(input);

    expect(fetchMock.mock.calls[0][0]).toBe('http://api.test/api/v1/customer-services');
    expect(fetchMock.mock.calls[0][1]?.method).toBe('POST');
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual(input);
  });

  it('aborts a bounded request and never exposes the provider error', async () => {
    vi.useFakeTimers();
    vi.mocked(fetch).mockImplementation((_url, init) => (
      new Promise((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => {
          reject(new Error('DashScope api key leaked by SDK'));
        });
      })
    ));
    const service = new RealtimeVoiceService({
      baseUrl: 'http://api.test',
      tenantId,
      timeoutMs: 25,
    });

    const pending = service.getCustomerService(serviceId).catch((error) => error as Error);
    await vi.advanceTimersByTimeAsync(25);

    const error = await pending;
    expect(error).toBeInstanceOf(Error);
    if (!(error instanceof Error)) throw new Error('expected bounded request failure');
    expect(error.message).toBe('平台服务暂时不可用，请稍后重试');
    expect(error.message).not.toContain('DashScope');
  });

  it('uploads recording as multipart and fetches playback blob with tenant header', async () => {
    const fetchMock = vi.mocked(fetch);
    const recordId = record().id;
    const audioBytes = new Uint8Array([1, 2, 3, 4]);
    const uploadedRecord: PlatformCallRecord = {
      ...record(),
      recording_status: 'ready',
      recording_mime_type: 'audio/webm',
      recording_size_bytes: 4,
      recording_failure_code: null,
    };
    fetchMock
      .mockResolvedValueOnce(jsonResponse(uploadedRecord))
      .mockResolvedValueOnce({
        ok: true,
        blob: vi.fn().mockResolvedValue(new Blob([audioBytes], { type: 'audio/webm' })),
      } as unknown as Response);
    const service = new RealtimeVoiceService({
      baseUrl: 'http://api.test',
      tenantId,
    });
    const file = new Blob([audioBytes], { type: 'audio/webm' });

    const uploaded = await service.uploadCallRecording(recordId, file);
    const blob = await service.fetchCallRecordingBlob(recordId);

    expect(uploaded.recording_status).toBe('ready');
    expect(uploaded.recording_mime_type).toBe('audio/webm');
    expect(uploaded.recording_size_bytes).toBe(4);
    expect(blob).toBeInstanceOf(Blob);
    expect(blob.size).toBe(4);
    expect(blob.type).toBe('audio/webm');

    const uploadUrl = 'http://api.test/api/v1/call-records/' + recordId + '/recording';
    expect(fetchMock.mock.calls[0][0]).toBe(uploadUrl);
    const uploadInit = fetchMock.mock.calls[0][1];
    expect(uploadInit?.method).toBe('POST');
    expect(new Headers(uploadInit?.headers).get('X-Tenant-ID')).toBe(tenantId);
    expect(new Headers(uploadInit?.headers).get('Content-Type')).toBeNull();
    expect(uploadInit?.body).toBeInstanceOf(FormData);
    const formData = uploadInit?.body as FormData;
    expect(formData.get('file')).toBeInstanceOf(Blob);

    expect(fetchMock.mock.calls[1][0]).toBe(uploadUrl);
    expect(fetchMock.mock.calls[1][1]?.method).toBe('GET');
    expect(new Headers(fetchMock.mock.calls[1][1]?.headers).get('X-Tenant-ID')).toBe(tenantId);
  });

  it('updates customer service tenant_prompt with expected_version', async () => {
    const fetchMock = vi.mocked(fetch);
    const current = customerService();
    const updated = customerService({ version: 2, tenant_prompt: '更新后的业务 Prompt' });
    fetchMock.mockResolvedValueOnce(jsonResponse(updated));
    const service = new RealtimeVoiceService({
      baseUrl: 'http://api.test',
      tenantId,
    });
    const body = updateFromInstance(current, '更新后的业务 Prompt');

    const result = await service.updateCustomerService(serviceId, body);

    expect(result.version).toBe(2);
    expect(result.tenant_prompt).toBe('更新后的业务 Prompt');
    expect(fetchMock.mock.calls[0][0]).toBe(
      'http://api.test/api/v1/customer-services/' + serviceId,
    );
    expect(fetchMock.mock.calls[0][1]?.method).toBe('PUT');
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).get('X-Tenant-ID')).toBe(tenantId);
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual(body);
  });

  it('surfaces version conflict without leaking provider detail', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: vi.fn().mockResolvedValue({ detail: 'Customer service version conflict' }),
    } as unknown as Response);
    const service = new RealtimeVoiceService({
      baseUrl: 'http://api.test',
      tenantId,
    });

    await expect(
      service.updateCustomerService(serviceId, updateFromInstance(customerService(), 'x')),
    ).rejects.toThrow(CUSTOMER_SERVICE_VERSION_CONFLICT);
  });

  it('aborts fetchCallRecordingBlob during body read when timeout elapses', async () => {
    vi.useFakeTimers();
    vi.mocked(fetch).mockImplementation((_url, init) => Promise.resolve({
      ok: true,
      blob: () => new Promise((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => {
          reject(new Error('provider blob read leaked detail'));
        });
      }),
    } as unknown as Response));
    const service = new RealtimeVoiceService({
      baseUrl: 'http://api.test',
      tenantId,
      timeoutMs: 25,
    });

    const pending = service.fetchCallRecordingBlob(record().id).catch((error) => error as Error);
    await vi.advanceTimersByTimeAsync(25);

    const error = await pending;
    expect(error).toBeInstanceOf(Error);
    if (!(error instanceof Error)) throw new Error('expected bounded blob fetch failure');
    expect(error.message).toBe('平台服务暂时不可用，请稍后重试');
    expect(error.message).not.toContain('provider blob read leaked detail');
  });

  it('relays an external abort to the call-record POST', async () => {
    let requestSignal: AbortSignal | undefined;
    vi.mocked(fetch).mockImplementation((_url, init) => {
      requestSignal = init?.signal || undefined;
      return new Promise((_resolve, reject) => {
        requestSignal?.addEventListener('abort', () => {
          reject(new Error('raw aborted fetch detail'));
        });
      });
    });
    const service = new RealtimeVoiceService({
      baseUrl: 'http://api.test',
      tenantId,
    });
    const controller = new AbortController();
    const pending = service.createDemoCallRecord({
      customer_service_id: serviceId,
      room_name: 'demo-room',
      status: 'interrupted',
      started_at: '2026-08-03T01:00:00Z',
      ended_at: '2026-08-03T01:00:02Z',
      duration_sec: 2,
      messages: [],
    }, controller.signal).catch((error) => error as Error);

    controller.abort();
    const error = await pending;

    expect(requestSignal?.aborted).toBe(true);
    expect(error).toBeInstanceOf(Error);
    if (!(error instanceof Error)) throw new Error('expected aborted request failure');
    expect(error.message).not.toContain('raw aborted fetch detail');
  });
});

describe('Platform call record normalization', () => {
  it('maps web Demo records into the existing tenant and operator page shape', () => {
    const normalized = normalizePlatformCallListResponse(
      { items: [record()], total: 1 },
      new Map([[serviceId, '演示 AI 语音客服']]),
    );

    const firstRecord: NormalizedCallRecordListItem = normalized.records[0];

    expect(normalized.total).toBe(1);
    expect(firstRecord).toMatchObject({
      aacId: record().id,
      callId: record().id,
      assistantName: '演示 AI 语音客服',
      attId: serviceId,
      direction: 'web',
      status: 'completed',
      startedAt: '2026-08-03T01:00:00Z',
      durationSec: 12,
      customerPhone: '',
      success: 1,
    });
  });

  it('normalizes final transcript text for the existing detail bubbles', () => {
    const normalized = normalizePlatformCallDetail(record(), '演示 AI 语音客服');
    const detail: NormalizedCallRecordDetail = normalized;

    expect(detail).toMatchObject({
      aacId: record().id,
      aacCallId: record().id,
      aacSuccess: 1,
      aacDurationSec: 12,
      aacStartedAt: '2026-08-03T01:00:00Z',
      aacEndedAt: '2026-08-03T01:00:12Z',
      aacCallType: 'webCall',
      attName: '演示 AI 语音客服',
    });
    expect(detail.messages).toEqual([
      { role: 'user', text: '你好', content: '你好', sequence: 1 },
      { role: 'assistant', text: '您好', content: '您好', sequence: 2 },
    ]);
  });

  it('passes recording metadata through normalized detail', () => {
    const normalized = normalizePlatformCallDetail({
      ...record(),
      recording_status: 'ready',
      recording_mime_type: 'audio/webm',
      recording_size_bytes: 4096,
      recording_failure_code: null,
    }, '演示 AI 语音客服');

    expect(normalized.recording_status).toBe('ready');
    expect(normalized.recording_mime_type).toBe('audio/webm');
    expect(normalized.recording_size_bytes).toBe(4096);
    expect(normalized.recording_failure_code).toBeNull();
  });
});
