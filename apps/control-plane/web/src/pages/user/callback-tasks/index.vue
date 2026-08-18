<template>
  <main class="callback-page">
    <header class="page-head">
      <div>
        <h1>回拨任务</h1>
        <p>租户真实回拨队列 · 本阶段不发起真实外呼</p>
      </div>
      <button type="button" class="primary" data-testid="new-callback" @click="showForm = !showForm">
        {{ showForm ? '收起' : '新建回拨' }}
      </button>
    </header>

    <form v-if="showForm" class="create-form" @submit.prevent="createTask">
      <label>电话<input v-model="form.callerPhone" required data-testid="cb-phone" /></label>
      <label>原因<input v-model="form.reason" required data-testid="cb-reason" /></label>
      <label>摘要<textarea v-model="form.summary" rows="3" data-testid="cb-summary" /></label>
      <button type="submit" class="primary" :disabled="saving" data-testid="cb-submit">
        {{ saving ? '保存中…' : '创建' }}
      </button>
      <p v-if="formError" class="error" role="alert">{{ formError }}</p>
    </form>

    <div v-if="loading" class="empty">加载中…</div>
    <div v-else-if="loadError" class="empty error" role="alert">{{ loadError }}</div>
    <div v-else-if="!list.length" class="empty">暂无回拨任务</div>
    <div v-else class="list">
      <article v-for="row in list" :key="row.id" class="card" data-testid="callback-row">
        <div>
          <div class="top">
            <strong>{{ row.reason }}</strong>
            <span class="status">{{ statusLabel(row.status) }}</span>
          </div>
          <p>{{ row.callerPhone }}</p>
          <p v-if="row.summary" class="summary">{{ row.summary }}</p>
        </div>
        <div class="actions">
          <button
            v-if="row.status === 'open'"
            type="button"
            data-testid="complete-callback"
            @click="complete(row)"
          >
            完成
          </button>
          <button
            v-if="row.status === 'done'"
            type="button"
            data-testid="reopen-callback"
            @click="reopen(row)"
          >
            重开
          </button>
        </div>
      </article>
    </div>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { TenantCallbackService } from '@/api/platform';

const svc = new TenantCallbackService();
const loading = ref(true);
const saving = ref(false);
const showForm = ref(false);
const loadError = ref('');
const formError = ref('');
const list = ref<any[]>([]);
const form = ref({
  callerPhone: '',
  reason: '',
  summary: '',
});

function statusLabel(status: string) {
  return ({ open: '待回拨', done: '已完成', cancelled: '已取消' } as any)[status] || status;
}

async function load() {
  loading.value = true;
  loadError.value = '';
  try {
    const res = await svc.list();
    list.value = res.list || [];
  } catch (e: any) {
    list.value = [];
    loadError.value = e?.message || '加载失败';
  } finally {
    loading.value = false;
  }
}

async function createTask() {
  saving.value = true;
  formError.value = '';
  try {
    await svc.create({
      callerPhone: form.value.callerPhone,
      reason: form.value.reason,
      summary: form.value.summary,
    });
    form.value = { callerPhone: '', reason: '', summary: '' };
    showForm.value = false;
    await load();
  } catch (e: any) {
    formError.value = e?.message || '创建失败';
  } finally {
    saving.value = false;
  }
}

async function complete(row: any) {
  await svc.markDone(row.id);
  await load();
}

async function reopen(row: any) {
  await svc.reopen(row.id);
  await load();
}

onMounted(load);
</script>

<style scoped lang="less">
.callback-page {
  display: grid;
  gap: 16px;
  max-width: 960px;
  margin: 0 auto;
  padding: 8px 4px 40px;
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
}

.page-head p {
  margin: 7px 0 0;
  color: var(--td-text-color-secondary, #5e626b);
}

.primary {
  border: 0;
  border-radius: 7px;
  padding: 9px 14px;
  background: var(--demo-primary, #0052d9);
  color: #fff;
  font-weight: 700;
  cursor: pointer;
}

.create-form {
  display: grid;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--demo-line, #e5e6eb);
  border-radius: 12px;
  background: #fff;
  label {
    display: grid;
    gap: 4px;
    font-size: 12px;
    color: #5e626b;
  }
  input, textarea {
    padding: 8px 10px;
    border: 1px solid #e5e6eb;
    border-radius: 6px;
    font: inherit;
  }
}

.list {
  display: grid;
  gap: 10px;
}

.card {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid #e5e6eb;
  border-radius: 12px;
  background: #fff;
}

.top {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.status {
  font-size: 12px;
  font-weight: 700;
  color: #0052d9;
  background: #e8f1ff;
  border-radius: 999px;
  padding: 2px 8px;
}

.summary, .empty, .card p {
  margin: 6px 0 0;
  color: #5e626b;
  font-size: 13px;
}

.actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  button {
    border: 1px solid #e5e6eb;
    background: #fff;
    border-radius: 6px;
    padding: 6px 10px;
    cursor: pointer;
  }
}

.error { color: #c62828; }
</style>
