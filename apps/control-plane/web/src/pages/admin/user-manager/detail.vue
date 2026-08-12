<template>
  <div class="detail-container">
    <t-card :title="isEdit ? t('pages.aiVoice.admin.userList.editUser') : t('pages.aiVoice.admin.userList.userDetail')">
      <t-form ref="form" :data="formData" :rules="FORM_RULES" label-width="120px" @submit="onSubmit">
        <!-- 基本信息 -->
        <t-divider>{{ t('pages.aiVoice.admin.userList.basicInfo') }}</t-divider>
        <t-row :gutter="[24, 16]">
          <t-col :span="12">
            <t-form-item :label="t('pages.aiVoice.admin.userList.userId')" name="userId">
              <t-input v-model="formData.userId" disabled />
            </t-form-item>
          </t-col>
          <t-col :span="12">
            <t-form-item :label="t('pages.aiVoice.admin.userList.userNickname')" name="userNickname">
              <t-space :size="12" align="center">
                <t-avatar v-if="formData.userAvatar" :image="formData.userAvatar" size="medium" />
                <t-avatar v-else size="medium">{{ formData.userNickname?.charAt(0) || 'U' }}</t-avatar>
                <t-input v-model="formData.userNickname" :placeholder="t('pages.aiVoice.admin.userList.nicknamePlaceholder')" style="flex: 1" />
              </t-space>
            </t-form-item>
          </t-col>
          <t-col :span="24">
            <t-form-item :label="t('pages.aiVoice.admin.userList.userAvatar')" name="userAvatar">
              <t-upload
                v-model="avatarFiles"
                :action="uploadAction"
                :headers="uploadHeaders"
                accept="image/*"
                theme="image"
                :size-limit="{ size: 10, unit: 'MB' }"
                :format-response="formatUploadResponse"
                @success="handleAvatarUploadSuccess"
                @fail="handleAvatarUploadFail"
                :tips="t('pages.aiVoice.admin.userList.supportedFormats')"
                :placeholder="t('pages.aiVoice.admin.userList.uploadAvatar')"
                :max="1"
              />
            </t-form-item>
          </t-col>
          <t-col :span="12">
            <t-form-item :label="t('pages.aiVoice.admin.userList.userAccount')" name="userAccount">
              <t-input v-model="formData.userAccount" disabled />
            </t-form-item>
          </t-col>
          <t-col :span="12">
            <t-form-item :label="t('pages.aiVoice.admin.userList.userCompanyName')" name="userCompanyName">
              <t-input v-model="formData.userCompanyName" :placeholder="t('pages.aiVoice.admin.userList.companyPlaceholder')" />
            </t-form-item>
          </t-col>
          <t-col :span="12">
            <t-form-item :label="t('pages.aiVoice.admin.userList.userMobile')" name="userMobile">
              <t-input v-model="formData.userMobile" :placeholder="t('pages.aiVoice.admin.userList.mobilePlaceholder')" clearable />
            </t-form-item>
          </t-col>
          <t-col :span="12">
            <t-form-item :label="t('pages.aiVoice.admin.userList.userStatus')" name="userStatus">
              <t-select v-model="formData.userStatus" :placeholder="t('pages.aiVoice.admin.userList.pleaseSelect')">
                <t-option :value="1" :label="t('pages.aiVoice.admin.userList.enabled')" />
                <t-option :value="0" :label="t('pages.aiVoice.admin.userList.disabled')" />
              </t-select>
            </t-form-item>
          </t-col>
        </t-row>


        <t-divider v-if="formData.keys && formData.keys.length > 0">绑定的密钥</t-divider>
        <t-table
            v-if="formData.keys && formData.keys.length > 0"
            :data="formData.keys"
            :columns="KEY_COLUMNS"
            row-key="keyId"
        >
          <template #keyStatus="{row}">
            <t-tag :theme="row.keyStatus === 1 ? 'success' : 'danger'" variant="light">
              {{ row.keyStatus === 1 ? '启用' : '禁用' }}
            </t-tag>
          </template>
        </t-table>

        <!-- 登录日志 -->
        <t-divider>{{ t('pages.aiVoice.admin.userList.loginLogs') }}</t-divider>
        <t-table
            :data="loginLogsData"
            :columns="LOGIN_LOG_COLUMNS"
            :loading="loginLogsLoading"
            :pagination="loginLogsPagination"
            :empty="t('pages.aiVoice.admin.userList.noLoginLogs')"
            row-key="logId"
            size="small"
            @page-change="handleLoginLogsPageChange"
        >
          <template #loginStatus="{row}">
            <t-tag :theme="row.loginStatus === 1 ? 'success' : 'danger'" variant="light">
              {{ row.loginStatus === 1 ? t('pages.aiVoice.admin.userList.loginSuccess') : t('pages.aiVoice.admin.userList.loginFailed') }}
            </t-tag>
          </template>
        </t-table>

        <!-- 操作日志 -->
        <t-divider>{{ t('pages.aiVoice.admin.userList.actionLogs') }}</t-divider>
        <t-table
            :data="actionLogsData"
            :columns="ACTION_LOG_COLUMNS"
            :loading="actionLogsLoading"
            :pagination="actionLogsPagination"
            :empty="t('pages.aiVoice.admin.userList.noActionLogs')"
            row-key="actionId"
            size="small"
            @page-change="handleActionLogsPageChange"
        >
        </t-table>

        <div class="button-container">
          <t-form-item>
            <t-space align="start">
              <t-button theme="primary" type="submit">{{ t('pages.aiVoice.admin.userList.save') }}</t-button>
              <t-button theme="default" @click="handleCancel">{{ t('pages.aiVoice.admin.userList.cancel') }}</t-button>
            </t-space>
          </t-form-item>
        </div>
      </t-form>
    </t-card>
  </div>
