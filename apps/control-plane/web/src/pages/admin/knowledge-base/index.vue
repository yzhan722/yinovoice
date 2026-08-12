<template>
  <div class="admin-knowledge-base">
    <t-card title="底层逻辑 Prompt" :bordered="false" class="platform-prompt-card">
      <p class="platform-prompt-hint">
        管理员可编辑对话规则、话术框架与分诊引导。租户用户只能只读查看，不能修改。
      </p>
      <div v-if="promptLoading" class="platform-prompt-state">加载中…</div>
      <div v-else-if="!csInstance" class="platform-prompt-state">
        暂无语音实例
        <t-button size="small" variant="outline" @click="loadPlatformPrompt">重试</t-button>
      </div>
      <template v-else>
        <t-textarea
          v-model="platformPrompt"
          :readonly="!platformEditing"
          :maxlength="8000"
          :autosize="{ minRows: 10, maxRows: 22 }"
          placeholder="填写平台底层对话逻辑与话术…"
        />
        <div class="platform-prompt-actions">
          <span class="char-count">{{ platformPrompt.length }} / 8000</span>
          <div class="btn-group">
            <template v-if="!platformEditing">
              <t-button theme="primary" variant="outline" @click="platformEditing = true">编辑</t-button>
            </template>
            <template v-else>
              <t-button variant="outline" :disabled="platformSaving" @click="cancelPlatformEdit">取消</t-button>
              <t-button theme="primary" :loading="platformSaving" @click="savePlatformPrompt">保存</t-button>
            </template>
          </div>
        </div>
      </template>
    </t-card>

    <t-card :title="t('pages.aiVoice.admin.knowledgeBase.title')" :bordered="false">
      <!-- 搜索表单 -->
      <div class="search-form-container">
        <t-form :data="searchForm" label-width="120px" @submit="handleSearch" @reset="handleReset">
          <t-row :gutter="16">
            <t-col :span="6">
              <t-form-item :label="t('pages.aiVoice.admin.knowledgeBase.fileName')" class="form-item-spacing">
                <t-input
                  v-model="searchForm.filName"
                  :placeholder="t('pages.aiVoice.admin.knowledgeBase.fileNamePlaceholder')"
                  clearable
                />
              </t-form-item>
            </t-col>
            <t-col :span="6">
              <t-form-item :label="t('pages.aiVoice.admin.knowledgeBase.extStatus')" class="form-item-spacing">
                <t-select
                  v-model="searchForm.filExtStatus"
                  :options="extStatusOptions"
                  :placeholder="t('pages.aiVoice.admin.knowledgeBase.allExtStatus')"
                  clearable
                  style="width: 100%"
                />
              </t-form-item>
            </t-col>
          </t-row>
          <t-row :gutter="16" class="search-actions-row">
            <t-col :span="24">
              <div class="search-actions">
                <t-space align="start">
                  <t-button theme="primary" type="submit">
                    {{ t('pages.aiVoice.admin.knowledgeBase.search') }}
                  </t-button>
                  <t-button theme="default" type="reset">
                    {{ t('pages.aiVoice.admin.knowledgeBase.reset') }}
                  </t-button>
                </t-space>
              </div>
            </t-col>
          </t-row>
        </t-form>
      </div>

      <!-- 操作工具栏 -->
      <div class="toolbar-container">
        <t-space>
          <t-button theme="primary" @click="handleUpload">
            {{ t('pages.aiVoice.admin.knowledgeBase.upload') }}
          </t-button>
          <t-button theme="success" :loading="syncing" @click="handleSync">
            <template #icon>
              <RefreshIcon />
            </template>
            {{ t('pages.aiVoice.admin.knowledgeBase.sync') }}
          </t-button>
          <t-select
            v-model="sortBy"
            :options="sortOptions"
            :placeholder="t('pages.aiVoice.admin.knowledgeBase.sortBy')"
            style="width: 150px"
            clearable
            @change="handleSortChange"
          />
        </t-space>
      </div>

      <!-- 文件列表 -->
      <t-table
        :data="tableData"
        :columns="columns"
        :loading="loading"
        :pagination="pagination"
        :empty="t('pages.aiVoice.admin.knowledgeBase.empty')"
        @page-change="handlePageChange"
      >
        <template #filName="{ row }">
          <t-link theme="primary" @click="handleViewAssistants(row)">
            {{ row.filName || '-' }}
          </t-link>
        </template>
        <template #filSizeBytes="{ row }">
          {{ formatFileSize(row.filSizeBytes || 0) }}
        </template>
        <template #filExtStatus="{ row }">
          <t-tag
            :theme="row.filExtStatus === 'done' ? 'success' : row.filExtStatus === 'failed' ? 'danger' : 'warning'"
            variant="light"
          >
            {{ extStatusLabel(row.filExtStatus) }}
          </t-tag>
        </template>
        <template #op="{ row }">
          <t-space>
            <t-link theme="primary" @click="handleViewAssistants(row)">
              {{ t('pages.aiVoice.admin.knowledgeBase.viewAssistants') }}
            </t-link>
            <t-link v-if="row.filUrl" theme="primary" @click="handleDownload(row)">
              {{ t('pages.aiVoice.admin.knowledgeBase.download') }}
            </t-link>
          </t-space>
        </template>
      </t-table>
    </t-card>

    <!-- 上传对话框 -->
    <t-dialog
      v-model:visible="uploadVisible"
      :header="t('pages.aiVoice.admin.knowledgeBase.uploadFile')"
      width="600px"
      @confirm="handleUploadSubmit"
    >
      <t-upload
        v-model="uploadFiles"
        :action="''"
        accept=".pdf,.docx,.txt,.csv"
        :max="1"
        :auto-upload="false"
        :tips="t('pages.aiVoice.admin.knowledgeBase.supportedFormats')"
        :before-upload="beforeUpload"
      />
    </t-dialog>

    <!-- 查看关联 Assistant 对话框 -->
    <t-dialog
      v-model:visible="assistantsVisible"
      :header="t('pages.aiVoice.admin.knowledgeBase.associatedAssistants')"
      width="800px"
    >
      <t-table
        :data="assistantsData"
        :columns="assistantsColumns"
        :loading="assistantsLoading"
        :empty="t('pages.aiVoice.admin.knowledgeBase.noAssistants')"
      />
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { MessagePlugin, PrimaryTableCol, DialogPlugin } from 'tdesign-vue-next';
import { ref, reactive, onMounted, onUnmounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { RefreshIcon } from 'tdesign-icons-vue-next';
import {
  CUSTOMER_SERVICE_VERSION_CONFLICT,
  DEMO_CUSTOMER_SERVICE_ID,
  OperatorKnowledgeService as AdminKnowledgeBaseService,
  RealtimeVoiceService,
} from '@/api/platform';
import type { CustomerServiceInstance } from '@/api/platform/RealtimeVoiceService';

const { t } = useI18n();
const knowledgeBaseService = new AdminKnowledgeBaseService();
const voiceSvc = new RealtimeVoiceService();

const promptLoading = ref(false);
const platformSaving = ref(false);
const platformEditing = ref(false);
const csInstance = ref<CustomerServiceInstance | null>(null);
const platformPrompt = ref('');
const platformDraft = ref('');

async function loadPlatformPrompt() {
  promptLoading.value = true;
  try {
    const current = await voiceSvc.getCustomerService(DEMO_CUSTOMER_SERVICE_ID);
    csInstance.value = current;
    platformPrompt.value = current.platform_prompt || '';
    platformDraft.value = platformPrompt.value;
    platformEditing.value = false;
  } catch (_) {
    csInstance.value = null;
    MessagePlugin.error('底层 Prompt 加载失败');
  } finally {
    promptLoading.value = false;
  }
}

function cancelPlatformEdit() {
  platformPrompt.value = platformDraft.value;
  platformEditing.value = false;
}

async function savePlatformPrompt() {
  const current = csInstance.value;
  if (!current) return;
  if (platformPrompt.value.length > 8000) {
    MessagePlugin.warning('底层 Prompt 不能超过 8000 字');
    return;
  }
  platformSaving.value = true;
  try {
    const updated = await voiceSvc.updateCustomerService(current.id, {
      expected_version: current.version,
      display_name: current.display_name,
      organization_name: current.organization_name,
      greeting: current.greeting,
      platform_prompt: platformPrompt.value,
      tenant_prompt: current.tenant_prompt || '',
      voice: current.voice,
      response: current.response,
    });
    csInstance.value = updated;
    platformPrompt.value = updated.platform_prompt || '';
    platformDraft.value = platformPrompt.value;
    platformEditing.value = false;
    MessagePlugin.success('底层 Prompt 已保存，下次通话生效');
  } catch (error) {
    const message = error instanceof Error ? error.message : '';
    if (message === CUSTOMER_SERVICE_VERSION_CONFLICT) {
      MessagePlugin.warning(CUSTOMER_SERVICE_VERSION_CONFLICT);
      await loadPlatformPrompt();
    } else {
      MessagePlugin.error(message || '保存失败');
    }
  } finally {
    platformSaving.value = false;
  }
}

const searchForm = reactive({
  filName: '',
  filExtStatus: null as string | null,
});

const extStatusOptions = [
  { label: 'processing', value: 'processing' },
  { label: 'done', value: 'done' },
  { label: 'failed', value: 'failed' },
];

const loading = ref(false);
const syncing = ref(false);
const tableData = ref<any[]>([]);
const uploadVisible = ref(false);
const uploadFiles = ref<any[]>([]);
const assistantsVisible = ref(false);
const assistantsData = ref<any[]>([]);
const assistantsLoading = ref(false);
const currentFileId = ref('');
const sortBy = ref<string>('');
let statusCheckTimer: ReturnType<typeof setInterval> | null = null;

const sortOptions = [
  { label: t('pages.aiVoice.admin.knowledgeBase.sortByName'), value: 'name' },
  { label: t('pages.aiVoice.admin.knowledgeBase.sortByTime'), value: 'time' },
];

const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
});

