<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue';
import {
  MediaDeviceFailure,
  ParticipantKind,
  Room,
  RoomEvent,
  Track,
  type Participant,
  type RemoteParticipant,
  type RemoteTrack,
  type TranscriptionSegment,
} from 'livekit-client';

import { RealtimeVoiceService } from '@/api/platform/RealtimeVoiceService';

import { createCallRecorder, type CallRecorder } from './call-recorder';
import {
  reduceTranscriptionSegments,
  sealStalePartialSegments,
  toFinalTranscriptMessages,
  type LiveTranscriptSegment,
  type TranscriptRole,
} from './live-transcript';

const recordingEnabled = import.meta.env.VITE_CALL_RECORDING_ENABLED !== 'false';

type ConnectionState =
  | 'idle'
  | 'connecting'
  | 'waiting-agent'
  | 'connected'
  | 'disconnecting'
  | 'error';
type MicrophoneState = 'not-requested' | 'requesting' | 'enabled' | 'disabled' | 'denied';
type AgentState = 'preparing' | 'listening' | 'thinking' | 'speaking';
type ConnectionPhase = 'token' | 'room' | 'microphone' | 'agent';
type CallStatus = 'completed' | 'interrupted' | 'failed';
type ParticipantWithKind = Pick<Participant, 'kind'> & {
  attributes?: Record<string, string>;
};
type RoomListeners = {
  trackSubscribed: (track: RemoteTrack) => void;
  trackUnsubscribed: (track: RemoteTrack) => void;
  disconnected: () => void;
  participantConnected: (participant: RemoteParticipant) => void;
  participantDisconnected: (participant: RemoteParticipant) => void;
  transcriptionReceived: (
    segments: TranscriptionSegment[],
    participant?: Participant,
  ) => void;
  participantAttributesChanged: (
    changedAttributes: Record<string, string>,
    participant: Participant,
  ) => void;
};
type ActiveSession = {
  attempt: number;
  roomName: string;
  startedAt: Date;
  agentReady: boolean;
  saved: boolean;
};
type AgentReadyWaiter = {
  cancel: () => void;
  ready: (participant: RemoteParticipant) => void;
};

const AGENT_READY_TIMEOUT_MS = 20_000;
const PHASE_TIMEOUT_MS = 10_000;
// livekit-client 2.x may wait for LocalTrackSubscribed after publish; older
// LiveKit servers (1.8.x) often never send it, so mic enable can take 15s+.
const MIC_PHASE_TIMEOUT_MS = 30_000;
const CLEANUP_TIMEOUT_MS = 1_000;
const SAVE_TIMEOUT_MS = 5_000;
const PARTIAL_TRANSCRIPT_STALE_MS = 4_000;
const PARTIAL_TRANSCRIPT_POLL_MS = 1_000;

class AttemptCancelledError extends Error {}
class AgentReadyTimeoutError extends Error {}
class PhaseTimeoutError extends Error {}

const props = defineProps<{
  customerServiceId: string;
}>();

const service = new RealtimeVoiceService();
const audioContainer = ref<HTMLElement | null>(null);
const connectionState = ref<ConnectionState>('idle');
const microphoneState = ref<MicrophoneState>('not-requested');
const agentState = ref<AgentState>('preparing');
const transcript = ref<LiveTranscriptSegment[]>([]);
const errorMessage = ref('');
const saveNotice = ref('');
const remoteAudioTracks = new Map<RemoteTrack, Room>();
const cleanupPromises = new WeakMap<Room, Promise<void>>();
const tearingDownRooms = new WeakSet<Room>();
const roomListeners = new WeakMap<Room, RoomListeners>();
const agentReadyWaiters = new WeakMap<Room, AgentReadyWaiter>();
let disposed = false;
let attemptGeneration = 0;
let activeRoom: Room | null = null;
let activeAttemptController: AbortController | null = null;
const partialTranscriptTimer = window.setInterval(() => {
  if (disposed || connectionState.value !== 'connected') return;
  transcript.value = sealStalePartialSegments(
    transcript.value,
    PARTIAL_TRANSCRIPT_STALE_MS,
  );
}, PARTIAL_TRANSCRIPT_POLL_MS);
let activeAgentParticipant: RemoteParticipant | null = null;
let activeAgentAttempt: number | null = null;
let authoritativeAgentStateAttempt: number | null = null;
let pendingAgentParticipant: RemoteParticipant | null = null;
let activeSession: ActiveSession | null = null;
let callRecorder: CallRecorder | null = null;
let stoppingRecorder: CallRecorder | null = null;
let recorderStopPromise: Promise<Blob | null> | null = null;

