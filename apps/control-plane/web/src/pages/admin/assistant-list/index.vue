<template>
  <div class="assistant-list">
    <t-card :title="$t('pages.aiVoice.admin.assistantList.title')">
      <!-- 搜索表单 -->
      <div class="search-form-container">
        <t-form :data="searchForm" label-width="120px" @submit="handleSearch" @reset="handleReset">
          <!-- 筛选项 -->
          <t-row :gutter="16">
            <t-col :span="6">
              <t-form-item :label="$t('pages.aiVoice.admin.assistantList.assistantName')" class="form-item-spacing">
                <t-input v-model="searchForm.attName"
                         :placeholder="$t('pages.aiVoice.admin.assistantList.assistantNamePlaceholder')" clearable/>
              </t-form-item>
            </t-col>
            <t-col :span="6">
              <t-form-item :label="$t('pages.aiVoice.admin.assistantList.assignedUserAccount')" class="form-item-spacing">
                <t-input v-model="searchForm.userAccount"
                         :placeholder="$t('pages.aiVoice.admin.assistantList.assignedUserAccountPlaceholder')" clearable/>
              </t-form-item>
            </t-col>
            <t-col :span="6">
              <t-form-item :label="$t('pages.aiVoice.admin.assistantList.status')" class="form-item-spacing">
                <t-select v-model="searchForm.attStatus" :options="statusOptions" clearable
                          :placeholder="$t('pages.aiVoice.admin.assistantList.pleaseSelect')"/>
              </t-form-item>
            </t-col>
          </t-row>
          <!-- 搜索栏 -->
          <t-row :gutter="16" class="search-actions-row">
            <t-col :span="24">
              <div class="search-actions">
                <t-space align="start">
                  <t-button theme="primary" type="submit">
                    {{ $t('pages.aiVoice.admin.assistantList.search') }}
                  </t-button>
                  <t-button theme="default" type="reset">
                    {{ $t('pages.aiVoice.admin.assistantList.reset') }}
                  </t-button>
                </t-space>
              </div>
            </t-col>
          </t-row>
        </t-form>
      </div>

      <!-- VAPI sync removed from P0 shell; Provider Adapter sync comes later -->
      <!--
      <div>
        <t-button theme="success" @click="handleSync">
          <template #icon>
            <RefreshIcon/>
          </template>
          {{ $t('pages.aiVoice.admin.assistantList.syncAssistants') }}
        </t-button>
      </div>
      -->

      <!-- 数据表格 -->
      <t-table
          :data="tableData"
          :columns="columns"
          :loading="loading"
          :pagination="pagination"
          @page-change="handlePageChange"
          @change="handleChange"
      >
        <template #attStatus="{ row }">
          <t-tag
              :theme="row.attStatus === 1 ? 'success' : row.attStatus === 0 ? 'warning' : 'danger'"
              variant="light"
          >
            {{
              row.attStatus === 1 ? $t('pages.aiVoice.admin.assistantList.enabled') :
                  row.attStatus === 0 ? $t('pages.aiVoice.admin.assistantList.disabled') :
                      $t('pages.aiVoice.admin.assistantList.deleted')
            }}
          </t-tag>
        </template>

        <template #assignedUser="{ row }">
          <div v-if="row.assignedUserName">
            <div>{{ row.assignedUserName }}</div>
            <div class="user-account">{{ row.assignedUserAccount }}</div>
          </div>
          <span v-else class="no-user">{{ $t('pages.aiVoice.admin.assistantList.noUser') }}</span>
        </template>

        <template #op="{ row }">
          <t-space>
            <t-link theme="primary" @click="handleEdit(row)">
              {{ $t('pages.aiVoice.admin.assistantList.edit') }}
            </t-link>
            <t-link theme="success" @click="handleAssign(row)">
              {{ $t('pages.aiVoice.admin.assistantList.assign') }}
            </t-link>
            <t-link theme="danger" @click="handleDelete(row)" v-if="row.attStatus !== -1">
              {{ $t('pages.aiVoice.admin.assistantList.delete') }}
            </t-link>
          </t-space>
        </template>
      </t-table>
    </t-card>

    <!-- 用户分配弹窗 -->
    <t-dialog
        v-model:visible="assignDialogVisible"
        :header="$t('pages.aiVoice.admin.assistantList.assignUser')"
        width="600px"
        @confirm="handleAssignConfirm"
        @cancel="handleAssignCancel"
    >
      <template #body>
        <div v-if="currentAssignedUser" class="current-user">
          <h4>{{ $t('pages.aiVoice.admin.assistantList.currentUser') }}</h4>
          <div class="user-info">
            <span>{{ currentAssignedUser.userNickname }}</span>
            <span class="user-account">{{ currentAssignedUser.userAccount }}</span>
          </div>
          <t-button theme="primary" size="small" @click="showUserList">
            {{ $t('pages.aiVoice.admin.assistantList.changeUser') }}
          </t-button>
        </div>
        <div v-else>
          <p>{{ $t('pages.aiVoice.admin.assistantList.noCurrentUser') }}</p>
          <t-button theme="primary" @click="showUserList">
            {{ $t('pages.aiVoice.admin.assistantList.assignUser') }}
          </t-button>
        </div>
      </template>
    </t-dialog>

    <!-- 用户选择弹窗 -->
    <t-dialog
        v-model:visible="userSelectDialogVisible"
        :header="$t('pages.aiVoice.admin.assistantList.selectUser')"
        width="900px"
        @confirm="handleUserSelectConfirm"
        @cancel="handleUserSelectCancel"
    >
      <template #body>
        <!-- 用户搜索 -->
        <t-form @submit="handleUserSearch" class="user-search-form">
          <div class="user-search-row">
            <t-form-item :label="$t('pages.aiVoice.admin.assistantList.userAccount')" class="user-search-item">
              <t-input v-model="userSearchForm.userAccount"
                       :placeholder="$t('pages.aiVoice.admin.assistantList.userAccountPlaceholder')" clearable/>
            </t-form-item>
            <t-form-item :label="$t('pages.aiVoice.admin.assistantList.userMobile')" class="user-search-item">
              <t-input v-model="userSearchForm.userMobile"
                       :placeholder="$t('pages.aiVoice.admin.assistantList.userMobilePlaceholder')" clearable/>
            </t-form-item>
            <div class="user-search-actions">
              <t-space>
                <t-button theme="primary" type="submit">
                  {{ $t('pages.aiVoice.admin.assistantList.search') }}
                </t-button>
                <t-button theme="default" @click="handleUserSearchReset">
                  {{ $t('pages.aiVoice.admin.assistantList.reset') }}
                </t-button>
              </t-space>
            </div>
          </div>
        </t-form>

        <!-- 用户列表 -->
        <div class="user-list-container">
          <t-table
              :data="userList"
              :columns="userColumns"
              :loading="userListLoading"
              row-key="userId"
              @select-change="handleUserSelect"
              :selected-row-keys="selectedUserIds"
              :select-on-row-click="true"
          >
            <template #userAvatar="{ row }">
              <t-avatar v-if="row.userAvatar" :image="row.userAvatar" size="medium"/>
              <t-avatar v-else size="medium">{{ row.userNickname?.charAt(0) || 'U' }}</t-avatar>
            </template>
          </t-table>
          <div class="top-items-hint">
            {{ $t('pages.aiVoice.admin.assistantList.top10Items') }}
          </div>
        </div>
      </template>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import {MessagePlugin, DialogPlugin, PrimaryTableCol} from 'tdesign-vue-next';
