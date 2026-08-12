<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

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
}>();

interface CallRecordServiceFacade {
  getDetail: (recordId: string) => Promise<NormalizedCallRecordDetail>;
  voiceService: {
    fetchCallRecordingBlob: (recordId: string, signal?: AbortSignal) => Promise<Blob>;
  };
}

const route = useRoute();
const router = useRouter();
const recordService = (props.scope === 'operator'
  ? new OperatorCallRecordService()
  : new TenantCallRecordService()) as CallRecordServiceFacade;
const loading = ref(true);
const errorMessage = ref('');
const detail = ref<NormalizedCallRecordDetail | null>(null);
const recordingLoading = ref(false);
const recordingError = ref(false);
const audioUrl = ref('');
let recordingAbortController: AbortController | null = null;

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

const formatDateTime = (value: string) => (
  value ? value.replace('T', ' ').replace('Z', ' UTC') : '—'
);

const messageText = (message: NormalizedTranscriptMessage) => (
  String(message.text || message.content)
);

const goBack = () => {
  void router.push({
    name: props.scope === 'operator' ? 'AdminCallHistoryIndex' : 'CallHistoryIndex',
  });
};

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

const loadRecording = async (recordId: string) => {
  abortRecordingFetch();
  resetRecordingState();
  if (detail.value?.recording_status !== 'ready') return;

  const controller = new AbortController();
  recordingAbortController = controller;
  recordingLoading.value = true;
  try {
    const blob = await recordService.voiceService.fetchCallRecordingBlob(recordId, controller.signal);
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

onMounted(async () => {
  const id = String(route.params.id || '');
  if (!id) {
    loading.value = false;
    errorMessage.value = '缺少通话记录 ID。';
    return;
  }
  try {
    detail.value = await recordService.getDetail(id);
  } catch {
    errorMessage.value = '无法加载 Demo 通话详情，请稍后重试。';
  } finally {
    loading.value = false;
  }
  if (detail.value) {
    void loadRecording(id);
  }
});

onBeforeUnmount(() => {
  abortRecordingFetch();
  resetRecordingState();
});
</script>

<template>
  <main class="detail-page">
    <button type="button" class="back-button" @click="goBack">← 返回通话记录</button>

    <aside v-if="scope === 'operator'" class="scope-notice">
      演示租户范围：此详情通过配置的 Demo tenant header 查询。
    </aside>

    <div v-if="loading" class="state-card">正在加载通话详情…</div>
    <div v-else-if="errorMessage" class="state-card is-error" role="alert">
      {{ errorMessage }}
    </div>
    <template v-else-if="detail">
      <section class="summary-card">
        <header>
          <div>
            <span class="eyebrow">Web voice Demo record</span>
            <h1>网页语音通话详情</h1>
          </div>
          <span class="status-tag">{{ statusLabel }}</span>
        </header>
        <dl class="summary-grid">
          <div>
            <dt>客服实例</dt>
            <dd>{{ detail.attName || detail.assistantName || '—' }}</dd>
          </div>
          <div>
            <dt>方向</dt>
            <dd>网页语音</dd>
          </div>
          <div>
            <dt>开始时间</dt>
            <dd>{{ formatDateTime(detail.aacStartedAt || detail.started_at) }}</dd>
          </div>
          <div>
            <dt>结束时间</dt>
            <dd>{{ formatDateTime(detail.aacEndedAt || detail.ended_at) }}</dd>
          </div>
          <div>
            <dt>通话时长</dt>
            <dd>{{ detail.aacDurationSec ?? detail.duration_sec ?? 0 }} 秒</dd>
          </div>
          <div>
            <dt>LiveKit 房间</dt>
            <dd><code>{{ detail.room_name || '—' }}</code></dd>
          </div>
          <div class="is-wide">
            <dt>记录 ID</dt>
            <dd><code>{{ detail.aacCallId || detail.callId || detail.id }}</code></dd>
          </div>
        </dl>
      </section>

      <section class="recording-card">
        <header>
          <h2>通话录音</h2>
        </header>
        <div v-if="recordingStatus === 'failed'" class="recording-state is-error">
          录音保存失败
        </div>
        <div v-else-if="recordingStatus === 'ready'">
          <div v-if="recordingLoading" class="recording-state">正在加载录音…</div>
          <div v-else-if="recordingError" class="recording-state is-error">录音无法播放</div>
          <audio
            v-else-if="audioUrl"
            class="recording-player"
            controls
            :src="audioUrl"
          />
        </div>
        <div v-else class="recording-state">无录音</div>
      </section>

      <section class="transcript-card">
        <header>
          <h2>最终字幕</h2>
          <p>仅保存 final 字幕；实时 partial 文本不会写入 Demo 记录。</p>
        </header>
        <div v-if="!detail.messages?.length" class="transcript-empty">
          本次通话没有可保存的最终字幕
        </div>
        <div v-else class="transcript-list">
          <article
            v-for="message in detail.messages"
            :key="message.sequence"
            class="message-row"
            :class="'is-' + message.role"
          >
            <div class="message-bubble">
              <span>{{ message.role === 'user' ? '您' : 'AI 客服' }}</span>
              <p>{{ messageText(message) }}</p>
            </div>
          </article>
        </div>
      </section>
    </template>
  </main>
</template>

<style scoped lang="less">
.detail-page {
  display: grid;
  gap: 16px;
  max-width: 960px;
  padding: 8px 4px 40px;
  margin: 0 auto;
}

.back-button {
  justify-self: start;
  padding: 7px 0;
  color: var(--td-brand-color, #0052d9);
  background: transparent;
  border: 0;
  cursor: pointer;
}

.scope-notice {
  padding: 12px 15px;
  color: #76520e;
  background: #fff8e6;
  border: 1px solid #f3d999;
  border-radius: 9px;
}

.state-card,
.summary-card,
.recording-card,
.transcript-card {
  padding: clamp(20px, 4vw, 28px);
  background: var(--td-bg-color-container, #fff);
  border: 1px solid var(--td-component-stroke, #e6e8eb);
  border-radius: 14px;
}

.state-card {
  color: #7a8492;
  text-align: center;
}

.state-card.is-error {
  color: #a63737;
}

.summary-card > header,
.recording-card > header,
.transcript-card > header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.eyebrow {
  color: #0052d9;
  font-weight: 700;
  font-size: 11px;
  letter-spacing: .08em;
  text-transform: uppercase;
}

h1,
h2 {
  margin: 6px 0 0;
  color: var(--td-text-color-primary, #1d2129);
}

.status-tag {
  padding: 6px 10px;
  color: #176642;
  font-weight: 700;
  font-size: 12px;
  background: #e8f8f0;
  border-radius: 999px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  margin: 26px 0 0;
}

.summary-grid div {
  min-width: 0;
}

.summary-grid .is-wide {
  grid-column: 1 / -1;
}

dt {
  color: #7b8492;
  font-size: 12px;
}

dd {
  margin: 6px 0 0;
  overflow-wrap: anywhere;
  color: #27364b;
  font-weight: 600;
}

.transcript-card > header p {
  max-width: 440px;
  margin: 0;
  color: #7b8492;
  font-size: 12px;
  line-height: 1.6;
  text-align: right;
}

.transcript-list {
  display: grid;
  gap: 14px;
  margin-top: 24px;
}

.message-row {
  display: flex;
}

.message-row.is-user {
  justify-content: flex-end;
}

.message-bubble {
  max-width: 76%;
  padding: 11px 14px;
  background: #f7f9fc;
  border: 1px solid #e0e5ec;
  border-radius: 12px;
}

.is-user .message-bubble {
  background: #eaf2ff;
  border-color: #c9dcfa;
}

.message-bubble span {
  color: #7b8492;
  font-size: 11px;
}

.message-bubble p {
  margin: 5px 0 0;
  color: #27364b;
  line-height: 1.6;
  white-space: pre-wrap;
}

.transcript-empty {
  padding: 48px 0 20px;
  color: #7b8492;
  text-align: center;
}

.recording-state {
  margin-top: 18px;
  color: #7b8492;
}

.recording-state.is-error {
  color: #a63737;
}

.recording-player {
  display: block;
  width: 100%;
  margin-top: 18px;
}

@media (max-width: 680px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .summary-grid .is-wide {
    grid-column: auto;
  }

  .transcript-card > header {
    flex-direction: column;
  }

  .transcript-card > header p {
    text-align: left;
  }

  .message-bubble {
    max-width: 92%;
  }
}
</style>