const connectionLabel = computed(() => {
  switch (connectionState.value) {
    case 'connecting':
      return '正在建立安全连接…';
    case 'waiting-agent':
      return '正在等待 AI 客服就绪…';
    case 'connected':
      return '实时语音已连接';
    case 'disconnecting':
      return '正在结束通话…';
    case 'error':
      return '语音连接异常';
    default:
      return '尚未开始通话';
  }
});

const microphoneLabel = computed(() => {
  switch (microphoneState.value) {
    case 'requesting':
      return '正在请求麦克风权限';
    case 'enabled':
      return '麦克风持续传输中';
    case 'disabled':
      return '麦克风已关闭';
    case 'denied':
      return '麦克风权限不可用';
    default:
      return '尚未请求麦克风权限';
  }
});

const agentLabel = computed(() => {
  switch (agentState.value) {
    case 'listening':
      return '正在聆听';
    case 'thinking':
      return '正在思考';
    case 'speaking':
      return '正在回答';
    default:
      return '准备中';
  }
});

const isAgentParticipant = (participant?: ParticipantWithKind | null) =>
  participant?.kind === ParticipantKind.AGENT;

const detachRemoteAudio = (track: RemoteTrack) => {
  for (const element of track.detach()) element.remove();
};

const findLocalMediaStreamTrack = (room: Room): MediaStreamTrack | null => {
  for (const publication of room.localParticipant.trackPublications.values()) {
    const mediaTrack = publication.track?.mediaStreamTrack;
    if (mediaTrack) return mediaTrack;
  }
  return null;
};

const findRemoteMediaStreamTrack = (room: Room): MediaStreamTrack | null => {
  for (const [track, trackRoom] of remoteAudioTracks) {
    if (trackRoom !== room) continue;
    const mediaTrack = track.mediaStreamTrack;
    if (mediaTrack) return mediaTrack;
  }
  return null;
};

const ensureCallRecorder = (): CallRecorder | null => {
  if (!recordingEnabled) return null;
  if (!callRecorder) callRecorder = createCallRecorder();
  return callRecorder;
};

const startOrUpdateRecorder = (room: Room, attempt: number) => {
  if (
    !recordingEnabled
    || disposed
    || tearingDownRooms.has(room)
    || attempt !== attemptGeneration
    || room !== activeRoom
    || recorderStopPromise
  ) return;
  // Already recording — do not remake on remote subscribe (would wipe chunks).
  if (callRecorder) return;
  const localTrack = findLocalMediaStreamTrack(room);
  if (!localTrack) return;
  const recorder = ensureCallRecorder();
  if (!recorder) return;
  try {
    recorder.start(localTrack, findRemoteMediaStreamTrack(room));
  } catch {
    // Recording is best-effort and must never interrupt the live call.
  }
};

const beginRecorderStop = (): Promise<Blob | null> => {
  if (recorderStopPromise) return recorderStopPromise;
  const recorder = callRecorder;
  callRecorder = null;
  if (!recorder) {
    recorderStopPromise = Promise.resolve(null);
    return recorderStopPromise;
  }
  stoppingRecorder = recorder;
  recorderStopPromise = (async () => {
    let timeoutId: number | undefined;
    try {
      const stopPromise = recorder.stop().catch(() => null);
      const timeoutPromise = new Promise<null>((resolve) => {
        timeoutId = window.setTimeout(() => resolve(null), CLEANUP_TIMEOUT_MS);
      });
      return await Promise.race([stopPromise, timeoutPromise]);
    } catch {
      return null;
    } finally {
      if (timeoutId !== undefined) window.clearTimeout(timeoutId);
      try {
        recorder.dispose();
      } catch {
        // Recording cleanup is best-effort.
      }
      if (stoppingRecorder === recorder) stoppingRecorder = null;
    }
  })();
  return recorderStopPromise;
};

const disposeCallRecorder = () => {
  // Only force-dispose the idle recorder. A mid-stop instance is owned by
  // beginRecorderStop's finally (timeout still force-disposes after timeout).
  const recorder = callRecorder;
  callRecorder = null;
  if (!recorder) return;
  try {
    recorder.dispose();
  } catch {
    // Recording cleanup is best-effort.
  }
};

const handleTrackSubscribed = (track: RemoteTrack, room: Room, attempt: number) => {
  if (track.kind !== Track.Kind.Audio) return;
  if (
    disposed
    || tearingDownRooms.has(room)
    || attempt !== attemptGeneration
    || room !== activeRoom
  ) {
    detachRemoteAudio(track);
    return;
  }
  const element = track.attach();
  element.dataset.yinoRemoteAudio = 'true';
  if (!audioContainer.value) {
    detachRemoteAudio(track);
    return;
  }
  remoteAudioTracks.set(track, room);
  audioContainer.value.appendChild(element);
  startOrUpdateRecorder(room, attempt);
};

