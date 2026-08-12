<template>
  <div class="user-list">
    <t-card :title="$t('pages.aiVoice.admin.userList.title')">
      <div class="search-form-container">
        <t-form :data="searchForm" label-width="100px" @submit="handleSearch" @reset="handleReset">
          <!-- 筛选项 -->
          <t-row :gutter="16">
            <t-col :span="6">
              <t-form-item class="form-item-spacing" :label="$t('pages.aiVoice.admin.userList.userAccount')">
                <t-input v-model="searchForm.userAccount" :placeholder="$t('pages.aiVoice.admin.userList.accountPlaceholder')" clearable />
              </t-form-item>
            </t-col>
            <t-col :span="6">
              <t-form-item class="form-item-spacing" :label="$t('pages.aiVoice.admin.userList.userMobile')">
                <t-input v-model="searchForm.userMobile" :placeholder="$t('pages.aiVoice.admin.userList.mobilePlaceholder')" clearable />
              </t-form-item>
            </t-col>
            <t-col :span="6">
              <t-form-item class="form-item-spacing" :label="$t('pages.aiVoice.admin.userList.userStatus')">
                <t-select v-model="searchForm.userStatus" :options="statusOptions" clearable :placeholder="$t('pages.aiVoice.admin.userList.pleaseSelect')" />
              </t-form-item>
            </t-col>
          </t-row>
          <!-- 搜索栏 -->
          <t-row :gutter="16" class="search-actions-row">
            <t-col :span="24">
              <div class="search-actions">
                <t-space align="start">
                  <t-button theme="primary" type="submit">
                    {{ $t('pages.aiVoice.admin.userList.search') }}
                  </t-button>
                  <t-button theme="default" type="reset">
                    {{ $t('pages.aiVoice.admin.userList.reset') }}
                  </t-button>
                </t-space>
              </div>
            </t-col>
          </t-row>
        </t-form>
      </div>

      <!-- 操作按钮区域 -->
      <div>
        <t-button theme="success" @click="handleCreate">
          <template #icon>
            <UserAddIcon />
          </template>
          {{ $t('pages.aiVoice.admin.userList.create') }}
        </t-button>
      </div>

      <t-table
        :data="tableData"
        :columns="columns"
        :loading="loading"
        :pagination="pagination"
        @page-change="handlePageChange"
        @change="handleChange"
      >
        <template #userAvatar="{ row }">
          <t-avatar v-if="row.userAvatar" :image="row.userAvatar" size="medium" />
          <t-avatar v-else size="medium">{{ row.userNickname?.charAt(0) || row.userAccount?.charAt(0) || 'U' }}</t-avatar>
        </template>
        <template #userStatus="{ row }">
          <t-tag 
            :theme="row.userStatus === 1 ? 'success' : row.userStatus === 0 ? 'warning' : 'danger'" 
            variant="light"
          >
            {{ 
              row.userStatus === 1 ? $t('pages.aiVoice.admin.userList.enabled') : 
              row.userStatus === 0 ? $t('pages.aiVoice.admin.userList.disabled') : 
              $t('pages.aiVoice.admin.userList.deleted')
            }}
          </t-tag>
        </template>
        <template #op="{ row }">
          <t-space align="start">

            <t-link theme="primary" @click="handleEdit(row)">
              {{ $t('pages.aiVoice.admin.userList.edit') }}
            </t-link>
            <t-link theme="danger" @click="handleDelete(row)">
              {{ $t('pages.aiVoice.admin.userList.delete') }}
            </t-link>
            <t-link theme="warning" @click="handleResetPassword(row)">
              {{ $t('pages.aiVoice.admin.userList.resetPassword') }}
            </t-link>
          </t-space>
        </template>
      </t-table>
    </t-card>

    <!-- 密码重置成功弹窗 -->
    <t-dialog
      v-model:visible="passwordResetVisible"
      :header="$t('pages.aiVoice.admin.userList.resetPasswordSuccess')"
      width="480px"
      destroy-on-close
      :show-overlay="true"
      :footer="false"
    >
      <template #body>
        <div style="padding: 8px 0;">
          <div style="margin-bottom: 16px; font-size: 14px;">
            <span style="color: #666; margin-right: 8px;">{{ $t('pages.aiVoice.admin.userList.userName') }}:</span>
            <span style="font-weight: 500; color: #333;">{{ resetPasswordInfo.userName }}</span>
          </div>
          <div style="margin-bottom: 12px; font-size: 14px; color: #666;">
            {{ $t('pages.aiVoice.admin.userList.newPassword') }}:
          </div>
          <div style="background: #f8f9fa; padding: 16px; border-radius: 6px; font-family: 'Consolas', 'Monaco', 'Courier New', monospace; font-size: 18px; font-weight: bold; text-align: center; border: 2px solid #e9ecef; user-select: all; letter-spacing: 2px; color: #495057; margin-bottom: 16px;">
            {{ resetPasswordInfo.newPassword }}
          </div>
          <div style="padding: 12px; background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 4px; color: #856404; font-size: 13px; line-height: 1.4;">
            {{ $t('pages.aiVoice.admin.userList.passwordResetTip') }}
          </div>
        </div>
      </template>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { MessagePlugin, DialogPlugin, PrimaryTableCol } from 'tdesign-vue-next';