const columns: PrimaryTableCol[] = [
  { title: t('pages.aiVoice.admin.knowledgeBase.fileName'), colKey: 'filName', width: 250, ellipsis: true },
  { title: t('pages.aiVoice.admin.knowledgeBase.fileSize'), colKey: 'filSizeBytes', width: 120 },
  { title: t('pages.aiVoice.admin.knowledgeBase.mimeType'), colKey: 'filMimeType', width: 150 },
  { title: t('pages.aiVoice.admin.knowledgeBase.extStatus'), colKey: 'filExtStatus', width: 120 },
  { title: t('pages.aiVoice.admin.knowledgeBase.createUser'), colKey: 'createUserAccount', width: 120 },
  { title: t('pages.aiVoice.admin.knowledgeBase.createTime'), colKey: 'filCreateTime', width: 180 },
  { title: t('pages.aiVoice.admin.knowledgeBase.operation'), colKey: 'op', width: 200, fixed: 'right' },
];

const assistantsColumns: PrimaryTableCol[] = [
  { title: t('pages.aiVoice.admin.knowledgeBase.assistantName'), colKey: 'attName', width: 200 },
  { title: t('pages.aiVoice.admin.knowledgeBase.assignedUser'), colKey: 'assignedUserAccount', width: 150 },
  { title: t('pages.aiVoice.admin.knowledgeBase.assignedUserNickname'), colKey: 'assignedUserNickname', width: 150 },
  { title: t('pages.aiVoice.admin.knowledgeBase.status'), colKey: 'attStatus', width: 100 },
];

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