const handleTrackUnsubscribed = (track: RemoteTrack, room: Room) => {
  detachRemoteAudio(track);
  remoteAudioTracks.delete(track);
  if (activeRoom !== room) return;
};

const handleTranscriptionReceived = (
  segments: TranscriptionSegment[],
  participant: Participant | undefined,
  room: Room,
  attempt: number,
) => {
  if (!isAttemptCurrent(attempt, room)) return;
  const role: TranscriptRole = isAgentParticipant(participant) ? 'assistant' : 'user';
  for (const segment of segments) {
    transcript.value = reduceTranscriptionSegments(transcript.value, {
      id: segment.id,
      role,
      text: segment.text,
      final: segment.final,
    });
  }
  if (authoritativeAgentStateAttempt !== attempt) {
    if (role === 'user') agentState.value = 'listening';
    else if (segments.some((segment) => segment.text)) agentState.value = 'speaking';
  }
};

const mapAgentState = (state: string | undefined): AgentState | null => {
  switch (state) {
    case 'listening':
      return 'listening';
    case 'thinking':
      return 'thinking';
    case 'speaking':
      return 'speaking';
    case 'initializing':
    case 'connecting':
      return 'preparing';
    default:
      return null;
  }
};

const handleParticipantAttributesChanged = (
  changedAttributes: Record<string, string>,
  participant: Participant,
  room: Room,
  attempt: number,
) => {
  if (!isAttemptCurrent(attempt, room) || !isAgentParticipant(participant)) return;
  const nextState = mapAgentState(changedAttributes['lk.agent.state']);
  if (nextState) {
    authoritativeAgentStateAttempt = attempt;
    agentState.value = nextState;
  }
};

const handleParticipantConnected = (
  participant: RemoteParticipant,
  room: Room,
  attempt: number,
) => {
  if (
    attempt === attemptGeneration
    && room === activeRoom
    && isAgentParticipant(participant)
  ) agentReadyWaiters.get(room)?.ready(participant);
};

const findReadyAgentParticipant = (room: Room) =>
  Array.from(room.remoteParticipants.values()).find(isAgentParticipant);

const invalidateActiveAttempt = (attempt?: number) => {
  if (attempt !== undefined && attempt !== attemptGeneration) return false;
  attemptGeneration += 1;
  activeAttemptController?.abort();
  activeAttemptController = null;
  if (activeRoom) agentReadyWaiters.get(activeRoom)?.cancel();
  activeAgentParticipant = null;
  activeAgentAttempt = null;
  authoritativeAgentStateAttempt = null;
  pendingAgentParticipant = null;
  return true;
};

const isAttemptCurrent = (attempt: number, room: Room) =>
  !disposed
  && attemptGeneration === attempt
  && activeRoom === room
  && connectionState.value !== 'disconnecting';

const isAttemptActive = (
  attempt: number,
  room: Room,
  controller: AbortController,
) => isAttemptCurrent(attempt, room) && !controller.signal.aborted;

const runBoundedSave = <T>(
  operation: Promise<T>,
  controller: AbortController,
): Promise<T> => (
  new Promise<T>((resolve, reject) => {
    let settled = false;
    const finish = (callback: () => void) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timeoutId);
      callback();
    };
    const timeoutId = window.setTimeout(() => {
      controller.abort();
      finish(() => reject(new Error('save timeout')));
    }, SAVE_TIMEOUT_MS);
    operation.then(
      (value) => finish(() => resolve(value)),
      () => finish(() => reject(new Error('save failed'))),
    );
  })
);

const persistSession = (attempt: number, status: CallStatus) => {
  const session = activeSession;
  if (!session || session.attempt !== attempt || session.saved) return;
  session.saved = true;
  const endedAt = new Date();
  const durationSec = Math.min(
    86_400,
    Math.max(0, Math.round((endedAt.getTime() - session.startedAt.getTime()) / 1_000)),
  );
  const request = {
    customer_service_id: props.customerServiceId,
    room_name: session.roomName,
    status,
    started_at: session.startedAt.toISOString(),
    ended_at: endedAt.toISOString(),
    duration_sec: durationSec,
    messages: toFinalTranscriptMessages(transcript.value),
  };
  const blobPromise = beginRecorderStop();
  void (async () => {
    let blob: Blob | null = null;
    try {
      blob = await blobPromise;
    } catch {
      blob = null;
    }
    const saveController = new AbortController();
    try {
      const record = await runBoundedSave(
        service.createDemoCallRecord(request, saveController.signal),
        saveController,
      );
      if (!record?.id || !blob || blob.size <= 0) return;
      const uploadController = new AbortController();
      try {
        await runBoundedSave(
          service.uploadCallRecording(record.id, blob, uploadController.signal),
          uploadController,
        );
      } catch {
        if (activeSession !== session) return;
        if (!disposed) saveNotice.value = '通话录音保存失败，文字记录已保存。';
      }
    } catch {
      if (activeSession !== session) return;
      if (!disposed) saveNotice.value = '通话记录保存失败，不影响本次通话。';
    }
  })();
};

