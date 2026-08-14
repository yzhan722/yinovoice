<template>
  <div class="kb-page">
    <div class="page-head">
      <div>
        <h1 class="title">知识库</h1>
        <p class="sub">
          可切换客服音色，并编辑业务知识 Prompt。底层对话逻辑由平台管理，此处只读展示全文。
          资料列表仍为演示框架，尚未接入实时语音检索增强。
        </p>
      </div>
      <t-button theme="primary" @click="uploadVisible = true">上传</t-button>
    </div>

    <div v-if="promptLoading" class="prompt-state card-block">加载配置…</div>
    <div v-else-if="!instance" class="prompt-state card-block">
      暂无语音实例
      <t-button size="small" variant="outline" class="retry-btn" @click="loadPrompt">重试</t-button>
    </div>
    <template v-else>
      <section class="prompt-card">
        <div class="prompt-head">
          <h2 class="prompt-title">客服音色</h2>
          <p class="prompt-hint">切换后点击保存，下次通话生效。</p>
        </div>
        <div class="voice-row">
          <t-select
            v-model="ttsVoice"
            :options="TTS_VOICE_OPTIONS"
            :disabled="!voiceEditing"
            style="width: 280px; max-width: 100%"
          />
          <div class="prompt-actions inline">
            <template v-if="!voiceEditing">
              <t-button theme="primary" variant="outline" @click="voiceEditing = true">编辑</t-button>
            </template>
            <template v-else>
              <t-button variant="outline" :disabled="voiceSaving" @click="cancelVoiceEdit">取消</t-button>
              <t-button theme="primary" :loading="voiceSaving" @click="saveVoice">保存</t-button>
            </template>
          </div>
        </div>
      </section>

      <section class="prompt-card">
        <div class="prompt-head">
          <h2 class="prompt-title">底层逻辑 Prompt（只读）</h2>
          <p class="prompt-hint">由管理员维护的对话规则与话术框架，用户不可修改。</p>
        </div>
        <t-textarea
          :value="platformPrompt"
          readonly
          :autosize="{ minRows: 8, maxRows: 18 }"
        />
      </section>

      <section class="prompt-card">
        <div class="prompt-head">
          <h2 class="prompt-title">业务知识 Prompt</h2>
          <p class="prompt-hint">机构信息、业务知识与补充提示词；保存后下次通话生效。</p>
        </div>
        <t-textarea
          v-model="tenantPrompt"
          :readonly="!tenantEditing"
          :maxlength="8000"
          :autosize="{ minRows: 10, maxRows: 22 }"
          placeholder="填写机构信息、业务边界与回答规则…"
        />
        <div class="prompt-actions">
          <span class="char-count">{{ tenantPrompt.length }} / 8000</span>
          <div class="btn-group">
            <template v-if="!tenantEditing">
              <t-button theme="primary" variant="outline" @click="tenantEditing = true">编辑</t-button>
            </template>
            <template v-else>
              <t-button variant="outline" :disabled="tenantSaving" @click="cancelTenantEdit">取消</t-button>
              <t-button theme="primary" :loading="tenantSaving" @click="saveTenantPrompt">保存</t-button>
            </template>
          </div>
        </div>
      </section>
    </template>

    <t-table
      row-key="filId"
      :data="files"
      :columns="columns"
      :loading="loading"
      empty="暂无文件"
    >
      <template #filSizeBytes="{ row }">{{ formatSize(row.filSizeBytes) }}</template>
      <template #filExtStatus="{ row }">
        <t-tag
          :theme="row.filExtStatus === 'done' ? 'success' : 'warning'"
          variant="light"
          size="small"
        >
          {{ row.filExtStatus === 'done' ? '就绪' : '处理中' }}
        </t-tag>
      </template>
    </t-table>

    <t-dialog
      v-model:visible="uploadVisible"
      header="上传文件"
      :confirm-btn="{ content: '上传', loading: uploading }"
      @confirm="doUpload"
    >
      <t-upload
        v-model="uploadFiles"
        theme="file"
        :auto-upload="false"
        :max="1"
        accept=".pdf,.txt,.docx,.csv"
      />
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { MessagePlugin } from 'tdesign-vue-next';
import {
  CUSTOMER_SERVICE_VERSION_CONFLICT,
  RealtimeVoiceService,
  TenantKnowledgeService,
  TTS_VOICE_OPTIONS,
} from '@/api/platform';
import {
  loadStoredInstanceId,
  resolveInstanceSelection,
  storeInstanceId,
} from '@/api/platform/instanceSelection';
import type {
  CustomerServiceInstance,
  TtsVoiceId,
} from '@/api/platform/RealtimeVoiceService';

