import { BASE_API } from '@/config/api';

export default {
  /** 管理员-通话记录分页（attName、userAccount、userNickname、startedAtFrom、startedAtTo、attAssistantId） */
  LIST: BASE_API + 'api/admin/call-history/list',
  /** 管理员-手动同步通话（可选 attVendorId、limit、createdAtGe/Le、updatedAtGe/Le） */
  SYNC: BASE_API + 'api/admin/call-history/sync',
  /** 管理员-通话详情（含 messages，已排除 system） */
  DETAIL: BASE_API + 'api/admin/call-history/detail',
};