const finishSessionWithError = (
  room: Room,
  attempt: number,
  message: string,
  disconnectRoom = true,
) => {
  if (!isAttemptCurrent(attempt, room)) return;
  persistSession(attempt, 'interrupted');
  void beginRecorderStop();
  if (!invalidateActiveAttempt(attempt)) return;
  const failureGeneration = attemptGeneration;
  connectionState.value = 'disconnecting';
  void cleanupRoom(room, disconnectRoom).then(() => {
    if (disposed || attemptGeneration !== failureGeneration) return;
    microphoneState.value = 'disabled';
    agentState.value = 'preparing';
    connectionState.value = 'error';
    errorMessage.value = message;
  });
};

const handleDisconnected = (room: Room, attempt: number) => {
  if (
    disposed
    || tearingDownRooms.has(room)
    || !isAttemptCurrent(attempt, room)
    || !['connecting', 'waiting-agent', 'connected'].includes(connectionState.value)
  ) return;
  finishSessionWithError(
    room,
    attempt,
    '语音连接已中断，请确认本地语音服务可用后重新连接。',
    false,
  );
};

const handleParticipantDisconnected = (
  participant: RemoteParticipant,
  room: Room,
  attempt: number,
) => {
  if (!isAttemptCurrent(attempt, room) || !isAgentParticipant(participant)) return;
  const isActiveAgent = connectionState.value === 'connected'
    && activeAgentAttempt === attempt
    && activeAgentParticipant === participant;
  const isPendingAgent = connectionState.value === 'waiting-agent'
    && pendingAgentParticipant === participant;
  if (!isActiveAgent && !isPendingAgent) return;
  finishSessionWithError(
    room,
    attempt,
    'AI 语音客服已离开当前会话，请重新连接。',
  );
};

const registerRoomListeners = (room: Room, attempt: number) => {
  if (roomListeners.has(room)) return;
  const listeners: RoomListeners = {
    trackSubscribed: (track) => handleTrackSubscribed(track, room, attempt),
    trackUnsubscribed: (track) => handleTrackUnsubscribed(track, room),
    disconnected: () => handleDisconnected(room, attempt),
    participantConnected: (participant) => (
      handleParticipantConnected(participant, room, attempt)
    ),
    participantDisconnected: (participant) => (
      handleParticipantDisconnected(participant, room, attempt)
    ),
    transcriptionReceived: (segments, participant) => (
      handleTranscriptionReceived(segments, participant, room, attempt)
    ),
    participantAttributesChanged: (attributes, participant) => (
      handleParticipantAttributesChanged(attributes, participant, room, attempt)
    ),
  };
  room.on(RoomEvent.TrackSubscribed, listeners.trackSubscribed);
  room.on(RoomEvent.TrackUnsubscribed, listeners.trackUnsubscribed);
  room.on(RoomEvent.Disconnected, listeners.disconnected);
  room.on(RoomEvent.ParticipantConnected, listeners.participantConnected);
  room.on(RoomEvent.ParticipantDisconnected, listeners.participantDisconnected);
  room.on(RoomEvent.TranscriptionReceived, listeners.transcriptionReceived);
  room.on(
    RoomEvent.ParticipantAttributesChanged,
    listeners.participantAttributesChanged,
  );
  roomListeners.set(room, listeners);
};

const unregisterRoomListeners = (room: Room) => {
  const listeners = roomListeners.get(room);
  if (!listeners) return;
  room.off(RoomEvent.TrackSubscribed, listeners.trackSubscribed);
  room.off(RoomEvent.TrackUnsubscribed, listeners.trackUnsubscribed);
  room.off(RoomEvent.Disconnected, listeners.disconnected);
  room.off(RoomEvent.ParticipantConnected, listeners.participantConnected);
  room.off(RoomEvent.ParticipantDisconnected, listeners.participantDisconnected);
  room.off(RoomEvent.TranscriptionReceived, listeners.transcriptionReceived);
  room.off(
    RoomEvent.ParticipantAttributesChanged,
    listeners.participantAttributesChanged,
  );
  roomListeners.delete(room);
};

