import type { Rating } from "../domain/types.js";
import type { SqliteStore } from "../storage/sqlite-store.js";

export class RatingService {
  constructor(
    private readonly store: SqliteStore,
    private readonly clock = () => new Date(),
  ) {}

  rate(profile: string, callId: string, score: number): Rating {
    if (!Number.isInteger(score) || score < 1 || score > 5) {
      throw new RangeError("score must be an integer from 1 to 5");
    }
    if (!this.store.getCall(profile, callId)) {
      throw new Error("call not found");
    }
    return this.store.upsertRating(profile, callId, score, this.clock().toISOString());
  }
}
