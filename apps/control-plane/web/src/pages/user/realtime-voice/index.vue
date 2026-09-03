<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import type {
  CustomerServiceInstance,
  TtsVoiceId,
} from '@/api/platform/RealtimeVoiceService';
import {
  CUSTOMER_SERVICE_VERSION_CONFLICT,
  RealtimeVoiceService,
  TTS_VOICE_OPTIONS,
} from '@/api/platform/RealtimeVoiceService';
import {
  loadStoredInstanceId,
  resolveInstanceSelection,
  storeInstanceId,
} from '@/api/platform/instanceSelection';
import LiveKitRealtimePanel from '@/components/realtime-voice/LiveKitRealtimePanel.vue';

const route = useRoute();
const router = useRouter();
const service = new RealtimeVoiceService();
const instances = ref<CustomerServiceInstance[]>([]);
const customerServiceId = ref<string | null>(null);
const ttsVoice = ref<TtsVoiceId>('longanqian');
const loading = ref(true);
const loadFailed = ref(false);
const voiceSaving = ref(false);
const voiceError = ref('');

const selectedInstance = computed(
  () => instances.value.find((item) => item.id === customerServiceId.value) ?? null,
);

function instanceLabel(item: CustomerServiceInstance): string {
  const name = item.display_name?.trim() || '未命名实例';
  const org = item.organization_name?.trim();
  return org ? `${name} · ${org}` : name;
}

function voiceFromInstance(item: CustomerServiceInstance | null): TtsVoiceId {
  const value = item?.voice?.tts_voice;
  if (value && TTS_VOICE_OPTIONS.some((option) => option.value === value)) {
    return value;
  }
  return 'longanqian';
}

function syncVoiceFromInstance(): void {
  ttsVoice.value = voiceFromInstance(selectedInstance.value);
}

function routeInstanceId(): string | null {
  return typeof route.query.instanceId === 'string' ? route.query.instanceId : null;
}

async function syncRoute(id: string | null): Promise<void> {
  if (!id || route.query.instanceId === id) return;
  await router.replace({
    query: {
      ...route.query,
      instanceId: id,
    },
  });
}

function selectInstance(id: string): void {
  if (!id || !instances.value.some((item) => item.id === id)) return;
  if (id === customerServiceId.value) {
    storeInstanceId(id);
    return;
  }
  customerServiceId.value = id;
  storeInstanceId(id);
  voiceError.value = '';
  syncVoiceFromInstance();
  void syncRoute(id);
}

function onInstanceChange(event: Event): void {
  selectInstance((event.target as HTMLSelectElement).value);
}

function replaceInstance(updated: CustomerServiceInstance): void {
  instances.value = instances.value.map((item) => (
    item.id === updated.id ? updated : item
  ));
}

async function applyVoice(next: TtsVoiceId): Promise<void> {
  const current = selectedInstance.value;
  if (!current || next === ttsVoice.value || voiceSaving.value) return;
  if (!TTS_VOICE_OPTIONS.some((option) => option.value === next)) return;
  voiceSaving.value = true;
  voiceError.value = '';
  try {
    const updated = await service.updateCustomerService(current.id, {
      expected_version: current.version,
      display_name: current.display_name,
      organization_name: current.organization_name,
      greeting: current.greeting,
      platform_prompt: current.platform_prompt || '',
      tenant_prompt: current.tenant_prompt || '',
      voice: {
        preset_id: 'mandarin-standard',
        locale: 'zh-CN',
        speaking_rate: 1,
        volume: 1,
        pitch: 0,
        style: 'professional-friendly',
        emotion: 'neutral',
        pause_profile: 'receptionist',
        ...current.voice,
        tts_voice: next,
      },
      response: current.response ?? {
        brevity: 'concise',
        max_spoken_sentences: 3,
        ask_one_question_at_a_time: true,
      },
      insights_profile: current.insights_profile ?? null,
    });
    replaceInstance(updated);
    ttsVoice.value = voiceFromInstance(updated);
  } catch (error) {
    const message = error instanceof Error ? error.message : '';
    voiceError.value = message === CUSTOMER_SERVICE_VERSION_CONFLICT
      ? CUSTOMER_SERVICE_VERSION_CONFLICT
      : '音色保存失败，请稍后重试。';
    if (message === CUSTOMER_SERVICE_VERSION_CONFLICT) {
      await loadInstances();
    }
  } finally {
    voiceSaving.value = false;
  }
}

function onVoiceChange(event: Event): void {
  void applyVoice((event.target as HTMLSelectElement).value as TtsVoiceId);
}