const settleForCleanup = (operation: PromiseLike<unknown> | unknown): Promise<void> => (
  new Promise((resolve) => {
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timeoutId);
      resolve();
    };
    const timeoutId = window.setTimeout(finish, CLEANUP_TIMEOUT_MS);
    Promise.resolve(operation).then(finish, finish);
  })
);

function cleanupRoom(room: Room, disconnectRoom = true): Promise<void> {
  const existingCleanup = cleanupPromises.get(room);
  if (existingCleanup) return existingCleanup;
  tearingDownRooms.add(room);
  agentReadyWaiters.get(room)?.cancel();
  unregisterRoomListeners(room);

  let finishCleanup!: () => void;
  const activeCleanup = new Promise<void>((resolve) => {
    finishCleanup = resolve;
  });
  cleanupPromises.set(room, activeCleanup);

  void (async () => {
    if (room === activeRoom || !activeRoom) disposeCallRecorder();
    const localTracks = Array.from(room.localParticipant.trackPublications.values())
      .flatMap((publication) => (publication.track ? [publication.track] : []));
    let microphoneDisabled: Promise<unknown>;
    try {
      microphoneDisabled = Promise.resolve(
        room.localParticipant.setMicrophoneEnabled(false),
      );
    } catch {
      microphoneDisabled = Promise.resolve();
    }
    for (const track of localTracks) track.stop();
    for (const [track, trackRoom] of remoteAudioTracks) {
      if (trackRoom !== room) continue;
      detachRemoteAudio(track);
      remoteAudioTracks.delete(track);
    }
    await settleForCleanup(microphoneDisabled);
    if (disconnectRoom) {
      try {
        await settleForCleanup(room.disconnect());
      } catch {
        // Media is already released; remote disconnect is best effort.
      }
    }
  })().finally(() => {
    cleanupPromises.delete(room);
    tearingDownRooms.delete(room);
    if (activeRoom === room) activeRoom = null;
    finishCleanup();
  });
  return activeCleanup;
}

const callLateResolutionCleanup = <T>(
  cleanup: ((value: T) => void | Promise<void>) | undefined,
  value: T,
) => {
  if (!cleanup) return;
  try {
    void Promise.resolve(cleanup(value)).catch(() => undefined);
  } catch {
    // A cancelled attempt remains isolated from late SDK resolution.
  }
};

const runBoundedPhase = <T>(
  operation: () => T | PromiseLike<T>,
  attempt: number,
  room: Room,
  controller: AbortController,
  onLateResolve?: (value: T) => void | Promise<void>,
  timeoutMs: number = PHASE_TIMEOUT_MS,
): Promise<T> => new Promise<T>((resolve, reject) => {
  let settled = false;
  const finish = (callback: () => void) => {
    if (settled) return;
    settled = true;
    window.clearTimeout(timeoutId);
    controller.signal.removeEventListener('abort', handleAbort);
    callback();
  };
  const handleAbort = () => finish(() => reject(new AttemptCancelledError()));
  const timeoutId = window.setTimeout(
    () => finish(() => {
      controller.abort();
      reject(new PhaseTimeoutError());
    }),
    timeoutMs,
  );
  let operationPromise: Promise<T>;
  try {
    operationPromise = Promise.resolve(operation());
  } catch (error) {
    operationPromise = Promise.reject(error);
  }
  operationPromise.then(
    (value) => {
      if (settled) {
        callLateResolutionCleanup(onLateResolve, value);
        return;
      }
      if (!isAttemptActive(attempt, room, controller)) {
        finish(() => reject(new AttemptCancelledError()));
        callLateResolutionCleanup(onLateResolve, value);
        return;
      }
      finish(() => resolve(value));
    },
    (error: unknown) => {
      if (!settled) finish(() => reject(error));
    },
  );
  if (controller.signal.aborted) handleAbort();
  else controller.signal.addEventListener('abort', handleAbort, { once: true });
});

const releaseLateMicrophone = async (room: Room) => {
  for (const publication of room.localParticipant.trackPublications.values()) {
    publication.track?.stop();
  }
  try {
    await settleForCleanup(room.localParticipant.setMicrophoneEnabled(false));
  } catch {
    // The cancelled attempt stays closed if late media cleanup fails.
  }
};

