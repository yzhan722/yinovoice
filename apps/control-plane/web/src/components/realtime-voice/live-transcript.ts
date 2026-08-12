export type TranscriptRole = 'user' | 'assistant';

export interface TranscriptDelta {
  id: string;
  role: TranscriptRole;
  text: string;
  final: boolean;
}

export interface LiveTranscriptSegment extends TranscriptDelta {
  sequence: number;
  updatedAt?: number;
}

export interface FinalTranscriptMessage {
  role: TranscriptRole;
  text: string;
  sequence: number;
}

export function reduceTranscriptionSegments(
  current: LiveTranscriptSegment[],
  delta: TranscriptDelta,
): LiveTranscriptSegment[] {
  const index = current.findIndex((segment) => segment.id === delta.id);
  if (index < 0) {
    return [
      ...current,
      {
        ...delta,
        sequence: current.reduce(
          (maximum, segment) => Math.max(maximum, segment.sequence),
          0,
        ) + 1,
        updatedAt: Date.now(),
      },
    ];
  }
  if (current[index].final && !delta.final) return current;

  const next = [...current];
  next[index] = {
    ...current[index],
    ...delta,
    sequence: current[index].sequence,
    updatedAt: Date.now(),
  };
  return next;
}

/** Seal partial bubbles that have not received updates (stuck “识别中…”). */
export function sealStalePartialSegments(
  current: LiveTranscriptSegment[],
  olderThanMs: number,
  now = Date.now(),
): LiveTranscriptSegment[] {
  let changed = false;
  const next = current.map((segment) => {
    if (segment.final || !segment.text.trim()) return segment;
    const updatedAt = segment.updatedAt ?? 0;
    if (now - updatedAt < olderThanMs) return segment;
    changed = true;
    return { ...segment, final: true, updatedAt: now };
  });
  return changed ? next : current;
}

export function toFinalTranscriptMessages(
  transcript: LiveTranscriptSegment[],
): FinalTranscriptMessage[] {
  return transcript
    .filter((segment) => segment.final && segment.text.trim())
    .sort((left, right) => left.sequence - right.sequence)
    .map(({ role, text, sequence }) => ({
      role,
      text: text.trim(),
      sequence,
    }));
}
