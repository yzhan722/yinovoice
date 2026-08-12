import AdminUserEnum from '@/enum/AdminUserEnum';
import $WRequest from '@/utils/request/WRequest';

/** Platform Operator — Tenant CRUD (legacy: AdminUserService / api/admin/user/*) */
export class OperatorTenantService {
  getTenantList(param) {
    return $WRequest.postNoAnimation(AdminUserEnum.GET_USER_LIST, { ...param });
  }

  getTenantDetail(param) {
    return $WRequest.post(AdminUserEnum.GET_USER_DETAIL, { ...param });
  }

  updateTenant(param) {
    return $WRequest.post(AdminUserEnum.UPDATE_USER, param);
  }

  getTenantLoginLogs(param) {
    return $WRequest.post(AdminUserEnum.GET_USER_LOGIN_LOGS, param);
  }

  checkAccount(userAccount) {
    return $WRequest.post(AdminUserEnum.CHECK_ACCOUNT, { userAccount });
  }

  createTenant(param) {
    return $WRequest.post(AdminUserEnum.CREATE_USER, param);
  }

  deleteTenant(param) {
    return $WRequest.post(AdminUserEnum.DELETE_USER, param);
  }

  updateTenantPassword(param) {
    return $WRequest.post(AdminUserEnum.UPDATE_USER_PASSWORD, param);
  }

  updateTenantAvatar(param) {
    return $WRequest.post(AdminUserEnum.UPDATE_USER_AVATAR, param);
  }

  getTenantActionLogs(param) {
    return $WRequest.post(AdminUserEnum.GET_USER_ACTION_LOGS, param);
  }

  queryLoginLogsByPage(param) {
    return $WRequest.post(AdminUserEnum.QUERY_LOGIN_LOGS_BY_PAGE, param);
  }

  queryActionLogsByPage(param) {
    return $WRequest.post(AdminUserEnum.QUERY_ACTION_LOGS_BY_PAGE, param);
  }

  // legacy aliases used by migrated pages
  getUserList(param) {
    return this.getTenantList(param);
  }
  getUserDetail(param) {
    return this.getTenantDetail(param);
  }
  updateUser(param) {
    return this.updateTenant(param);
  }
  createUser(param) {
    return this.createTenant(param);
  }
  deleteUser(param) {
    return this.deleteTenant(param);
  }
  updateUserPassword(param) {
    return this.updateTenantPassword(param);
  }
  updateUserAvatar(param) {
    return this.updateTenantAvatar(param);
  }
  getUserLoginLogs(param) {
    return this.getTenantLoginLogs(param);
  }
  getUserActionLogs(param) {
    return this.getTenantActionLogs(param);
  }
}