function extStatusLabel(extStatus: string | null): string {
  if (!extStatus) return '-';
  return extStatus;
}

// 支持的文件类型（仅 PDF、DOCX、TXT、CSV）
const allowedMimeTypes = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
  'text/csv',
];

function beforeUpload(file: File) {
  if (!allowedMimeTypes.includes(file.type)) {
    MessagePlugin.error(t('pages.aiVoice.admin.knowledgeBase.unsupportedFileType'));
    return false;
  }
  return true;
}

// 检查并更新 processing 状态的文件
async function checkProcessingFiles() {
  const processingFiles = tableData.value.filter(
    (file: any) => file.filExtStatus === 'processing'
  );
  if (processingFiles.length === 0) {
    return;
  }

  // 并发更新所有 processing 文件的状态
  const updatePromises = processingFiles.map((file: any) =>
    knowledgeBaseService
      .updateStatus(file.filFileId)
      .then((res: any) => {
        // 更新本地数据
        const index = tableData.value.findIndex(
          (f: any) => f.filFileId === file.filFileId
        );
        if (index !== -1) {
          tableData.value[index].filExtStatus = res.filExtStatus;
          tableData.value[index].filStatus = res.filStatus;
        }
      })
      .catch((e) => {
        console.error(`Failed to update file ${file.filFileId}:`, e);
      })
  );

  await Promise.all(updatePromises);
}

async function loadData() {
  loading.value = true;
  try {
    const res: any = await knowledgeBaseService.getList({
      current: pagination.current,
      size: pagination.pageSize,
      filName: searchForm.filName || undefined,
      filExtStatus: searchForm.filExtStatus || undefined,
      sortBy: sortBy.value || undefined,
    });
    tableData.value = res.records || [];
    pagination.total = res.total || 0;
  } catch (e) {
    console.error(e);
    MessagePlugin.error(t('pages.aiVoice.admin.knowledgeBase.loadFailed'));
  } finally {
    loading.value = false;
  }
}

