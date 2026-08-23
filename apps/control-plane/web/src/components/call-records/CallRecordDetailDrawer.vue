<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import {
  OperatorCallRecordService,
  TenantCallRecordService,
} from '@/api/platform';
import type {
  NormalizedCallRecordDetail,
  NormalizedTranscriptMessage,
  RecordingStatus,
} from '@/api/platform/RealtimeVoiceService';

const props = defineProps<{
  scope: 'tenant' | 'operator';
  recordId: string;
  visible: boolean;
}>();

const emit = defineEmits<{
  'update:visible': [value: boolean];
}>();

interface CallRecordServiceFacade {
  getDetail: (recordId: string) => Promise<NormalizedCallRecordDetail>;
  voiceService: {
    fetchCallRecordingBlob: (recordId: string, signal?: AbortSignal) => Promise<Blob>;
  };
}

const router = useRouter();
const recordService = (props.scope === 'operator'
  ? new OperatorCallRecordService()
  : new TenantCallRecordService()) as CallRecordServiceFacade;

const loading = ref(false);
const errorMessage = ref('');
const detail = ref<NormalizedCallRecordDetail | null>(null);
const recordingLoading = ref(false);
const recordingError = ref(false);
const audioUrl = ref('');
let recordingAbortController: AbortController | null = null;
let loadGeneration = 0;

const statusLabel = computed(() => {
  const labels: Record<string, string> = {
    completed: '已完成',
    interrupted: '已中断',
    failed: '失败',
  };
  const status = String(detail.value?.aacStatus || detail.value?.status || '');
  return labels[status] || '—';
});

const recordingStatus = computed<RecordingStatus | ''>(() => (
  detail.value?.recording_status || ''
));

const durationLabel = computed(() => {
  const sec = Number(detail.value?.aacDurationSec ?? detail.value?.duration_sec ?? 0);
  if (!sec) return '—';
  if (sec < 60) return `${sec} 秒`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return s ? `${m} 分 ${s} 秒` : `${m} 分`;
});

const displayId = computed(() => (
  String(detail.value?.aacCallId || detail.value?.callId || detail.value?.id || props.recordId)
));

const formatDateTime = (value: string) => (
  value ? value.replace('T', ' ').replace(/\.\d+Z$/, ' UTC').replace('Z', ' UTC') : '—'
);

const messageText = (message: NormalizedTranscriptMessage) => (
  String(message.text || message.content || '')
);

const abortRecordingFetch = () => {
  recordingAbortController?.abort();
  recordingAbortController = null;
};

const resetRecordingState = () => {
  if (audioUrl.value) {
    URL.revokeObjectURL(audioUrl.value);
    audioUrl.value = '';
  }
  recordingLoading.value = false;
  recordingError.value = false;
};

const loadRecording = async (id: string) => {
  abortRecordingFetch();
  resetRecordingState();
  if (detail.value?.recording_status !== 'ready') return;

  const controller = new AbortController();
  recordingAbortController = controller;
  recordingLoading.value = true;
  try {
    const blob = await recordService.voiceService.fetchCallRecordingBlob(id, controller.signal);
    if (controller.signal.aborted) return;
    audioUrl.value = URL.createObjectURL(blob);
  } catch {
    if (controller.signal.aborted) return;
    recordingError.value = true;
  } finally {
    if (recordingAbortController === controller) {
      recordingAbortController = null;
    }
    if (!controller.signal.aborted) {
      recordingLoading.value = false;
    }
  }
};

const loadDetail = async (id: string) => {
  if (!id) return;
  const generation = ++loadGeneration;
  loading.value = true;
  errorMessage.value = '';
  detail.value = null;
  abortRecordingFetch();
  resetRecordingState();
  try {
    const next = await recordService.getDetail(id);
    if (generation !== loadGeneration) return;
    detail.value = next;
    void loadRecording(id);
  } catch {
    if (generation !== loadGeneration) return;
    errorMessage.value = '无法加载通话详情，请稍后重试。';
  } finally {
    if (generation === loadGeneration) loading.value = false;
  }
};

const close = () => {
  emit('update:visible', false);
};

const openFullPage = () => {
  const name = props.scope === 'operator'
    ? 'AdminCallHistoryDetail'
    : 'UserCallHistoryDetail';
  emit('update:visible', false);
  void router.push({ name, params: { id: props.recordId } });
};

watch(
  () => [props.visible, props.recordId] as const,
  ([visible, id]) => {
    if (visible && id) {
      void loadDetail(id);
      return;
    }
    abortRecordingFetch();
    resetRecordingState();
    detail.value = null;
    errorMessage.value = '';
  },
);

onBeforeUnmount(() => {
  loadGeneration += 1;
  abortRecordingFetch();
  resetRecordingState();
});
</script>

