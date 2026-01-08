export interface BackoffOptions {
  minMs?: number;
  maxMs?: number;
  factor?: number;
  jitterRatio?: number; // 0.0 ~ 1.0
}

export const createBackoff = (opts: BackoffOptions = {}) => {
  const minMs = opts.minMs ?? 1000;
  const maxMs = opts.maxMs ?? 8000;
  const factor = opts.factor ?? 1.6;
  const jitterRatio = opts.jitterRatio ?? 0.2;

  let attempt = 0;

  const reset = () => {
    attempt = 0;
  };

  const next = () => {
    const raw = Math.min(maxMs, Math.round(minMs * Math.pow(factor, attempt)));
    attempt += 1;
    const jitter = Math.round(raw * jitterRatio * (Math.random() * 2 - 1)); // +/- jitter
    return Math.max(minMs, raw + jitter);
  };

  return { reset, next };
};