async function loadInstances(): Promise<void> {
  loading.value = true;
  loadFailed.value = false;
  voiceError.value = '';
  try {
    const page = await service.listCustomerServices({ limit: 100, offset: 0 });
    instances.value = page.items;
    const selected = resolveInstanceSelection({
      availableIds: page.items.map((item) => item.id),
      routeId: routeInstanceId(),
      storedId: loadStoredInstanceId(),
    });
    customerServiceId.value = selected;
    storeInstanceId(selected);
    syncVoiceFromInstance();
    await syncRoute(selected);
  } catch {
    instances.value = [];
    customerServiceId.value = null;
    loadFailed.value = true;
  } finally {
    loading.value = false;
  }
}

watch(
  () => route.query.instanceId,
  (value) => {
    const routeId = typeof value === 'string' ? value : null;
    if (!routeId) return;
    selectInstance(routeId);
  },
);

onMounted(() => {
  void loadInstances();
});
</script>

<template>
  <main class="realtime-page">
    <header class="page-head">
      <div>
        <h1>实时语音</h1>
        <p>选择语音实例和音色后，用浏览器麦克风连续对话</p>
      </div>
    </header>

    <section
      v-if="!loading && !loadFailed && instances.length"
      class="instance-switcher"
    >
      <label class="instance-switcher__label" for="voice-instance-select">当前语音 AI</label>
      <select
        id="voice-instance-select"
        data-testid="voice-instance-select"
        :value="customerServiceId ?? ''"
        @change="onInstanceChange"
      >
        <option v-for="item in instances" :key="item.id" :value="item.id">
          {{ instanceLabel(item) }}
        </option>
      </select>
      <label class="instance-switcher__label" for="voice-tts-select">客服音色</label>
      <select
        id="voice-tts-select"
        data-testid="voice-tts-select"
        :value="ttsVoice"
        :disabled="voiceSaving || !selectedInstance"
        @change="onVoiceChange"
      >
        <option v-for="option in TTS_VOICE_OPTIONS" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
      <p v-if="voiceError" class="instance-switcher__error" role="alert">{{ voiceError }}</p>
      <p class="instance-switcher__hint">
        切换实例或音色会结束当前通话。音色会保存到当前实例，下次开始后生效。
      </p>
    </section>

    <div v-if="loading" class="status-note">正在加载语音实例…</div>
    <div v-else-if="loadFailed" class="status-note is-error">实例加载失败，请稍后重试。</div>
    <div v-else-if="!customerServiceId" class="status-note">当前租户暂无可用语音实例。</div>
    <LiveKitRealtimePanel
      v-else
      :key="customerServiceId + ':' + ttsVoice"
      :customer-service-id="customerServiceId"
    />
  </main>
</template>

<style scoped lang="less">
.realtime-page {
  display: grid;
  gap: 18px;
  max-width: 1120px;
  padding: 8px 4px 40px;
  margin: 0 auto;
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.page-head h1 {
  margin: 0;
  color: var(--td-text-color-primary);
  font-size: 26px;
}

.page-head p {
  margin: 7px 0 0;
  color: var(--td-text-color-secondary);
}

.instance-switcher {
  display: grid;
  gap: 8px;
  padding: 14px 16px;
  background: var(--td-bg-color-container, #fff);
  border: 1px solid var(--td-component-stroke, #e7e7e7);
  border-radius: 12px;
}

.instance-switcher__label {
  color: var(--td-text-color-secondary);
  font-size: 13px;
  font-weight: 600;
}

.instance-switcher select {
  width: min(420px, 100%);
  padding: 9px 12px;
  color: var(--td-text-color-primary);
  font-size: 15px;
  background: var(--td-bg-color-container, #fff);
  border: 1px solid var(--td-component-stroke, #dcdcdc);
  border-radius: 8px;
}

.instance-switcher select:disabled {
  opacity: 0.7;
}

.instance-switcher__hint {
  margin: 0;
  color: var(--td-text-color-secondary);
  font-size: 13px;
  line-height: 1.55;
}

.instance-switcher__error {
  margin: 0;
  color: #c62828;
  font-size: 13px;
}

.status-note {
  padding: 12px 15px;
  color: var(--td-text-color-secondary);
  line-height: 1.6;
  background: var(--td-bg-color-container, #fff);
  border: 1px solid var(--td-component-stroke, #e7e7e7);
  border-radius: 9px;
}

.status-note.is-error {
  color: #c62828;
}

@media (max-width: 680px) {
  .realtime-page {
    padding: 4px 0 28px;
  }

  .page-head {
    flex-direction: column;
  }
}
</style>
