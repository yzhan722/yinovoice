<template>
  <div class="chat-history">
    <t-card :title="$t('pages.aiVoice.userCenter.chatHistory.title')">
      <div class="search-form-container">
        <t-form :data="searchForm" label-width="100px" @submit="handleSearch" @reset="handleReset">
          <t-row :gutter="16">
          <t-col :span="6">
            <t-form-item :label="$t('pages.aiVoice.userCenter.chatHistory.dateRange')">
              <t-date-range-picker v-model="searchForm.dateRange" clearable />
            </t-form-item>
          </t-col>
          <t-col :span="6">
            <t-form-item :label="$t('pages.aiVoice.userCenter.chatHistory.status')">
              <t-select v-model="searchForm.status" :options="statusOptions" clearable placeholder="Select status" />
            </t-form-item>
          </t-col>
          <t-col :span="12">
            <t-form-item>
              <t-space>
                <t-button theme="primary" type="submit">
                  {{ $t('pages.aiVoice.userCenter.chatHistory.search') }}
                </t-button>
                <t-button theme="default" type="reset">Reset</t-button>
              </t-space>
            </t-form-item>
          </t-col>
        </t-row>
      </t-form>
      </div>

      <t-table
        :data="tableData"
        :columns="columns as any"
        :loading="loading"
        :pagination="pagination"
        @page-change="handlePageChange"
        @change="handleChange"
      >
        <template #sessionId="{ row }">
          <t-link theme="primary" @click="handleViewDetail(row)">
            {{ row.sessionId }}
          </t-link>
        </template>
        <template #op="{ row }">
          <t-link theme="primary" @click="handleViewDetail(row)">
            {{ $t('pages.aiVoice.userCenter.chatHistory.viewDetail') }}
          </t-link>
        </template>
      </t-table>
    </t-card>

    <!-- Detail Dialog -->
    <t-dialog
      v-model:visible="detailVisible"
      :header="$t('pages.aiVoice.userCenter.chatHistory.viewDetail')"
      width="800px"
    >
      <div v-if="currentDetail">
        <t-descriptions :data="detailDescriptions" :column="2" />
        <t-divider />
        <div class="messages-container">
          <h4>{{ $t('pages.aiVoice.userCenter.chatHistory.messages') }}</h4>
          <t-list :split="true">
            <t-list-item v-for="(msg, index) in currentDetail.messages" :key="index">
              <div class="message-item">
                <div class="message-role">{{ msg.role }}</div>
                <div class="message-content">{{ msg.content }}</div>
                <div class="message-time">{{ msg.timestamp }}</div>
              </div>
            </t-list-item>
          </t-list>
        </div>
      </div>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { MessagePlugin, PrimaryTableCol } from 'tdesign-vue-next';
import { ref, reactive, computed } from 'vue';

import { ChatService } from '@/api/ChatService';
import { t } from '@/locales';

const chatService = new ChatService();

const searchForm = reactive({
  dateRange: [],
  status: '',
});

const loading = ref(false);
const tableData = ref([]);
const detailVisible = ref(false);
const currentDetail = ref(null);

const statusOptions = [
  { label: 'Active', value: 'active' },
  { label: 'Completed', value: 'completed' },
  { label: 'Failed', value: 'failed' },
];

const getColumns = (): PrimaryTableCol[] => [
  {
    title: t('pages.aiVoice.userCenter.chatHistory.sessionId'),
    colKey: 'sessionId',
    width: 200,
  },
  {
    title: t('pages.aiVoice.userCenter.chatHistory.startTime'),
    colKey: 'startTime',
    width: 180,
  },
  {
    title: t('pages.aiVoice.userCenter.chatHistory.endTime'),
    colKey: 'endTime',
    width: 180,
  },
  {
    title: t('pages.aiVoice.userCenter.chatHistory.messages'),
    colKey: 'messageCount',
    width: 120,
  },
  {
    title: t('pages.aiVoice.userCenter.chatHistory.duration'),
    colKey: 'duration',
    width: 120,
  },
  {
    title: 'Operation',
    colKey: 'op',
    width: 150,
    fixed: 'right',
  },
];

const columns = computed(() => getColumns());

const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
});

const detailDescriptions = computed(() => {
  if (!currentDetail.value) return [];
  const detail = currentDetail.value;
  return [
    { label: String(t('pages.aiVoice.userCenter.chatHistory.sessionId')), content: detail.sessionId },
    { label: String(t('pages.aiVoice.userCenter.chatHistory.startTime')), content: detail.startTime },
    { label: String(t('pages.aiVoice.userCenter.chatHistory.endTime')), content: detail.endTime },
    { label: String(t('pages.aiVoice.userCenter.chatHistory.duration')), content: detail.duration },
  ];
});

const handleSearch = () => {
  // TODO: Implement search
  loadData();
};

const handleReset = () => {
  searchForm.dateRange = [];
  searchForm.status = '';
  loadData();
};

const handlePageChange = (pageInfo: { current: number; pageSize: number }) => {
  pagination.current = pageInfo.current;
  pagination.pageSize = pageInfo.pageSize;
  loadData();
};

const handleChange = () => {
  // Handle table change
};

const handleViewDetail = async (row: any) => {
  try {
    const detail: any = await chatService.getChatDetail(row.sessionId);
    if (detail) {
      currentDetail.value = detail;
      detailVisible.value = true;
    } else {
      currentDetail.value = row;
      detailVisible.value = true;
    }
  } catch (error) {
    MessagePlugin.error('Failed to load chat detail');
  }
};

const loadData = async () => {
  loading.value = true;
  try {
    const response: any = await chatService.getChatList({
      current: pagination.current,
      pageSize: pagination.pageSize,
      ...searchForm,
    });
    tableData.value = response.list;
    pagination.total = response.total;
  } catch (error) {
    MessagePlugin.error('Failed to load chat history');
  } finally {
    loading.value = false;
  }
};

// Load data on mount
loadData();
</script>

<style scoped lang="less">
.chat-history {
  padding: 24px;

  .search-form-container {
    padding: 24px;
    margin-bottom: 24px;
    background: var(--td-bg-color-container);
    border-radius: var(--td-radius-default);
  }

  .messages-container {
    margin-top: 16px;

    .message-item {
      padding: 12px;
      border-radius: 4px;
      background: var(--td-bg-color-container);

      .message-role {
        font-weight: bold;
        margin-bottom: 8px;
      }

      .message-content {
        margin-bottom: 8px;
      }

      .message-time {
        font-size: 12px;
        color: var(--td-text-color-placeholder);
      }
    }
  }
}
</style>

