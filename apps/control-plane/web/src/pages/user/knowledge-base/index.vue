<template>
  <div class="kb-page">
    <div class="page-head">
      <div>
        <h1 class="title">知识库</h1>
        <p class="sub">
          业务知识条目会编译进当前实例的业务 Prompt，作为通话配置的事实来源。不检索 PDF，也不走实时 RAG。
          保存或写入 Prompt 后，可用下方发布/回滚做配置快照。
        </p>
      </div>
      <div class="head-actions">
        <t-button variant="outline" :disabled="!instance" @click="openCreate">新增条目</t-button>
        <t-button theme="primary" :disabled="!instance" @click="uploadVisible = true">上传 txt</t-button>
      </div>
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
          <p class="prompt-hint">机构信息与知识条目编译结果；标记之间的内容由「写入业务 Prompt」覆盖。</p>
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

      <section class="prompt-card">
        <div class="prompt-head">
          <h2 class="prompt-title">配置发布</h2>
          <p class="prompt-hint">
            当前通话使用上面这份配置。发布会留下快照；回滚会恢复快照并提升版本号。
            {{
              diff?.published_revision
                ? `最近发布为第 ${diff.published_revision} 版。`
                : '尚未发布基线，请先发布当前配置。'
            }}
          </p>
        </div>
        <p v-if="!diffChanges.length" class="prompt-hint">与最近发布相比没有未发布改动。</p>
        <ul v-else class="diff-list">
          <li v-for="change in diffChanges" :key="change.field">
            <strong>{{ change.field }}</strong>
            ：{{ formatDiffValue(change.before) }} → {{ formatDiffValue(change.after) }}
          </li>
        </ul>
        <div class="prompt-actions">
          <div class="btn-group">
            <t-select
              v-model="rollbackRevision"
              :options="revisionOptions"
              placeholder="选择回滚版本"
              style="width: 220px"
            />
            <t-button
              variant="outline"
              :disabled="!rollbackRevision"
              :loading="rollbackSaving"
              @click="rollbackConfig"
            >
              回滚
            </t-button>
          </div>
          <t-button theme="primary" :loading="publishSaving" @click="publishConfig">
            发布当前配置
          </t-button>
        </div>
      </section>
    </template>

    <t-table
      row-key="id"
      :data="documents"
      :columns="columns"
      :loading="loading"
      empty="暂无知识条目"
    >
      <template #updated_at="{ row }">{{ formatTime(row.updated_at) }}</template>
      <template #op="{ row }">
        <t-button size="small" variant="text" theme="primary" @click="openEdit(row)">编辑</t-button>
        <t-button size="small" variant="text" theme="danger" @click="removeDoc(row)">删除</t-button>
      </template>
    </t-table>
    <div class="table-actions">
      <t-button
        theme="primary"
        variant="outline"
        :disabled="!instance"
        :loading="applySaving"
        @click="applyKnowledge"
      >
        写入业务 Prompt
      </t-button>
    </div>

    <t-dialog
      v-model:visible="uploadVisible"
      header="上传 txt"
      :confirm-btn="{ content: '上传', loading: uploading }"
      @confirm="doUpload"
    >
      <t-upload
        v-model="uploadFiles"
        theme="file"
        :auto-upload="false"
        :max="1"
        accept=".txt,text/plain"
      />
    </t-dialog>

    <t-dialog
      v-model:visible="editVisible"
      :header="editingId ? '编辑知识条目' : '新增知识条目'"
      :confirm-btn="{ content: '保存', loading: docSaving }"
      @confirm="saveDocument"
    >
      <t-input v-model="editTitle" placeholder="标题" maxlength="80" />
      <t-textarea
        v-model="editBody"
        placeholder="正文"
        :maxlength="4000"
        :autosize="{ minRows: 6, maxRows: 14 }"
        style="margin-top: 12px"
      />
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
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
  ConfigDiffChange,
  ConfigRevision,
  CustomerServiceInstance,
  TtsVoiceId,
} from '@/api/platform/RealtimeVoiceService';