import {ref, reactive} from 'vue';
import {useRouter} from 'vue-router';
import {RefreshIcon} from 'tdesign-icons-vue-next';

import { OperatorInstanceService as AdminAssistantService } from '@/api/platform';
import {t} from '@/locales';

const router = useRouter();

const adminAssistantService = new AdminAssistantService();

const searchForm = reactive({
  attName: '',
  userAccount: '',
  attStatus: null,
});

const loading = ref(false);
const tableData = ref([]);

// 弹窗状态
const assignDialogVisible = ref(false);
const userSelectDialogVisible = ref(false);
const currentAssistant = ref(null);
const currentAssignedUser = ref(null);

// 用户搜索
const userSearchForm = reactive({
  userAccount: '',
  userMobile: '',
});
const userList = ref([]);
const userListLoading = ref(false);
const selectedUserIds = ref([]);

const statusOptions = [
  {label: t('pages.aiVoice.admin.assistantList.enabled'), value: 1},
  {label: t('pages.aiVoice.admin.assistantList.disabled'), value: 0},
  {label: t('pages.aiVoice.admin.assistantList.deleted'), value: -1},
];

const columns: PrimaryTableCol[] = [
  {
    title: t('pages.aiVoice.admin.assistantList.assistantId'),
    colKey: 'attVendorId',
    width: 180,
    ellipsis: true,
  },
  {
    title: t('pages.aiVoice.admin.assistantList.assistantName'),
    colKey: 'attName',
    width: 150,
  },
  {
    title: t('pages.aiVoice.admin.assistantList.user'),
    colKey: 'assignedUser',
    width: 150,
  },
  {
    title: t('pages.aiVoice.admin.assistantList.voiceProvider'),
    colKey: 'attVoiceProvider',
    width: 120,
  },
  {
    title: t('pages.aiVoice.admin.assistantList.model'),
    colKey: 'attModelName',
    width: 120,
  },
  {
    title: t('pages.aiVoice.admin.assistantList.status'),
    colKey: 'attStatus',
    width: 100,
  },
  {
    title: t('pages.aiVoice.admin.assistantList.createTime'),
    colKey: 'attCreateTime',
    width: 160,
  },
  {
    title: t('pages.aiVoice.admin.assistantList.actions'),
    colKey: 'op',
    width: 220,
    fixed: 'right',
  },
];