</template>
<script setup lang="ts">
import { MessagePlugin, PrimaryTableCol } from 'tdesign-vue-next';
import { onMounted, ref, reactive } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import type { FormRule } from 'tdesign-vue-next';

import { OperatorTenantService as AdminUserService } from '@/api/platform';
import { UploadService } from '@/api/UploadService';
import { useI18n } from 'vue-i18n';
import UploadEnum from '@/enum/UploadEnum';

const { t } = useI18n();

const router = useRouter();
const route = useRoute();
const adminUserService = new AdminUserService();
const uploadService = new UploadService();

const userId = ref(route.params.ticketId || route.params.userId);
const isEdit = ref(route.query.mode !== 'view');
const formData = ref({
  userId: '',
  userNickname: '',
  userAccount: '',
  userCompanyName: '',
  userMobile: '',
  userAvatar: '',
  userStatus: 1,
  keys: []
});

// 用于 t-upload 组件的文件列表
const avatarFiles = ref([]);
const loginLogsData = ref<any[]>([]);
const actionLogsData = ref<any[]>([]);
const loginLogsLoading = ref(false);
const actionLogsLoading = ref(false);

const loginLogsPagination = reactive({
  current: 1,
  pageSize: 5,
  total: 0,
});

const actionLogsPagination = reactive({
  current: 1,
  pageSize: 5,
  total: 0,
});

// 上传配置
const uploadAction = UploadEnum.UPLOAD_IMAGE;
const uploadHeaders = {
  'Authorization': `Bearer ${getAdminToken()}`
};

function getAdminToken() {
  try {
    const adminTokenData = sessionStorage.getItem('adminToken');
    if (adminTokenData) {
      const data = JSON.parse(adminTokenData);
      return data.token;
    }
  } catch (e) {
    // ignore
  }
  return '';
}

