<template>
  <div class="create-container">
    <t-card :title="$t('pages.aiVoice.admin.userList.createUser')">
      <t-form ref="form" :data="formData" :rules="FORM_RULES" label-width="120px" @submit="onSubmit">
        <!-- 基本信息 -->
        <t-divider>{{ $t('pages.aiVoice.admin.userList.basicInfo') }}</t-divider>
        <t-row :gutter="[24, 16]">
          <t-col :span="24">
            <t-form-item :label="$t('pages.aiVoice.admin.userList.userAvatar')" name="userAvatar">
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
                :tips="$t('pages.aiVoice.admin.userList.supportedFormats')"
                :placeholder="$t('pages.aiVoice.admin.userList.uploadAvatar')"
                :max="1"
              />
            </t-form-item>
          </t-col>
          <t-col :span="12">
            <t-form-item :label="$t('pages.aiVoice.admin.userList.userNickname')" name="userNickname">
              <t-input v-model="formData.userNickname" :placeholder="$t('pages.aiVoice.admin.userList.nicknamePlaceholder')" clearable />
            </t-form-item>
          </t-col>
          <t-col :span="12">
            <t-form-item :label="$t('pages.aiVoice.admin.userList.userAccount')" name="userAccount">
              <t-input v-model="formData.userAccount" :placeholder="$t('pages.aiVoice.admin.userList.accountPlaceholder')" clearable />
            </t-form-item>
          </t-col>
          <t-col :span="12">
            <t-form-item :label="$t('pages.aiVoice.admin.userList.userCompanyName')" name="userCompanyName">
              <t-input v-model="formData.userCompanyName" :placeholder="$t('pages.aiVoice.admin.userList.companyPlaceholder')" clearable />
            </t-form-item>
          </t-col>
          <t-col :span="12">
            <t-form-item :label="$t('pages.aiVoice.admin.userList.userMobile')" name="userMobile">
              <t-input v-model="formData.userMobile" :placeholder="$t('pages.aiVoice.admin.userList.mobilePlaceholder')" clearable />
            </t-form-item>
          </t-col>
          <t-col :span="12">
            <t-form-item :label="$t('pages.aiVoice.admin.userList.password')" name="userPassword">
              <t-input 
                v-model="formData.userPassword" 
                type="password" 
                :placeholder="$t('pages.aiVoice.admin.userList.passwordPlaceholder')"
                clearable
              />
            </t-form-item>
          </t-col>
          <t-col :span="12">
            <t-form-item :label="$t('pages.aiVoice.admin.userList.userStatus')" name="userStatus">
              <t-select v-model="formData.userStatus" :placeholder="$t('pages.aiVoice.admin.userList.pleaseSelect')">
                <t-option :value="1" :label="$t('pages.aiVoice.admin.userList.enabled')" />
                <t-option :value="0" :label="$t('pages.aiVoice.admin.userList.disabled')" />
              </t-select>
            </t-form-item>
          </t-col>
        </t-row>

        <div class="button-container">
          <t-form-item>
            <t-space align="start">
              <t-button theme="primary" type="submit" :loading="submitting">
                {{ $t('pages.aiVoice.admin.userList.save') }}
              </t-button>
              <t-button theme="default" @click="handleCancel">
                {{ $t('pages.aiVoice.admin.userList.cancel') }}
              </t-button>
            </t-space>
          </t-form-item>
        </div>
      </t-form>
    </t-card>
  </div>
</template>

<script setup lang="ts">
import { MessagePlugin } from 'tdesign-vue-next';
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import type { FormRule } from 'tdesign-vue-next';

import { OperatorTenantService as AdminUserService } from '@/api/platform';
import { t } from '@/locales';
import UploadEnum from '@/enum/UploadEnum';

const router = useRouter();
const adminUserService = new AdminUserService();

const submitting = ref(false);
const formData = ref({
  userNickname: '',
  userAccount: '',
  userCompanyName: '',
  userMobile: '',
  userPassword: '',
  userAvatar: '',
  userStatus: 1,
});

// 用于 t-upload 组件的文件列表
const avatarFiles = ref([]);

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

const FORM_RULES: Record<string, FormRule[]> = {
  userNickname: [
    { required: true, message: t('pages.aiVoice.admin.userList.pleaseEnter') + t('pages.aiVoice.admin.userList.userNickname'), type: 'error' },
    { max: 50, message: 'User nickname cannot exceed 50 characters', type: 'error' }
  ],
  userAccount: [
    { required: true, message: t('pages.aiVoice.admin.userList.pleaseEnter') + t('pages.aiVoice.admin.userList.userAccount'), type: 'error' },
    { email: true, message: 'Please enter a valid email address', type: 'error' },
    { max: 100, message: 'User account cannot exceed 100 characters', type: 'error' }
  ],
  userCompanyName: [
    { max: 100, message: 'Company name cannot exceed 100 characters', type: 'error' }
  ],
  userMobile: [
    { required: true, message: t('pages.aiVoice.admin.userList.pleaseEnter') + t('pages.aiVoice.admin.userList.userMobile'), type: 'error' },
    { max: 20, message: 'Mobile number cannot exceed 20 characters', type: 'error' }
  ],
  userPassword: [
    { required: true, message: t('pages.aiVoice.admin.userList.pleaseEnter') + t('pages.aiVoice.admin.userList.password'), type: 'error' },
    { min: 6, message: 'Password must be at least 6 characters', type: 'error' },
    { max: 20, message: 'Password cannot exceed 20 characters', type: 'error' }
  ],
};

const onSubmit = async (ctx: any) => {
  if (ctx.validateResult === true) {
    submitting.value = true;
    try {
      // 提交前检查账号是否已存在
      const accountExists = await adminUserService.checkAccount(formData.value.userAccount);
      if (accountExists) {
        MessagePlugin.error(t('pages.aiVoice.admin.userList.accountExists'));
        submitting.value = false;
        return;
      }

      await adminUserService.createUser({
        userNickname: formData.value.userNickname,
        userAccount: formData.value.userAccount,
        userCompanyName: formData.value.userCompanyName,
        userMobile: formData.value.userMobile,
        userPassword: formData.value.userPassword,
        userAvatar: formData.value.userAvatar,
        userStatus: formData.value.userStatus,
      });

      MessagePlugin.success(t('pages.aiVoice.admin.userList.saveSuccess'));
      router.push('/admin/user-manager');
    } catch (error) {
      console.error('Create user error:', error);
      // 显示具体的错误信息，如果有的话
      const errorMessage = error?.message || error?.data?.message || t('pages.aiVoice.admin.userList.saveFailed');
      MessagePlugin.error(errorMessage);
    } finally {
      submitting.value = false;
    }
  }
};

const handleCancel = () => {
  router.back();
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
</script>

<style lang="less" scoped>
.create-container {
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
</style>