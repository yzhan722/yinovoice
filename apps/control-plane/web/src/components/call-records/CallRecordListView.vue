<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import {
  OperatorCallRecordService,
  TenantCallRecordService,
} from '@/api/platform';
import type { NormalizedCallRecordListItem } from '@/api/platform/RealtimeVoiceService';

const props = defineProps<{
  scope: 'tenant' | 'operator';
}>();

const router = useRouter();
const recordService = props.scope === 'operator'
  ? new OperatorCallRecordService()
  : new TenantCallRecordService();
const records = ref<NormalizedCallRecordListItem[]>([]);
const loading = ref(true);
const errorMessage = ref('');
const actionError = ref('');
const busyId = ref('');
const showDeleted = ref(false);
const current = ref(1);
const pageSize = 10;
const total = ref(0);
let loadGeneration = 0;

const title = computed(() => (
  props.scope === 'operator' ? '通话记录' : '网页语音 Demo 记录'
));
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));

const statusLabel = (status: string) => ({
  completed: '已完成',
  interrupted: '已中断',
  failed: '失败',
}[status] || status || '—');

const statusClass = (status: string) => (
  status === 'completed' ? 'is-success' : status === 'failed' ? 'is-error' : 'is-warning'
);

const formatDateTime = (value: string) => (
  value ? value.replace('T', ' ').replace('Z', ' UTC') : '—'
);

const shortId = (value: string) => (
  value && value.length > 14 ? value.slice(0, 12) + '…' : value || '—'
);

const recordKey = (record: NormalizedCallRecordListItem) => (
  String(record.aacId || record.callId)
);

const load = async () => {
  const generation = ++loadGeneration;
  loading.value = true;
  errorMessage.value = '';
  try {
    const response = await recordService.getList({
      current: current.value,
      page: current.value,
      pageSize,
      includeDeleted: showDeleted.value,
    });
    if (generation !== loadGeneration) return;
    records.value = response?.records || response?.list || [];
    total.value = Number(response?.total || 0);
  } catch {
    if (generation !== loadGeneration) return;
    records.value = [];
    total.value = 0;
    errorMessage.value = '无法加载 Demo 通话记录，请稍后重试。';
  } finally {
    if (generation === loadGeneration) loading.value = false;
  }
};

const viewDetail = (record: NormalizedCallRecordListItem) => {
  if (record.deleted) return;
  const name = props.scope === 'operator'
    ? 'AdminCallHistoryDetail'
    : 'UserCallHistoryDetail';
  void router.push({
    name,
    params: { id: recordKey(record) },
  });
};

const removeRecord = async (record: NormalizedCallRecordListItem) => {
  const id = recordKey(record);
  if (!id || busyId.value || record.deleted) return;
  if (!window.confirm('确认软删除这条通话记录？可勾选“显示已删除”后恢复。')) {
    return;
  }
  busyId.value = id;
  actionError.value = '';
  try {
    await recordService.remove(id);
    await load();
  } catch {
    actionError.value = '删除失败，请稍后重试。';
  } finally {
    busyId.value = '';
  }
};

const restoreRecord = async (record: NormalizedCallRecordListItem) => {
  const id = recordKey(record);
  if (!id || busyId.value || !record.deleted) return;
  busyId.value = id;
  actionError.value = '';
  try {
    await recordService.restore(id);
    await load();
  } catch {
    actionError.value = '恢复失败，请稍后重试。';
  } finally {
    busyId.value = '';
  }
};

const changePage = (next: number) => {
  if (next < 1 || next > totalPages.value || next === current.value) return;
  current.value = next;
  void load();
};

watch(showDeleted, () => {
  current.value = 1;
  void load();
});

onMounted(load);
</script>

