<script setup lang="ts">
import {ref, defineProps, defineModel} from 'vue';
import UploadDirectory from "@/components/upload-directory.vue";

const props = defineProps(["actionUrl"])
const filePath = defineModel<string>('filePath', { default: '' });
const files = ref<any[]>([]);

const ABRIDGE_NAME = [10, 7];

const disabled = ref(false);
const autoUpload = ref(false);
const showThumbnail = ref(true);
const allowUploadDuplicateFile = ref(false);
const isBatchUpload = ref(false);
const uploadAllFilesInOneRequest = ref(false);

const formatResponse = (res: any) => {
  if (!res) {
    return {status: 'fail', error: '上传失败，原因：文件过大或网络不通'};
  }
  if (res?.XMLHttpRequest?.responseText) {
    const responseO = JSON.parse(res.XMLHttpRequest.responseText);
    if (!responseO.success) {
      return {status: 'fail', error: responseO.msg};
    }
  }
  return res;
};
const handleUploadDirectory = (res: any[]) => {
  files.value = files.value.concat(res);
};
</script>

<template>
  <t-space direction="vertical" style="width:100%">
    <!--    <t-space>-->
    <!--      <t-checkbox v-model="disabled">禁用状态</t-checkbox>-->
    <!--      <t-checkbox v-model="autoUpload">自动上传</t-checkbox>-->
    <!--      <t-checkbox v-model="showThumbnail">显示文件缩略图</t-checkbox>-->
    <!--    <t-checkbox v-model="allowUploadDuplicateFile"> 允许上传同名文件</t-checkbox>-->
    <!--      <t-checkbox v-model="isBatchUpload"> 整体替换上传</t-checkbox>-->
    <!--      <t-checkbox v-model="uploadAllFilesInOneRequest"> 多个文件一个请求上传</t-checkbox>-->
    <!--    </t-space>-->

    <!--    <br/>-->

    <upload-directory @upload="handleUploadDirectory"/>
    <t-upload
        v-model="files"
        :action="props.actionUrl"
        placeholder="支持批量上传文件，文件格式不限，最多只能上传 100 份文件,单个文件最大500M"
        theme="file-flow"
        multiple
        withCredentials
        :headers="{'file-path':encodeURIComponent(filePath)}"
        :disabled="disabled"
        :abridge-name="ABRIDGE_NAME"
        :auto-upload="autoUpload"
        :sizeLimit="{ size: 500, unit: 'MB', message: '文件大小不超过 {sizeLimit} MB' }"
        :max="100"
        :show-thumbnail="showThumbnail"
        :allow-upload-duplicate-file="allowUploadDuplicateFile"
        :is-batch-upload="isBatchUpload"
        :upload-all-files-in-one-request="uploadAllFilesInOneRequest"
        :format-response="formatResponse"
    ></t-upload>
  </t-space>
</template>

<style scoped lang="less">

</style>
