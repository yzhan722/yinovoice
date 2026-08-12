import UserEnum from "@/enum/UserEnum";
import $WRequest from "@/utils/request/WRequest";

export class UserService {
    /**
     * 获取用户信息
     */
    getUserInfo(param) {
        const requestUrl = UserEnum.GET_USER_INFO;
        return $WRequest.post(requestUrl, {
            ...param
        }).then(res => {
            return res;
        })
    }

    /**
     * 获取用户个人资料
     */
    getUserProfile(param) {
        const requestUrl = UserEnum.GET_USER_PROFILE;
        return $WRequest.post(requestUrl, {
            ...param
        }).then(res => {
            return res;
        })
    }

    /**
     * 更新用户个人资料
     */
    updateUserProfile(param) {
        const requestUrl = UserEnum.UPDATE_USER_PROFILE;
        return $WRequest.post(requestUrl, {
            ...param
        }).then(res => {
            return res;
        })
    }

    /**
     * 修改密码
     */
    changePassword(param) {
        const requestUrl = UserEnum.CHANGE_PASSWORD;
        return $WRequest.post(requestUrl, {
            ...param
        }).then(res => {
            return res;
        })
    }
}