const waitForAgentReady = (
  room: Room,
  attempt: number,
  controller: AbortController,
): Promise<RemoteParticipant> => {
  const existingAgent = findReadyAgentParticipant(room);
  if (existingAgent) {
    pendingAgentParticipant = existingAgent;
    return Promise.resolve(existingAgent);
  }
  return new Promise<RemoteParticipant>((resolve, reject) => {
    let settled = false;
    let waiter!: AgentReadyWaiter;
    const finish = (callback: () => void) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timeoutId);
      controller.signal.removeEventListener('abort', cancel);
      if (agentReadyWaiters.get(room) === waiter) agentReadyWaiters.delete(room);
      callback();
    };
    const cancel = () => finish(() => {
      pendingAgentParticipant = null;
      reject(new AttemptCancelledError());
    });
    const ready = (participant: RemoteParticipant) => {
      pendingAgentParticipant = participant;
      finish(() => {
        if (isAttemptActive(attempt, room, controller)) resolve(participant);
        else {
          pendingAgentParticipant = null;
          reject(new AttemptCancelledError());
        }
      });
    };
    const timeoutId = window.setTimeout(
      () => finish(() => {
        pendingAgentParticipant = null;
        reject(new AgentReadyTimeoutError());
      }),
      AGENT_READY_TIMEOUT_MS,
    );
    waiter = { cancel, ready };
    agentReadyWaiters.set(room, waiter);
    if (controller.signal.aborted) cancel();
    else controller.signal.addEventListener('abort', cancel, { once: true });
    const racedAgent = findReadyAgentParticipant(room);
    if (racedAgent) ready(racedAgent);
  });
};

const runConnectAttempt = async (
  attempt: number,
  room: Room,
  controller: AbortController,
) => {
  let phase: ConnectionPhase = 'token';
  registerRoomListeners(room, attempt);
  try {
    const join = await runBoundedPhase(
      () => service.issueLiveKitToken(
        props.customerServiceId,
        'web-demo-' + attempt + '-' + Date.now(),
        controller.signal,
      ),
      attempt,
      room,
      controller,
    );
    if (!isAttemptActive(attempt, room, controller)) {
      await cleanupRoom(room);
      return;
    }
    activeSession = {
      attempt,
      roomName: join.room_name,
      startedAt: new Date(),
      agentReady: false,
      saved: false,
    };
    phase = 'room';
    await runBoundedPhase(
      () => room.connect(join.server_url, join.token),
      attempt,
      room,
      controller,
      () => cleanupRoom(room),
    );
    if (!isAttemptActive(attempt, room, controller)) {
      await cleanupRoom(room);
      return;
    }
    phase = 'microphone';
    microphoneState.value = 'requesting';
    await runBoundedPhase(
      () => room.localParticipant.setMicrophoneEnabled(true),
      attempt,
      room,
      controller,
      () => releaseLateMicrophone(room),
      MIC_PHASE_TIMEOUT_MS,
    );
    if (!isAttemptActive(attempt, room, controller)) {
      await cleanupRoom(room);
      return;
    }
    microphoneState.value = 'enabled';
    startOrUpdateRecorder(room, attempt);
    connectionState.value = 'waiting-agent';
    phase = 'agent';
    const agentParticipant = await waitForAgentReady(room, attempt, controller);
    if (!isAttemptActive(attempt, room, controller)) {
      await cleanupRoom(room);
      return;
    }
    pendingAgentParticipant = null;
    activeAgentParticipant = agentParticipant;
    activeAgentAttempt = attempt;
    if (activeSession?.attempt === attempt) activeSession.agentReady = true;
    const readyState = mapAgentState(
      agentParticipant.attributes?.['lk.agent.state'],
    );
    if (readyState) {
      authoritativeAgentStateAttempt = attempt;
      agentState.value = readyState;
    } else if (authoritativeAgentStateAttempt !== attempt) {
      agentState.value = 'listening';
    }
    connectionState.value = 'connected';
  } catch (error) {
    if (error instanceof AttemptCancelledError || !isAttemptCurrent(attempt, room)) {
      void beginRecorderStop();
      await cleanupRoom(room);
      return;
    }
    if (activeSession?.attempt === attempt) persistSession(attempt, 'failed');
    const errorGeneration = attemptGeneration;
    void beginRecorderStop();
    await cleanupRoom(room);
    if (
      disposed
      || attemptGeneration !== errorGeneration
      || connectionState.value === 'disconnecting'
    ) return;
    connectionState.value = 'error';
    agentState.value = 'preparing';
    if (phase === 'token') {
      microphoneState.value = 'disabled';
      errorMessage.value = '无法获取安全连接凭据，请确认 Platform API 已启动后重试。';
    } else if (phase === 'microphone') {
      const failure = MediaDeviceFailure.getFailure(error);
      if (failure === MediaDeviceFailure.PermissionDenied) {
        microphoneState.value = 'denied';
        errorMessage.value = '无法使用麦克风，请在浏览器地址栏允许麦克风访问后重试。';
      } else if (error instanceof PhaseTimeoutError) {
        microphoneState.value = 'disabled';
        errorMessage.value = '麦克风发布超时（多为 LiveKit 版本协商较慢），请关闭其他占麦标签后重试。';
      } else {
        microphoneState.value = 'disabled';
        errorMessage.value = '无法启动麦克风，请确认设备已连接且未被其他应用占用后重试。';
      }
    } else if (phase === 'agent' && error instanceof AgentReadyTimeoutError) {
      microphoneState.value = 'disabled';
      errorMessage.value = 'AI 语音客服暂未就绪，请确认 Worker 已启动后重试。';
    } else {
      microphoneState.value = 'disabled';
      errorMessage.value = '无法连接语音客服，请确认本地语音服务已启动后重试。';
    }
  }
};