async function loadLoginLogs() {
  if (!userId.value) return;
  loginLogsLoading.value = true;
  try {
    const res: any = await adminUserService.queryLoginLogsByPage({
      current: loginLogsPagination.current,
      size: loginLogsPagination.pageSize,
      userId: userId.value,
    });
    loginLogsData.value = res.records || [];
    loginLogsPagination.total = res.total || 0;
  } catch (e) {
    console.error(e);
    MessagePlugin.error('加载登录日志失败');
  } finally {
    loginLogsLoading.value = false;
  }
}

async function loadActionLogs() {
  if (!userId.value) return;
  actionLogsLoading.value = true;
  try {
    const res: any = await adminUserService.queryActionLogsByPage({
      current: actionLogsPagination.current,
      size: actionLogsPagination.pageSize,
      userId: userId.value,
    });
    actionLogsData.value = res.records || [];
    actionLogsPagination.total = res.total || 0;
  } catch (e) {
    console.error(e);
    MessagePlugin.error('加载操作日志失败');
  } finally {
    actionLogsLoading.value = false;
  }
}

function handleLoginLogsPageChange(pageInfo: any) {
  loginLogsPagination.current = pageInfo.current;
  loginLogsPagination.pageSize = pageInfo.pageSize;
  loadLoginLogs();
}

function handleActionLogsPageChange(pageInfo: any) {
  actionLogsPagination.current = pageInfo.current;
  actionLogsPagination.pageSize = pageInfo.pageSize;
  loadActionLogs();
}

const FORM_RULES: Record<string, FormRule[]> = {
  userNickname: [
    { required: true, message: t('pages.aiVoice.admin.userList.pleaseEnter') + t('pages.aiVoice.admin.userList.userNickname'), type: 'error' },
    { max: 50, message: 'User nickname cannot exceed 50 characters', type: 'error' }
  ],
  userCompanyName: [
    { max: 100, message: 'Company name cannot exceed 100 characters', type: 'error' }
  ],
  userMobile: [
    { max: 20, message: 'Mobile number cannot exceed 20 characters', type: 'error' }
  ]
};

const KEY_COLUMNS: PrimaryTableCol[] = [
  {
    title: '密钥ID',
    width: 100,
    colKey: 'keyId',
  },
  {
    title: '密钥名称',
    width: 150,
    colKey: 'keyName',
  },
  {
    title: '密钥值',
    width: 200,
    colKey: 'keyValue',
  },
  {
    title: '密钥状态',
    width: 100,
    colKey: 'keyStatus',
  },
  {
    title: '过期时间',
    width: 180,
    colKey: 'keyExpiryTime',
  },
  {
    title: '绑定时间',
    width: 180,
    colKey: 'bindTime',
  },
];

const LOGIN_LOG_COLUMNS: PrimaryTableCol[] = [
  {
    title: t('pages.aiVoice.admin.userList.loginIp'),
    width: 150,
    colKey: 'loginIp',
  },
  {
    title: t('pages.aiVoice.admin.userList.loginDevice'),
    width: 200,
    colKey: 'loginDevice',
  },
  {
    title: t('pages.aiVoice.admin.userList.loginTime'),
    width: 180,
    colKey: 'loginTime',
  },
  {
    title: t('pages.aiVoice.admin.userList.loginStatus'),
    width: 100,
    colKey: 'loginStatus',
  },
  {
    title: t('pages.aiVoice.admin.userList.loginRemark'),
    width: 200,
    colKey: 'loginRemark',
  },
];

const ACTION_LOG_COLUMNS: PrimaryTableCol[] = [
  {
    title: t('pages.aiVoice.admin.userList.actionType'),
    width: 120,
    colKey: 'actionType',
  },
  {
    title: t('pages.aiVoice.admin.userList.actionDetail'),
    width: 250,
    colKey: 'actionDetail',
  },
  {
    title: t('pages.aiVoice.admin.userList.actionTime'),
    width: 180,
    colKey: 'actionTime',
  },
  {
    title: t('pages.aiVoice.admin.userList.actionIp'),
    width: 150,
    colKey: 'actionIp',
  },
  {
    title: t('pages.aiVoice.admin.userList.actionDevice'),
    width: 200,
    colKey: 'actionDevice',
  },
];