const userColumns: PrimaryTableCol[] = [
  {
    colKey: 'row-select',
    type: 'single',
    width: 60,
    checkProps: {allowUncheck: true},
  },
  {
    title: t('pages.aiVoice.admin.assistantList.userAvatar'),
    colKey: 'userAvatar',
    width: 100,
  },
  {
    title: t('pages.aiVoice.admin.assistantList.userNickname'),
    colKey: 'userNickname',
    width: 120,
  },
  {
    title: t('pages.aiVoice.admin.assistantList.userAccount'),
    colKey: 'userAccount',
    width: 200,
  },
  {
    title: t('pages.aiVoice.admin.assistantList.userMobile'),
    colKey: 'userMobile',
    width: 150,
  },
];

const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
});

const handleSearch = () => {
  loadData();
};

const handleReset = () => {
  searchForm.attName = '';
  searchForm.userAccount = '';
  searchForm.attStatus = null;
  loadData();
};

const handlePageChange = (pageInfo: any) => {
  pagination.current = pageInfo.current;
  pagination.pageSize = pageInfo.pageSize;
  loadData();
};

const handleChange = () => {
  // Handle table change
};

const handleEdit = (row: any) => {
  router.push(`/admin/assistant-list/detail/${row.attId}`);
};

const handleDelete = (row: any) => {
  const dialog = DialogPlugin.confirm({
    header: t('pages.aiVoice.admin.assistantList.confirmDelete'),
    body: t('pages.aiVoice.admin.assistantList.deleteConfirmMessage', {name: row.attName}),
    confirmBtn: t('pages.aiVoice.admin.assistantList.confirm'),
    cancelBtn: t('pages.aiVoice.admin.assistantList.cancel'),
    onConfirm: async () => {
      try {
        // TODO: Call API to delete assistant (logical delete)
        MessagePlugin.success(t('pages.aiVoice.admin.assistantList.deleteSuccess'));
        dialog.destroy();
        loadData();
      } catch (error) {
        MessagePlugin.error(t('pages.aiVoice.admin.assistantList.deleteFailed'));
      }
    },
  });
};

const handleSync = async () => {
  try {
    loading.value = true;
    await adminAssistantService.syncAssistants();
    MessagePlugin.success(t('pages.aiVoice.admin.assistantList.syncSuccess'));
    loadData();
  } catch (error) {
    MessagePlugin.error(t('pages.aiVoice.admin.assistantList.syncFailed'));
  } finally {
    loading.value = false;
  }
};

const handleAssign = (row: any) => {
  currentAssistant.value = row;
  currentAssignedUser.value = row.assignedUserName ? {
    userNickname: row.assignedUserName,
    userAccount: row.assignedUserAccount
  } : null;
  assignDialogVisible.value = true;
};

const handleAssignConfirm = () => {
  assignDialogVisible.value = false;
};

const handleAssignCancel = () => {
  assignDialogVisible.value = false;
  currentAssistant.value = null;
  currentAssignedUser.value = null;
};

const showUserList = async () => {
  userSelectDialogVisible.value = true;
  await loadUserList();
};

const handleUserSearch = async () => {
  await loadUserList();
};

const handleUserSearchReset = () => {
  userSearchForm.userAccount = '';
  userSearchForm.userMobile = '';
  loadUserList();
};

const handleUserSelect = (selectedRowKeys: any[]) => {
  selectedUserIds.value = selectedRowKeys;
};