interface KnowledgeDoc {
  id: string;
  title: string;
  body: string;
  updated_at: string;
}

const svc = new TenantKnowledgeService();
const voiceSvc = new RealtimeVoiceService();
const route = useRoute();
const loading = ref(false);
const uploading = ref(false);
const documents = ref<KnowledgeDoc[]>([]);
const uploadVisible = ref(false);
const uploadFiles = ref<any[]>([]);
const editVisible = ref(false);
const editingId = ref<string | null>(null);
const editTitle = ref('');
const editBody = ref('');
const docSaving = ref(false);
const applySaving = ref(false);
const publishSaving = ref(false);
const rollbackSaving = ref(false);

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
const diff = ref<{ published_revision: number | null; changes: ConfigDiffChange[] } | null>(null);
const revisions = ref<ConfigRevision[]>([]);
const rollbackRevision = ref<number | undefined>(undefined);

const columns = [
  { title: '标题', colKey: 'title', ellipsis: true },
  { title: '更新时间', colKey: 'updated_at', width: 180 },
  { title: '操作', colKey: 'op', width: 140 },
];

const diffChanges = computed(() => diff.value?.changes || []);
const revisionOptions = computed(() =>
  revisions.value.map((item) => ({
    label: `第 ${item.revision} 版（${item.source}）`,
    value: item.revision,
  })),
);

function formatTime(value: string) {
  if (!value) return '—';
  return value.replace('T', ' ').slice(0, 19);
}

function formatDiffValue(value: unknown) {
  if (value == null || value === '') return '（空）';
  const text = String(value);
  return text.length > 80 ? `${text.slice(0, 80)}…` : text;
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

async function loadDocuments() {
  if (!selectedInstanceId.value) {
    documents.value = [];
    return;
  }
  loading.value = true;
  try {
    const res = await svc.list(selectedInstanceId.value);
    documents.value = res.items || [];
  } catch (_) {
    documents.value = [];
    MessagePlugin.error('知识条目加载失败');
  } finally {
    loading.value = false;
  }
}

async function loadPublishState() {
  if (!selectedInstanceId.value) {
    diff.value = null;
    revisions.value = [];
    return;
  }
  try {
    const [nextDiff, nextRevisions] = await Promise.all([
      voiceSvc.getConfigDiff(selectedInstanceId.value),
      voiceSvc.listConfigRevisions(selectedInstanceId.value),
    ]);
    diff.value = nextDiff;
    revisions.value = nextRevisions.items || [];
  } catch (_) {
    diff.value = null;
    revisions.value = [];
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
    await Promise.all([loadDocuments(), loadPublishState()]);
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
    insights_profile: current.insights_profile ?? null,
  });
}

async function afterConfigChanged(updated: CustomerServiceInstance) {
  applyInstance(updated);
  await loadPublishState();
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
    const updated = await persistUpdate({ tenant_prompt: tenantPrompt.value });
    if (!updated) return;
    await afterConfigChanged(updated);
    MessagePlugin.success('业务 Prompt 已保存，下次通话生效');
  } catch (error) {
    await handleConfigError(error, '保存失败');
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
    });
    if (!updated) return;
    await afterConfigChanged(updated);
    MessagePlugin.success('客服音色已保存，下次通话生效');
  } catch (error) {
    await handleConfigError(error, '保存失败');
  } finally {
    voiceSaving.value = false;
  }
}

async function handleConfigError(error: unknown, fallback: string) {
  const message = error instanceof Error ? error.message : '';
  if (message === CUSTOMER_SERVICE_VERSION_CONFLICT) {
    MessagePlugin.warning(CUSTOMER_SERVICE_VERSION_CONFLICT);
    await loadPrompt();
    return;
  }
  MessagePlugin.error(message || fallback);
}

function openCreate() {
  editingId.value = null;
  editTitle.value = '';
  editBody.value = '';
  editVisible.value = true;
}

