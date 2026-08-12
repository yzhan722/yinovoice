export interface ImportMetaEnv {
  readonly VITE_IS_REQUEST_PROXY: string;
  readonly VITE_API_URL: string;
  readonly VITE_API_URL_PREFIX: string;
  readonly VITE_BASE_API: string;
  readonly VITE_PYTHON_API: string;
  readonly VITE_SHELL_MOCK?: string;
  readonly VITE_BASE_URL?: string;
  readonly VITE_PLATFORM_API_BASE?: string;
  readonly VITE_DEMO_TENANT_ID?: string;
  readonly VITE_DEMO_CUSTOMER_SERVICE_ID?: string;
}
