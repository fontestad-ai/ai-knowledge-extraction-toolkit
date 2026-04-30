const RATE_LIMIT = 15;
const WINDOW_MS = 60_000;

interface RateLimitResult {
  success: boolean;
  limit: number;
  remaining: number;
  reset: number;
}

class LocalRateLimiter {
  private readonly buckets = new Map<string, number[]>();

  async limit(key: string): Promise<RateLimitResult> {
    const now = Date.now();
    const windowStart = now - WINDOW_MS;
    const existing = this.buckets.get(key) ?? [];
    const recent = existing.filter((timestamp) => timestamp > windowStart);

    if (recent.length >= RATE_LIMIT) {
      const reset = recent[0] + WINDOW_MS;
      this.buckets.set(key, recent);
      return {
        success: false,
        limit: RATE_LIMIT,
        remaining: 0,
        reset,
      };
    }

    recent.push(now);
    this.buckets.set(key, recent);
    return {
      success: true,
      limit: RATE_LIMIT,
      remaining: RATE_LIMIT - recent.length,
      reset: now + WINDOW_MS,
    };
  }
}

export const ratelimit = new LocalRateLimiter();
