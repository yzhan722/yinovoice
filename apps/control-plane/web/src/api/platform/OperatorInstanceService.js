import AdminAssistantEnum from '@/enum/AdminAssistantEnum';
import $WRequest from '@/utils/request/WRequest';

/** Platform Operator — Voice Agent Instance (legacy: AdminAssistantService) */
export class OperatorInstanceService {
  getInstanceList(param) {
    return $WRequest.postNoAnimation(AdminAssistantEnum.GET_ASSISTANT_LIST, { ...param });
  }

  getInstanceDetail(param) {
    return $WRequest.post(AdminAssistantEnum.GET_ASSISTANT_DETAIL, { ...param });
  }

  updateInstance(param) {
    return $WRequest.post(AdminAssistantEnum.UPDATE_ASSISTANT, param);
  }

  /** @deprecated VAPI sync — do not expose in P0 UI */
  syncInstances() {
    return $WRequest.post(AdminAssistantEnum.SYNC_ASSISTANTS, {});
  }

  assignInstance(param) {
    return $WRequest.post(AdminAssistantEnum.ASSIGN_ASSISTANT, param);
  }

  searchTenants(searchTerm) {
    return $WRequest.post(AdminAssistantEnum.SEARCH_USERS, { searchTerm });
  }

  // legacy aliases
  getAssistantList(param) {
    return this.getInstanceList(param);
  }
  getAssistantDetail(param) {
    return this.getInstanceDetail(param);
  }
  updateAssistant(param) {
    return this.updateInstance(param);
  }
  syncAssistants() {
    return this.syncInstances();
  }
  assignAssistant(param) {
    return this.assignInstance(param);
  }
  searchUsers(searchTerm) {
    return this.searchTenants(searchTerm);
  }
}
