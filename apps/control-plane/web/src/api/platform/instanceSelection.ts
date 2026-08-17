export const INSTANCE_SELECTION_STORAGE_KEY = 'yino-selected-instance-id';

export interface InstanceSelectionInput {
  availableIds: string[];
  routeId?: string | null;
  storedId?: string | null;
}

export function resolveInstanceSelection({
  availableIds,
  routeId,
  storedId,
}: InstanceSelectionInput): string | null {
  if (routeId && availableIds.includes(routeId)) return routeId;
  if (storedId && availableIds.includes(storedId)) return storedId;
  return availableIds[0] ?? null;
}

export function loadStoredInstanceId(): string | null {
  return window.sessionStorage.getItem(INSTANCE_SELECTION_STORAGE_KEY);
}

export function storeInstanceId(instanceId: string | null): void {
  if (instanceId) {
    window.sessionStorage.setItem(INSTANCE_SELECTION_STORAGE_KEY, instanceId);
  } else {
    window.sessionStorage.removeItem(INSTANCE_SELECTION_STORAGE_KEY);
  }
}
