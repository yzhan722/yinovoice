import UserBasicEnum from '@/enum/UserBasicEnum';
import $WRequest from '@/utils/request/WRequest';
import {
  shellMockEnabled,
  shellLogin,
  shellTenantProfile,
} from '@/mocks/shell';

export class UserBasicService {
  /** Tenant login: /api/user/login */
  login(param) {
    if (shellMockEnabled()) {
      return Promise.resolve(shellLogin('tenant', param?.account, param?.password));
    }
    return $WRequest.post(UserBasicEnum.LOGIN, { ...param }).then((res) => res);
  }

  getUserInfo(param) {
    if (shellMockEnabled()) {
      return Promise.resolve(shellTenantProfile());
    }
    return $WRequest.post(UserBasicEnum.GET_USER_INFO, { ...param }).then((res) => res);
  }

  logout() {
    if (shellMockEnabled()) {
      return Promise.resolve({ ok: true });
    }
    return $WRequest.post(UserBasicEnum.LOGOUT).then((res) => res);
  }

  getAccessToken(param) {
    if (shellMockEnabled()) {
      return Promise.resolve({ accessToken: 'shell-access-token' });
    }
    return $WRequest
      .request(UserBasicEnum.GET_ACCESS_TOKEN, { ...param }, {}, 'POST', true, false)
      .then((res) => res);
  }
}