<template>
  <t-drawer
    :visible="visible"
    size="520px"
    placement="right"
    :footer="false"
    destroy-on-close
    data-testid="call-detail-drawer"
    @update:visible="emit('update:visible', $event)"
  >
    <template #header>
      <div class="drawer-head">
        <div>
          <div class="eyebrow">通话详情</div>
          <div class="title-row">
            <code class="call-id">{{ displayId }}</code>
            <span class="status-tag">{{ statusLabel }}</span>
          </div>
        </div>
        <div class="duration">{{ durationLabel }}</div>
      </div>
    </template>

    <div class="drawer-body">
      <div v-if="loading" class="state">正在加载…</div>
      <div v-else-if="errorMessage" class="state is-error" role="alert">{{ errorMessage }}</div>
      <template v-else-if="detail">
        <dl class="meta">
          <div>
            <dt>客服实例</dt>
            <dd>{{ detail.attName || detail.assistantName || '—' }}</dd>
          </div>
          <div>
            <dt>开始时间</dt>
            <dd>{{ formatDateTime(detail.aacStartedAt || detail.started_at) }}</dd>
          </div>
          <div>
            <dt>方向</dt>
            <dd>网页语音</dd>
          </div>
          <div>
            <dt>结束时间</dt>
            <dd>{{ formatDateTime(detail.aacEndedAt || detail.ended_at) }}</dd>
          </div>
        </dl>

        <section class="panel">
          <header>
            <h3>录音</h3>
          </header>
          <div v-if="recordingStatus === 'failed'" class="state is-error">录音保存失败</div>
          <div v-else-if="recordingStatus === 'ready'">
            <div v-if="recordingLoading" class="state">正在加载录音…</div>
            <div v-else-if="recordingError" class="state is-error">录音无法播放</div>
            <audio
              v-else-if="audioUrl"
              class="player"
              controls
              data-testid="drawer-recording-player"
              :src="audioUrl"
            />
          </div>
          <div v-else class="state">无录音</div>
        </section>

        <section class="panel transcript-panel">
          <header>
            <h3>转写</h3>
            <span class="muted">对话预览</span>
          </header>
          <div v-if="!detail.messages?.length" class="state">本次通话没有最终字幕</div>
          <div v-else class="bubbles" data-testid="drawer-transcript">
            <article
              v-for="message in detail.messages"
              :key="message.sequence"
              class="bubble-row"
              :class="'is-' + message.role"
            >
              <div class="bubble">
                <span class="who">{{ message.role === 'user' ? '用户' : 'AI 客服' }}</span>
                <p>{{ messageText(message) }}</p>
              </div>
            </article>
          </div>
        </section>

        <div class="footer-actions">
          <button type="button" class="ghost" data-testid="drawer-open-full" @click="openFullPage">
            在新页打开 / 编辑
          </button>
          <button type="button" class="primary" @click="close">关闭</button>
        </div>
      </template>
    </div>
  </t-drawer>
</template>

<style scoped lang="less">
.drawer-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  padding-right: 8px;
}

.eyebrow {
  color: #687386;
  font-size: 12px;
  font-weight: 600;
}

.title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

.call-id {
  font-size: 13px;
  word-break: break-all;
}

.status-tag {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: 999px;
  background: #eef3ff;
  color: #2f5bda;
  font-size: 12px;
  font-weight: 700;
}

.duration {
  color: #1d2129;
  font-size: 18px;
  font-weight: 800;
  white-space: nowrap;
}

.drawer-body {
  display: grid;
  gap: 14px;
  padding-bottom: 12px;
}

.state {
  color: #687386;
  font-size: 13px;
}

.state.is-error {
  color: #a63737;
}

.meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 14px;
  margin: 0;
  padding: 12px 14px;
  background: #f7f9fc;
  border-radius: 10px;
}

dt {
  color: #687386;
  font-size: 11px;
}

dd {
  margin: 3px 0 0;
  font-size: 13px;
  color: #1d2129;
}

.panel {
  padding: 12px 14px;
  border: 1px solid #e6ebf1;
  border-radius: 10px;
  background: #fff;
}

.panel header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 10px;
}

.panel h3 {
  margin: 0;
  font-size: 14px;
}

.muted {
  color: #8a93a3;
  font-size: 12px;
}

.player {
  width: 100%;
}

.bubbles {
  display: grid;
  gap: 10px;
  max-height: min(52vh, 420px);
  overflow: auto;
  padding-right: 2px;
}

.bubble-row {
  display: grid;
}

.bubble-row.is-assistant {
  justify-items: start;
}

.bubble-row.is-user {
  justify-items: end;
}

.bubble {
  max-width: 88%;
  padding: 10px 12px;
  border-radius: 14px;
  background: #f3f5f9;
}

.bubble-row.is-user .bubble {
  background: #e8f0ff;
}

.who {
  display: block;
  margin-bottom: 4px;
  font-size: 11px;
  font-weight: 700;
  color: #0b5fff;
}

.bubble-row.is-user .who {
  color: #b45309;
  text-align: right;
}

.bubble p {
  margin: 0;
  font-size: 13px;
  line-height: 1.45;
  white-space: pre-wrap;
  color: #1d2129;
}

.footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 4px;
}

.ghost,
.primary {
  min-height: 36px;
  padding: 0 14px;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 700;
}

.ghost {
  color: #2f5bda;
  background: #fff;
  border: 1px solid #d7dde5;
}

.primary {
  color: #fff;
  background: var(--td-brand-color, #0052d9);
  border: 0;
}
</style>
