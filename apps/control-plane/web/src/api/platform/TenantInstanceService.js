import UserEnum from '@/enum/UserEnum';
import $WRequest from '@/utils/request/WRequest';
import { shellMockEnabled } from '@/mocks/shell';
import { listInstances, getTemplate } from '@/mocks/templateStore';

/** Tenant — Voice Agent Instance (legacy: UserAssistantService) */
export class TenantInstanceService {
  async getMyList() {
    if (shellMockEnabled()) {
      const { list } = await listInstances();
      return list.map((x) => ({
        attId: x.attId,
        attVendorId: x.attVendorId,
        attName: x.attName,
        templateId: x.templateId,
        templateVersion: x.templateVersion,
        templateName: x.templateName,
        orgName: x.fields?.orgName || '',
        businessHours: x.fields?.businessHours || '',
        callReadySlot: true,
      }));
    }
    return $WRequest.postNoAnimation(UserEnum.ASSISTANT_OPTIONS, {});
  }

  async getDetail(attId) {
    if (shellMockEnabled()) {
      const { list } = await listInstances();
      const inst = list.find((x) => String(x.attId) === String(attId));
      if (!inst) {
        const err = new Error('实例不存在');
        err.code = 404;
        throw err;
      }
      let templateName = inst.templateName;
      try {
        const tpl = await getTemplate(inst.templateId);
        templateName = tpl.name;
      } catch (_) {}
      return {
        attId: inst.attId,
        attName: inst.attName,
        attVendorId: inst.attVendorId,
        templateId: inst.templateId,
        templateVersion: inst.templateVersion,
        templateName,
        fields: inst.fields,
        userSystemPrompt: `【壳模式】绑定模板 ${templateName} @ ${inst.templateVersion}\n机构：${inst.fields?.orgName || ''}\n地址：${inst.fields?.address || ''}`,
        attFirstMessage: `您好，这里是${inst.fields?.orgName || inst.attName}，有什么可以帮您？`,
        attVoicemailMessage: '我们暂时无法接听，请留言。',
        attEndCallMessage: '感谢来电，再见。',
        attForwardingPhone: inst.fields?.contactPhone || '',
        attVoiceConfig: JSON.stringify({ provider: '11labs', voiceId: 'sarah', stability: 0.5, similarityBoost: 0.75 }),
        attModelConfig: JSON.stringify({ provider: 'openai', model: 'gpt-4o-mini', temperature: 0.7, maxTokens: 2000 }),
        attTranscriberConfig: JSON.stringify({ provider: 'deepgram', model: 'nova-2', language: 'zh' }),
      };
    }
    return $WRequest.postNoAnimation(UserEnum.ASSISTANT_DETAIL, { attId });
  }

  async update(param) {
    if (shellMockEnabled()) {
      try {
        const raw = sessionStorage.getItem('yino-shell-template-store-v3');
        if (raw) {
          const data = JSON.parse(raw);
          const inst = data.instances.find((x) => String(x.attId) === String(param.attId));
          if (inst) {
            if (param.userSystemPrompt != null) inst.userSystemPrompt = param.userSystemPrompt;
            if (param.attFirstMessage != null) inst.attFirstMessage = param.attFirstMessage;
            if (param.attName != null) inst.attName = param.attName;
            sessionStorage.setItem('yino-shell-template-store-v3', JSON.stringify(data));
          }
        }
      } catch (_) {}
      return { ok: true, ...param };
    }
    return $WRequest.post(UserEnum.ASSISTANT_UPDATE, { ...param });
  }
}