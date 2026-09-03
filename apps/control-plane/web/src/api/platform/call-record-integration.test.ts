import { describe, expect, it, vi } from 'vitest';

vi.mock('@/store', () => ({
  useUserStore: () => ({}),
}));

import { getMenuList } from '@/api/permission';

import { OperatorCallRecordService } from './OperatorCallRecordService';
import { TenantCallRecordService } from './TenantCallRecordService';

function facade() {
  return {
    listNormalizedCallRecords: vi.fn().mockResolvedValue({
      records: [{ aacId: 'record-1' }],
      list: [{ aacId: 'record-1' }],
      total: 1,
      ready: true,
    }),
    getNormalizedCallRecord: vi.fn().mockResolvedValue({ aacId: 'record-1' }),
  };
}

describe('call record page services', () => {
  it('maps tenant page pagination to the Platform API facade', async () => {
    const voice = facade();
    const service = new TenantCallRecordService(voice);

    const result = await service.getList({ page: 2, pageSize: 10 });
    const detail = await service.getDetail('record-1');

    expect(voice.listNormalizedCallRecords).toHaveBeenCalledWith({
      limit: 10,
      offset: 10,
      includeDeleted: false,
    });
    expect(voice.getNormalizedCallRecord).toHaveBeenCalledWith('record-1');
    expect(result.total).toBe(1);
    expect(detail.aacId).toBe('record-1');
  });

  it('uses the configured demo tenant facade for operator pagination', async () => {
    const voice = facade();
    const service = new OperatorCallRecordService(voice);

    await service.getList({ current: 3, pageSize: 5 });
    await service.getDetail('record-1');

    expect(voice.listNormalizedCallRecords).toHaveBeenCalledWith({
      limit: 5,
      offset: 10,
      includeDeleted: false,
    });
    expect(voice.getNormalizedCallRecord).toHaveBeenCalledWith('record-1');
  });
});

describe('realtime voice and record menus', () => {
  it('places tenant realtime voice ahead of tenant call history', async () => {
    const { list } = await getMenuList('user') as any;
    const realtime = list.find((menu: any) => menu.path === '/user/realtime-voice');
    const records = list.find((menu: any) => menu.path === '/user/call-history');

    expect(realtime.meta.title).toEqual({ zh_CN: '实时语音', en_US: 'Realtime Voice' });
    expect(realtime.meta.orderNo).toBeLessThan(records.meta.orderNo);
    expect(realtime.children[0].component).toBe('user/realtime-voice/index');
  });

  it('exposes tenant telephony and scheduling pages', async () => {
    const { list } = await getMenuList('user') as any;
    const telephony = list.find((menu: any) => menu.path === '/user/telephony');
    const scheduling = list.find((menu: any) => menu.path === '/user/scheduling');

    expect(telephony.meta.title).toEqual({ zh_CN: '电话号码', en_US: 'Phone Numbers' });
    expect(scheduling.meta.title).toEqual({ zh_CN: '排期设置', en_US: 'Scheduling' });
    expect(telephony.children[0].component).toBe('user/telephony/index');
    expect(scheduling.children[0].component).toBe('user/scheduling/index');
  });

  it('hides achievement and celebration gamification from the tenant sidebar', async () => {
    const { list } = (await getMenuList('user')) as any;
    const achievements = list.find((menu: any) => menu.path === '/user/achievements');
    const celebration = list.find((menu: any) => menu.path === '/user/celebration');
    expect(achievements.meta.hideInMenu).toBe(true);
    expect(celebration.meta.hideInMenu).toBe(true);
  });

  it('makes demo-tenant call records routable for operator users', async () => {
    const { list } = await getMenuList('admin') as any;
    const records = list.find((menu: any) => menu.path === '/admin/call-history');

    expect(records.meta.title).toEqual({ zh_CN: '通话记录', en_US: 'Call Records' });
    expect(records.children.map((child: any) => child.name)).toEqual([
      'AdminCallHistoryIndex',
      'AdminCallHistoryDetail',
    ]);
  });
});
