<template>
  <div>
    <t-button :icon="h(UploadIcon)" @click="triggerUpload">上传文件夹</t-button>
    <input type="file" webkitdirectory @change="handleUpload" style="display:none;" ref="folderInput"/>
  </div>
</template>

<script setup>
import {ref, h} from 'vue';

const folderInput = ref(null);
import {UploadIcon} from 'tdesign-icons-vue-next';

const emit = defineEmits(["upload"]);
const handleUpload = (event) => {
  const files = event.target.files;
  const fileList = Array.from(files).map(file => ({
    lastModified: file.lastModified,
    name: file.name,
    percent: 0,
    raw: file,
    size: file.size,
    status: 'waiting',
    type: file.type,
    uploadTime: new Date().toISOString(),
    url: URL.createObjectURL(file),
    filePath: file.webkitRelativePath || file.name,
  }));
  emit('upload', fileList);
};

const triggerUpload = () => {
  folderInput.value.click();
};

const handleChange = (info) => {
  console.log('Upload change:', info);
};
</script>

<style scoped lang="less">
</style>
