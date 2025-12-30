export function getApiErrorMessage(error: any, fallback: string): string {
  const data = error?.response?.data;

  const message =
    data?.message ??
    (typeof data?.error === 'string' ? data.error : data?.error?.message) ??
    data?.detail ??
    error?.message ??
    fallback;

  if (typeof message === 'string' && message.trim()) return message;
  return fallback;
}
