<template>
  <div class="dialog-backdrop" role="presentation" @click.self="$emit('close')">
    <section class="dialog" role="dialog" aria-modal="true" aria-labelledby="create-title">
      <div class="dialog-head">
        <h2 id="create-title">新建语音实例</h2>
        <button type="button" class="close" aria-label="关闭" @click="$emit('close')">×</button>
      </div>
      <form @submit.prevent="submit">
        <label>
          实例名称
          <input v-model.trim="form.display_name" data-testid="display-name" required maxlength="80" />
        </label>
        <label>
          机构名称
          <input v-model.trim="form.organization_name" data-testid="organization-name" required maxlength="120" />
        </label>
        <label>
          欢迎语
          <textarea v-model.trim="form.greeting" data-testid="greeting" required maxlength="300" rows="3" />
        </label>
        <label>
          音色
          <select v-model="form.tts_voice">
            <option v-for="voice in TTS_VOICE_OPTIONS" :key="voice.value" :value="voice.value">
              {{ voice.label }}
            </option>
          </select>
        </label>
        <label>
          Platform Prompt
          <textarea v-model="form.platform_prompt" maxlength="8000" rows="4" />
        </label>
        <label>
          Tenant Prompt
          <textarea v-model="form.tenant_prompt" maxlength="8000" rows="4" />
        </label>
        <p v-if="errorMessage" role="alert" class="error">{{ errorMessage }}</p>
        <div class="actions">
          <button type="button" :disabled="submitting" @click="$emit('close')">取消</button>
          <button type="submit" :disabled="submitting">{{ submitting ? '创建中…' : '创建实例' }}</button>
        </div>
      </form>
    </section>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue';
import { RealtimeVoiceService, TTS_VOICE_OPTIONS } from '@/api/platform';
import type { CustomerServiceInstance, TtsVoiceId } from '@/api/platform/RealtimeVoiceService';

const emit = defineEmits<{
  (event: 'close'): void;
  (event: 'created', instance: CustomerServiceInstance): void;
}>();

const service = new RealtimeVoiceService();
const submitting = ref(false);
const errorMessage = ref('');
const form = reactive({
  display_name: '演示前台接待',
  organization_name: '合成演示机构',
  greeting: '您好，这里是合成演示机构客服，请问有什么可以帮您？',
  platform_prompt: [
    '你是 Yino 语音客服演示助手。',
    '回答简洁、礼貌，一次只问一个问题。',
    '只使用合成演示信息，不编造真实客户、患者或医疗结论。',
    '若信息不足，先澄清需求，再给出可执行的下一步建议。',
  ].join('\n'),
  tenant_prompt: [
    '机构：合成演示机构。',
    '服务范围：前台接待、预约咨询指引、活动信息说明（均为虚构演示数据）。',
    '营业时间：周一至周五 09:00-18:00（演示）。',
    '转人工触发：用户明确要求人工，或连续两轮无法理解意图。',
    '禁止：收集真实身份证号、详细病历、支付密码等敏感信息。',
  ].join('\n'),
  tts_voice: 'longanqian' as TtsVoiceId,
});

async function submit() {
  if (submitting.value) return;
  submitting.value = true;
  errorMessage.value = '';
  try {
    const instance = await service.createCustomerService({
      display_name: form.display_name,
      organization_name: form.organization_name,
      greeting: form.greeting,
      platform_prompt: form.platform_prompt,
      tenant_prompt: form.tenant_prompt,
      voice: {
        preset_id: 'mandarin-standard', locale: 'zh-CN', speaking_rate: 1, volume: 1,
        pitch: 0, style: 'professional-friendly', emotion: 'neutral',
        pause_profile: 'receptionist', tts_voice: form.tts_voice,
      },
      response: {
        brevity: 'concise', max_spoken_sentences: 3, ask_one_question_at_a_time: true,
      },
    });
    emit('created', instance);
  } catch {
    errorMessage.value = '创建失败，请检查输入后重试。';
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped lang="less">
.dialog-backdrop { position: fixed; inset: 0; z-index: 1000; display: grid; place-items: center; padding: 20px; background: rgb(0 0 0 / 45%); }
.dialog { width: min(640px, 100%); max-height: 90vh; overflow: auto; padding: 22px; border-radius: 12px; background: var(--demo-card, #fff); }
.dialog-head, .actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
h2 { margin: 0; }
.close { border: 0; background: transparent; font-size: 26px; cursor: pointer; }
form { display: grid; gap: 14px; margin-top: 18px; }
label { display: grid; gap: 6px; color: var(--demo-ink); font-weight: 600; }
input, textarea, select { box-sizing: border-box; width: 100%; padding: 9px 10px; border: 1px solid var(--demo-line, #dcdcdc); border-radius: 6px; font: inherit; }
.actions { justify-content: flex-end; }
.actions button { padding: 8px 16px; cursor: pointer; }
.error { margin: 0; color: #c62828; }
</style>