function openEdit(row: KnowledgeDoc) {
  editingId.value = row.id;
  editTitle.value = row.title;
  editBody.value = row.body;
  editVisible.value = true;
}

async function saveDocument() {
  if (!selectedInstanceId.value) return false;
  if (!editTitle.value.trim() || !editBody.value.trim()) {
    MessagePlugin.warning('请填写标题和正文');
    return false;
  }
  docSaving.value = true;
  try {
    const payload = { title: editTitle.value.trim(), body: editBody.value.trim() };
    if (editingId.value) {
      await svc.update(selectedInstanceId.value, editingId.value, payload);
    } else {
      await svc.create(selectedInstanceId.value, payload);
    }
    editVisible.value = false;
    await loadDocuments();
    MessagePlugin.success('知识条目已保存');
  } catch (_) {
    MessagePlugin.error('保存失败');
  } finally {
    docSaving.value = false;
  }
  return true;
}

async function removeDoc(row: KnowledgeDoc) {
  if (!selectedInstanceId.value) return;
  try {
    await svc.remove(selectedInstanceId.value, row.id);
    await loadDocuments();
    MessagePlugin.success('已删除');
  } catch (_) {
    MessagePlugin.error('删除失败');
  }
}

async function applyKnowledge() {
  const current = instance.value;
  if (!current || !selectedInstanceId.value) return;
  applySaving.value = true;
  try {
    const updated = await svc.apply(selectedInstanceId.value, current.version);
    await afterConfigChanged(updated);
    MessagePlugin.success('已写入业务 Prompt，下次通话生效');
  } catch (error) {
    await handleConfigError(error, '写入失败');
  } finally {
    applySaving.value = false;
  }
}

async function publishConfig() {
  if (!selectedInstanceId.value) return;
  publishSaving.value = true;
  try {
    await voiceSvc.publishConfig(selectedInstanceId.value);
    await loadPublishState();
    MessagePlugin.success('已发布当前配置快照');
  } catch (_) {
    MessagePlugin.error('发布失败');
  } finally {
    publishSaving.value = false;
  }
}

async function rollbackConfig() {
  const current = instance.value;
  if (!current || !selectedInstanceId.value || !rollbackRevision.value) return;
  rollbackSaving.value = true;
  try {
    const result = await voiceSvc.rollbackConfig(
      selectedInstanceId.value,
      rollbackRevision.value,
      current.version,
    );
    await afterConfigChanged(result.instance);
    MessagePlugin.success('已回滚并写入当前配置');
  } catch (error) {
    await handleConfigError(error, '回滚失败');
  } finally {
    rollbackSaving.value = false;
  }
}

async function doUpload() {
  const file = uploadFiles.value?.[0]?.raw || uploadFiles.value?.[0];
  if (!file) {
    MessagePlugin.warning('请选择文件');
    return false;
  }
  const name = String(file.name || '');
  if (!name.toLowerCase().endsWith('.txt')) {
    MessagePlugin.warning('仅支持 .txt 文本');
    return false;
  }
  if (!selectedInstanceId.value) return false;
  uploading.value = true;
  try {
    const body = await file.text();
    const title = name.replace(/\.txt$/i, '').trim() || '未命名条目';
    await svc.create(selectedInstanceId.value, { title, body });
    MessagePlugin.success('已上传并保存为知识条目');
    uploadVisible.value = false;
    uploadFiles.value = [];
    await loadDocuments();
  } catch (_) {
    MessagePlugin.error('上传失败');
  } finally {
    uploading.value = false;
  }
  return true;
}

onMounted(() => {
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

.head-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
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
  align-items: center;
}

.char-count {
  font-size: 12px;
  color: var(--demo-muted);
}

.diff-list {
  margin: 0 0 8px;
  padding-left: 18px;
  font-size: 13px;
  color: var(--demo-ink);
  line-height: 1.5;
}

.table-actions {
  display: flex;
  justify-content: flex-end;
  margin: 12px 0 24px;
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
