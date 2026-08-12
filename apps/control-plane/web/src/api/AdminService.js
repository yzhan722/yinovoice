import AdminEnum from '@/enum/AdminEnum';
import $WRequest from '@/utils/request/WRequest';
import {
  shellMockEnabled,
  shellLogin,
  shellOperatorProfile,
} from '@/mocks/shell';

export class AdminService {
  login(param) {
    if (shellMockEnabled()) {
      return Promise.resolve(shellLogin('operator', param?.account, param?.password));
    }
    return $WRequest.post(AdminEnum.LOGIN, { ...param }).then((res) => res);
  }

  getAdminInfo(param) {
    if (shellMockEnabled()) {
      return Promise.resolve(shellOperatorProfile());
    }
    return $WRequest.post(AdminEnum.GET_ADMIN_INFO, { ...param }).then((res) => res);
  }
}
