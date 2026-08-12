import { flushPromises, mount, type VueWrapper } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const serviceState = vi.hoisted(() => ({
  issueToken: vi.fn(),
  createRecord: vi.fn(),
  uploadRecording: vi.fn(),
}));

const recorderState = vi.hoisted(() => ({
  create: vi.fn(),
  instances: [] as Array<{
    start: ReturnType<typeof vi.fn>;
    stop: ReturnType<typeof vi.fn>;
    dispose: ReturnType<typeof vi.fn>;
  }>,
}));

const livekitState = vi.hoisted(() => ({
  rooms: [] as any[],
}));

vi.mock('@/api/platform/RealtimeVoiceService', () => ({
  RealtimeVoiceService: class {
    issueLiveKitToken(...args: unknown[]) {
      return serviceState.issueToken(...args);
    }

    createDemoCallRecord(...args: unknown[]) {
      return serviceState.createRecord(...args);
    }

    uploadCallRecording(...args: unknown[]) {
      return serviceState.uploadRecording(...args);
    }
  },
}));

vi.mock('./call-recorder', () => ({
  createCallRecorder: () => recorderState.create(),
}));

vi.mock('livekit-client', () => {
  const RoomEvent = {
    TrackSubscribed: 'trackSubscribed',
    TrackUnsubscribed: 'trackUnsubscribed',
    Disconnected: 'disconnected',
    ParticipantConnected: 'participantConnected',
    ParticipantDisconnected: 'participantDisconnected',
    TranscriptionReceived: 'transcriptionReceived',
    ParticipantAttributesChanged: 'participantAttributesChanged',
  };
  class FakeRoom {
    listeners = new Map<string, Set<(...args: any[]) => void>>();

    listenerHistory = new Map<string, Array<(...args: any[]) => void>>();

    agent = { kind: 'agent', identity: 'agent-1', attributes: {} };

    remoteParticipants = new Map([['agent-1', this.agent]]);

    localTrack = {
      stop: vi.fn(),
      mediaStreamTrack: { id: 'local-mic', kind: 'audio', stop: vi.fn() },
    };

    localParticipant = {
      trackPublications: new Map([['mic', { track: this.localTrack }]]),
      setMicrophoneEnabled: vi.fn().mockResolvedValue(undefined),
    };

    connect = vi.fn().mockResolvedValue(undefined);

    disconnect = vi.fn().mockResolvedValue(undefined);

    on = vi.fn((event: string, listener: (...args: any[]) => void) => {
      const listeners = this.listeners.get(event) || new Set();
      listeners.add(listener);
      this.listeners.set(event, listeners);
      const history = this.listenerHistory.get(event) || [];
      history.push(listener);
      this.listenerHistory.set(event, history);
      return this;
    });

    off = vi.fn((event: string, listener: (...args: any[]) => void) => {
      this.listeners.get(event)?.delete(listener);
      return this;
    });

    emit(event: string, ...args: any[]) {
      for (const listener of this.listeners.get(event) || []) listener(...args);
    }

    constructor() {
      livekitState.rooms.push(this);
    }
  }

  return {
    MediaDeviceFailure: {
      PermissionDenied: 'permission-denied',
      getFailure: (error: any) => error?.mediaFailure,
    },
    ParticipantKind: {
      AGENT: 'agent',
    },
    Room: FakeRoom,
    RoomEvent,
    Track: {
      Kind: {
        Audio: 'audio',
      },
    },
  };
});

import LiveKitRealtimePanel from './LiveKitRealtimePanel.vue';

const customerServiceId = '00000000-0000-0000-0000-000000000101';

function createMediaStreamTrack(id: string) {
  return { id, kind: 'audio', stop: vi.fn() } as unknown as MediaStreamTrack;
}

function createRemoteAudioTrack() {
  const element = document.createElement('audio');
  return {
    kind: 'audio',
    mediaStreamTrack: createMediaStreamTrack('remote-audio'),
    attach: vi.fn(() => element),
    detach: vi.fn(() => [element]),
    element,
  };
}