<template>
  <main class="records-page">
    <header class="page-head">
      <div>
        <h1>{{ title }}</h1>
        <p>浏览器实时语音 Demo 生成的租户内记录，不是电话 CDR。</p>
      </div>
      <span class="demo-tag">Demo-only</span>
    </header>

    <aside v-if="scope === 'operator'" class="scope-notice">
      演示租户范围：当前使用配置的 Demo tenant header，仅供联调查看，不代表全局生产 RBAC。
    </aside>

    <section class="toolbar">
      <label class="toggle">
        <input v-model="showDeleted" type="checkbox" data-testid="show-deleted" />
        显示已删除
      </label>
      <p class="hint">
        已删除记录需先点「恢复」，才能打开详情继续修改。
      </p>
    </section>

    <section class="records-card">
      <div v-if="loading" class="state-box">正在加载通话记录…</div>
      <div v-else-if="errorMessage" class="state-box is-error" role="alert">
        {{ errorMessage }}
      </div>
      <div v-else-if="!records.length" class="state-box">
        {{ showDeleted ? '暂无通话记录（含已删除）' : '暂无网页语音 Demo 记录' }}
      </div>
      <div v-else class="records-table-wrap">
        <p v-if="actionError" class="inline-error" role="alert">{{ actionError }}</p>
        <table class="records-table">
          <thead>
            <tr>
              <th>记录 ID</th>
              <th>客服实例</th>
              <th>方向</th>
              <th>状态</th>
              <th>开始时间</th>
              <th>时长</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="record in records"
              :key="record.aacId"
              :class="{ 'is-deleted': record.deleted }"
            >
              <td>
                <code>{{ shortId(record.callId) }}</code>
                <span v-if="record.deleted" class="deleted-tag">已删除</span>
              </td>
              <td>{{ record.assistantName || '—' }}</td>
              <td><span class="direction-tag">网页语音</span></td>
              <td>
                <span class="status-tag" :class="statusClass(record.status)">
                  {{ statusLabel(record.status) }}
                </span>
              </td>
              <td>{{ formatDateTime(record.startedAt) }}</td>
              <td>{{ record.durationSec != null ? record.durationSec + ' 秒' : '—' }}</td>
              <td class="actions-cell">
                <button
                  v-if="!record.deleted"
                  type="button"
                  class="link-button"
                  @click="viewDetail(record)"
                >
                  查看详情
                </button>
                <button
                  v-if="!record.deleted"
                  type="button"
                  class="link-button is-danger"
                  :disabled="busyId === recordKey(record)"
                  @click="removeRecord(record)"
                >
                  {{ busyId === recordKey(record) ? '删除中…' : '删除' }}
                </button>
                <button
                  v-if="record.deleted"
                  type="button"
                  class="link-button"
                  data-testid="restore-button"
                  :disabled="busyId === recordKey(record)"
                  @click="restoreRecord(record)"
                >
                  {{ busyId === recordKey(record) ? '恢复中…' : '恢复' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <nav v-if="totalPages > 1" class="pagination" aria-label="通话记录分页">
      <button type="button" :disabled="current === 1" @click="changePage(current - 1)">
        上一页
      </button>
      <span>第 {{ current }} / {{ totalPages }} 页</span>
      <button
        type="button"
        :disabled="current === totalPages"
        @click="changePage(current + 1)"
      >
        下一页
      </button>
    </nav>
  </main>
</template>

<style scoped lang="less">
.records-page {
  display: grid;
  gap: 16px;
  max-width: 1180px;
  padding: 8px 4px 40px;
  margin: 0 auto;
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

h1 {
  margin: 0;
  color: var(--td-text-color-primary, #1d2129);
  font-size: 26px;
}

.page-head p,
.hint {
  margin: 7px 0 0;
  color: #687386;
  font-size: 13px;
}

.demo-tag,
.direction-tag,
.status-tag,
.deleted-tag {
  display: inline-flex;
  align-items: center;
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 12px;
}

.demo-tag {
  color: #5b6472;
  background: #eef1f5;
}

.toolbar,
.scope-notice,
.records-card {
  padding: 16px 18px;
  background: #fff;
  border: 1px solid #e6ebf1;
  border-radius: 12px;
}

.toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  cursor: pointer;
}

.state-box {
  padding: 28px 8px;
  color: #687386;
  text-align: center;
}

.state-box.is-error,
.inline-error {
  color: #a63737;
}

.records-table-wrap {
  overflow-x: auto;
}

.records-table {
  width: 100%;
  min-width: 860px;
  border-collapse: collapse;
}

th,
td {
  padding: 14px 16px;
  text-align: left;
  border-bottom: 1px solid #edf0f3;
}

th {
  color: #687386;
  font-weight: 600;
  font-size: 12px;
  background: #f7f9fc;
}

td {
  color: #2d3748;
  font-size: 14px;
}

tr.is-deleted td {
  background: #fbfbfc;
  color: #8a93a3;
}

.deleted-tag {
  margin-left: 8px;
  color: #8a4b4b;
  background: #fdeeee;
}

.status-tag.is-success {
  color: #176642;
  background: #e8f8f0;
}

.status-tag.is-warning {
  color: #775411;
  background: #fff5d9;
}

.status-tag.is-error {
  color: #a13a3a;
  background: #fff0f0;
}

.actions-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.link-button {
  padding: 0;
  color: var(--td-brand-color, #0052d9);
  background: transparent;
  border: 0;
  cursor: pointer;
}

.link-button.is-danger {
  color: #a63737;
}

.link-button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  color: #687386;
  font-size: 13px;
}

.pagination button {
  min-height: 34px;
  padding: 0 12px;
  background: #fff;
  border: 1px solid #d7dde5;
  border-radius: 7px;
}

@media (max-width: 680px) {
  .page-head {
    flex-direction: column;
  }
}
</style>
