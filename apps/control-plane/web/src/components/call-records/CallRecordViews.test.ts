import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const routerPush = vi.hoisted(() => vi.fn());
const serviceState = vi.hoisted(() => ({
  getList: vi.fn(),
  getDetail: vi.fn(),
}));
const recordingState = vi.hoisted(() => ({
  fetchBlob: vi.fn(),
}));
const objectUrlState = vi.hoisted(() => ({
  create: vi.fn(() => 'blob:mock-recording-url'),
  revoke: vi.fn(),
}));

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'record-1' } }),
  useRouter: () => ({ push: routerPush }),
}));

vi.mock('@/api/platform', () => {
  class CallRecordService {
    voiceService = {
      fetchCallRecordingBlob: (...args: unknown[]) => recordingState.fetchBlob(...args),
    };

    getList(...args: unknown[]) {
      return serviceState.getList(...args);
    }

    getDetail(...args: unknown[]) {
      return serviceState.getDetail(...args);
    }
  }
  return {
    TenantCallRecordService: CallRecordService,
    OperatorCallRecordService: CallRecordService,
  };
});

import CallRecordDetailView from './CallRecordDetailView.vue';
import CallRecordListView from './CallRecordListView.vue';

const listRecord = {
  aacId: 'record-1',
  callId: 'record-1',
  assistantName: '演示 AI 语音客服',
  direction: 'web',
  status: 'completed',
  startedAt: '2026-08-03T01:00:00Z',
  durationSec: 12,
};