const connect = async () => {
  if (!['idle', 'error'].includes(connectionState.value)) return;
  const attempt = ++attemptGeneration;
  // dynacast off: older/self-hosted LiveKit + reverse-proxy paths negotiate more reliably.
  const room = new Room({ adaptiveStream: true, dynacast: false });
  const controller = new AbortController();
  activeRoom = room;
  activeAttemptController = controller;
  activeSession = null;
  callRecorder = null;
  stoppingRecorder = null;
  recorderStopPromise = null;
  transcript.value = [];
  connectionState.value = 'connecting';
  microphoneState.value = 'not-requested';
  agentState.value = 'preparing';
  errorMessage.value = '';
  saveNotice.value = '';
  try {
    await runConnectAttempt(attempt, room, controller);
  } finally {
    if (activeAttemptController === controller) activeAttemptController = null;
  }
};

const disconnect = async () => {
  if (!['connecting', 'waiting-agent', 'connected'].includes(connectionState.value)) return;
  const room = activeRoom;
  const attempt = attemptGeneration;
  const status = activeSession?.attempt === attempt && activeSession.agentReady
    ? 'completed'
    : 'interrupted';
  persistSession(attempt, status);
  void beginRecorderStop();
  invalidateActiveAttempt(attempt);
  connectionState.value = 'disconnecting';
  if (room) await cleanupRoom(room);
  if (disposed) return;
  errorMessage.value = '';
  microphoneState.value = 'disabled';
  agentState.value = 'preparing';
  connectionState.value = 'idle';
};

onBeforeUnmount(() => {
  disposed = true;
  window.clearInterval(partialTranscriptTimer);
  const room = activeRoom;
  const attempt = attemptGeneration;
  persistSession(attempt, 'interrupted');
  void beginRecorderStop();
  invalidateActiveAttempt(attempt);
  if (room) void cleanupRoom(room);
});
</script>

<template>
  <section class="voice-panel" aria-labelledby="realtime-voice-title">
    <header class="voice-panel__header">
      <div>
        <span class="voice-panel__eyebrow">Continuous browser audio</span>
        <h2 id="realtime-voice-title">实时语音客服</h2>
        <p>开始后麦克风会持续传输，字幕与 AI 状态会同步更新。</p>
      </div>
      <span class="connection-pill" :class="'is-' + connectionState">
        {{ connectionLabel }}
      </span>
    </header>

    <div class="status-grid" aria-live="polite">
      <div>
        <span>AI 状态</span>
        <strong data-testid="agent-state">{{ agentLabel }}</strong>
      </div>
      <div>
        <span>麦克风</span>
        <strong>{{ microphoneLabel }}</strong>
      </div>
    </div>

    <p v-if="errorMessage" class="voice-alert voice-alert--error" role="alert">
      {{ errorMessage }}
    </p>
    <p v-if="saveNotice" class="voice-alert voice-alert--notice" role="status">
      {{ saveNotice }}
    </p>

    <div class="transcript" data-testid="live-transcript" aria-live="polite">
      <div v-if="!transcript.length" class="transcript__empty">
        通话开始后，您与 AI 客服的实时字幕会显示在这里。
      </div>
      <article
        v-for="segment in transcript"
        :key="segment.id"
        class="transcript__row"
        :class="'is-' + segment.role"
      >
        <div class="transcript__bubble" :class="{ 'is-partial': !segment.final }">
          <span>{{ segment.role === 'user' ? '您' : 'AI 客服' }}</span>
          <p>{{ segment.text }}</p>
          <small v-if="!segment.final">识别中…</small>
        </div>
      </article>
    </div>

    <footer class="voice-actions">
      <button
        v-if="connectionState === 'idle' || connectionState === 'error'"
        type="button"
        class="voice-button voice-button--primary"
        data-testid="voice-connect"
        @click="connect"
      >
        开始通话
      </button>
      <button
        v-else
        type="button"
        class="voice-button voice-button--secondary"
        data-testid="voice-disconnect"
        :disabled="connectionState === 'disconnecting'"
        @click="disconnect"
      >
        {{
          connectionState === 'disconnecting'
            ? '正在结束…'
            : connectionState === 'connected'
              ? '结束通话'
              : '取消连接'
        }}
      </button>
      <p>建议使用耳机减少回声；结束时会立即释放麦克风和远端音频。</p>
    </footer>

    <div ref="audioContainer" class="remote-audio" aria-hidden="true" />
  </section>