function handleSortChange() {
  loadData();
}

function handleSearch() {
  pagination.current = 1;
  loadData();
}

function handleReset() {
  searchForm.filName = '';
  searchForm.filExtStatus = null;
  pagination.current = 1;
  loadData();
}

function handlePageChange(pageInfo: any) {
  pagination.current = pageInfo.current;
  pagination.pageSize = pageInfo.pageSize;
  loadData();
}

function handleUpload() {
  uploadVisible.value = true;
  uploadFiles.value = [];
}

async function handleUploadSubmit() {
  if (!uploadFiles.value?.length) {
    MessagePlugin.warning(t('pages.aiVoice.admin.knowledgeBase.selectFileFirst'));
    return;
  }
  // TDesign Upload 组件：文件对象在 raw 属性中
  const fileItem = uploadFiles.value[0];
  const file = fileItem?.raw || fileItem?.file || fileItem;
  if (!file || !(file instanceof File)) {
    MessagePlugin.warning(t('pages.aiVoice.admin.knowledgeBase.selectFileFirst'));
    return;
  }
  try {
    await knowledgeBaseService.uploadFile(file);
    MessagePlugin.success(t('pages.aiVoice.admin.knowledgeBase.uploadSuccess'));
    uploadVisible.value = false;
    uploadFiles.value = [];
    loadData();
  } catch (e) {
    console.error(e);
    MessagePlugin.error(t('pages.aiVoice.admin.knowledgeBase.uploadFailed'));
  }
}

async function handleSync() {
  syncing.value = true;
  try {
    const res: any = await knowledgeBaseService.sync();
    MessagePlugin.success(
      t('pages.aiVoice.admin.knowledgeBase.syncSuccess', { count: res?.synced || 0 })
    );
    loadData();
  } catch (e) {
    console.error(e);
    MessagePlugin.error(t('pages.aiVoice.admin.knowledgeBase.syncFailed'));
  } finally {
    syncing.value = false;
  }
}

async function handleViewAssistants(row: any) {
  currentFileId.value = row.filFileId;
  assistantsVisible.value = true;
  assistantsLoading.value = true;
  try {
    const res: any = await knowledgeBaseService.getAssistants(row.filFileId);
    assistantsData.value = res || [];
  } catch (e) {
    console.error(e);
    MessagePlugin.error(t('pages.aiVoice.admin.knowledgeBase.loadAssistantsFailed'));
  } finally {
    assistantsLoading.value = false;
  }
}

function handleDownload(row: any) {
  if (row.filUrl) {
    window.open(row.filUrl, '_blank');
  } else {
    MessagePlugin.warning(t('pages.aiVoice.admin.knowledgeBase.downloadUrlNotAvailable'));
  }
}

onMounted(() => {
  loadData();
  void loadPlatformPrompt();
  // 每 5 秒检查一次 processing 状态的文件
  statusCheckTimer = setInterval(() => {
    checkProcessingFiles();
  }, 5000);
});

onUnmounted(() => {
  if (statusCheckTimer) {
    clearInterval(statusCheckTimer);
    statusCheckTimer = null;
  }
});
</script>

<style scoped lang="less">
.admin-knowledge-base {
  padding: 24px;

  .platform-prompt-card {
    margin-bottom: 16px;
  }

  .platform-prompt-hint {
    margin: 0 0 12px;
    font-size: 13px;
    color: var(--td-text-color-secondary);
    line-height: 1.5;
  }

  .platform-prompt-state {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 13px;
    color: var(--td-text-color-secondary);
  }

  .platform-prompt-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-top: 12px;
  }

  .btn-group {
    display: flex;
    gap: 8px;
  }

  .char-count {
    font-size: 12px;
    color: var(--td-text-color-placeholder);
  }

  .search-form-container {
    background: var(--td-bg-color-container);
    border-radius: var(--td-radius-default);
    padding: 24px;
    margin-bottom: 16px;

    .form-item-spacing {
      margin-bottom: 16px;
    }

    .search-actions-row {
      margin-top: 20px;
      display: flex;
      justify-content: flex-end;

      .search-actions {
        display: flex;
        justify-content: flex-end;
      }
    }
  }

  .toolbar-container {
    margin-bottom: 16px;
  }
}
</style>
