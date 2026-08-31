<template>
  <div class="demo-page">
    <div class="page-head">
      <div>
        <h1 class="demo-page-title">电话号码</h1>
        <p class="demo-page-sub">E.164 入站号码绑定当前租户实例 · LiveKit SIP</p>
      </div>
      <button type="button" class="primary" data-testid="new-phone" @click="showForm = !showForm">
        {{ showForm ? '收起' : '绑定号码' }}
      </button>
    </div>

    <form v-if="showForm" class="create-form demo-card" @submit.prevent="createNumber">
      <label>E.164 号码<input v-model="form.e164Number" required placeholder="+61400000001" data-testid="phone-e164" /></label>
      <label>
        绑定实例
        <select v-model="form.instanceId" required data-testid="phone-instance">
          <option value="" disabled>选择实例</option>
          <option v-for="item in instances" :key="item.id" :value="item.id">
            {{ item.display_name || item.id }}
          </option>
        </select>
      </label>
      <button type="submit" class="primary" :disabled="saving">{{ saving ? '保存中…' : '创建' }}</button>
      <p v-if="formError" class="error" role="alert">{{ formError }}</p>
    </form>

    <article v-for="row in list" :key="row.id" class="demo-list-card demo-card" data-testid="phone-row">
      <div>
        <h3>{{ row.e164_number }}</h3>
        <p>{{ row.enabled ? '已启用' : '已禁用' }} · 实例 {{ row.voice_agent_instance_id }}</p>
      </div>
      <button type="button" data-testid="delete-phone" @click="removeNumber(row)">解绑</button>
    </article>
    <div v-if="loading" class="empty">加载中…</div>
    <div v-else-if="!list.length" class="empty">暂无绑定号码</div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { MessagePlugin } from 'tdesign-vue-next';
import { RealtimeVoiceService, TenantPhoneNumberService } from '@/api/platform';

const phones = new TenantPhoneNumberService();
const voice = new RealtimeVoiceService();
const loading = ref(false);
const saving = ref(false);
const showForm = ref(false);
const formError = ref('');
const list = ref<any[]>([]);
const instances = ref<any[]>([]);
const form = ref({ e164Number: '', instanceId: '' });

async function load() {
  loading.value = true;
  try {
    const [numbers, services] = await Promise.all([
      phones.list(),
      voice.listCustomerServices(),
    ]);
    list.value = Array.isArray(numbers) ? numbers : numbers.items || [];
    instances.value = services.items || [];
    if (!form.value.instanceId && instances.value[0]) {
      form.value.instanceId = instances.value[0].id;
    }
  } catch (error: any) {
    MessagePlugin.error(error?.message || '无法加载号码');
  } finally {
    loading.value = false;
  }
}

async function createNumber() {
  saving.value = true;
  formError.value = '';
  try {
    await phones.create({
      e164Number: form.value.e164Number,
      instanceId: form.value.instanceId,
    });
    showForm.value = false;
    form.value.e164Number = '';
    await load();
  } catch (error: any) {
    formError.value = error?.message || '创建失败';
  } finally {
    saving.value = false;
  }
}

async function removeNumber(row: any) {
  if (!window.confirm(`确认解绑 ${row.e164_number}？`)) return;
  try {
    await phones.remove(row.id);
    await load();
  } catch (error: any) {
    MessagePlugin.error(error?.message || '解绑失败');
  }
}

onMounted(load);
</script>

<style scoped lang="less">
.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.primary {
  border: 0;
  border-radius: 7px;
  padding: 9px 14px;
  background: var(--demo-primary);
  color: #fff;
  font-weight: 700;
  cursor: pointer;
}
.create-form {
  display: grid;
  gap: 10px;
  padding: 14px;
  margin-bottom: 14px;
  label {
    display: grid;
    gap: 4px;
    font-size: 12px;
    color: var(--demo-muted);
  }
  input, select {
    padding: 8px 10px;
    border: 1px solid var(--demo-line);
    border-radius: 6px;
  }
}
.error { color: #c62828; margin: 0; font-size: 13px; }
.demo-list-card {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 14px;
  margin-bottom: 10px;
  button {
    border: 1px solid var(--demo-line);
    background: #fff;
    border-radius: 6px;
    padding: 6px 10px;
    cursor: pointer;
  }
}
.empty { padding: 24px; text-align: center; color: var(--demo-muted); }
h3 { margin: 0; font-size: 16px; }
p { margin: 6px 0 0; color: var(--demo-muted); font-size: 12px; }
</style>