const detailRecord = {
  ...listRecord,
  aacCallId: 'record-1',
  aacSuccess: 1,
  aacDurationSec: 12,
  aacStartedAt: '2026-08-03T01:00:00Z',
  aacEndedAt: '2026-08-03T01:00:12Z',
  aacCreatedAt: '2026-08-03T01:00:13Z',
  aacStatus: 'completed',
  aacCallType: 'webCall',
  attName: '演示 AI 语音客服',
  room_name: 'demo-room',
  recording_status: 'none',
  messages: [
    { role: 'user', text: '最终用户文本', content: '最终用户文本', sequence: 1 },
    { role: 'assistant', text: '最终客服文本', content: '最终客服文本', sequence: 2 },
  ],
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

describe('call record list view', () => {
  beforeEach(() => {
    routerPush.mockReset();
    serviceState.getList.mockReset().mockResolvedValue({
      records: [listRecord],
      list: [listRecord],
      total: 1,
      ready: true,
    });
    serviceState.getDetail.mockReset().mockResolvedValue(detailRecord);
  });

  it('shows tenant web Demo records without fabricated telephony fields', async () => {
    const wrapper = mount(CallRecordListView, { props: { scope: 'tenant' } });
    await flushPromises();

    expect(wrapper.text()).toContain('网页语音 Demo 记录');
    expect(wrapper.text()).toContain('演示 AI 语音客服');
    expect(wrapper.text()).toContain('网页语音');
    expect(wrapper.text()).toContain('已完成');
    expect(wrapper.text()).not.toContain('客户号码');
    expect(wrapper.text()).not.toContain('接通率');
    expect(wrapper.text()).not.toContain('同步');
  });

  it('labels operator records as configured demo-tenant scope', async () => {
    const wrapper = mount(CallRecordListView, { props: { scope: 'operator' } });
    await flushPromises();

    expect(wrapper.text()).toContain('演示租户范围');
    expect(wrapper.text()).toContain('不代表全局生产 RBAC');
    expect(wrapper.text()).not.toContain('厂商同步');
  });
  it('keeps the newest page when an older page request resolves late', async () => {
    type ListResponse = { records: Array<typeof listRecord>; total: number };
    const pageTwo = deferred<ListResponse>();
    const pageThree = deferred<ListResponse>();
    serviceState.getList
      .mockResolvedValueOnce({ records: [listRecord], total: 30 })
      .mockReturnValueOnce(pageTwo.promise)
      .mockReturnValueOnce(pageThree.promise);
    const wrapper = mount(CallRecordListView, { props: { scope: 'tenant' } });
    await flushPromises();
    const buttons = wrapper.findAll('.pagination button');

    await buttons[1].trigger('click');
    await buttons[1].trigger('click');
    expect(serviceState.getList).toHaveBeenCalledTimes(3);
    pageThree.resolve({
      records: [{ ...listRecord, aacId: 'record-3', assistantName: 'page-three' }],
      total: 30,
    });
    await flushPromises();
    pageTwo.resolve({
      records: [{ ...listRecord, aacId: 'record-2', assistantName: 'page-two' }],
      total: 30,
    });
    await flushPromises();

    expect(wrapper.text()).toContain('page-three');
    expect(wrapper.text()).not.toContain('page-two');
  });
});

describe('call record detail view', () => {
  beforeEach(() => {
    routerPush.mockReset();
    serviceState.getDetail.mockReset().mockResolvedValue(detailRecord);
    recordingState.fetchBlob.mockReset().mockResolvedValue(new Blob(['audio'], { type: 'audio/webm' }));
    objectUrlState.create.mockReset().mockReturnValue('blob:mock-recording-url');
    objectUrlState.revoke.mockReset();
    vi.stubGlobal('URL', {
      createObjectURL: objectUrlState.create,
      revokeObjectURL: objectUrlState.revoke,
    });
  });

  it('renders web call summary and final transcript bubbles', async () => {
    const wrapper = mount(CallRecordDetailView, { props: { scope: 'tenant' } });
    await flushPromises();

    expect(wrapper.text()).toContain('网页语音');
    expect(wrapper.text()).toContain('演示 AI 语音客服');
    expect(wrapper.text()).toContain('最终用户文本');
    expect(wrapper.text()).toContain('最终客服文本');
    expect(wrapper.text()).toContain('12 秒');
    expect(wrapper.text()).not.toContain('客户号码');
    expect(wrapper.text()).not.toContain('总费用');
    expect(wrapper.text()).not.toContain('播放录音');
  });

  it('keeps operator detail explicitly scoped to the demo tenant', async () => {
    const wrapper = mount(CallRecordDetailView, { props: { scope: 'operator' } });
    await flushPromises();

    expect(wrapper.text()).toContain('演示租户范围');
    expect(serviceState.getDetail).toHaveBeenCalledWith('record-1');
  });

  it('shows no-recording copy when recording_status is none', async () => {
    serviceState.getDetail.mockResolvedValue({ ...detailRecord, recording_status: 'none' });
    const wrapper = mount(CallRecordDetailView, { props: { scope: 'tenant' } });
    await flushPromises();

    expect(wrapper.text()).toContain('无录音');
    expect(recordingState.fetchBlob).not.toHaveBeenCalled();
    expect(wrapper.find('audio').exists()).toBe(false);
  });

  it('shows failed copy when recording_status is failed', async () => {
    serviceState.getDetail.mockResolvedValue({ ...detailRecord, recording_status: 'failed' });
    const wrapper = mount(CallRecordDetailView, { props: { scope: 'tenant' } });
    await flushPromises();

    expect(wrapper.text()).toContain('录音保存失败');
    expect(recordingState.fetchBlob).not.toHaveBeenCalled();
    expect(wrapper.find('audio').exists()).toBe(false);
  });

  it('loads ready recording into an audio player', async () => {
    serviceState.getDetail.mockResolvedValue({ ...detailRecord, recording_status: 'ready' });
    const wrapper = mount(CallRecordDetailView, { props: { scope: 'tenant' } });
    await flushPromises();

    expect(recordingState.fetchBlob).toHaveBeenCalledWith('record-1', expect.any(AbortSignal));
    expect(objectUrlState.create).toHaveBeenCalled();
    const audio = wrapper.find('audio');
    expect(audio.exists()).toBe(true);
    expect(audio.attributes('src')).toBe('blob:mock-recording-url');
    expect(wrapper.text()).not.toContain('录音无法播放');
  });

  it('shows loading copy while a ready recording is fetched', async () => {
    const pending = deferred<Blob>();
    serviceState.getDetail.mockResolvedValue({ ...detailRecord, recording_status: 'ready' });
    recordingState.fetchBlob.mockReturnValue(pending.promise);
    const wrapper = mount(CallRecordDetailView, { props: { scope: 'tenant' } });
    await flushPromises();

    expect(wrapper.text()).toContain('正在加载录音…');
    expect(wrapper.find('audio').exists()).toBe(false);

    pending.resolve(new Blob(['audio'], { type: 'audio/webm' }));
    await flushPromises();

    expect(wrapper.find('audio').exists()).toBe(true);
  });

  it('shows playback error when ready recording fetch fails', async () => {
    serviceState.getDetail.mockResolvedValue({ ...detailRecord, recording_status: 'ready' });
    recordingState.fetchBlob.mockRejectedValue(new Error('network'));
    const wrapper = mount(CallRecordDetailView, { props: { scope: 'tenant' } });
    await flushPromises();

    expect(wrapper.text()).toContain('录音无法播放');
    expect(wrapper.find('audio').exists()).toBe(false);
  });

  it('revokes the object URL on unmount', async () => {
    serviceState.getDetail.mockResolvedValue({ ...detailRecord, recording_status: 'ready' });
    const wrapper = mount(CallRecordDetailView, { props: { scope: 'tenant' } });
    await flushPromises();
    wrapper.unmount();

    expect(objectUrlState.revoke).toHaveBeenCalledWith('blob:mock-recording-url');
  });

  it('does not create object URL when unmounted before recording resolves', async () => {
    const pending = deferred<Blob>();
    serviceState.getDetail.mockResolvedValue({ ...detailRecord, recording_status: 'ready' });
    recordingState.fetchBlob.mockReturnValue(pending.promise);
    const wrapper = mount(CallRecordDetailView, { props: { scope: 'tenant' } });
    await flushPromises();

    expect(recordingState.fetchBlob).toHaveBeenCalledWith('record-1', expect.any(AbortSignal));
    wrapper.unmount();
    pending.resolve(new Blob(['audio'], { type: 'audio/webm' }));
    await flushPromises();

    expect(objectUrlState.create).not.toHaveBeenCalled();
  });
});
