import { describe, expect, it } from 'vitest';

import { resolveInstanceSelection } from './instanceSelection';

const firstId = '00000000-0000-0000-0000-000000000101';
const secondId = '00000000-0000-0000-0000-000000000102';

describe('resolveInstanceSelection', () => {
  it('prefers a valid route selection over stored and first ids', () => {
    expect(resolveInstanceSelection({
      availableIds: [firstId, secondId],
      routeId: secondId,
      storedId: firstId,
    })).toBe(secondId);
  });

  it('falls back from stale selections to the first available UUID', () => {
    expect(resolveInstanceSelection({
      availableIds: [firstId, secondId],
      routeId: 'stale-route-id',
      storedId: 'stale-stored-id',
    })).toBe(firstId);
  });

  it('returns null for an empty tenant instance list', () => {
    expect(resolveInstanceSelection({ availableIds: [] })).toBeNull();
  });
});
