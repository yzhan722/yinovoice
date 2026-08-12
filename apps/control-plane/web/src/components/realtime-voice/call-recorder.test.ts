import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { createCallRecorder } from './call-recorder';

const mediaRecorderState = vi.hoisted(() => ({
  instances: [] as FakeMediaRecorder[],
  supported: true,
}));

const audioContextState = vi.hoisted(() => ({
  instances: [] as FakeAudioContext[],
  remoteMixFails: false,
}));

class FakeMediaStream {
  constructor(public tracks: MediaStreamTrack[]) {}

  getAudioTracks() {
    return this.tracks.filter((track) => track.kind === 'audio');
  }
}

class FakeMediaRecorder {
  state: RecordingState = 'inactive';

  mimeType = 'audio/webm';

  ondataavailable: ((event: BlobEvent) => void) | null = null;

  onstop: (() => void) | null = null;

  start = vi.fn(() => {
    this.state = 'recording';
  });

  stop = vi.fn(() => {
    this.state = 'inactive';
    this.ondataavailable?.({
      data: new Blob(['recorded-audio'], { type: this.mimeType }),
    } as BlobEvent);
    this.onstop?.();
  });

  constructor(public stream: MediaStream) {
    mediaRecorderState.instances.push(this);
  }
}

class FakeAudioContext {
  closed = false;

  createMediaStreamDestination = vi.fn(() => {
    const track = createMockTrack('mixed-track');
    return { stream: new FakeMediaStream([track]) };
  });

  createMediaStreamSource = vi.fn((stream: FakeMediaStream) => {
    if (
      audioContextState.remoteMixFails
      && stream.tracks.some((track) => track.id === 'remote')
    ) {
      throw new Error('remote mix failed');
    }

    return { connect: vi.fn() };
  });

  close = vi.fn(async () => {
    this.closed = true;
  });

  constructor() {
    audioContextState.instances.push(this);
  }
}

function createMockTrack(id: string): MediaStreamTrack {
  return {
    id,
    kind: 'audio',
    stop: vi.fn(),
    enabled: true,
  } as unknown as MediaStreamTrack;
}

function installBrowserMocks() {
  vi.stubGlobal('MediaStream', FakeMediaStream);

  vi.stubGlobal(
    'MediaRecorder',
    class extends FakeMediaRecorder {
      static isTypeSupported() {
        return mediaRecorderState.supported;
      }
    },
  );

  vi.stubGlobal('AudioContext', FakeAudioContext);
}

describe('createCallRecorder', () => {
  beforeEach(() => {
    mediaRecorderState.instances = [];
    mediaRecorderState.supported = true;
    audioContextState.instances = [];
    audioContextState.remoteMixFails = false;
    installBrowserMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('mixes local and remote tracks via AudioContext when both are provided', () => {
    const recorder = createCallRecorder();
    const local = createMockTrack('local');
    const remote = createMockTrack('remote');

    recorder.start(local, remote);

    const context = audioContextState.instances[0];
    expect(context.createMediaStreamSource).toHaveBeenCalledTimes(2);
    expect(context.createMediaStreamDestination).toHaveBeenCalledTimes(1);
    expect(mediaRecorderState.instances).toHaveLength(1);
    expect(mediaRecorderState.instances[0].start).toHaveBeenCalled();
  });

  it('records local only when remote track is missing', () => {
    const recorder = createCallRecorder();
    const local = createMockTrack('local');

    recorder.start(local);

    const context = audioContextState.instances[0];
    expect(context.createMediaStreamSource).toHaveBeenCalledTimes(1);
    expect(mediaRecorderState.instances).toHaveLength(1);
  });

  it('records local only when remote mix fails', () => {
    audioContextState.remoteMixFails = true;
    const recorder = createCallRecorder();
    const local = createMockTrack('local');
    const remote = createMockTrack('remote');

    recorder.start(local, remote);

    const context = audioContextState.instances[0];
    expect(context.createMediaStreamSource).toHaveBeenCalledTimes(2);
    expect(mediaRecorderState.instances).toHaveLength(1);
    expect(mediaRecorderState.instances[0].start).toHaveBeenCalled();
  });

  it('returns a blob when stop is called after recording', async () => {
    const recorder = createCallRecorder();
    recorder.start(createMockTrack('local'));

    const blob = await recorder.stop();

    expect(blob).toBeInstanceOf(Blob);
    expect(blob?.size).toBeGreaterThan(0);
    expect(blob?.type).toBe('audio/webm');
  });

  it('returns null from stop when recording never started', async () => {
    const recorder = createCallRecorder();

    await expect(recorder.stop()).resolves.toBeNull();
  });

  it('no-ops start and returns null from stop when MediaRecorder is unsupported', async () => {
    vi.unstubAllGlobals();
    vi.stubGlobal('MediaStream', FakeMediaStream);
    vi.stubGlobal('AudioContext', FakeAudioContext);
    vi.stubGlobal('MediaRecorder', undefined);

    const recorder = createCallRecorder();
    recorder.start(createMockTrack('local'));

    expect(mediaRecorderState.instances).toHaveLength(0);
    await expect(recorder.stop()).resolves.toBeNull();
  });

  it('dispose stops mixed destination track and closes AudioContext without stopping input tracks', () => {
    const recorder = createCallRecorder();
    const local = createMockTrack('local');
    const remote = createMockTrack('remote');

    recorder.start(local, remote);

    const context = audioContextState.instances[0];
    const destination = context.createMediaStreamDestination.mock.results[0].value;
    const mixedTrack = destination.stream.getAudioTracks()[0];

    recorder.dispose();

    expect(mixedTrack.stop).toHaveBeenCalled();
    expect(local.stop).not.toHaveBeenCalled();
    expect(remote.stop).not.toHaveBeenCalled();
    expect(context.close).toHaveBeenCalled();
  });

  it('still yields a blob when MediaRecorder.onstop fires asynchronously', async () => {
    class AsyncOnstopMediaRecorder {
      state: RecordingState = 'inactive';

      mimeType = 'audio/webm';

      ondataavailable: ((event: BlobEvent) => void) | null = null;

      onstop: (() => void) | null = null;

      start = vi.fn(() => {
        this.state = 'recording';
      });

      stop = vi.fn(() => {
        this.state = 'inactive';
        this.ondataavailable?.({
          data: new Blob(['async-recorded-audio'], { type: this.mimeType }),
        } as BlobEvent);
        queueMicrotask(() => {
          this.onstop?.();
        });
      });

      constructor(public stream: MediaStream) {
        mediaRecorderState.instances.push(this as unknown as FakeMediaRecorder);
      }

      static isTypeSupported() {
        return true;
      }
    }

    vi.stubGlobal('MediaRecorder', AsyncOnstopMediaRecorder);

    const recorder = createCallRecorder();
    recorder.start(createMockTrack('local'));

    const blobPromise = recorder.stop();
    // Simulate panel cleanup racing stop: must NOT dispose mid-stop or chunks clear.
    const blob = await blobPromise;

    expect(blob).toBeInstanceOf(Blob);
    expect(blob?.size).toBeGreaterThan(0);
  });
});
