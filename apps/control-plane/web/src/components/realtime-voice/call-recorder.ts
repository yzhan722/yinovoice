export type CallRecorder = {
  start: (localTrack: MediaStreamTrack, remoteTrack?: MediaStreamTrack | null) => void;
  stop: () => Promise<Blob | null>;
  dispose: () => void;
};

function isMediaRecorderSupported(): boolean {
  return typeof MediaRecorder !== 'undefined';
}

export function createCallRecorder(): CallRecorder {
  let audioContext: AudioContext | null = null;
  let mediaRecorder: MediaRecorder | null = null;
  let mixedTrack: MediaStreamTrack | null = null;
  let chunks: Blob[] = [];

  function resetRecorderState() {
    mediaRecorder = null;
    mixedTrack = null;
    chunks = [];
  }

  function attachRecorder(stream: MediaStream) {
    mediaRecorder = new MediaRecorder(stream);
    chunks = [];
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        chunks.push(event.data);
      }
    };
    mediaRecorder.start();
  }

  function connectLocalTrack(
    context: AudioContext,
    destination: MediaStreamAudioDestinationNode,
    localTrack: MediaStreamTrack,
  ) {
    const localSource = context.createMediaStreamSource(new MediaStream([localTrack]));
    localSource.connect(destination);
  }

  function connectRemoteTrack(
    context: AudioContext,
    destination: MediaStreamAudioDestinationNode,
    remoteTrack: MediaStreamTrack,
  ) {
    const remoteSource = context.createMediaStreamSource(new MediaStream([remoteTrack]));
    remoteSource.connect(destination);
  }

  function start(localTrack: MediaStreamTrack, remoteTrack?: MediaStreamTrack | null) {
    if (!isMediaRecorderSupported()) {
      return;
    }

    dispose();

    try {
      audioContext = new AudioContext();
      const destination = audioContext.createMediaStreamDestination();
      connectLocalTrack(audioContext, destination, localTrack);

      if (remoteTrack) {
        try {
          connectRemoteTrack(audioContext, destination, remoteTrack);
        } catch (error) {
          console.warn('call-recorder: remote mix failed, recording local only', error);
        }
      }

      mixedTrack = destination.stream.getAudioTracks()[0] ?? null;
      if (mixedTrack) {
        attachRecorder(new MediaStream([mixedTrack]));
        return;
      }
    } catch (error) {
      console.warn('call-recorder: mix setup failed, recording local only', error);
      if (audioContext) {
        void audioContext.close();
        audioContext = null;
      }
    }

    try {
      attachRecorder(new MediaStream([localTrack]));
    } catch (error) {
      console.warn('call-recorder: failed to start MediaRecorder', error);
      resetRecorderState();
    }
  }

  async function stop(): Promise<Blob | null> {
    const recorder = mediaRecorder;
    if (!recorder || recorder.state === 'inactive') {
      return null;
    }

    return new Promise((resolve) => {
      recorder.onstop = () => {
        if (chunks.length === 0) {
          resolve(null);
          return;
        }

        resolve(new Blob(chunks, { type: recorder.mimeType || 'audio/webm' }));
      };

      try {
        recorder.stop();
      } catch {
        resolve(null);
      }
    });
  }

  function dispose() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      try {
        mediaRecorder.stop();
      } catch {
        // Ignore stop errors during cleanup.
      }
    }

    if (mixedTrack) {
      mixedTrack.stop();
      mixedTrack = null;
    }

    if (audioContext) {
      void audioContext.close();
      audioContext = null;
    }

    resetRecorderState();
  }

  return {
    start,
    stop,
    dispose,
  };
}