import { UserAddIcon } from 'tdesign-icons-vue-next';
import { ref, reactive } from 'vue';
import { useRouter } from 'vue-router';

import { OperatorTenantService as AdminUserService } from '@/api/platform';
import { t } from '@/locales';

const router = useRouter();
const adminUserService = new AdminUserService();

const searchForm = reactive({
  userAccount: '',
  userMobile: '',
  userStatus: null,
});

const loading = ref(false);
const tableData = ref([]);
const passwordResetVisible = ref(false);
const resetPasswordInfo = ref({
  userName: '',
  newPassword: ''
});

const statusOptions = [
  { label: t('pages.aiVoice.admin.userList.enabled'), value: 1 },
  { label: t('pages.aiVoice.admin.userList.disabled'), value: 0 },
  { label: t('pages.aiVoice.admin.userList.deleted'), value: -1 },
];

const columns: PrimaryTableCol[] = [
  {
    title: t('pages.aiVoice.admin.userList.userId'),
    colKey: 'userId',
    width: 100,
  },
  {
    title: t('pages.aiVoice.admin.userList.userAvatar'),
    colKey: 'userAvatar',
    width: 80,
  },
  {
    title: t('pages.aiVoice.admin.userList.userNickname'),
    colKey: 'userNickname',
    width: 120,
  },
  {
    title: t('pages.aiVoice.admin.userList.userAccount'),
    colKey: 'userAccount',
    width: 150,
  },
  {
    title: t('pages.aiVoice.admin.userList.userCompanyName'),
    colKey: 'userCompanyName',
    width: 180,
  },
  {
    title: t('pages.aiVoice.admin.userList.userMobile'),
    colKey: 'userMobile',
    width: 150,
  },
  {
    title: t('pages.aiVoice.admin.userList.userStatus'),
    colKey: 'userStatus',
    width: 100,
  },
  {
    title: t('pages.aiVoice.admin.userList.createTime'),
    colKey: 'userCreateTime',
    width: 180,
  },
  {
    title: t('pages.aiVoice.admin.userList.actions'),
    colKey: 'op',
    width: 200,
    fixed: 'right',
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
  searchForm.userAccount = '';
  searchForm.userMobile = '';
  searchForm.userStatus = null;
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

const handleCreate = () => {
  router.push('/admin/user-manager/create');
};

const handleEdit = (row: any) => {
  router.push(`/admin/user-manager/detail/${row.userId}?mode=edit`);
};

const handleResetPassword = (row: any) => {
  const confirmDialog = DialogPlugin.confirm({
    header: t('pages.aiVoice.admin.userList.resetPasswordConfirm'),
    body: t('pages.aiVoice.admin.userList.resetPasswordMessage', { name: row.userNickname || row.userAccount }),
    confirmBtn: t('pages.aiVoice.admin.userList.confirm'),
    cancelBtn: t('pages.aiVoice.admin.userList.cancel'),
    onConfirm: async () => {
      try {
        // 生成随机密码
        const newPassword = generateRandomPassword();
        await adminUserService.updateUserPassword({
          userId: row.userId,
          newPassword: newPassword,
        });
        
        confirmDialog.destroy();
        
        // 设置密码重置信息并显示弹窗
        resetPasswordInfo.value = {
          userName: row.userNickname || row.userAccount,
          newPassword: newPassword
        };
        passwordResetVisible.value = true;
      } catch (error) {
        MessagePlugin.error(t('pages.aiVoice.admin.userList.resetPasswordFailed'));
      }
    },
  });
};

// 生成随机密码
const generateRandomPassword = () => {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let password = '';
  for (let i = 0; i < 8; i++) {
    password += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return password;
};

const handleDelete = (row: any) => {
  const dialog = DialogPlugin.confirm({
    header: t('pages.aiVoice.admin.userList.confirmDelete'),
    body: t('pages.aiVoice.admin.userList.deleteConfirmMessage', {name: row.userNickname || row.userAccount}),
    confirmBtn: t('pages.aiVoice.admin.userList.confirm'),
    cancelBtn: t('pages.aiVoice.admin.userList.cancel'),
    onConfirm: async () => {
      try {
        await adminUserService.deleteUser({userId: row.userId});
        MessagePlugin.success(t('pages.aiVoice.admin.userList.deleteSuccess'));
        dialog.destroy();
        loadData();
      } catch (error) {
        MessagePlugin.error(t('pages.aiVoice.admin.userList.deleteFailed'));
      }
    },
  });
};

const loadData = async () => {
  loading.value = true;
  try {
    const response: any = await adminUserService.getUserList({
      current: pagination.current,
      pageSize: pagination.pageSize,
      ...searchForm,
    });
    tableData.value = response.records || response.list || [];
    pagination.total = response.total || 0;
  } catch (error) {
    MessagePlugin.error(t('pages.aiVoice.admin.userList.loadFailed') || 'Failed to load user list');
  } finally {
    loading.value = false;
  }
};

// Load data on mount
loadData();
</script>

<style scoped lang="less">
.user-list {
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

  .table-actions {
    margin-bottom: 16px;
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 12px;
  }

  // 表单项间距
  .form-item-spacing {
    margin-bottom: 15px !important;
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
</style>