const handleUserSelectConfirm = async () => {
  if (selectedUserIds.value.length === 0) {
    MessagePlugin.warning(t('pages.aiVoice.admin.assistantList.pleaseSelectUser'));
    return;
  }

  try {
    const selectedUser = userList.value.find(user => user.userId === selectedUserIds.value[0]);
    await adminAssistantService.assignAssistant({
      attId: currentAssistant.value.attId,
      userId: selectedUser.userId
    });

    MessagePlugin.success(t('pages.aiVoice.admin.assistantList.assignSuccess'));
    userSelectDialogVisible.value = false;
    assignDialogVisible.value = false;
    selectedUserIds.value = [];
    loadData();
  } catch (error) {
    MessagePlugin.error(t('pages.aiVoice.admin.assistantList.assignFailed'));
  }
};

const handleUserSelectCancel = () => {
  userSelectDialogVisible.value = false;
  selectedUserIds.value = [];
  userSearchForm.userAccount = '';
  userSearchForm.userMobile = '';
};

const loadUserList = async () => {
  userListLoading.value = true;
  try {
    const searchTerm = userSearchForm.userAccount || userSearchForm.userMobile;
    const response = await adminAssistantService.searchUsers(searchTerm);
    userList.value = response;
  } catch (error) {
    MessagePlugin.error(t('pages.aiVoice.admin.assistantList.loadUsersFailed'));
  } finally {
    userListLoading.value = false;
  }
};

const loadData = async () => {
  loading.value = true;
  try {
    const response: any = await adminAssistantService.getAssistantList({
      current: pagination.current,
      pageSize: pagination.pageSize,
      ...searchForm,
    });
    tableData.value = response.records || [];
    pagination.total = response.total || 0;
  } catch (error) {
    MessagePlugin.error(t('pages.aiVoice.admin.assistantList.loadFailed'));
  } finally {
    loading.value = false;
  }
};

// Load data on mount
loadData();
</script>

<style scoped lang="less">
.assistant-list {
  padding: 24px;

  .search-form-container {
    padding: 24px;
    margin-bottom: 24px;
    background: var(--td-bg-color-container);
    border-radius: var(--td-radius-default);

    .search-actions-row {
      margin-top: 20px;
      display: flex;
      justify-content: flex-end;
    }
  }

  // 表单项间距
  .form-item-spacing {
    margin-bottom: 15px !important;
  }

  .user-account {
    font-size: 12px;
    color: var(--td-text-color-placeholder);
    margin-top: 4px;
  }

  .no-user {
    color: var(--td-text-color-placeholder);
    font-style: italic;
  }

  .current-user {
    margin-bottom: 16px;

    h4 {
      margin-bottom: 8px;
      color: var(--td-text-color-primary);
    }

    .user-info {
      padding: 12px;
      background: var(--td-bg-color-container-hover);
      border-radius: var(--td-radius-default);
      margin-bottom: 12px;

      .user-account {
        display: block;
        margin-top: 4px;
      }
    }
  }

  .search-actions-right {
    display: flex;
    justify-content: flex-end;
    width: 100%;
  }

  .user-search-form {
    margin-bottom: 16px;
    width: 100%;
  }

  .user-search-form :deep(.t-form) {
    width: 100%;
  }

  .user-search-row {
    display: flex;
    align-items: flex-end;
    gap: 16px;
    flex-wrap: nowrap;
    width: 100%;
  }

  .user-search-item {
    flex: 1;
    margin-bottom: 0;
    min-width: 0;
  }

  .user-search-item :deep(.t-form-item) {
    margin-bottom: 0;
  }

  .user-search-item :deep(.t-form-item__label) {
    width: auto;
    min-width: 80px;
  }


  .user-list-container {
    position: relative;
    min-height: 300px;
    margin-top: 16px;
  }

  .top-items-hint {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    padding: 8px 16px;
    font-size: 12px;
    color: var(--td-text-color-placeholder);
    background: var(--td-bg-color-container);
    border-top: 1px solid var(--td-border-level-1-color);
    z-index: 10;
  }

  // 左对齐表格操作按钮
  :deep(.t-table__cell) {
    .t-space {
      justify-content: flex-start;
    }
  }

  :deep(.t-form-item__content) {
    .t-input,
    .t-select {
      width: 100%;
    }
  }
}

:deep(.user-search-actions) {
  display: flex;
  justify-content: flex-end;
}
</style>

