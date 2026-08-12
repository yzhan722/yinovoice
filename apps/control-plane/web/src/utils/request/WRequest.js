import {MessagePlugin, LoadingPlugin} from 'tdesign-vue-next';
import {VAxios} from './Axios';
import {ContentTypeEnum} from "@/constants";

/**
 *  request 请求公共入口
 * @param url 请求url
 * @param data 请求数据
 * @param header 请求头部
 * @param method 请求方法
 * @param loading 是否产生loading遮罩
 * @param errMsg 报错时是否提示用户
 * @returns {Promise<unknown>}
 */
const getAdminToken = () => {
    try {
        const adminTokenData = sessionStorage.getItem('adminToken');
        if (adminTokenData) {
            const data = JSON.parse(adminTokenData);
            if (data.expireTime && data.expireTime > Date.now()) return data.token;
            sessionStorage.removeItem('adminToken');
        }
        return '';
    } catch (e) {
        return '';
    }
};

const getUserToken = () => {
    try {
        const userTokenData = sessionStorage.getItem('userToken');
        if (userTokenData) {
            const data = JSON.parse(userTokenData);
            if (data.expireTime && data.expireTime > Date.now()) return data.token;
            sessionStorage.removeItem('userToken');
        }
        return '';
    } catch (e) {
        return '';
    }
};

const isAdminApi = (url) => url && (url.includes('/api/admin/') || url.includes('/admin/'));
const isUserApi = (url) => url && url.includes('/api/user/') && !url.includes('/api/user/login');

const request = (url, data, header, method, loading, errMsg) => {
    const axios = new VAxios({
        // 超时
        timeout: 180 * 1000,
        // 携带Cookie
        withCredentials: true,
        // 配置项，下面的选项都可以在独立的接口请求中覆盖
        requestOptions: {
            // 格式化提交参数时间
            formatDate: true,
            // 是否加入时间戳
            joinTime: true,
            // 是否忽略请求取消令牌
            // 如果启用，则重复请求时不进行处理
            // 如果禁用，则重复请求时会取消当前请求
            ignoreCancelToken: true,
            // 是否携带token
            withToken: true,
            // 重试
            retry: {
                count: 3,
                delay: 1000,
            },
        },
    });
    //判断是否loading
    if (loading) {
        LoadingPlugin(true);
    }
    return new Promise((resolve, reject) => {
        // 如果是管理员接口，添加管理员token
        const requestConfig = {
            url: url,
            data: data,
            headers: header || {},
            method: method,
            params: method === "get" ? data : null,
            withCredentials: true
        };

        if (!requestConfig.headers) requestConfig.headers = {};
        if (isAdminApi(requestConfig.url)) {
            const t = getAdminToken();
            if (t) requestConfig.headers.Authorization = `Bearer ${t}`;
        } else if (isUserApi(requestConfig.url)) {
            const t = getUserToken();
            if (t) requestConfig.headers.Authorization = `Bearer ${t}`;
        }

        axios.request(requestConfig).then(res => {
            let result = res.data;
            if (result.success || result.code === 0 || result.ret === 0) {
                resolve(result.data !== undefined ? result.data : result);
            } else {
                if (errMsg) {
                    MessagePlugin.error({
                        content: result.msg, duration: 5000
                    })
                }
                reject(result);
            }
        }).catch(message => {
            console.error(message);
            let result = {
                msg: "Request error，Please reload the page", success: false
            }
            //todo 报错提示
            if (errMsg) {
                MessagePlugin.error({
                    content: result.msg, duration: 5000
                })
            }
            reject(message);
        }).finally(() => {
            LoadingPlugin(false);
        })
    })
}


//post 请求（常用）
const post = (url, data) => {
    return request(url, data, null, "post", true, true);
}

const get = (url, data) => {
    return request(url, data, null, "get", true, true);
}

const postNoAnimation = (url, data) => {
    return request(url, data, null, "post", false, true);
}
const getNoAnimation = (url, data) => {
    return request(url, data, null, "post", false, true);
}

export default {
    request, post, get, postNoAnimation, getNoAnimation
}