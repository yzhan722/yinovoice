/**
 * In-memory Template / Instance store for shell demo (VITE_SHELL_MOCK).
 * Survives HMR via sessionStorage snapshot.
 */

const STORE_KEY = 'yino-shell-template-store-v3';

/** @typedef {'draft'|'published'|'disabled'} TemplateStatus */

function seed() {
  return {
    templates: [
      {
        id: 'tpl-generic-receptionist',
        name: 'Generic Receptionist',
        type: 'generic',
        version: '1.0.0',
        status: 'published',
        parentTemplateId: null,
        parentVersion: null,
        description: '行业无关接待员：FAQ、信息收集、通用预约、转人工与回拨。',
        requiredFields: [
          { key: 'orgName', label: '机构名称', required: true },
          { key: 'address', label: '地址', required: true },
          { key: 'businessHours', label: '营业时间', required: true },
          { key: 'contactPhone', label: '联系电话', required: false },
        ],
        publishedAt: '2026-07-29T10:00:00+08:00',
      },
      {
        id: 'tpl-dental',
        name: 'Dental Receptionist',
        type: 'domain',
        version: '1.0.0',
        status: 'published',
        parentTemplateId: 'tpl-generic-receptionist',
        parentVersion: '1.0.0',
        description: '由通用模板派生的牙科模板：咨询、预约、不诊断与紧急回退。',
        requiredFields: [
          { key: 'orgName', label: '诊所名称', required: true },
          { key: 'address', label: '诊所地址', required: true },
          { key: 'businessHours', label: '营业时间', required: true },
          { key: 'doctors', label: '医生名单（逗号分隔）', required: true },
          { key: 'services', label: '主要服务项目', required: true },
          { key: 'notifyStaff', label: '人工通知对象', required: false },
        ],
        publishedAt: '2026-07-30T09:00:00+08:00',
      },
      {
        id: 'tpl-generic-v2-draft',
        name: 'Generic Receptionist',
        type: 'generic',
        version: '1.1.0-draft',
        status: 'draft',
        parentTemplateId: null,
        parentVersion: null,
        description: '下一版通用模板草稿（未发布，租户不可见）。',
        requiredFields: [
          { key: 'orgName', label: '机构名称', required: true },
          { key: 'address', label: '地址', required: true },
        ],
        publishedAt: null,
      },
    ],
    instances: [
      {
        id: 'ins-1001',
        attId: 1001,
        attName: '太平洋口腔 · 新北前台',
        attVendorId: 'inst-1001',
        templateId: 'tpl-dental',
        templateVersion: '1.0.0',
        templateName: 'Dental Receptionist',
        fields: {
          orgName: '常州太平洋口腔（新北旗舰店）',
          address: '常州市新北区通江南路266号（城市候机楼北侧 / 三井加油站旁）',
          businessHours: '周一至周日 08:30–17:30（无休假门诊）',
          doctors: '刘正秋, 易虎, 张正乔, 密燕, 杜飞, 虞晓婷',
          services: '种植牙, 隐形矫正, 舌侧矫正, 儿牙早矫, DSD美学修复, 洁牙洗牙',
          notifyStaff: '前台预约组',
          contactPhone: '400-0519-020',
        },
        createdAt: '2026-08-01T10:00:00+08:00',
      },
    ],
    nextAttId: 1002,
  };
}

function load() {
  try {
    const raw = sessionStorage.getItem(STORE_KEY);
    if (raw) return JSON.parse(raw);
  } catch (_) {}
  const data = seed();
  save(data);
  return data;
}

function save(data) {
  sessionStorage.setItem(STORE_KEY, JSON.stringify(data));
}

export function listTemplates({ publishedOnly = false } = {}) {
  const data = load();
  let list = [...data.templates];
  if (publishedOnly) list = list.filter((t) => t.status === 'published');
  return Promise.resolve({ list });
}

export function getTemplate(id) {
  const data = load();
  const tpl = data.templates.find((t) => t.id === id);
  if (!tpl) {
    const err = new Error('模板不存在');
    err.code = 404;
    return Promise.reject(err);
  }
  return Promise.resolve(tpl);
}

export function setTemplateStatus(id, status) {
  const data = load();
  const tpl = data.templates.find((t) => t.id === id);
  if (!tpl) {
    const err = new Error('模板不存在');
    err.code = 404;
    return Promise.reject(err);
  }
  if (!['draft', 'published', 'disabled'].includes(status)) {
    return Promise.reject(new Error('非法状态'));
  }
  // published versions are immutable content-wise; status may move published ↔ disabled
  if (tpl.status === 'draft' && status === 'disabled') {
    return Promise.reject(new Error('草稿不能直接停用，请先发布或保持草稿'));
  }
  tpl.status = status;
  if (status === 'published' && !tpl.publishedAt) {
    tpl.publishedAt = new Date().toISOString();
    tpl.version = tpl.version.replace(/-draft$/, '') || '1.0.0';
  }
  save(data);
  return Promise.resolve(tpl);
}

export function listInstances() {
  const data = load();
  return Promise.resolve({ list: [...data.instances] });
}

export function createInstanceFromTemplate({ templateId, fields, attName }) {
  const data = load();
  const tpl = data.templates.find((t) => t.id === templateId);
  if (!tpl) {
    const err = new Error('模板不存在');
    err.code = 404;
    return Promise.reject(err);
  }
  if (tpl.status !== 'published') {
    const err = new Error('只能从已发布模板创建实例');
    err.code = 400;
    return Promise.reject(err);
  }
  for (const f of tpl.requiredFields || []) {
    if (f.required && !(fields?.[f.key] || '').toString().trim()) {
      const err = new Error(`请填写：${f.label}`);
      err.code = 400;
      return Promise.reject(err);
    }
  }
  const attId = data.nextAttId++;
  const vendor = `inst-${attId}`;
  const instance = {
    id: `ins-${attId}`,
    attId,
    attName: (attName || fields?.orgName || `Instance ${attId}`).toString(),
    attVendorId: vendor,
    templateId: tpl.id,
    templateVersion: tpl.version,
    templateName: tpl.name,
    fields: { ...fields },
    createdAt: new Date().toISOString(),
  };
  data.instances.push(instance);
  save(data);
  return Promise.resolve(instance);
}

export function resetShellTemplateStore() {
  sessionStorage.removeItem(STORE_KEY);
  return load();
}
