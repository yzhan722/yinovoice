import { describe, expect, it } from 'vitest';

import {
  reduceTranscriptionSegments,
  sealStalePartialSegments,
  toFinalTranscriptMessages,
  type TranscriptDelta,
} from './live-transcript';

describe('live transcript reducer', () => {
  it('replaces a partial segment in place and seals it with the final text', () => {
    const deltas: TranscriptDelta[] = [
      { id: 'user-1', role: 'user', text: '我想', final: false },
      { id: 'user-1', role: 'user', text: '我想预约', final: false },
      { id: 'user-1', role: 'user', text: '我想预约明天', final: true },
    ];

    const result = deltas.reduce(reduceTranscriptionSegments, []);

    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({
      id: 'user-1',
      role: 'user',
      text: '我想预约明天',
      final: true,
      sequence: 1,
    });
    expect(typeof result[0].updatedAt).toBe('number');
  });

  it('ignores a late partial update after a segment is final', () => {
    const final = reduceTranscriptionSegments([], {
      id: 'agent-1',
      role: 'assistant',
      text: '已经为您查看',
      final: true,
    });

    const result = reduceTranscriptionSegments(final, {
      id: 'agent-1',
      role: 'assistant',
      text: '旧输出',
      final: false,
    });

    expect(result).toEqual(final);
  });

  it('seals stale partial segments after the idle window', () => {
    const partial = reduceTranscriptionSegments([], {
      id: 'user-stuck',
      role: 'user',
      text: '我想了解营业时间',
      final: false,
    });
    const sealed = sealStalePartialSegments(partial, 4_000, (partial[0].updatedAt ?? 0) + 4_001);
    expect(sealed[0].final).toBe(true);
    expect(sealStalePartialSegments(partial, 4_000, (partial[0].updatedAt ?? 0) + 100)).toBe(
      partial,
    );
  });

  it('persists only nonblank final messages in first-seen order', () => {
    const transcript = [
      {
        id: 'agent-2',
        role: 'assistant' as const,
        text: '  可以的  ',
        final: true,
        sequence: 2,
      },
      {
        id: 'user-1',
        role: 'user' as const,
        text: '预约明天',
        final: true,
        sequence: 1,
      },
      {
        id: 'user-2',
        role: 'user' as const,
        text: '还在说',
        final: false,
        sequence: 3,
      },
    ];

    expect(toFinalTranscriptMessages(transcript)).toEqual([
      { role: 'user', text: '预约明天', sequence: 1 },
      { role: 'assistant', text: '可以的', sequence: 2 },
    ]);
  });
});