</template>

<style scoped lang="less">
.voice-panel {
  display: grid;
  gap: 20px;
  padding: clamp(20px, 4vw, 32px);
  background: var(--td-bg-color-container, #fff);
  border: 1px solid var(--td-component-stroke, #e6e8eb);
  border-radius: 16px;
  box-shadow: 0 18px 48px rgb(31 66 111 / 8%);
}

.voice-panel__header,
.voice-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.voice-panel__eyebrow {
  color: var(--td-brand-color, #0052d9);
  font-weight: 700;
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
}

h2 {
  margin: 6px 0 8px;
  color: var(--td-text-color-primary, #1d2129);
  font-size: 24px;
}

.voice-panel__header p,
.voice-actions p {
  margin: 0;
  color: var(--td-text-color-secondary, #5e626b);
  line-height: 1.6;
}

.connection-pill {
  flex: 0 0 auto;
  padding: 8px 12px;
  color: #526176;
  font-weight: 700;
  font-size: 12px;
  background: #f1f4f8;
  border-radius: 999px;
}

.connection-pill.is-connected {
  color: #176642;
  background: #e8f8f0;
}

.connection-pill.is-connecting,
.connection-pill.is-waiting-agent,
.connection-pill.is-disconnecting {
  color: #775411;
  background: #fff5d9;
}

.connection-pill.is-error {
  color: #a13a3a;
  background: #fff0f0;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.status-grid > div {
  display: grid;
  gap: 6px;
  padding: 15px 16px;
  background: var(--td-bg-color-secondarycontainer, #f7f9fc);
  border-radius: 10px;
}

.status-grid span {
  color: var(--td-text-color-placeholder, #8b8f97);
  font-size: 12px;
}

.status-grid strong {
  color: var(--td-text-color-primary, #1d2129);
  font-size: 15px;
}

.voice-alert {
  margin: 0;
  padding: 12px 14px;
  line-height: 1.6;
  border-radius: 8px;
}

.voice-alert--error {
  color: #a63737;
  background: #fff3f3;
}

.voice-alert--notice {
  color: #76520e;
  background: #fff8e6;
}

.transcript {
  min-height: 240px;
  max-height: 420px;
  padding: 18px;
  overflow-y: auto;
  background: #f7f9fc;
  border: 1px solid #e7ebf0;
  border-radius: 12px;
}

.transcript__empty {
  display: grid;
  min-height: 200px;
  color: #8b8f97;
  place-items: center;
  text-align: center;
}

.transcript__row {
  display: flex;
  margin-bottom: 14px;
}

.transcript__row.is-user {
  justify-content: flex-end;
}

.transcript__bubble {
  max-width: min(78%, 620px);
  padding: 11px 14px;
  background: #fff;
  border: 1px solid #dfe5ed;
  border-radius: 12px;
}

.is-user .transcript__bubble {
  background: #eaf2ff;
  border-color: #c9dcfa;
}

.transcript__bubble.is-partial {
  opacity: .72;
}

.transcript__bubble span,
.transcript__bubble small {
  color: #758094;
  font-size: 11px;
}

.transcript__bubble p {
  margin: 4px 0 0;
  color: #27364b;
  line-height: 1.55;
  white-space: pre-wrap;
}

.voice-button {
  min-height: 44px;
  padding: 0 22px;
  font-weight: 700;
  border-radius: 8px;
  cursor: pointer;
}

.voice-button--primary {
  color: #fff;
  background: var(--td-brand-color, #0052d9);
  border: 1px solid var(--td-brand-color, #0052d9);
}

.voice-button--secondary {
  color: #9b3434;
  background: #fff;
  border: 1px solid #d7a3a3;
}

.voice-button:disabled {
  cursor: wait;
  opacity: .65;
}

.voice-actions p {
  max-width: 520px;
  font-size: 13px;
  text-align: right;
}

.remote-audio {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}

@media (max-width: 680px) {
  .voice-panel__header,
  .voice-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .connection-pill {
    align-self: start;
  }

  .status-grid {
    grid-template-columns: 1fr;
  }

  .voice-button {
    width: 100%;
  }

  .voice-actions p {
    text-align: left;
  }

  .transcript__bubble {
    max-width: 92%;
  }
}
</style>
