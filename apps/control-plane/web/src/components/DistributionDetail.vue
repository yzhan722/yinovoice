<script setup lang="ts">
import {defineProps, onMounted, watch, toRaw} from 'vue';
//@ts-ignore
import {DistributionBasicService} from '@/api/DistributionBasicService';

const props = defineProps(["data", "type"]);
const $DistributionBasicService = new DistributionBasicService();


import {ref, reactive} from 'vue';
import {MessagePlugin} from 'tdesign-vue-next';

const departmentList = ref([]);
const formDisabled = ref(true);
const form = ref(null);
//一行显示几个部门
const departmentColumn = ref(4);
const formData = reactive({
  wellName: '',
  fileName: '',
  sender: '',
  date: '',
  reportTime: '',
  dataList: [],
  id: null
});

watch(() => departmentList.value, (newVal) => {
  const data = [...newVal];
  const column = departmentColumn.value;
  const dataList = [];
  while (data.length > 0) {
    dataList.push(data.splice(0, column));
  }
  formData.dataList = dataList;
});

onMounted(() => {
  formDisabled.value = props.type !== 'add' && props.type !== 'edit';
  initDepartmentList().then((res: any[] | undefined) => {
    initDetail(res || []);
  });
  initDate();
})

const initDate = () => {
  if (!formData.date) {
    const now = new Date();
    formData.date = now.getFullYear() + '-' + (now.getMonth() + 1) + '-' + now.getDate();
  }
}
const initDepartmentList = () => {
  if (departmentList.value && departmentList.value.length > 0) {
    return Promise.resolve();
  }
  return $DistributionBasicService.getDepartmentList().then((res: Array<Object>) => {
    departmentList.value = res;
    return [...res];
  });
}

const initDetail = (dataList: any) => {
  if (!props.data.id) {
    return;
  }
  $DistributionBasicService.getDistributionDetail({
    id: props.data.id
  }).then((res: any) => {
    formData.wellName = res.wellName;
    formData.fileName = res.fileName;
    formData.sender = res.sender;
    formData.date = res.date;
    formData.reportTime = res.reportTime;
    if (props.data._isCopy) {
      formData.id = null;
    } else {
      formData.id = res.id;
    }
    departmentList.value = dataList.map((item: any) => {
      return {
        ...item,
        value: res[item.name] ? res[item.name] : ''
      }
    });
  });
}

const onReset = () => {
  initDate();
  MessagePlugin.success('重置成功');
};

const validate = () => {
  return new Promise(async (resolve, reject) => {
    const validateResult = await form.value.validate();
    if (typeof validateResult !== 'boolean') {
      const key = Object.keys(validateResult)[0];
      MessagePlugin.error(validateResult[key][0].message);
      return reject(validateResult[key]);
    }
    if (formData.dataList && formData.dataList.length > 0) {
      for (let i = 0; i < formData.dataList.length; i++) {
        for (let j = 0; j < formData.dataList[i].length; j++) {
          if (!(!formData.dataList[i][j].value || formData.dataList[i][j].value == 1)) {
            MessagePlugin.error('分发数量只能为0或1，或者为空');
            return reject();
          }
        }
      }
    }
    const result = toRaw(formData);
    resolve({
      ...result
    });
  });
};

defineExpose({
  validate
})

</script>

<template>
  <div class="distribution-detail-container">
    <t-space direction="vertical" size="large" align="center" style="width:100%">

      <t-form
          ref="form"
          :data="formData"
          reset-type="initial"
          :disabled="formDisabled"
          colon
          @reset="onReset"
      >
        <t-space align="center" style="width:100%;margin-bottom: 20px;">
          <t-form-item label="井名" name="wellName">
            <t-input v-model="formData.wellName" placeholder="请输入井名"></t-input>
          </t-form-item>

          <t-form-item label="资料名称" name="fileName">
            <t-input v-model="formData.fileName" placeholder="请输入资料名称"></t-input>
          </t-form-item>

          <t-form-item label="来文单位" name="sender">
            <t-input v-model="formData.sender" placeholder="请输入来文单位"></t-input>
          </t-form-item>
        </t-space>

        <t-space align="center" style="width:100%;margin-bottom: 20px;" v-for="(item,index) in formData.dataList">
          <t-form-item v-for="department in item" :key="department.name" :label="department.name"
                       :name="item.name">
            <t-input-number v-model="department.value" style="width:100%;" theme="column" max="1" min="0" type="number"
                            :placeholder="!formDisabled?'分发 '+department.name:''"/>
          </t-form-item>
        </t-space>

        <t-space align="center" style="width:100%;margin-bottom: 20px;">

          <t-form-item label="收发日期" name="date" :rules="[{required:true,message:'请选择收发日期'}]">
            <t-date-picker v-model="formData.date" style="width:100%" placeholder="请选择收发日期" mode="date"/>
          </t-form-item>

          <t-form-item label="报告日期" name="reportTime">
            <t-input v-model="formData.reportTime" style="width:100%"
                     :placeholder="!formDisabled?'请输入报告日期':' '"/>
          </t-form-item>
        </t-space>

        <t-form-item>
          <t-space size="large" style="display:flex;justify-content:flex-end;">
            <t-button theme="default" variant="base" type="reset" v-if="!formDisabled && type=='add'">重置</t-button>
          </t-space>
        </t-form-item>
      </t-form>
    </t-space>
  </div>
</template>

<style scoped lang="less">
/deep/ .t-input.t-is-disabled .t-input__inner {
  color: var(--td-text-color-primary) !important;
}
</style>
