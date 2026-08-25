<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import {
  OperatorCallRecordService,
  TenantCallRecordService,
} from '@/api/platform';
import type {
  CallRecordStatus,
  NormalizedCallRecordDetail,
  NormalizedTranscriptMessage,
  RecordingStatus,
} from '@/api/platform/RealtimeVoiceService';

const props = defineProps<{
  scope: 'tenant' | 'operator';
}>();

interface CallRecordServiceFacade {
  getDetail: (recordId: string) => Promise<NormalizedCallRecordDetail>;
  update: (
    recordId: string,
    update: { status: CallRecordStatus; messages: Array<{
      role: 'user' | 'assistant';
      text: string;
      sequence: number;
    }> },
  ) => Promise<unknown>;
  remove: (recordId: string) => Promise<void>;
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
const saving = ref(false);
const deleting = ref(false);
const errorMessage = ref('');
const actionError = ref('');
const detail = ref<NormalizedCallRecordDetail | null>(null);
const editStatus = ref<CallRecordStatus>('completed');
const editMessages = ref<Array<{ role: 'user' | 'assistant'; text: string; sequence: number }>>([]);
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

const directionLabel = computed(() => {
  const direction = String(detail.value?.direction || '');
  if (direction === 'inbound') return '入站电话';
  if (direction === 'outbound') return '外呼';
  return '网页语音';
});

const formatDateTime = (value: string) => (
  value ? value.replace('T', ' ').replace('Z', ' UTC') : '—'
);

const messageText = (message: NormalizedTranscriptMessage) => (
  String(message.text || message.content)
);

const recordId = computed(() => String(route.params.id || ''));

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

const applyDetailToForm = (value: NormalizedCallRecordDetail) => {
  editStatus.value = (value.aacStatus || value.status || 'completed') as CallRecordStatus;
  editMessages.value = (value.messages || []).map((message, index) => ({
    role: message.role,
    text: String(message.text || message.content || ''),
    sequence: Number(message.sequence ?? index),
  }));
};

const saveChanges = async () => {
  if (!detail.value || saving.value) return;
  saving.value = true;
  actionError.value = '';
  try {
    await recordService.update(recordId.value, {
      status: editStatus.value,
      messages: editMessages.value.map((message, index) => ({
        role: message.role,
        text: message.text.trim(),
        sequence: Number.isFinite(message.sequence) ? message.sequence : index,
      })).filter((message) => message.text.length > 0),
    });
    detail.value = await recordService.getDetail(recordId.value);
    applyDetailToForm(detail.value);
  } catch {
    actionError.value = '保存失败，请检查输入后重试。';
  } finally {
    saving.value = false;
  }
};

const removeRecord = async () => {
  if (!detail.value || deleting.value) return;
  if (!window.confirm('确认软删除这条通话记录？删除后将返回列表。')) return;
  deleting.value = true;
  actionError.value = '';
  try {
    await recordService.remove(recordId.value);
    goBack();
  } catch {
    actionError.value = '删除失败，请稍后重试。';
    deleting.value = false;
  }
};

onMounted(async () => {
  const id = recordId.value;
  if (!id) {
    loading.value = false;
    errorMessage.value = '缺少通话记录 ID。';
    return;
  }
  try {
    detail.value = await recordService.getDetail(id);
    applyDetailToForm(detail.value);
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
            <span class="eyebrow">通话记录</span>
            <h1>{{ directionLabel }}详情</h1>
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
            <dd>{{ directionLabel }}</dd>
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

      <section class="edit-card">
        <header>
          <h2>编辑记录</h2>
          <p>可修改状态与最终字幕；保存走 PUT，删除为软删除。</p>
        </header>
        <p v-if="actionError" class="inline-error" role="alert">{{ actionError }}</p>
        <label class="field">
          状态
          <select v-model="editStatus" data-testid="edit-status">
            <option value="completed">已完成</option>
            <option value="interrupted">已中断</option>
            <option value="failed">失败</option>
          </select>
        </label>
        <div class="message-editor">
          <label
            v-for="(message, index) in editMessages"
            :key="message.sequence + '-' + index"
            class="field"
          >
            {{ message.role === 'user' ? '用户字幕' : 'AI 字幕' }} #{{ message.sequence }}
            <textarea
              v-model="message.text"
              rows="2"
              :data-testid="'edit-message-' + index"
            />
          </label>
          <p v-if="!editMessages.length" class="transcript-empty">
            本次通话没有可编辑的最终字幕
          </p>
        </div>
        <div class="edit-actions">
          <button type="button" class="danger-button" :disabled="deleting || saving" @click="removeRecord">
            {{ deleting ? '删除中…' : '软删除' }}
          </button>
          <button type="button" class="primary-button" :disabled="saving || deleting" @click="saveChanges">
            {{ saving ? '保存中…' : '保存修改' }}
          </button>
        </div>
      </section>

      <section class="transcript-card">
        <header>
          <h2>当前字幕预览</h2>
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

.scope-notice,
.state-card,
.summary-card,
.recording-card,
.edit-card,
.transcript-card {
  padding: 18px 20px;
  background: #fff;
  border: 1px solid #e6ebf1;
  border-radius: 12px;
}

.state-card.is-error,
.inline-error {
  color: #a63737;
}

.summary-card header,
.recording-card header,
.edit-card header,
.transcript-card header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.eyebrow {
  color: #687386;
  font-size: 12px;
}

h1,
h2 {
  margin: 4px 0 0;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 18px;
  margin: 0;
}

.summary-grid .is-wide {
  grid-column: 1 / -1;
}

dt {
  color: #687386;
  font-size: 12px;
}

dd {
  margin: 4px 0 0;
}

.status-tag {
  padding: 4px 10px;
  border-radius: 999px;
  background: #eef3ff;
  color: #2f5bda;
  font-size: 12px;
}

.recording-state,
.transcript-empty {
  color: #687386;
}

.recording-player {
  width: 100%;
}

.field {
  display: grid;
  gap: 6px;
  margin-bottom: 12px;
  font-weight: 600;
}

select,
textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 9px 10px;
  border: 1px solid #d7dde5;
  border-radius: 8px;
  font: inherit;
}

.edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.primary-button,
.danger-button {
  min-height: 36px;
  padding: 0 14px;
  border-radius: 8px;
  cursor: pointer;
}

.primary-button {
  color: #fff;
  background: var(--td-brand-color, #0052d9);
  border: 0;
}

.danger-button {
  color: #a63737;
  background: #fff;
  border: 1px solid #f0c2c2;
}

.transcript-list {
  display: grid;
  gap: 10px;
}

.message-row.is-user {
  justify-items: end;
}

.message-bubble {
  max-width: 85%;
  padding: 10px 12px;
  border-radius: 12px;
  background: #f5f7fb;
}

.message-row.is-user .message-bubble {
  background: #eaf1ff;
}

.message-bubble span {
  display: block;
  margin-bottom: 4px;
  color: #687386;
  font-size: 12px;
}

.message-bubble p {
  margin: 0;
  white-space: pre-wrap;
}

@media (max-width: 680px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
