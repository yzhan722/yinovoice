/**
 * CONTEXT naming facade for Platform Operator ↔ Tenant / Instance / Call Record.
 * HTTP paths still hit legacy AVM endpoints until Platform Core ships.
 */
export { OperatorTenantService } from './OperatorTenantService';
export { OperatorInstanceService } from './OperatorInstanceService';
export { TenantInstanceService } from './TenantInstanceService';
export { OperatorCallRecordService } from './OperatorCallRecordService';
export { TenantCallRecordService } from './TenantCallRecordService';
export {
  CUSTOMER_SERVICE_VERSION_CONFLICT,
  DEMO_CUSTOMER_SERVICE_ID,
  DEMO_TENANT_ID,
  RealtimeVoiceService,
  TTS_VOICE_OPTIONS,
} from './RealtimeVoiceService';
export { CALL_API_PATHS, normalizeCallListItem, normalizeCallDetail } from './callContract';
export { OperatorDashboardService } from './OperatorDashboardService';
export { TenantDashboardService } from './TenantDashboardService';
export { OperatorKnowledgeService } from './OperatorKnowledgeService';
export { TenantKnowledgeService } from './TenantKnowledgeService';
export { OperatorTemplateService, TenantInstanceFactoryService } from './TemplateServices';
export {
  TenantCallbackService,
  TenantAppointmentService,
  TenantKnowledgeMock,
  TenantHomeService,
} from './OpsServices';