function createRecorderMock(blob: Blob | null = new Blob(['audio'], { type: 'audio/webm' })) {
  const recorder = {
    start: vi.fn(),
    stop: vi.fn().mockResolvedValue(blob),
    dispose: vi.fn(),
  };
  recorderState.instances.push(recorder);
  return recorder;
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function joinResponse() {
  return {
    server_url: 'ws://localhost:7880',
    room_name: 'room-current',
    participant_identity: 'web-1',
    token: 'short-lived-token',
  };
}

async function mountAndStart(): Promise<{ wrapper: VueWrapper; room: any }> {
  const wrapper = mount(LiveKitRealtimePanel, {
    props: { customerServiceId },
  });
  await wrapper.get('[data-testid="voice-connect"]').trigger('click');
  await flushPromises();
  await flushPromises();
  return { wrapper, room: livekitState.rooms.at(-1) };
}

describe('LiveKitRealtimePanel', () => {
  beforeEach(() => {
    livekitState.rooms.length = 0;
    recorderState.instances.length = 0;
    recorderState.create.mockReset().mockImplementation(() => createRecorderMock());
    serviceState.issueToken.mockReset().mockResolvedValue({
      server_url: 'ws://localhost:7880',
      room_name: 'room-current',
      participant_identity: 'web-1',
      token: 'short-lived-token',
    });
    serviceState.createRecord.mockReset().mockResolvedValue({ id: 'record-1' });
    serviceState.uploadRecording.mockReset().mockResolvedValue({
      id: 'record-1',
      recording_status: 'ready',
    });
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  it('starts one continuous microphone call without record/submit controls', async () => {
    const { wrapper, room } = await mountAndStart();

    expect(room.connect).toHaveBeenCalledWith(
      'ws://localhost:7880',
      'short-lived-token',
    );
    expect(room.localParticipant.setMicrophoneEnabled).toHaveBeenCalledWith(true);
    expect(wrapper.text()).toContain('结束通话');
    expect(wrapper.text()).toContain('正在聆听');
    expect(wrapper.text()).not.toContain('停止录音');
    expect(wrapper.text()).not.toContain('提交');

    wrapper.unmount();
    await flushPromises();
  });

  it('renders incremental user/agent transcript and Chinese agent states', async () => {
    const { wrapper, room } = await mountAndStart();
    const user = { kind: 'standard', identity: 'web-1' };

    room.emit(
      'transcriptionReceived',
      [{ id: 'u-1', text: '我想', final: false }],
      user,
    );
    room.emit(
      'transcriptionReceived',
      [{ id: 'u-1', text: '我想预约', final: true }],
      user,
    );
    room.emit(
      'transcriptionReceived',
      [{ id: 'a-1', text: '好的', final: false }],
      room.agent,
    );
    room.emit(
      'participantAttributesChanged',
      { 'lk.agent.state': 'thinking' },
      room.agent,
    );
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain('我想预约');
    expect(wrapper.text()).not.toContain('我想我想预约');
    expect(wrapper.text()).toContain('好的');
    expect(wrapper.text()).toContain('正在思考');

    room.emit(
      'participantAttributesChanged',
      { 'lk.agent.state': 'speaking' },
      room.agent,
    );
    await wrapper.vm.$nextTick();
    expect(wrapper.text()).toContain('正在回答');

    wrapper.unmount();
    await flushPromises();
  });

  it('attaches remote audio immediately when LiveKit publishes it', async () => {
    const { wrapper, room } = await mountAndStart();
    const track = createRemoteAudioTrack();

    room.emit('trackSubscribed', track);
    await wrapper.vm.$nextTick();

    expect(track.attach).toHaveBeenCalledTimes(1);
    expect(track.element.dataset.yinoRemoteAudio).toBe('true');
    expect(wrapper.element.contains(track.element)).toBe(true);

    wrapper.unmount();
    await flushPromises();
  });

  it('ends locally, releases every resource and saves final transcript once', async () => {
    const { wrapper, room } = await mountAndStart();
    const track = createRemoteAudioTrack();
    const user = { kind: 'standard', identity: 'web-1' };
    room.emit('trackSubscribed', track);
    room.emit(
      'transcriptionReceived',
      [
        { id: 'u-1', text: '最终用户文本', final: true },
        { id: 'u-2', text: '用户还在说', final: false },
      ],
      user,
    );
    room.emit(
      'transcriptionReceived',
      [{ id: 'a-1', text: '最终客服文本', final: true }],
      room.agent,
    );

    await wrapper.get('[data-testid="voice-disconnect"]').trigger('click');
    await flushPromises();
    await flushPromises();

    expect(room.localParticipant.setMicrophoneEnabled).toHaveBeenCalledWith(false);
    expect(room.localTrack.stop).toHaveBeenCalledTimes(1);
    expect(track.detach).toHaveBeenCalled();
    expect(track.element.isConnected).toBe(false);
    expect(room.off).toHaveBeenCalledTimes(7);
    expect(room.disconnect).toHaveBeenCalledTimes(1);
    expect(serviceState.createRecord).toHaveBeenCalledTimes(1);
    expect(serviceState.createRecord.mock.calls[0][0]).toMatchObject({
      customer_service_id: customerServiceId,
      room_name: 'room-current',
      status: 'completed',
      messages: [
        { role: 'user', text: '最终用户文本', sequence: 1 },
        { role: 'assistant', text: '最终客服文本', sequence: 3 },
      ],
    });

    wrapper.unmount();
    await flushPromises();
    expect(serviceState.createRecord).toHaveBeenCalledTimes(1);
  });

  it('saves an unexpected disconnect as interrupted without duplicating it', async () => {
    const { wrapper, room } = await mountAndStart();

    room.emit('disconnected');
    await flushPromises();
    await flushPromises();

    expect(serviceState.createRecord).toHaveBeenCalledTimes(1);
    expect(serviceState.createRecord.mock.calls[0][0].status).toBe('interrupted');
    expect(wrapper.text()).toContain('语音连接已中断');

    wrapper.unmount();
    await flushPromises();
    expect(serviceState.createRecord).toHaveBeenCalledTimes(1);
  });

  it('saves cancellation after token issuance during room connect as interrupted', async () => {
    const token = deferred<ReturnType<typeof joinResponse>>();
    serviceState.issueToken.mockReturnValue(token.promise);
    const wrapper = mount(LiveKitRealtimePanel, {
      props: { customerServiceId },
    });

    await wrapper.get('[data-testid="voice-connect"]').trigger('click');
    const room = livekitState.rooms.at(-1);
    room.connect.mockReturnValue(new Promise(() => undefined));
    token.resolve(joinResponse());
    await flushPromises();

    await wrapper.get('[data-testid="voice-disconnect"]').trigger('click');
    await flushPromises();

    expect(serviceState.createRecord).toHaveBeenCalledTimes(1);
    expect(serviceState.createRecord.mock.calls[0][0]).toMatchObject({
      room_name: 'room-current',
      status: 'interrupted',
    });

    wrapper.unmount();
    await flushPromises();
  });

  it('saves user cancellation while waiting for the agent as interrupted', async () => {
    const token = deferred<ReturnType<typeof joinResponse>>();
    serviceState.issueToken.mockReturnValue(token.promise);
    const wrapper = mount(LiveKitRealtimePanel, {
      props: { customerServiceId },
    });

    await wrapper.get('[data-testid="voice-connect"]').trigger('click');
    const room = livekitState.rooms.at(-1);
    room.remoteParticipants.clear();
    token.resolve(joinResponse());
    await flushPromises();

    await wrapper.get('[data-testid="voice-disconnect"]').trigger('click');
    await flushPromises();

    expect(serviceState.createRecord).toHaveBeenCalledTimes(1);
    expect(serviceState.createRecord.mock.calls[0][0].status).toBe('interrupted');

    wrapper.unmount();
    await flushPromises();
  });

  it('saves user cancellation while microphone startup is pending as interrupted', async () => {
    const token = deferred<ReturnType<typeof joinResponse>>();
    serviceState.issueToken.mockReturnValue(token.promise);
    const wrapper = mount(LiveKitRealtimePanel, {
      props: { customerServiceId },
    });

    await wrapper.get('[data-testid="voice-connect"]').trigger('click');
    const room = livekitState.rooms.at(-1);
    room.localParticipant.setMicrophoneEnabled.mockReturnValue(
      new Promise(() => undefined),
    );
    token.resolve(joinResponse());
    await flushPromises();

    await wrapper.get('[data-testid="voice-disconnect"]').trigger('click');
    await flushPromises();

    expect(serviceState.createRecord).toHaveBeenCalledTimes(1);
    expect(serviceState.createRecord.mock.calls[0][0].status).toBe('interrupted');

    wrapper.unmount();
    await flushPromises();
  });

  it('saves a microphone startup failure after token issuance as failed', async () => {
    const token = deferred<ReturnType<typeof joinResponse>>();
    serviceState.issueToken.mockReturnValue(token.promise);
    const wrapper = mount(LiveKitRealtimePanel, {
      props: { customerServiceId },
    });

    await wrapper.get('[data-testid="voice-connect"]').trigger('click');
    const room = livekitState.rooms.at(-1);
    room.localParticipant.setMicrophoneEnabled.mockRejectedValue(
      new Error('raw microphone SDK failure'),
    );
    token.resolve(joinResponse());
    await flushPromises();

    expect(serviceState.createRecord).toHaveBeenCalledTimes(1);
    expect(serviceState.createRecord.mock.calls[0][0].status).toBe('failed');
    expect(wrapper.text()).not.toContain('raw microphone SDK failure');

    wrapper.unmount();
    await flushPromises();
  });

  it('ignores late events captured from a previous room attempt', async () => {
    const first = await mountAndStart();
    const oldTranscript = first.room.listenerHistory
      .get('transcriptionReceived')[0];
    const oldTrackHandler = first.room.listenerHistory.get('trackSubscribed')[0];
    await first.wrapper.get('[data-testid="voice-disconnect"]').trigger('click');
    await flushPromises();
    await first.wrapper.get('[data-testid="voice-connect"]').trigger('click');
    await flushPromises();
    await flushPromises();
    const staleTrack = createRemoteAudioTrack();

    oldTranscript(
      [{ id: 'old', text: '不应出现的旧输出', final: true }],
      first.room.agent,
    );
    oldTrackHandler(staleTrack);
    await first.wrapper.vm.$nextTick();

    expect(first.wrapper.text()).not.toContain('不应出现的旧输出');
    expect(staleTrack.attach).not.toHaveBeenCalled();
    expect(staleTrack.detach).toHaveBeenCalled();

    first.wrapper.unmount();
    await flushPromises();
  });

  it('does not let late cleanup from an old room cancel the new room agent wait', async () => {
    vi.useFakeTimers();
    const firstToken = deferred<ReturnType<typeof joinResponse>>();
    const secondToken = deferred<ReturnType<typeof joinResponse>>();
    const firstConnect = deferred<void>();
    serviceState.issueToken
      .mockReturnValueOnce(firstToken.promise)
      .mockReturnValueOnce(secondToken.promise);
    const wrapper = mount(LiveKitRealtimePanel, {
      props: { customerServiceId },
    });

    await wrapper.get('[data-testid="voice-connect"]').trigger('click');
    const firstRoom = livekitState.rooms.at(-1);
    firstRoom.connect.mockReturnValue(firstConnect.promise);
    firstToken.resolve(joinResponse());
    await flushPromises();
    await vi.advanceTimersByTimeAsync(10_000);
    await flushPromises();
    await vi.advanceTimersByTimeAsync(1_000);
    await flushPromises();
    expect(firstRoom.disconnect).toHaveBeenCalledTimes(1);

    await wrapper.get('[data-testid="voice-connect"]').trigger('click');
    const secondRoom = livekitState.rooms.at(-1);
    secondRoom.remoteParticipants.clear();
    secondToken.resolve(joinResponse());
    await flushPromises();
    await flushPromises();
    expect(secondRoom.localParticipant.setMicrophoneEnabled).toHaveBeenCalledWith(true);

    firstConnect.resolve();
    await flushPromises();
    expect(firstRoom.disconnect).toHaveBeenCalledTimes(2);
    secondRoom.emit('participantConnected', secondRoom.agent);
    await flushPromises();

    expect(wrapper.find('[data-testid="voice-disconnect"]').exists()).toBe(true);
    expect(wrapper.find('[data-testid="voice-connect"]').exists()).toBe(false);
    expect(wrapper.get('[data-testid="agent-state"]').text()).toBe('正在聆听');

    wrapper.unmount();
    await flushPromises();
    vi.useRealTimers();
  });

  it('shows a safe error and never renders a raw SDK/provider message', async () => {
    serviceState.issueToken.mockRejectedValue(
      new Error('DashScope api_key=provider-secret connection failed'),
    );
    const wrapper = mount(LiveKitRealtimePanel, {
      props: { customerServiceId },
    });

    await wrapper.get('[data-testid="voice-connect"]').trigger('click');
    await flushPromises();
    await flushPromises();

    expect(wrapper.text()).toContain('无法获取安全连接凭据');
    expect(wrapper.text()).not.toContain('DashScope');
    expect(wrapper.text()).not.toContain('provider-secret');

    wrapper.unmount();
    await flushPromises();
  });

  it('does not let record-save failure delay cleanup or destroy the transcript', async () => {
    serviceState.createRecord.mockRejectedValue(
      new Error('raw database/provider failure'),
    );
    const { wrapper, room } = await mountAndStart();
    room.emit(
      'transcriptionReceived',
      [{ id: 'u-1', text: '请保留这句话', final: true }],
      { kind: 'standard', identity: 'web-1' },
    );

    await wrapper.get('[data-testid="voice-disconnect"]').trigger('click');
    await flushPromises();
    await flushPromises();

    expect(room.disconnect).toHaveBeenCalledTimes(1);
    expect(wrapper.find('[data-testid="voice-connect"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('请保留这句话');
    expect(wrapper.text()).toContain('通话记录保存失败，不影响本次通话');
    expect(wrapper.text()).not.toContain('raw database');

    wrapper.unmount();
    await flushPromises();
  });

  it('cleans up microphone, tracks, listeners and room when unmounted', async () => {
    const { wrapper, room } = await mountAndStart();
    const track = createRemoteAudioTrack();
    room.emit('trackSubscribed', track);

    wrapper.unmount();
    await flushPromises();
    await flushPromises();

    expect(room.localParticipant.setMicrophoneEnabled).toHaveBeenCalledWith(false);
    expect(room.localTrack.stop).toHaveBeenCalledTimes(1);
    expect(track.detach).toHaveBeenCalled();
    expect(room.off).toHaveBeenCalledTimes(7);
    expect(room.disconnect).toHaveBeenCalledTimes(1);
  });

  it('does not let an old attempt save failure write into a newer call UI', async () => {
    const firstSave = deferred<unknown>();
    serviceState.createRecord
      .mockReturnValueOnce(firstSave.promise)
      .mockResolvedValue({ id: 'record-2' });
    const { wrapper } = await mountAndStart();

    await wrapper.get('[data-testid="voice-disconnect"]').trigger('click');
    await flushPromises();
    await wrapper.get('[data-testid="voice-connect"]').trigger('click');
    await flushPromises();
    firstSave.reject(new Error('late old attempt failure'));
    await flushPromises();

    expect(wrapper.find('.voice-alert--notice').exists()).toBe(false);

    wrapper.unmount();
    await flushPromises();
  });

  it('aborts the record POST when the bounded save timeout expires', async () => {
    vi.useFakeTimers();
    serviceState.createRecord.mockReturnValue(new Promise(() => undefined));
    const { wrapper } = await mountAndStart();

    await wrapper.get('[data-testid="voice-disconnect"]').trigger('click');
    await flushPromises();
    const signal = serviceState.createRecord.mock.calls[0]?.[1] as AbortSignal | undefined;
    await vi.advanceTimersByTimeAsync(5_000);

    expect(signal).toBeInstanceOf(AbortSignal);
    expect(signal?.aborted).toBe(true);

    wrapper.unmount();
    await flushPromises();
  });

  it('uses the ready agent existing LiveKit state instead of forcing listening', async () => {
    const token = deferred<ReturnType<typeof joinResponse>>();
    serviceState.issueToken.mockReturnValue(token.promise);
    const wrapper = mount(LiveKitRealtimePanel, {
      props: { customerServiceId },
    });

    await wrapper.get('[data-testid="voice-connect"]').trigger('click');
    const room = livekitState.rooms.at(-1);
    room.agent.attributes['lk.agent.state'] = 'thinking';
    token.resolve(joinResponse());
    await flushPromises();

    expect(wrapper.get('[data-testid="agent-state"]').text()).toBe('正在思考');

    wrapper.unmount();
    await flushPromises();
  });

  it('keeps LiveKit agent state authoritative across out-of-order transcripts', async () => {
    const { wrapper, room } = await mountAndStart();

    room.emit(
      'participantAttributesChanged',
      { 'lk.agent.state': 'thinking' },
      room.agent,
    );
    room.emit(
      'transcriptionReceived',
      [{ id: 'late-a-1', text: 'late assistant transcript', final: true }],
      room.agent,
    );
    await wrapper.vm.$nextTick();
    expect(wrapper.get('[data-testid="agent-state"]').text()).toBe('正在思考');

    room.emit(
      'participantAttributesChanged',
      { 'lk.agent.state': 'listening' },
      room.agent,
    );
    room.emit(
      'transcriptionReceived',
      [{ id: 'late-a-2', text: 'even later assistant transcript', final: true }],
      room.agent,
    );
    await wrapper.vm.$nextTick();
    expect(wrapper.get('[data-testid="agent-state"]').text()).toBe('正在聆听');

    wrapper.unmount();
    await flushPromises();
  });

  it('starts recorder after mic is enabled and does not remake on remote subscribe', async () => {
    const { wrapper, room } = await mountAndStart();
    const recorder = recorderState.instances[0];
    expect(recorderState.create).toHaveBeenCalled();
    expect(recorder.start).toHaveBeenCalledWith(
      room.localTrack.mediaStreamTrack,
      null,
    );

    const track = createRemoteAudioTrack();
    room.emit('trackSubscribed', track);
    await wrapper.vm.$nextTick();

    // Remaking would wipe in-progress chunks; keep the already-started recorder.
    expect(recorder.start).toHaveBeenCalledTimes(1);
    expect(recorderState.create).toHaveBeenCalledTimes(1);

    wrapper.unmount();
    await flushPromises();
  });

  it('stops recorder, creates the call record, then uploads the recording blob', async () => {
    const callOrder: string[] = [];
    const blob = new Blob(['mixed-audio'], { type: 'audio/webm' });
    recorderState.create.mockImplementation(() => createRecorderMock(blob));
    serviceState.createRecord.mockImplementation(async (...args: unknown[]) => {
      callOrder.push('create');
      return { id: 'record-1' };
    });
    serviceState.uploadRecording.mockImplementation(async (...args: unknown[]) => {
      callOrder.push('upload');
      return { id: 'record-1', recording_status: 'ready' };
    });

    const { wrapper } = await mountAndStart();
    const recorder = recorderState.instances[0];
    recorder.stop.mockImplementation(async () => {
      callOrder.push('stop');
      return blob;
    });

    await wrapper.get('[data-testid="voice-disconnect"]').trigger('click');
    await flushPromises();
    await flushPromises();

    expect(callOrder).toEqual(['stop', 'create', 'upload']);
    expect(serviceState.uploadRecording).toHaveBeenCalledWith(
      'record-1',
      blob,
      expect.any(AbortSignal),
    );
    expect(recorder.dispose).toHaveBeenCalled();

    wrapper.unmount();
    await flushPromises();
  });

  it('keeps transcript success notice path when recording upload fails', async () => {
    serviceState.uploadRecording.mockRejectedValue(new Error('raw upload failure'));
    const { wrapper, room } = await mountAndStart();
    room.emit(
      'transcriptionReceived',
      [{ id: 'u-1', text: '文字应保留', final: true }],
      { kind: 'standard', identity: 'web-1' },
    );

    await wrapper.get('[data-testid="voice-disconnect"]').trigger('click');
    await flushPromises();
    await flushPromises();

    expect(serviceState.createRecord).toHaveBeenCalledTimes(1);
    expect(serviceState.uploadRecording).toHaveBeenCalledTimes(1);
    expect(room.disconnect).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain('文字应保留');
    expect(wrapper.text()).toContain('通话录音保存失败，文字记录已保存。');
    expect(wrapper.text()).not.toContain('raw upload failure');
    expect(wrapper.find('[data-testid="voice-connect"]').exists()).toBe(true);

    wrapper.unmount();
    await flushPromises();
  });

  it('does not block disconnect teardown when recorder.stop never resolves', async () => {
    vi.useFakeTimers();
    recorderState.create.mockImplementation(() => {
      const recorder = createRecorderMock();
      recorder.stop.mockReturnValue(new Promise(() => undefined));
      return recorder;
    });
    const { wrapper, room } = await mountAndStart();
    const recorder = recorderState.instances[0];

    await wrapper.get('[data-testid="voice-disconnect"]').trigger('click');
    await flushPromises();
    await flushPromises();

    expect(room.disconnect).toHaveBeenCalledTimes(1);
    expect(wrapper.find('[data-testid="voice-connect"]').exists()).toBe(true);
    expect(serviceState.createRecord).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1_000);
    await flushPromises();
    await flushPromises();

    expect(serviceState.createRecord).toHaveBeenCalledTimes(1);
    expect(recorder.dispose).toHaveBeenCalled();

    wrapper.unmount();
    await flushPromises();
    vi.useRealTimers();
  });

  it('disposes the recorder during cleanup without blocking teardown', async () => {
    const { wrapper, room } = await mountAndStart();
    const recorder = recorderState.instances[0];

    wrapper.unmount();
    await flushPromises();
    await flushPromises();

    expect(recorder.dispose).toHaveBeenCalled();
    expect(room.disconnect).toHaveBeenCalledTimes(1);
  });

  it('still uploads blob when cleanup runs while recorder.stop is pending (async onstop)', async () => {
    const blob = new Blob(['async-onstop-audio'], { type: 'audio/webm' });
    const stopDeferred = deferred<Blob | null>();
    recorderState.create.mockImplementation(() => {
      const recorder = createRecorderMock(blob);
      recorder.stop.mockReturnValue(stopDeferred.promise);
      return recorder;
    });

    const { wrapper, room } = await mountAndStart();
    const recorder = recorderState.instances[0];

    await wrapper.get('[data-testid="voice-disconnect"]').trigger('click');
    await flushPromises();
    await flushPromises();

    // Room teardown must proceed; mid-stop recorder must not be force-disposed yet.
    expect(room.disconnect).toHaveBeenCalledTimes(1);
    expect(wrapper.find('[data-testid="voice-connect"]').exists()).toBe(true);
    expect(recorder.dispose).not.toHaveBeenCalled();
    expect(serviceState.uploadRecording).not.toHaveBeenCalled();

    stopDeferred.resolve(blob);
    await flushPromises();
    await flushPromises();

    expect(serviceState.uploadRecording).toHaveBeenCalledWith(
      'record-1',
      blob,
      expect.any(AbortSignal),
    );
    expect(recorder.dispose).toHaveBeenCalled();

    wrapper.unmount();
    await flushPromises();
  });
});