const svc = new TenantKnowledgeService();
const voiceSvc = new RealtimeVoiceService();
const route = useRoute();
const loading = ref(false);
const uploading = ref(false);
const files = ref<any[]>([]);
const uploadVisible = ref(false);
const uploadFiles = ref<any[]>([]);

const promptLoading = ref(false);
const instance = ref<CustomerServiceInstance | null>(null);
const platformPrompt = ref('');
const tenantPrompt = ref('');
const tenantDraft = ref('');
const ttsVoice = ref<TtsVoiceId>('longanqian');
const voiceDraft = ref<TtsVoiceId>('longanqian');

const tenantEditing = ref(false);
const tenantSaving = ref(false);
const voiceEditing = ref(false);
const voiceSaving = ref(false);
const selectedInstanceId = ref<string | null>(null);

const columns = [
  { title: '文件名', colKey: 'filName', ellipsis: true },
  { title: '大小', colKey: 'filSizeBytes', width: 100 },
  { title: '状态', colKey: 'filExtStatus', width: 100 },
  { title: '时间', colKey: 'filCreateTime', width: 180 },
];

function formatSize(n: number) {
  if (!n) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function applyInstance(current: CustomerServiceInstance) {
  instance.value = current;
  platformPrompt.value = current.platform_prompt || '';
  tenantPrompt.value = current.tenant_prompt || '';
  tenantDraft.value = tenantPrompt.value;
  const voice = (current.voice?.tts_voice || 'longanqian') as TtsVoiceId;
  ttsVoice.value = voice;
  voiceDraft.value = voice;
  tenantEditing.value = false;
  voiceEditing.value = false;
}

async function load() {
  loading.value = true;
  try {
    const res: any = await svc.getList({});
    files.value = res?.records || [];
  } catch (_) {
    files.value = [];
    MessagePlugin.error('加载失败');
  } finally {
    loading.value = false;
  }
}

async function loadPrompt() {
  promptLoading.value = true;
  try {
    const page = await voiceSvc.listCustomerServices({ limit: 100, offset: 0 });
    selectedInstanceId.value = resolveInstanceSelection({
      availableIds: page.items.map((item) => item.id),
      routeId: typeof route.query.instanceId === 'string' ? route.query.instanceId : null,
      storedId: loadStoredInstanceId(),
    });
    storeInstanceId(selectedInstanceId.value);
    if (!selectedInstanceId.value) {
      instance.value = null;
      return;
    }
    const current = await voiceSvc.getCustomerService(selectedInstanceId.value);
    applyInstance(current);
  } catch (_) {
    instance.value = null;
    MessagePlugin.error('配置加载失败');
  } finally {
    promptLoading.value = false;
  }
}

function cancelTenantEdit() {
  tenantPrompt.value = tenantDraft.value;
  tenantEditing.value = false;
}

function cancelVoiceEdit() {
  ttsVoice.value = voiceDraft.value;
  voiceEditing.value = false;
}

async function persistUpdate(partial: {
  tenant_prompt?: string;
  voice?: CustomerServiceInstance['voice'];
  successMessage: string;
}) {
  const current = instance.value;
  if (!current) return null;
  return voiceSvc.updateCustomerService(current.id, {
    expected_version: current.version,
    display_name: current.display_name,
    organization_name: current.organization_name,
    greeting: current.greeting,
    platform_prompt: current.platform_prompt || '',
    tenant_prompt: partial.tenant_prompt ?? current.tenant_prompt,
    voice: partial.voice ?? current.voice,
    response: current.response,
  });
}

async function saveTenantPrompt() {
  const current = instance.value;
  if (!current) return;
  if (tenantPrompt.value.length > 8000) {
    MessagePlugin.warning('业务 Prompt 不能超过 8000 字');
    return;
  }
  tenantSaving.value = true;
  try {
    const updated = await persistUpdate({
      tenant_prompt: tenantPrompt.value,
      successMessage: '',
    });
    if (!updated) return;
    applyInstance(updated);
    MessagePlugin.success('业务 Prompt 已保存，下次通话生效');
  } catch (error) {
    const message = error instanceof Error ? error.message : '';
    if (message === CUSTOMER_SERVICE_VERSION_CONFLICT) {
      MessagePlugin.warning(CUSTOMER_SERVICE_VERSION_CONFLICT);
      await loadPrompt();
    } else {
      MessagePlugin.error(message || '保存失败');
    }
  } finally {
    tenantSaving.value = false;
  }
}

async function saveVoice() {
  const current = instance.value;
  if (!current) return;
  voiceSaving.value = true;
  try {
    const updated = await persistUpdate({
      voice: { ...current.voice, tts_voice: ttsVoice.value },
      successMessage: '',
    });
    if (!updated) return;
    applyInstance(updated);
    MessagePlugin.success('客服音色已保存，下次通话生效');
  } catch (error) {
    const message = error instanceof Error ? error.message : '';
    if (message === CUSTOMER_SERVICE_VERSION_CONFLICT) {
      MessagePlugin.warning(CUSTOMER_SERVICE_VERSION_CONFLICT);
      await loadPrompt();
    } else {
      MessagePlugin.error(message || '保存失败');
    }
  } finally {
    voiceSaving.value = false;
  }
}

async function doUpload() {
  const file = uploadFiles.value?.[0]?.raw || uploadFiles.value?.[0];
  if (!file) {
    MessagePlugin.warning('请选择文件');
    return false;
  }
  uploading.value = true;
  try {
    await svc.uploadFile(file);
    MessagePlugin.success('已上传（演示）');
    uploadVisible.value = false;
    uploadFiles.value = [];
    await load();
  } catch (_) {
    MessagePlugin.error('上传失败');
  } finally {
    uploading.value = false;
  }
  return true;
}

onMounted(() => {
  void load();
  void loadPrompt();
});
</script>

<style scoped lang="less">
.kb-page {
  padding: 8px 4px 40px;
  max-width: 960px;
  margin: 0 auto;
  font-family: var(--demo-font);
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.title {
  margin: 0;
  font-size: 24px;
  font-weight: 800;
  color: var(--demo-ink);
}

.sub {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--demo-muted);
  max-width: 680px;
  line-height: 1.5;
}

.card-block,
.prompt-card {
  margin-bottom: 16px;
  padding: 16px 18px 14px;
  background: var(--demo-card);
  border-radius: var(--demo-radius);
  box-shadow: var(--demo-shadow);
}

.prompt-head {
  margin-bottom: 12px;
}

.prompt-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--demo-ink);
}

.prompt-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--demo-muted);
  line-height: 1.45;
}

.prompt-state {
  font-size: 13px;
  color: var(--demo-muted);
  display: flex;
  align-items: center;
  gap: 10px;
}

.retry-btn {
  margin-left: 4px;
}

.voice-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.prompt-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 10px;

  &.inline {
    margin-top: 0;
  }
}

.btn-group {
  display: flex;
  gap: 8px;
}

.char-count {
  font-size: 12px;
  color: var(--demo-muted);
}

:deep(.t-table) {
  background: var(--demo-card);
  border-radius: var(--demo-radius);
  overflow: hidden;
  box-shadow: var(--demo-shadow);
}

@media (max-width: 768px) {
  .kb-page {
    padding: 12px 4px 28px;
    max-width: 100%;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }

  .page-head {
    flex-direction: column;
    align-items: stretch;
  }

  .title {
    font-size: 20px;
  }

  :deep(.t-table) {
    min-width: 480px;
  }
}
</style>