const fetchData = () => {
  // 获取用户详情
  adminUserService.getUserDetail({
    userId: userId.value
  }).then((res: any) => {
    formData.value = {
      userId: res.userId || '',
      userNickname: res.userNickname || '',
      userAccount: res.userAccount || '',
      userCompanyName: res.userCompanyName || '',
      userMobile: res.userMobile || '',
      userAvatar: res.userAvatar || '',
      userStatus: res.userStatus !== undefined ? res.userStatus : 1,
      keys: res.keys || []
    };
    
    // 设置头像文件列表
    if (res.userAvatar) {
      avatarFiles.value = [{
        name: 'avatar.jpg',
        url: res.userAvatar,
        status: 'success'
      }];
    } else {
      avatarFiles.value = [];
    }
  }).catch(() => {
    MessagePlugin.error('获取用户详情失败');
  });

  // 加载登录日志（分页）
  loadLoginLogs();

  // 加载操作日志（分页）
  loadActionLogs();
};

onMounted(() => {
  if (userId.value) {
    fetchData();
  }
});

const onSubmit = async (ctx: any) => {
  if (ctx.validateResult === true) {
    try {
      // 更新基本信息（包括手机号和头像）
      await adminUserService.updateUser({
        userId: formData.value.userId,
        userNickname: formData.value.userNickname,
        userCompanyName: formData.value.userCompanyName,
        userMobile: formData.value.userMobile,
        userAvatar: formData.value.userAvatar,
        userStatus: formData.value.userStatus,
      });

      MessagePlugin.success(t('pages.aiVoice.admin.userList.saveSuccess'));
      fetchData()
    } catch (error) {
      console.error('Update user error:', error);
      // 显示具体的错误信息，如果有的话
      const errorMessage = error?.message || error?.data?.message || t('pages.aiVoice.admin.userList.saveFailed');
      MessagePlugin.error(errorMessage);
    }
  }
};

// 头像上传相关

const formatUploadResponse = (response: any) => {
  console.log('Original response:', response);
  // 转换后端响应格式为 t-upload 期望的格式
  if (response && response.data && response.data.url) {
    return {
      status: 'success',
      url: response.data.url
    };
  }
  return response;
};

const handleAvatarUploadSuccess = (context: any) => {
  const { response } = context;
  console.log('Upload success context:', context); // 调试日志
  if (response && response.url) {
    formData.value.userAvatar = response.url;
    MessagePlugin.success(t('pages.aiVoice.admin.userList.uploadSuccess'));
  }
};

const handleAvatarUploadFail = () => {
  MessagePlugin.error(t('pages.aiVoice.admin.userList.uploadFailed'));
};

const handleCancel = () => {
  router.back();
};
</script>

<style lang="less" scoped>
.detail-container {
  background-color: var(--td-bg-color-container);
  padding: 24px;
  border-radius: var(--td-radius-medium);
}

.avatar-upload-container {
  display: flex;
  align-items: center;
  gap: 16px;

  .user-avatar {
    flex-shrink: 0;
  }

  .avatar-upload-actions {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
}

.button-container {
  margin-top: 32px;
  
  :deep(.t-form-item) {
    margin-bottom: 0;
  }
  
  :deep(.t-form-item__content) {
    justify-content: flex-start;
  }
}

.logs-more {
  margin-top: 16px;
  text-align: center;
}

// 输入框间距优化
:deep(.t-form-item) {
  margin-bottom: 20px;
}

:deep(.t-form-item__content) {
  .t-input,
  .t-select {
    width: 100%;
  }
}

// 左对齐按钮
:deep(.t-space) {
  justify-content: flex-start;
}

// 表格样式优化
:deep(.t-table) {
  .t-table__cell {
    padding: 8px 16px;
  }
}
</style>

