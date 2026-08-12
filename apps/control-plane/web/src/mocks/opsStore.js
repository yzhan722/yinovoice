/**
 * Shell mock ops + dashboard fixtures (clinic-realistic, ~1 week).
 * Bump STORE_KEY when seed shape changes so demos refresh.
 */

const STORE_KEY = 'yino-shell-ops-store-v4';

function dayOffset(days, hour = 10, minute = 0) {
  const d = new Date();
  d.setHours(hour, minute, 0, 0);
  d.setDate(d.getDate() + days);
  return d.toISOString();
}

function seed() {
  return {
    callbacks: [
      {
        id: 'cb-1001',
        status: 'open',
        reason: '预约写入失败需回拨',
        callerPhone: '138****2210',
        instanceName: '太平洋口腔 · 新北前台',
        attId: 1001,
        summary: '张先生希望改到周五下午洁牙，系统写预约超时，已告知人工回电确认。',
        createdAt: dayOffset(0, 9, 20),
        updatedAt: dayOffset(0, 9, 20),
      },
      {
        id: 'cb-1003',
        status: 'open',
        reason: '种植咨询转人工',
        callerPhone: '136****7721',
        instanceName: '太平洋口腔 · 新北前台',
        attId: 1001,
        summary: '询问种植大致费用与是否可分期，要求顾问回电说明。',
        createdAt: dayOffset(0, 11, 5),
        updatedAt: dayOffset(0, 11, 5),
      },
      {
        id: 'cb-1004',
        status: 'open',
        reason: '儿童齿科家长回电',
        callerPhone: '159****3340',
        instanceName: '太平洋口腔 · 新北前台',
        attId: 1001,
        summary: '孩子第一次看牙紧张，希望前台说明流程与陪同政策。',
        createdAt: dayOffset(-1, 16, 40),
        updatedAt: dayOffset(-1, 16, 40),
      },
      {
        id: 'cb-1005',
        status: 'open',
        reason: '医保报销咨询',
        callerPhone: '187****9012',
        instanceName: '太平洋口腔 · 新北前台',
        attId: 1001,
        summary: '询问洁牙是否可刷医保，语音未能完整回答，需人工确认政策。',
        createdAt: dayOffset(0, 14, 12),
        updatedAt: dayOffset(0, 14, 12),
      },
      {
        id: 'cb-1006',
        status: 'open',
        reason: '改期确认',
        callerPhone: '131****5568',
        instanceName: '太平洋口腔 · 新北前台',
        attId: 1001,
        summary: '原周三补牙档期冲突，需确认周四上午是否仍有空位。',
        createdAt: dayOffset(-1, 10, 15),
        updatedAt: dayOffset(-1, 10, 15),
      },
      {
        id: 'cb-1002',
        status: 'done',
        reason: '用户要求转人工',
        callerPhone: '139****8801',
        instanceName: '太平洋口腔 · 新北前台',
        attId: 1001,
        summary: '咨询种植价格，已于昨日完成回拨并预约面诊。',
        createdAt: dayOffset(-2, 15, 0),
        updatedAt: dayOffset(-1, 11, 30),
      },
      {
        id: 'cb-1007',
        status: 'done',
        reason: '地址导航说明',
        callerPhone: '150****2209',
        instanceName: '太平洋口腔 · 新北前台',
        attId: 1001,
        summary: '已短信发送停车场与地铁出口指引。',
        createdAt: dayOffset(-3, 9, 40),
        updatedAt: dayOffset(-3, 10, 5),
      },
    ],
    appointments: [
      {
        id: 'apt-2001',
        status: 'confirmed',
        patientName: '张先生',
        phone: '138****2210',
        service: '常规洁牙',
        slotStart: dayOffset(0, 15, 0),
        slotEnd: dayOffset(0, 15, 30),
        instanceName: '太平洋口腔 · 新北前台',
        source: 'demo-scheduling-authority',
        createdAt: dayOffset(-1, 18, 0),
      },
      {
        id: 'apt-2003',
        status: 'confirmed',
        patientName: '王女士',
        phone: '186****4410',
        service: '补牙复查',
        slotStart: dayOffset(0, 10, 30),
        slotEnd: dayOffset(0, 11, 0),
        instanceName: '太平洋口腔 · 新北前台',
        source: 'demo-scheduling-authority',
        createdAt: dayOffset(-2, 12, 0),
      },
      {
        id: 'apt-2004',
        status: 'confirmed',
        patientName: '陈小朋友',
        phone: '159****3340',
        service: '儿童涂氟',
        slotStart: dayOffset(0, 16, 30),
        slotEnd: dayOffset(0, 17, 0),
        instanceName: '太平洋口腔 · 新北前台',
        source: 'demo-scheduling-authority',
        createdAt: dayOffset(-1, 9, 0),
      },
      {
        id: 'apt-2005',
        status: 'pending',
        patientName: '赵先生',
        phone: '137****7788',
        service: '种植初诊咨询',
        slotStart: dayOffset(1, 14, 0),
        slotEnd: dayOffset(1, 14, 30),
        instanceName: '太平洋口腔 · 新北前台',
        source: 'demo-scheduling-authority',
        createdAt: dayOffset(0, 8, 50),
      },
      {
        id: 'apt-2006',
        status: 'pending',
        patientName: '周女士',
        phone: '188****1122',
        service: '牙齿美白咨询',
        slotStart: dayOffset(2, 11, 0),
        slotEnd: dayOffset(2, 11, 30),
        instanceName: '太平洋口腔 · 新北前台',
        source: 'demo-scheduling-authority',
        createdAt: dayOffset(0, 13, 20),
      },
      {
        id: 'apt-2007',
        status: 'confirmed',
        patientName: '刘先生',
        phone: '135****9090',
        service: '洗牙',
        slotStart: dayOffset(3, 9, 30),
        slotEnd: dayOffset(3, 10, 0),
        instanceName: '太平洋口腔 · 新北前台',
        source: 'demo-scheduling-authority',
        createdAt: dayOffset(-2, 16, 0),
      },
      {
        id: 'apt-2008',
        status: 'confirmed',
        patientName: '孙女士',
        phone: '133****5566',
        service: '正畸复诊',
        slotStart: dayOffset(4, 15, 0),
        slotEnd: dayOffset(4, 15, 40),
        instanceName: '太平洋口腔 · 新北前台',
        source: 'demo-scheduling-authority',
        createdAt: dayOffset(-3, 11, 0),
      },
      {
        id: 'apt-2009',
        status: 'confirmed',
        patientName: '吴先生',
        phone: '152****3344',
        service: '拔智齿评估',
        slotStart: dayOffset(5, 10, 0),
        slotEnd: dayOffset(5, 10, 30),
        instanceName: '太平洋口腔 · 新北前台',
        source: 'demo-scheduling-authority',
        createdAt: dayOffset(-4, 14, 0),
      },
      {
        id: 'apt-2002',
        status: 'cancelled',
        patientName: '李女士',
        phone: '137****5566',
        service: '初诊咨询',
        slotStart: dayOffset(1, 9, 0),
        slotEnd: dayOffset(1, 9, 30),
        instanceName: '太平洋口腔 · 新北前台',
        source: 'demo-scheduling-authority',
        createdAt: dayOffset(-1, 20, 0),
      },
    ],
    followUps: [
      {
        id: 'fu-1',
        title: '回拨张先生确认周五洁牙档期',
        status: 'todo',
        related: 'cb-1001',
        createdAt: dayOffset(0, 9, 25),
      },
      {
        id: 'fu-2',
        title: '回电说明种植费用与面诊准备',
        status: 'todo',
        related: 'cb-1003',
        createdAt: dayOffset(0, 11, 10),
      },
      {
        id: 'fu-3',
        title: '确认赵先生种植初诊待确认预约',
        status: 'todo',
        related: 'apt-2005',
        createdAt: dayOffset(0, 8, 55),
      },
      {
        id: 'fu-4',
        title: '整理儿童齿科陪同说明并短信发送',
        status: 'doing',
        related: 'cb-1004',
        createdAt: dayOffset(-1, 16, 50),
      },
      {
        id: 'fu-5',
        title: '核对医保洁牙政策答复口径',
        status: 'doing',
        related: 'cb-1005',
        createdAt: dayOffset(0, 14, 20),
      },
      {
        id: 'fu-6',
        title: '回访昨日种植咨询客户是否到店',
        status: 'done',
        related: 'cb-1002',
        createdAt: dayOffset(-1, 11, 40),
      },
      {
        id: 'fu-7',
        title: '确认王女士今日补牙复查到诊',
        status: 'done',
        related: 'apt-2003',
        createdAt: dayOffset(0, 9, 0),
      },
    ],
    activities: [
      {
        id: 'act-1',
        text: '处理回拨：张先生改期洁牙',
        at: dayOffset(0, 9, 22),
        kind: 'callback',
      },
      {
        id: 'act-2',
        text: '确认预约：王女士补牙复查（今日 10:30）',
        at: dayOffset(0, 8, 10),
        kind: 'appointment',
      },
      {
        id: 'act-3',
        text: '来电咨询：种植费用（已转人工待回拨）',
        at: dayOffset(0, 11, 6),
        kind: 'call',
      },
      {
        id: 'act-4',
        text: '确认预约：陈小朋友儿童涂氟（今日 16:30）',
        at: dayOffset(-1, 17, 0),
        kind: 'appointment',
      },
      {
        id: 'act-5',
        text: '完成回拨：种植价格咨询并预约面诊',
        at: dayOffset(-1, 11, 30),
        kind: 'callback',
      },
      {
        id: 'act-6',
        text: '知识库更新：价目表示例解析中',
        at: dayOffset(0, 13, 40),
        kind: 'knowledge',
      },
      {
        id: 'act-7',
        text: '来电：营业时间与停车指引',
        at: dayOffset(-2, 14, 20),
        kind: 'call',
      },
    ],
    /** Demo-only call analytics (UI showcase; not live telephony) */
    callStats: {
      todayCount: 18,
      weekCount: 86,
      monthCount: 312,
      todayMinutes: 142,
      connectedToday: 16,
      effectiveToday: 12,
      openCallbacksYesterday: 3,
      trend: [0, 1, 2, 3, 4, 5, 6].map((i) => {
        const d = new Date();
        d.setDate(d.getDate() - (6 - i));
        const weekday = d.getDay(); // 0 Sun
        const base = weekday === 0 ? 6 : weekday === 6 ? 10 : 12 + (weekday % 3);
        return {
          date: d.toISOString().slice(0, 10),
          count: base + (i % 2),
          minutes: base * 7 + i * 3,
          connected: Math.max(4, base - 1),
          effective: Math.max(3, base - 3),
        };
      }),
    },
    knowledgeFiles: [
      {
        filId: 501,
        filName: '太平洋口腔新北店介绍与FAQ.txt',
        filSizeBytes: 4280,
        filMimeType: 'text/plain',
        filExtStatus: 'done',
        filUrl: '',
        filCreateTime: dayOffset(-3, 10, 0),
        scope: 'mine',
      },
      {
        filId: 502,
        filName: '通江南路266号交通与停车.docx',
        filSizeBytes: 18200,
        filMimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        filExtStatus: 'done',
        filUrl: '',
        filCreateTime: dayOffset(-1, 11, 0),
        scope: 'associated',
      },
      {
        filId: 503,
        filName: '种植与矫正项目说明.pdf',
        filSizeBytes: 96000,
        filMimeType: 'application/pdf',
        filExtStatus: 'processing',
        filUrl: '',
        filCreateTime: dayOffset(0, 13, 30),
        scope: 'mine',
      },
      {
        filId: 504,
        filName: '儿童齿科须知.pdf',
        filSizeBytes: 22000,
        filMimeType: 'application/pdf',
        filExtStatus: 'done',
        filUrl: '',
        filCreateTime: dayOffset(-5, 15, 0),
        scope: 'mine',
      },
      {
        filId: 505,
        filName: '种植面诊准备事项.txt',
        filSizeBytes: 3100,
        filMimeType: 'text/plain',
        filExtStatus: 'done',
        filUrl: '',
        filCreateTime: dayOffset(-2, 9, 0),
        scope: 'mine',
      },
    ],
    nextCb: 1108,
    nextApt: 2110,
    nextFil: 560,
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

export function listCallbackTasks({ status } = {}) {
  const data = load();
  let list = [...data.callbacks];
  if (status) list = list.filter((x) => x.status === status);
  list.sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
  return Promise.resolve({ list });
}

export function updateCallbackStatus(id, status) {
  const data = load();
  const row = data.callbacks.find((x) => x.id === id);
  if (!row) return Promise.reject(new Error('任务不存在'));
  row.status = status;
  row.updatedAt = new Date().toISOString();
  save(data);
  return Promise.resolve(row);
}

export function createCallbackTask(partial = {}) {
  const data = load();
  const id = `cb-${data.nextCb++}`;
  const row = {
    id,
    status: 'open',
    reason: partial.reason || '人工回拨',
    callerPhone: partial.callerPhone || '未知号码',
    instanceName: partial.instanceName || '',
    attId: partial.attId ?? null,
    summary: partial.summary || '',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
  data.callbacks.unshift(row);
  save(data);
  return Promise.resolve(row);
}

export function listAppointments() {
  const data = load();
  const list = [...data.appointments].sort((a, b) =>
    String(a.slotStart).localeCompare(String(b.slotStart)),
  );
  return Promise.resolve({ list });
}

export function listFollowUps({ status } = {}) {
  const data = load();
  let list = [...(data.followUps || [])];
  if (status) list = list.filter((x) => x.status === status);
  const order = { todo: 0, doing: 1, done: 2 };
  list.sort((a, b) => (order[a.status] ?? 9) - (order[b.status] ?? 9));
  return Promise.resolve({ list });
}

export function updateFollowUpStatus(id, status) {
  const data = load();
  const row = (data.followUps || []).find((x) => x.id === id);
  if (!row) return Promise.reject(new Error('跟进事项不存在'));
  if (!['todo', 'doing', 'done'].includes(status)) {
    return Promise.reject(new Error('非法状态'));
  }
  row.status = status;
  save(data);
  return Promise.resolve(row);
}

export function listActivities() {
  const data = load();
  const list = [...(data.activities || [])].sort((a, b) =>
    String(b.at).localeCompare(String(a.at)),
  );
  return Promise.resolve({ list });
}

export function getCallStats() {
  const data = load();
  return Promise.resolve(data.callStats || null);
}

export function getHomeSummary() {
  const data = load();
  const openCallbacks = data.callbacks.filter((x) => x.status === 'open').length;
  const yesterdayOpen = data.callStats?.openCallbacksYesterday ?? 0;
  const delta = openCallbacks - yesterdayOpen;

  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const endOfToday = new Date(startOfToday);
  endOfToday.setDate(endOfToday.getDate() + 1);
  const endOfWeek = new Date(startOfToday);
  endOfWeek.setDate(endOfWeek.getDate() + 7);

  const apts = data.appointments.filter((x) => x.status !== 'cancelled');
  const todayApts = apts.filter((x) => {
    const t = new Date(x.slotStart).getTime();
    return t >= startOfToday.getTime() && t < endOfToday.getTime();
  }).length;
  const weekApts = apts.filter((x) => {
    const t = new Date(x.slotStart).getTime();
    return t >= startOfToday.getTime() && t < endOfWeek.getTime();
  }).length;
  const pendingConfirm = data.appointments.filter((x) => x.status === 'pending').length;

  const followUps = data.followUps || [];
  return Promise.resolve({
    callbacks: {
      open: openCallbacks,
      delta,
    },
    appointments: {
      today: todayApts,
      week: weekApts,
      pendingConfirm,
    },
    followUps: {
      todo: followUps.filter((x) => x.status === 'todo').length,
      doing: followUps.filter((x) => x.status === 'doing').length,
      done: followUps.filter((x) => x.status === 'done').length,
    },
    callStats: data.callStats,
  });
}

export function listKnowledgeFiles({ scope } = {}) {
  const data = load();
  let list = [...data.knowledgeFiles];
  if (scope === 'mine') list = list.filter((x) => x.scope === 'mine');
  if (scope === 'associated') list = list.filter((x) => x.scope === 'associated');
  return Promise.resolve({ list, total: list.length });
}

export function addKnowledgeFile(fileMeta = {}) {
  const data = load();
  const row = {
    filId: data.nextFil++,
    filName: fileMeta.filName || '未命名.txt',
    filSizeBytes: fileMeta.filSizeBytes || 1024,
    filMimeType: fileMeta.filMimeType || 'application/octet-stream',
    filExtStatus: 'processing',
    filUrl: '',
    filCreateTime: new Date().toISOString(),
    scope: 'mine',
  };
  data.knowledgeFiles.unshift(row);
  save(data);
  setTimeout(() => {
    try {
      const latest = load();
      const f = latest.knowledgeFiles.find((x) => x.filId === row.filId);
      if (f) {
        f.filExtStatus = 'done';
        save(latest);
      }
    } catch (_) {}
  }, 1500);
  return Promise.resolve(row);
}
