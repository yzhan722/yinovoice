import type { IngestResult, NormalizedEvent } from "../domain/types.js";
import type { SqliteStore } from "../storage/sqlite-store.js";

export class EventIngestionService {
  constructor(private readonly store: SqliteStore) {}

  ingest(event: NormalizedEvent): IngestResult {
    return this.store.ingest(event);
  }
}
